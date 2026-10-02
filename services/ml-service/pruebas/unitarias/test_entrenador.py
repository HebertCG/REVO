"""
Pruebas del entrenamiento del modelo.

Lo que mas importa aqui no es el accuracy: es el LIFT sobre la regla trivial.
Con el dataset sintetico actual, la etiqueta es casi siempre el argmax del
vector de afinidades, asi que una regla de una linea sin ML alcanza ~99%. Un
accuracy alto no dice nada; lo unico informativo es cuanto aporta el modelo
POR ENCIMA de esa regla.

Estas pruebas fijan el comportamiento actual sin cambiarlo. Si algun dia se
redisena el modelo, tendran que actualizarse a proposito.
"""
import os

import numpy as np
import pytest

from model import trainer


class FilaEntrenamiento:
    """Imita una fila de ml_training_data sin necesitar base de datos."""

    def __init__(self, afinidades: list[float], specialization_id: int):
        for i, valor in enumerate(afinidades, start=1):
            setattr(self, f"aff_{i}", valor)
        self.specialization_id = specialization_id


class BaseFalsa:
    """
    Sesion de mentira: devuelve filas y apunta lo que se le pide guardar.

    El entrenamiento no necesita PostgreSQL para probarse, y usar uno real
    haria estas pruebas lentas y dependientes del entorno.
    """

    def __init__(self, filas):
        self._filas = filas
        self.guardado = []
        self.confirmaciones = 0

    def query(self, _modelo):
        return self

    def all(self):
        return self._filas

    def add(self, objeto):
        self.guardado.append(objeto)

    def commit(self):
        self.confirmaciones += 1


def dataset(muestras_por_clase: int = 12, ruido: float = 0.0):
    """Genera un dataset donde la etiqueta es la afinidad dominante."""
    generador = np.random.default_rng(42)
    filas = []
    for clase in range(1, 11):
        for _ in range(muestras_por_clase):
            afinidades = list(generador.uniform(0.05, 0.45, 10))
            afinidades[clase - 1] = generador.uniform(0.75, 1.0)
            if ruido and generador.random() < ruido:
                # Una parte de las muestras se etiqueta mal a proposito, para
                # comprobar que las metricas lo reflejan.
                filas.append(FilaEntrenamiento(afinidades, (clase % 10) + 1))
            else:
                filas.append(FilaEntrenamiento(afinidades, clase))
    return filas


@pytest.fixture
def modelo_en_tmp(tmp_path, monkeypatch):
    """Aparta el almacen de artefactos a un directorio temporal.

    Antes esto apartaba un unico .pkl. Ahora el entrenador escribe un
    directorio por version mas un puntero de version activa, asi que lo que
    se aisla es el almacen entero.
    """
    almacen = tmp_path / "almacen"
    monkeypatch.setattr(trainer.settings, "MODEL_DIR", str(almacen))
    monkeypatch.setattr(trainer.settings, "MODEL_PATH_HEREDADO", str(tmp_path / "no-existe.pkl"))
    trainer.cargar_artefacto_activo.cache_clear()
    yield almacen
    trainer.cargar_artefacto_activo.cache_clear()


class TestCargaDeDatos:
    def test_convierte_las_filas_en_matriz_y_etiquetas(self):
        X, y = trainer.load_training_data(BaseFalsa(dataset(2)))

        assert X.shape == (20, 10)
        assert y.shape == (20,)

    def test_respeta_el_orden_de_las_afinidades(self):
        fila = FilaEntrenamiento([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0], 10)

        X, _ = trainer.load_training_data(BaseFalsa([fila]))

        assert list(X[0]) == pytest.approx([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])

    def test_una_afinidad_nula_cuenta_como_cero(self):
        fila = FilaEntrenamiento([0.5] * 10, 1)
        fila.aff_3 = None

        X, _ = trainer.load_training_data(BaseFalsa([fila]))

        assert X[0][2] == 0.0

    def test_sin_datos_falla_con_un_mensaje_util(self):
        # Entrenar con cero filas produciria un modelo inservible en silencio.
        with pytest.raises(ValueError, match="entrenamiento"):
            trainer.load_training_data(BaseFalsa([]))


class TestEntrenamiento:
    def test_deja_el_modelo_guardado_en_disco(self, modelo_en_tmp):
        metricas = trainer.train_model(BaseFalsa(dataset()))

        assert (modelo_en_tmp / metricas["model_version"] / "modelo.pkl").exists()

    def test_devuelve_las_metricas_completas(self, modelo_en_tmp):
        metricas = trainer.train_model(BaseFalsa(dataset()))

        assert set(metricas) >= {
            "model_version", "accuracy", "precision", "recall", "f1",
            "baseline_accuracy", "lift_over_baseline",
            "training_samples", "test_samples",
        }

    def test_las_metricas_son_proporciones_validas(self, modelo_en_tmp):
        m = trainer.train_model(BaseFalsa(dataset()))

        for clave in ("accuracy", "precision", "recall", "f1"):
            assert 0.0 <= m[clave] <= 1.0, clave

    def test_compara_contra_la_regla_trivial(self, modelo_en_tmp):
        # Es la metrica honesta: sin ella, un 99% de accuracy sobre datos
        # donde la etiqueta es el argmax parece un exito y no lo es.
        m = trainer.train_model(BaseFalsa(dataset()))

        assert m["lift_over_baseline"] == pytest.approx(
            m["accuracy"] - m["baseline_accuracy"], abs=1e-6
        )

    def test_con_datos_donde_manda_el_argmax_la_regla_trivial_acierta(self, modelo_en_tmp):
        # Documenta el problema real del dataset actual: la regla de una
        # linea ya acierta casi todo, asi que el modelo aporta poco.
        m = trainer.train_model(BaseFalsa(dataset()))

        assert m["baseline_accuracy"] > 0.9

    def test_las_muestras_se_reparten_en_entrenamiento_y_prueba(self, modelo_en_tmp):
        filas = dataset(12)

        m = trainer.train_model(BaseFalsa(filas))

        assert m["training_samples"] + m["test_samples"] == len(filas)
        # 80/20: el conjunto de prueba tiene que ser el menor.
        assert m["test_samples"] < m["training_samples"]

    def test_registra_el_entrenamiento_en_la_base(self, modelo_en_tmp):
        db = BaseFalsa(dataset())

        trainer.train_model(db, trained_by_id=7)

        assert len(db.guardado) == 1
        assert db.confirmaciones == 1
        assert db.guardado[0].trained_by == 7

    def test_la_version_permite_distinguir_entrenamientos(self, modelo_en_tmp):
        m = trainer.train_model(BaseFalsa(dataset()))

        assert m["model_version"].startswith("v")
        assert len(m["model_version"]) > 5

    def test_un_dataset_con_ruido_baja_el_acierto(self, modelo_en_tmp):
        # Si el accuracy saliera igual con datos peores, la metrica no
        # estaria midiendo nada.
        limpio = trainer.train_model(BaseFalsa(dataset(ruido=0.0)))["accuracy"]
        sucio = trainer.train_model(BaseFalsa(dataset(ruido=0.35)))["accuracy"]

        assert sucio < limpio


class TestCacheDelModelo:
    def test_el_modelo_se_lee_del_disco_una_sola_vez(self, modelo_en_tmp):
        # Sin cache, cada prediccion y cada refresco del panel admin (que
        # consulta cada 5 segundos) releian el .pkl entero.
        trainer.train_model(BaseFalsa(dataset()))

        primero = trainer.load_model()
        segundo = trainer.load_model()

        assert primero is segundo

    def test_reentrenar_con_un_modelo_valido_invalida_la_cache(self, modelo_en_tmp):
        # Si no se invalidara, el servicio seguiria sirviendo el modelo viejo
        # despues de promover uno nuevo, y nadie lo notaria.
        trainer.train_model(BaseFalsa(dataset()))
        viejo = trainer.load_model()

        resultado = trainer.train_model(BaseFalsa(dataset()))
        nuevo = trainer.load_model()

        assert resultado["promovido"] is True
        assert nuevo is not viejo


class TestPuertaDePromocion:
    """
    Entrenar ya no implica desplegar.

    Antes, `joblib.dump` sobre la ruta que lee el servicio hacia que cualquier
    reentrenamiento entrara en produccion al instante. Y el reentrenamiento
    es AUTOMATICO cada 50 predicciones, asi que un dataset que se degradaba
    degradaba el modelo en produccion sin que nadie interviniera.
    """

    def test_un_modelo_peor_no_llega_a_produccion(self, modelo_en_tmp):
        trainer.train_model(BaseFalsa(dataset()))
        activo_antes = trainer.load_model()

        resultado = trainer.train_model(BaseFalsa(dataset(ruido=0.35)))

        assert resultado["promovido"] is False
        assert "regresion" in resultado["motivo"]
        # Y lo que importa de verdad: se sigue sirviendo el bueno.
        assert trainer.load_model() is activo_antes

    def test_el_modelo_rechazado_se_guarda_igualmente(self, modelo_en_tmp):
        # Guardarlo sin promoverlo permite inspeccionar despues por que se
        # rechazo, y promoverlo a mano si la decision fue equivocada.
        trainer.train_model(BaseFalsa(dataset()))

        rechazado = trainer.train_model(BaseFalsa(dataset(ruido=0.35)))

        assert (modelo_en_tmp / rechazado["model_version"] / "modelo.pkl").exists()

    def test_el_primer_modelo_siempre_entra(self, modelo_en_tmp):
        # No tener modelo es peor que tener uno mediocre: sin el, ningun
        # alumno recibe resultado.
        resultado = trainer.train_model(BaseFalsa(dataset(ruido=0.4)))

        assert resultado["promovido"] is True

    def test_avisa_cuando_no_supera_a_la_regla_trivial(self, modelo_en_tmp):
        # El dataset de esta prueba tiene la etiqueta = argmax, asi que el
        # lift es ~0. El aviso es lo que impide que ese accuracy se cite como
        # evidencia de que el modelo acierta.
        resultado = trainer.train_model(BaseFalsa(dataset()))

        assert any("trivial" in aviso for aviso in resultado["avisos"])

    def test_sin_modelo_entrenado_avisa_con_claridad(self, modelo_en_tmp):
        trainer.load_model.cache_clear()

        with pytest.raises(FileNotFoundError, match="Entrene"):
            trainer.load_model()


class TestVecindarioAlEntrenar:
    """
    El umbral de "perfil poco visto" se calcula al entrenar y viaja con el
    modelo. Si se calculara aparte, un modelo nuevo podria acabar juzgado
    con el umbral de otro dataset.
    """

    def test_el_resultado_trae_el_umbral(self, modelo_en_tmp):
        m = trainer.train_model(BaseFalsa(dataset()))

        assert m["vecindario"]["umbral"] > 0
        assert m["vecindario"]["k"] == 10

    def test_el_umbral_se_guarda_en_los_metadatos_del_modelo(self, modelo_en_tmp):
        from model import artefactos

        m = trainer.train_model(BaseFalsa(dataset()))

        guardado = artefactos.cargar(trainer.settings.MODEL_DIR, m["model_version"])
        assert guardado.metadatos["vecindario"] == m["vecindario"]


class TestCacheEntreWorkers:
    """
    DEFECTO encontrado en la prueba de carga: con 2 workers, el que entrenaba
    limpiaba SU cache, pero el otro seguia sirviendo el modelo anterior hasta
    reiniciarse. El puntero `activo.json` es compartido; la cache no.
    """

    def test_si_otro_proceso_promueve_se_sirve_el_nuevo(self, modelo_en_tmp):
        from model import artefactos
        trainer.train_model(BaseFalsa(dataset()))
        viejo = trainer.cargar_artefacto_activo()

        # Otro worker entrena y promueve. En ESTE proceso nadie llama a
        # cache_clear: es exactamente lo que pasa en produccion.
        otro = artefactos.version_libre(trainer.settings.MODEL_DIR, "v-del-otro-worker")
        artefactos.guardar(trainer.settings.MODEL_DIR, otro, viejo.modelo,
                           metadatos=dict(viejo.metadatos))
        artefactos.promover(trainer.settings.MODEL_DIR, otro)

        assert trainer.cargar_artefacto_activo().version == otro

    def test_sin_cambios_de_version_sigue_sin_releer_el_disco(self, modelo_en_tmp):
        trainer.train_model(BaseFalsa(dataset()))

        assert trainer.cargar_artefacto_activo() is trainer.cargar_artefacto_activo()
