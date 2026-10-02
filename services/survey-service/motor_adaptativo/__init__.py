"""
motor_adaptativo — El cuestionario elige cada pregunta en vez de sortearla.

Sustituye el `ORDER BY random()` de la fase 2 por una seleccion que maximiza
lo que se aprende de cada respuesta. Es lo que en la literatura se llama
Computerized Adaptive Testing.

Reparto de responsabilidades:

    artefacto.py   carga el modelo compilado (el tensor de verosimilitudes)
    creencia.py    el estado: que rama encaja y cuanto, en log-espacio
    seleccion.py   elige la siguiente pregunta por ganancia de informacion
    parada.py      decide cuando hay suficiente

Ninguno de los cuatro toca la base de datos: son funciones puras sobre
estructuras inmutables. Eso los hace triviales de probar sin PostgreSQL, y
es deliberado — el acceso a datos se queda en routers/sessions.py.
"""
