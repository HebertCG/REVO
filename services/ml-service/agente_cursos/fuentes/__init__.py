"""
fuentes — Adaptadores de catalogos de cursos.

Toda fuente hereda de `Fuente` y declara su `base_legal`: por que se puede
usar. No es documentacion decorativa — ese texto viaja a la columna
`curso_candidatos.base_legal`, que es NOT NULL, asi que una fuente que no
pueda justificarse no llega a producir un candidato.

Precedente del proyecto: la tabla `jobs` se retiro porque Remotive ofrece
API oficial y raspar HTML era peor en todo. Aqui se prefiere API oficial,
despues datos abiertos, y solo al final raspado respetuoso.
"""
