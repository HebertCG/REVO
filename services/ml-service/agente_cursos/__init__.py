"""
agente_cursos — Busca y propone cursos para el roadmap del alumno.

El roadmap son 30 huecos: 10 ramas x 3 niveles (Fundamentos, Construccion,
Experto). Hasta ahora cada hueco tenia UN curso, metido a mano una vez y
nunca revisado.

Reparto:

    fuentes/    de donde salen los cursos. Cada una declara su base legal;
                sin ella no puede producir candidatos (la columna es NOT NULL)
    puntuacion  que significa "el mejor curso" para un alumno de REVO
    agente      orquesta: busca, puntua, filtra y propone

El agente NO escribe en `courses`. Propone en `curso_candidatos` y un
administrador aprueba. El permiso lo impide ademas a nivel de base de datos.
"""
