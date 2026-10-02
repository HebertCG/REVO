"""
El resultado completo de una prediccion se guarda y se devuelve tal cual.

DEFECTO QUE ESTO CORRIGE: la pantalla de resultado carga la prediccion con
GET /predict/{id}, y esa ruta solo devolvia lo que habia en la tabla:
primaria, top-3 y version. La calibracion, la incertidumbre, el conjunto
conformal y `all_probabilities` se calculaban en el POST y se perdian: nunca
llegaron al alumno, y la grafica de barras de la pagina salia vacia.

Recalcular en el GET no vale: si el modelo se reentrena, la recomendacion de
un alumno cambiaria sola con el tiempo. Se guarda lo que el modelo dijo en
su momento.
"""
import json

from routers.predict import CAMPOS_DETALLE, detalle_de
from schemas import PredictResponse

CIBER = {"specialization_id": 4, "name": "Ciberseguridad", "icon": "",
         "color": "#dc2626", "confidence": 0.7, "confidence_pct": 70.0}

RESULTADO = {
    "primary": CIBER,
    "top3": [],
    "all_probabilities": {"Ciberseguridad": 70.0, "Desarrollo de Software": 20.0},
    "feature_vector": {"aff_4": 0.9},
    "model_version": "v1",
    "calibrado": True,
    "incertidumbre": {"lectura": "definido"},
    "conjunto_conformal": [CIBER],
    "presentacion": {"modo": "una"},
    "probabilidades_por_id": {4: 0.7, 1: 0.2},
    "vecindario_entrenamiento": {"umbral": 0.6},
}
VECTORIAL = {
    "vecindario": {"disponible": True, "perfil_poco_visto": False},
    "ocupaciones_afines": [{"codigo_soc": "15-1212.00", "titulo": "Information Security Analysts",
                            "correlacion": 0.996}],
}


class TestDetalle:
    def test_guarda_todo_lo_que_la_pantalla_necesita(self):
        detalle = detalle_de(RESULTADO, VECTORIAL)

        assert set(detalle) == set(CAMPOS_DETALLE)
        assert detalle["ocupaciones_afines"][0]["codigo_soc"] == "15-1212.00"
        assert detalle["all_probabilities"]["Ciberseguridad"] == 70.0

    def test_no_duplica_lo_que_ya_tiene_columna_propia(self):
        # feature_vector, primary y model_version ya son columnas: repetirlos
        # aqui abriria la puerta a que discrepen.
        detalle = detalle_de(RESULTADO, VECTORIAL)

        assert "feature_vector" not in detalle
        assert "primary" not in detalle
        assert "model_version" not in detalle

    def test_cabe_en_una_columna_json(self):
        # Las claves enteras de probabilidades_por_id romperian el JSON de
        # PostgreSQL al leerlo de vuelta; por eso no se guardan.
        json.loads(json.dumps(detalle_de(RESULTADO, VECTORIAL)))

    def test_el_get_puede_reconstruir_la_respuesta_con_el(self):
        detalle = json.loads(json.dumps(detalle_de(RESULTADO, VECTORIAL)))

        respuesta = PredictResponse(
            prediction_id=1, session_id=1, primary=RESULTADO["primary"],
            top3=[], model_version="v1", **detalle)

        assert respuesta.calibrado is True
        assert respuesta.vecindario["perfil_poco_visto"] is False
        assert respuesta.all_probabilities["Ciberseguridad"] == 70.0


class TestConVecindario:
    def test_el_mensaje_guardado_ya_no_dice_claramente_si_el_perfil_es_raro(self):
        # El caso de la prediccion 296, de principio a fin.
        from routers.predict import con_vecindario
        resultado = {**RESULTADO,
                     "incertidumbre": {"lectura": "definido",
                                       "incertidumbre_epistemica_alta": False},
                     "presentacion": {"modo": "resultado_unico", "mostrar_n": 1,
                                      "mensaje": "Tus respuestas apuntan claramente a una rama."}}
        vectorial = {**VECTORIAL, "vecindario": {"perfil_poco_visto": True}}

        detalle = detalle_de(con_vecindario(resultado, vectorial), vectorial)

        assert detalle["incertidumbre"]["lectura"] == "perfil_poco_visto"
        assert detalle["presentacion"]["cautela"] is True
        assert "claramente" not in detalle["presentacion"]["mensaje"]
