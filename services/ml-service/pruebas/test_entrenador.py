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
    """Aparta el .pkl a un directorio temporal: no se pisa el modelo real."""
    ruta = tmp_path / "modelo" / "prueba.pkl"
    monkeypatch.setattr(trainer.settings, "MODEL_PATH", str(ruta))
    trainer.load_model.cache_clear()
    yield ruta
    trainer.load_model.cache_clear()


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
        trainer.train_model(BaseFalsa(dataset()))

        assert os.path.exists(modelo_en_tmp)

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

    def test_reentrenar_invalida_la_cache(self, modelo_en_tmp):
        # Si no se invalidara, el servicio seguiria sirviendo el modelo viejo
        # despues de reentrenar, y nadie lo notaria.
        trainer.train_model(BaseFalsa(dataset()))
        viejo = trainer.load_model()

        trainer.train_model(BaseFalsa(dataset(ruido=0.3)))
        nuevo = trainer.load_model()

        assert nuevo is not viejo

    def test_sin_modelo_entrenado_avisa_con_claridad(self, modelo_en_tmp):
        trainer.load_model.cache_clear()

        with pytest.raises(FileNotFoundError, match="Entrene"):
            trainer.load_model()
