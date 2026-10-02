"""
Pruebas del almacen versionado de modelos.

Lo que se protege aqui es la posibilidad de volver atras. Antes, entrenar
sobrescribia el unico .pkl que habia: si el modelo nuevo salia peor, el
anterior ya no existia.

Dos pruebas merecen atencion especial:

  * `test_guardar_no_promueve`: separar guardar de promover es lo que
    permite medir un candidato antes de desplegarlo. Si guardar promoviera,
    la puerta de promocion no serviria de nada.

  * `test_una_version_no_puede_salirse_del_almacen`: la version acaba
    viniendo de la base de datos o de una peticion de administracion, asi
    que es entrada no confiable.
"""
import json

import pytest
from sklearn.linear_model import LogisticRegression

from model import artefactos


@pytest.fixture
def modelo():
    import numpy as np
    clf = LogisticRegression(max_iter=200)
    clf.fit(np.array([[0.0] * 10, [1.0] * 10, [0.5] * 10]), np.array([1, 2, 3]))
    return clf


class TestGuardarYCargar:
    def test_guardar_y_cargar_devuelve_lo_mismo(self, tmp_path, modelo):
        artefactos.guardar(tmp_path, "v1", modelo, {"algoritmo": "LogisticRegression"})

        cargado = artefactos.cargar(tmp_path, "v1")

        assert cargado.version == "v1"
        assert cargado.metadatos["algoritmo"] == "LogisticRegression"

    def test_guardar_no_promueve(self, tmp_path, modelo):
        # Si guardar promoviera, la puerta de promocion seria decorativa: el
        # modelo entraria en produccion antes de que nadie lo midiera.
        artefactos.guardar(tmp_path, "v1", modelo, {})

        assert artefactos.version_activa(tmp_path) is None

    def test_promover_mueve_el_puntero(self, tmp_path, modelo):
        artefactos.guardar(tmp_path, "v1", modelo, {})

        artefactos.promover(tmp_path, "v1")

        assert artefactos.version_activa(tmp_path) == "v1"

    def test_la_calibracion_viaja_con_su_modelo(self, tmp_path, modelo):
        # Una temperatura solo vale para EL modelo con el que se calculo.
        # Guardarla suelta la desacopla y en el siguiente reentrenamiento
        # pasa a describir un modelo que ya no existe.
        artefactos.guardar(tmp_path, "v1", modelo, {}, calibracion={"temperatura": 2.5})

        assert artefactos.cargar(tmp_path, "v1").temperatura == 2.5

    def test_un_modelo_sin_calibrar_usa_temperatura_neutra(self, tmp_path, modelo):
        # 1.0 deja las probabilidades intactas, asi que el camino sin
        # calibrar funciona sin ramificar en el codigo que la usa.
        artefactos.guardar(tmp_path, "v1", modelo, {})

        cargado = artefactos.cargar(tmp_path, "v1")

        assert cargado.temperatura == 1.0
        assert cargado.esta_calibrado is False

    def test_el_conjunto_bootstrap_se_guarda_y_se_recupera(self, tmp_path, modelo):
        artefactos.guardar(tmp_path, "v1", modelo, {}, conjunto=[modelo, modelo])

        assert len(artefactos.cargar(tmp_path, "v1").conjunto) == 2


class TestVueltaAtras:
    def test_se_puede_volver_a_una_version_anterior(self, tmp_path, modelo):
        # Es el motivo de existir del modulo.
        artefactos.guardar(tmp_path, "v1", modelo, {"metricas": {"f1": 0.9}})
        artefactos.guardar(tmp_path, "v2", modelo, {"metricas": {"f1": 0.4}})
        artefactos.promover(tmp_path, "v2")

        artefactos.promover(tmp_path, "v1")

        assert artefactos.cargar_activo(tmp_path).metadatos["metricas"]["f1"] == 0.9

    def test_las_versiones_se_listan_de_la_mas_nueva_a_la_mas_vieja(self, tmp_path, modelo):
        for version in ("v20260101", "v20260301", "v20260201"):
            artefactos.guardar(tmp_path, version, modelo, {})

        assert artefactos.versiones(tmp_path) == ["v20260301", "v20260201", "v20260101"]


class TestColisionDeVersiones:
    """
    La version se construye con marca de tiempo AL SEGUNDO. Dos
    entrenamientos dentro del mismo segundo generaban la misma cadena.

    El dano no era perder un artefacto: la puerta de promocion lee las
    metricas del modelo ACTIVO para comparar, y si el candidato ya habia
    pisado ese directorio, la puerta se comparaba consigo misma y aprobaba
    cualquier cosa. Un fallo silencioso que anulaba la proteccion entera.
    """

    def test_una_version_libre_se_devuelve_tal_cual(self, tmp_path):
        assert artefactos.version_libre(tmp_path, "v1") == "v1"

    def test_una_version_ocupada_recibe_sufijo(self, tmp_path, modelo):
        artefactos.guardar(tmp_path, "v1", modelo, {})

        assert artefactos.version_libre(tmp_path, "v1") == "v1_2"

    def test_varias_colisiones_seguidas_siguen_dando_nombres_distintos(self, tmp_path, modelo):
        nombres = []
        for _ in range(4):
            version = artefactos.version_libre(tmp_path, "v1")
            artefactos.guardar(tmp_path, version, modelo, {})
            nombres.append(version)

        assert len(set(nombres)) == 4

    def test_un_directorio_sin_modelo_no_cuenta_como_ocupado(self, tmp_path):
        # Un directorio a medias de un entrenamiento que fallo no debe
        # bloquear el nombre para siempre.
        (tmp_path / "v1").mkdir()

        assert artefactos.version_libre(tmp_path, "v1") == "v1"


class TestFallosYBordes:
    def test_sin_modelo_activo_falla_con_un_mensaje_accionable(self, tmp_path):
        with pytest.raises(artefactos.ArtefactoNoEncontrado, match="Entrene"):
            artefactos.cargar_activo(tmp_path)

    def test_no_se_puede_promover_una_version_incompleta(self, tmp_path):
        # Un puntero a un directorio sin modelo deja el servicio devolviendo
        # 503 sin explicar por que.
        (tmp_path / "v-vacia").mkdir()

        with pytest.raises(artefactos.ArtefactoNoEncontrado):
            artefactos.promover(tmp_path, "v-vacia")

    def test_una_version_no_puede_salirse_del_almacen(self, tmp_path, modelo):
        # La version viene de la base de datos o de una peticion: es entrada
        # no confiable. Sin sanear, '../..' escribe fuera del almacen.
        with pytest.raises(ValueError):
            artefactos.ruta_de(tmp_path, "..")

        assert artefactos.ruta_de(tmp_path, "../../escape").parent == tmp_path

    def test_un_puntero_corrupto_no_se_hace_pasar_por_ausencia(self, tmp_path, modelo):
        artefactos.guardar(tmp_path, "v1", modelo, {})
        (tmp_path / artefactos.FICHERO_PUNTERO).write_text("{no es json", encoding="utf-8")

        # Devuelve None (el servicio se recupera entrenando) pero el error
        # queda en el log: son dos situaciones distintas.
        assert artefactos.version_activa(tmp_path) is None

    def test_las_versiones_de_un_almacen_inexistente_son_lista_vacia(self, tmp_path):
        assert artefactos.versiones(tmp_path / "no-existe") == []

    def test_el_puntero_es_json_valido(self, tmp_path, modelo):
        artefactos.guardar(tmp_path, "v1", modelo, {})
        artefactos.promover(tmp_path, "v1")

        contenido = json.loads((tmp_path / artefactos.FICHERO_PUNTERO).read_text())

        assert contenido == {"version": "v1"}


class TestAdopcionDelHeredado:
    def test_adopta_el_pkl_suelto_del_esquema_anterior(self, tmp_path, modelo):
        # Sin esto, el primer despliegue de este codigo sobre una instalacion
        # que ya tenia modelo se queda sin version activa y devuelve 503
        # hasta que alguien entrene a mano.
        import joblib
        suelto = tmp_path / "viejo.pkl"
        joblib.dump(modelo, suelto)
        almacen = tmp_path / "almacen"

        version = artefactos.adoptar_heredado(almacen, suelto)

        assert version == artefactos.VERSION_HEREDADA
        assert artefactos.version_activa(almacen) == artefactos.VERSION_HEREDADA

    def test_no_pisa_un_almacen_que_ya_tiene_version_activa(self, tmp_path, modelo):
        import joblib
        suelto = tmp_path / "viejo.pkl"
        joblib.dump(modelo, suelto)
        almacen = tmp_path / "almacen"
        artefactos.guardar(almacen, "v-buena", modelo, {})
        artefactos.promover(almacen, "v-buena")

        assert artefactos.adoptar_heredado(almacen, suelto) is None
        assert artefactos.version_activa(almacen) == "v-buena"

    def test_sin_pkl_que_adoptar_no_hace_nada(self, tmp_path):
        assert artefactos.adoptar_heredado(tmp_path, tmp_path / "no-existe.pkl") is None

    def test_deja_constancia_de_que_no_se_conocen_sus_metricas(self, tmp_path, modelo):
        import joblib
        suelto = tmp_path / "viejo.pkl"
        joblib.dump(modelo, suelto)
        almacen = tmp_path / "almacen"

        artefactos.adoptar_heredado(almacen, suelto)

        nota = artefactos.cargar_activo(almacen).metadatos["nota"]
        assert "metricas" in nota
