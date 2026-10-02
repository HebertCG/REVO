# REVO — Reglas de programación y plan de acción

> Documento de trabajo vivo. Se edita a medida que avanza el proyecto.
> El [README.md](README.md) explica **qué es** REVO; este fichero explica
> **cómo se construye** y **en qué punto está**.
>
> Última actualización: 2026-09-21

---

# Parte I — Reglas de programación

Estas reglas no son aspiracionales: salen de decisiones ya tomadas en este
repositorio, y varias existen porque algo se rompió primero. Donde hay un
ejemplo real, se cita.

## 1. La frontera entre servicios la impone PostgreSQL, no el código

Cada tabla la escribe **un solo servicio**:

| Servicio | Tablas que escribe |
|---|---|
| `auth-service` | `users`, `user_consents`, `legal_documents` |
| `survey-service` | `questionnaire_sessions`, `answers`, `psychometric_answers` |
| `ml-service` | `predictions`, `prediction_feedbacks`, `ml_training_data`, `model_training_logs` |

Cada servicio se conecta con **su propio rol de base de datos** (`revo_auth`,
`revo_survey`, `revo_ml`), sin `SUPERUSER` y sin `BYPASSRLS`. `revo_ml` no
alcanza `answers` aunque el código se lo pida; `revo_survey` no alcanza
`ml_training_data`. Esto es lo que mantiene el acoplamiento bajo **pese a
compartir base de datos**.

**Regla:** antes de declarar en un servicio un modelo de una tabla que no le
pertenece, pregúntate si lo que hace falta es una llamada HTTP al servicio
dueño. Casi siempre lo es.

> Precedente: `survey-service/database.py` tenía declarado un modelo `User`
> que ninguna ruta usaba. Se retiró porque sugería que el cuestionario es
> dueño de los datos del alumno cuando no lo es.

## 2. Alta cohesión: un módulo responde a una sola pregunta

Cuando un módulo empieza a responder a dos preguntas distintas, se parte —
aunque funcione.

> Precedente: `survey-service` servía los catálogos de cursos y empleos
> además de ejecutar el cuestionario. Esas rutas no leen sesiones ni
> respuestas; van indexadas por especialización, que es lo que produce
> `ml-service`. Se movieron (migración 17), **y los permisos se movieron con
> el código**. Mover uno sin el otro deja dos mentiras a la vez.

Tamaños: 200–400 líneas por fichero, 800 como techo. Funciones por debajo de
50 líneas. Anidamiento máximo de 4 niveles: por encima, retornos tempranos.

## 3. Bajo acoplamiento: `revo_comun` es solo lo transversal

En `services/comun/revo_comun` va lo que no pertenece a ningún dominio:
motor de base de datos, contexto RLS, tokens, cupos de peticiones, cabeceras
de seguridad, formato de errores.

**Nunca** va lógica de negocio compartida. Si dos servicios necesitan la
misma regla de negocio, eso no es una utilidad común: es una señal de que la
responsabilidad está en el servicio equivocado.

## 4. La identidad viaja verificada y llega hasta la base de datos

- La identidad sale del token verificado (`servicio.principal`), nunca de un
  parámetro de la petición.
- Se propaga a PostgreSQL como contexto RLS (`set_config('revo.user_id', …,
  true)`, local a la transacción). Sin el tercer argumento `true`, el valor
  se queda pegado a la conexión y el siguiente alumno del pool hereda la
  identidad del anterior.
- Los `WHERE user_id == …` se conservan **aunque RLS ya lo garantice**:
  documentan la intención y mantienen la ruta correcta si alguna vez corre
  contra una base sin políticas.
- Entre servicios se emite un token nuevo de vida corta, no se reenvía el
  del alumno. Si acaba en un log, caduca en minutos en vez de en 24 horas.

## 5. Cada ruta declara su cupo

Toda ruta lleva `Depends(servicio.limitar("<politica>"))`. La política dice
además qué hacer si Redis cae:

- `fail_open=True` en rutas de alumno: prioriza que la clase no se caiga.
- `fail_open=False` en rutas de administración: son pocas y de mucho valor;
  ahí se prioriza no perder el control.

## 6. Reglas de base de datos

- Migraciones **numeradas e idempotentes**. Se pueden reejecutar enteras.
- Toda migración termina en un bloque `DO $verificacion$` que **falla con
  `RAISE EXCEPTION`** si el resultado no es el esperado. Comprobar que lo
  vivo sigue vivo importa más que comprobar que lo retirado se fue.
- Funciones `SECURITY DEFINER` **siempre** con `SET search_path = public,
  pg_temp`. Sin eso, un esquema controlado por el atacante suplanta las
  tablas que la función nombra.
- **Una columna que siempre vale lo mismo es una mentira.** O se llena con
  un dato real o se retira. Un `0` fijo en una columna numérica de un
  informe se lee como una medida tomada, no como un hueco.
- No se añaden columnas «por si acaso». Si la reforma del modelo necesita
  ponderación, la columna vuelve **con valores de verdad y con el código que
  los usa, en la misma migración**.

## 7. Errores: explícitos, y sin filtrar el interior

- Se manejan en todos los niveles; nunca se tragan en silencio.
- El mensaje al alumno distingue causas: un 404 no es lo mismo que una caída
  del servicio. Decirle «no encontrado» cuando lo que falló fue la red le
  hace creer que perdió su evaluación.
- `except Exception: detail=str(e)` está prohibido en respuestas HTTP: ahí
  caben rutas del servidor y estructura de la base de datos. El manejador
  común devuelve un identificador de rastreo y deja la traza en el log.

## 8. La documentación explica el problema, no el código

El estilo de este repositorio es que cada módulo y cada migración empiezan
explicando **qué se rompía antes**. Un comentario que dice lo que el código
ya dice sobra; uno que dice por qué se descartó la alternativa evita que
alguien la reintroduzca dentro de seis meses.

## 9. Nombres

- Carpetas y módulos nuevos **en español** (`pruebas/`, `basedatos/`,
  `limites/`, `seguridad/`).
- El esquema de base de datos se mantiene **en inglés**, que es como está
  hoy. La coherencia dentro de cada capa vale más que la uniformidad global.
- Constantes en `UPPER_SNAKE_CASE`, clases en `PascalCase`, resto en
  `snake_case` (Python) o `camelCase` (JavaScript).
- Sin números mágicos: `PUNTUACION_MAXIMA_RAMA = 30.0`, no `30.0` repetido.

## 10. Pruebas

- Cada servicio tiene su carpeta `pruebas/`.
- Objetivo de cobertura: 80 %.
- Las pruebas van primero cuando se corrige un fallo: primero la prueba que
  lo reproduce, después el arreglo.
- **Lo que se puede verificar ejecutándolo, se ejecuta.** No se da por buena
  una migración porque «el SQL parece correcto»: se aplica contra un
  PostgreSQL desechable y se comprueba el resultado.

## 11. Reglas específicas de aprendizaje automático

Estas son nuevas y nacen del diagnóstico de la Fase 0.

- **Ninguna métrica se reporta sin su línea base.** Un *accuracy* suelto no
  dice nada. Si el modelo no supera a la regla trivial, el número que hay
  que enseñar es el *lift*, y si es ≤ 0 hay que decirlo.
- **Un modelo que no supera su línea base no se despliega.**
- **No se entrena mezclando filas de procedencias distintas** sin una
  columna que lo diga. Si unas filas traen una característica y otras no, el
  modelo aprende *cuándo se cargó la fila*, no algo del alumno.
- **Lo que se le enseña al alumno como «confianza» tiene que estar
  calibrado.** Un 87 % que acierta el 60 % de las veces es una mentira con
  formato de dato.
- **Todo lo que decida el sistema tiene que poder reconstruirse después.**
  Si no se puede explicar por qué se hizo una pregunta concreta a un alumno
  concreto, no es defendible en una sustentación.

---

# Parte II — Plan de acción

**Punto A:** un cuestionario de 29 preguntas fijas que suma puntos por rama,
y una regresión logística entrenada con 1000 filas sintéticas donde la
etiqueta es `argmax(afinidades)` por construcción — es decir, un modelo que
no aporta nada sobre una regla de una línea.

**Punto B:** un cuestionario adaptativo que elige cada pregunta para
maximizar lo que aprende, sobre un modelo que sabe cuánta confianza merece
su propia respuesta, cuándo no tiene suficiente información, y si la
recomendación que da es estable para esa persona concreta.

## Nota sobre el alcance

El objetivo declarado es «que el modelo tenga conciencia». La conciencia
literal no es alcanzable y afirmarla en una memoria de tesis es indefendible.
Lo que sí es construible, y es lo que este plan entrega, son las cuatro
capacidades concretas que la palabra apunta:

| Lo pedido | Lo que se construye | Se mide con |
|---|---|---|
| «que sepa si está bien o mal» | Calibración de probabilidades | ECE, Brier, diagrama de fiabilidad |
| «que sepa diferenciar» | Incertidumbre aleatoria vs. epistémica | Entropía, distancia al soporte |
| «que sepa si es la mejor para esa persona» | Contrafactuales individuales y estabilidad | Margen, perturbación mínima |
| «como Akinator» | Selección adaptativa por ganancia de información | Reducción de entropía por pregunta |

---

## El problema de fondo: el modelo se muerde la cola

Antes de cualquier decisión técnica hay que nombrar el defecto estructural,
porque determina todo lo demás.

**Hoy el sistema pregunta al alumno cuánto le gusta cada rama, y luego
predice la rama que más le gusta.** La entrada y la etiqueta son la misma
cosa medida dos veces. Por eso `argmax(aff_1..aff_10)` acierta el 99,8 %: no
es que el problema sea fácil, es que no hay problema. No se está prediciendo
nada, se está devolviendo lo que el alumno acaba de decir.

Ningún algoritmo arregla esto. Ni una red neuronal, ni un *gradient
boosting*, ni un *transformer*. Mientras la etiqueta se derive de la
entrada, el techo de cualquier modelo es «repetir la entrada».

**Para romperlo hace falta una fuente de verdad externa al alumno.** Y
resulta que la ficha de investigación ya la nombra.

### RIASEC, Big Five y O\*NET no son un adorno del título: son la solución

El título registrado del trabajo promete «variables psicométricas (RIASEC y
Big Five) e Inteligencia Artificial Explicable (XAI)». Hoy no existe ninguno
de los tres en el código. Eso es a la vez el mayor riesgo en sustentación y
la salida al problema de la circularidad:

| Instrumento | Qué aporta | Por qué rompe la circularidad |
|---|---|---|
| **RIASEC** (Holland) | 6 dimensiones de interés vocacional | Mide intereses **generales**, no preferencia por una rama concreta. El alumno no dice «me gusta Ciberseguridad»; dice si prefiere trabajar con ideas, con personas o con cosas |
| **Big Five** (OCEAN) | 5 dimensiones de personalidad | Ortogonal a los intereses. Un perfil de personalidad no es derivable de la afinidad declarada |
| **O\*NET** | Catálogo ocupacional oficial con código RIASEC por ocupación | **Es la etiqueta externa.** El encaje perfil→ocupación sale de datos del Departamento de Trabajo de EE. UU., no de lo que el alumno cree de sí mismo |

Con esto, la cadena deja de ser circular:

```
ANTES:   alumno dice "me gusta la rama 4"  ->  modelo predice "rama 4"
                    (la etiqueta ES la entrada)

DESPUÉS: alumno responde instrumento validado  ->  perfil RIASEC + Big Five
         perfil  ->  encaje con ocupaciones O*NET  ->  especialización
                    (la etiqueta viene de fuera del alumno)
```

Los tres instrumentos son **de uso libre y citables**, que es justo lo que una
tesis necesita. Licencias verificadas (2026-09-20):

| Recurso | Licencia | Implicación |
|---|---|---|
| **O\*NET Interest Profiler** (RIASEC, 60 ítems) | CC BY 4.0 / *O\*NET Career Exploration Tools Content License*. Su banco de ítems procede de dominio público | Libre, **pero exige atribución**. Hay que incluir el aviso de atribución en el producto y en la memoria |
| **Base de datos O\*NET** (códigos RIASEC por ocupación SOC) | CC BY 4.0 | Igual: descargable y libre, con atribución |
| **IPIP** (marcadores Big Five) | **Dominio público** | Se puede copiar, editar y **traducir** sin permiso ni pago. Gestionado por el Oregon Research Institute |

> **Ojo con el matiz:** O\*NET se cita a menudo como «dominio público» y no lo
> es del todo — es CC BY 4.0. La diferencia es la obligación de atribuir. Dar
> por buena la etiqueta equivocada en una memoria es un error evitable.
>
> Y una ventaja concreta del IPIP: al estar en dominio público se puede
> **traducir al español** sin trámite. Es la vía realista para aplicarlo a
> alumnos de Piura, aunque la traducción habrá que documentarla como una
> limitación (un instrumento traducido sin revalidar no conserva
> automáticamente sus propiedades psicométricas).

Fuentes: [Interest Profiler — O\*NET Resource Center](https://www.onetcenter.org/IP.html) ·
[O\*NET Interest Profiler Manual](https://www.onetcenter.org/reports/IP_Manual.html) ·
[IPIP](https://ipip.ori.org/) ·
[IPIP — Wikipedia](https://en.wikipedia.org/wiki/International_Personality_Item_Pool)

### Advertencia sobre el texto actual del producto

El pie de página y la landing afirman hoy: *«Especializaciones ancladas al
catálogo ocupacional O\*NET»*. **No hay ni un dato de O\*NET en el
repositorio.** Mientras la Fase 2 no esté hecha, esa frase no es defendible.
O se implementa el anclaje, o se retira la afirmación. Las dos cosas son
aceptables; dejarla como está, no.

---

## Fase 0 — Reforma de la base de datos ✅ COMPLETADA

Ver migraciones 20 a 23 en `database/`.

- [x] Retirar objetos muertos: `feedback`, `jobs`, `admin_actions_log` y dos vistas
- [x] Retirar columnas que nunca contuvieron nada en `questions`
- [x] Persistir la fase 3 (`psychometric_answers`) — antes moría en `sessionStorage`
- [x] Ampliar `ml_training_data` con perfil de trabajo, trazabilidad y señal de calidad
- [x] Rellenar `duration_seconds` (señal de calidad del dato)
- [x] Corregir el generador del instalador, al que le faltaba la migración 19
- [x] Corregir `03_seed_questions.sql`, que impedía reejecutar el instalador
- [x] Verificado: instalador completo aplicado **dos veces** sobre PostgreSQL 16 limpio, código 0

**Pendiente de la Fase 0:** regenerar `database/supabase/INSTALAR_SUPABASE.privado.sql`
con `python database/rellenar_instalador.py` (lleva contraseñas reales, no se
toca automáticamente). Desde la migración 33 son **cinco** contraseñas: hay
que añadir `REVO_CLAVE_AGENTE` a las cuatro de siempre, o se generará una
nueva para cada rol y se romperán las conexiones actuales.

### Actualizar e instalar la base (revisado el 2026-09-21)

- **Base que ya existe:** `bash database/herramientas/aplicar_migraciones.sh`. Aplica de la
  10 a la 38, comprueba pgvector antes de empezar y termina verificando RLS,
  documentos legales y vectores. Probado dos veces seguidas sobre la base de
  desarrollo: mismos recuentos de filas antes y después.
- **Instalación desde cero:** probada en un contenedor desechable con la
  imagen nueva: las 38 migraciones corren limpias con todas sus verificaciones.

Lo que hubo que arreglar para llegar ahí:

1. **Una instalación limpia no arrancaba.** Docker ejecuta todo `.sql` de
   `database/`, y los instaladores de Supabase estaban ahí: tras las 38
   migraciones corría el instalador entero otra vez y abortaba. Movidos a
   `database/supabase/`, que Docker ignora.
2. **El camino de actualización llevaba roto desde la migración 20.** La 10,
   la 15 y la 17 tocaban tablas que la 20 retiró (`feedback`, `jobs`,
   `admin_actions_log`); ahora solo actúan si existen. Las verificaciones de
   la 15, la 29 y la 30 esperaban el estado de su época y fallaban tras
   migraciones posteriores legítimas; ahora comprueban lo suyo.
3. **Dos autocomprobaciones borraban datos reales al reaplicarse.** La 27
   hacía `DELETE FROM user_consents WHERE doc_type = 'psychometric'`: el
   consentimiento psicométrico de **todos** los alumnos. La 24 borraba
   muestras por valor. Ahora se deshacen solas, sin ningún `DELETE`.
   Comprobado sembrando filas que el código viejo habría borrado.
4. **La 25 no se reaplica nunca:** empieza con `TRUNCATE ml_training_data`.
   Solo vale para una base vacía, y el script lo dice.

---

## Fase 1 — Cerrar el circuito de datos y arreglar lo que impide medir

Sin esto, las fases siguientes no tienen con qué trabajar. `psychometric_answers`
existe pero nadie escribe en ella, que es exactamente el defecto que se
acaba de corregir en otras tablas.

### 1.a — Bloqueantes de `ml-service` ✅ RESUELTOS

- [x] **`predictions.model_version` era una constante.** Guardaba `"v1.0"`
      fijo mientras `model_training_logs` guardaba la versión real, así que
      era imposible saber qué modelo generó qué predicción. Ahora guarda la
      versión real del artefacto activo.
- [x] **No había versionado de artefactos.** `joblib.dump` sobre una ruta
      única llamada `decision_tree.pkl`. Ahora hay un directorio por versión
      con su modelo, calibración, umbral conformal y conjunto bootstrap, más
      un puntero de versión activa escrito de forma atómica
      ([`model/artefactos.py`](services/ml-service/model/artefactos.py)).
- [x] **Entrenar ya no implica desplegar.** Puerta de promoción que rechaza
      un candidato peor que el activo
      ([`model/promocion.py`](services/ml-service/model/promocion.py)).
      Importa porque el reentrenamiento es **automático** cada 50
      predicciones.
- [x] **El bucle de realimentación solo reforzaba aciertos.** Solo se
      reinyectaban los vectores con `diagnostic_affinity = True`. Ahora el
      desacuerdo con corrección entra como `source='human_corrected'`
      (migración 24), que son las únicas filas que pueden corregir al modelo.

**Bug encontrado al probar:** la versión se construía con marca de tiempo **al
segundo**, así que dos entrenamientos en el mismo segundo compartían nombre;
el segundo pisaba el directorio del primero y **la puerta de promoción acababa
comparándose consigo misma y aprobando cualquier cosa**. Corregido con
`version_libre()` y fijado con pruebas.

### 1.b — La fase 3 y la coherencia del producto

- [ ] `POST /psychometric/sessions/{id}/answers` en `survey-service`
- [ ] El frontend envía las respuestas de fase 3 en vez de solo guardarlas en `sessionStorage`
- [ ] Derivar `psy_a..psy_d` de forma determinista y enviarlas a `/predict/` junto a las afinidades
- [ ] Arreglar `calcArchetype`: hoy desempata con `Math.random()`, así que el mismo alumno puede recibir arquetipos distintos
- [ ] Unificar la fuente de verdad de las especializaciones (hoy los colores viven en cuatro sitios y ya divergieron)

---

## Fase 2 — Anclaje externo: RIASEC + Big Five + O\*NET ✅ HECHA

**Esta es la fase que da sentido a todas las demás.** Sin una etiqueta que no
salga del propio alumno, el mejor modelo del mundo sigue siendo un espejo.

### 2.a — El anclaje ✅ HECHO

- [x] Descargar la base de O\*NET y extraer el perfil RIASEC — **8 307 filas, 923 ocupaciones, O\*NET 31.0, fecha 02/2026**
- [x] Mapear las 10 especializaciones a ocupaciones SOC documentando el criterio — [`mapeo_ramas_onet.py`](database/onet/mapeo_ramas_onet.py)
- [x] Derivar la matriz de similitud `S` de los perfiles y **retirar `BLOQUES` del generador**
- [x] **Cumplir** la afirmación sobre O\*NET del pie de página (antes era falsa)
- [x] Añadir la atribución CC BY 4.0 en el producto

El encaje con las ocupaciones reales resultó casi exacto: O\*NET tiene
*Penetration Testers*, *Digital Forensics Analysts*, *Software Quality
Assurance Analysts and Testers*, *Web and Digital Interface Designers*…

**Perfiles RIASEC obtenidos (medidos por O\*NET, no asignados por nosotros):**

| Rama | Código Holland | Qué la distingue |
|---|---|---|
| Diseño UX/UI | **A**IC | Artistic 5,43 — la única artística |
| Gestión y Producto | C**E**I | Enterprising 5,50 — la única emprendedora |
| Investigación | **I**CR | Investigative 6,14 — la más alta |
| Soporte Técnico | C**R**I | Social 2,79 — la que trata con personas |
| QA & Testing | ICR | Enterprising 1,57 — la más baja |

**La matriz derivada confirmó los bloques hechos a mano y corrigió dos
cosas:** descubrió Data Science ↔ Sistemas Empresariales (0,70), que no
estaba, y aisló Gestión y UX/UI, que sí estaban agrupadas y resultan no
parecerse a nada.

**Efecto medido sobre el modelo** (validación cruzada 5×3, y confirmado
entrenando contra la base real):

| | Con matriz a mano | Con matriz O\*NET |
|---|---|---|
| Acierto de `argmax` | 65,8 % | 82,7 % |
| Acierto del modelo | 74,8 % | **90,0 %** |
| **Lift** | +9,1 | **+7,7** |
| ECE tras calibrar | 0,040 | **0,014** |
| Alumnos con **una sola** rama recomendada | 25 % | **69 %** |

> El `argmax` sube porque O\*NET dice que las ramas se parecen **menos** de lo
> que yo había supuesto. El lift baja un poco por eso mismo — hay menos
> margen — pero sigue siendo holgado, y ahora la estructura no la puso nadie
> de este proyecto.

### 2.b — La medición ✅ HECHA

- [x] **Mini-IP** de O\*NET: los 30 ítems, verbatim del Apéndice A del informe de Rounds et al. (2016)
- [x] **Mini-IPIP**: los 20 ítems con su clave de corrección, de `ipip.ori.org/MiniIPIPKey.htm`
- [x] Tablas `riasec_items`, `bigfive_items`, `student_profiles` (migración 26), bajo RLS
- [x] Puntuación **según los manuales**: Mini-IP suma 0–20 por tipo; Mini-IPIP invierte y promedia 1–5
- [x] Encaje perfil-alumno → perfil-rama por **correlación de Pearson** + letras Holland compartidas
- [x] Traducción al español con **el original en inglés en la misma fila**, para que la fidelidad sea auditable
- [x] Revisar el consentimiento: recoger personalidad es más sensible que recoger preferencias técnicas (Ley 29733)

**Por qué correlación y no distancia:** el perfil del alumno va en escala
0–20 y el de la ocupación en la 1–7 de O\*NET. La correlación es invariante a
escala y desplazamiento, así que compara **la forma** del perfil — qué
dimensiones destacan sobre las demás del propio alumno. Eso además neutraliza
la aquiescencia: quien marca «me gusta» a todo sale con el mismo perfil
relativo. Es la práctica habitual para medir congruencia en psicología
vocacional.

**La prueba que valida toda la fase:** un alumno que responde que le gustaría
«pintar escenografías» y «componer música» —sin que ningún ítem mencione
jamás una especialización de Ingeniería de Sistemas— acaba en **Diseño
UX/UI**. Un perfil emprendedor acaba en **Gestión y Producto**. Uno social
pone **Soporte Técnico** por delante de **Investigación**. Esa es la cadena
no circular funcionando.

### Hallazgo: Apertura no está equilibrada en el Mini-IPIP

Al probar la puntuación salió que el factor **Apertura tiene 1 ítem directo y
3 invertidos**, mientras Extraversión, Amabilidad, Responsabilidad y
Neuroticismo van 2 y 2. Es así **en el instrumento publicado**, no es un error
de transcripción.

Consecuencia medible: quien contesta lo mismo a todo sale centrado (3,0) en
los otros cuatro factores y **desplazado (2,0) en Apertura**, que por tanto
arrastra un sesgo de aquiescencia que los demás no tienen.

**No se corrige.** Añadir un ítem que el instrumento no tiene rompería la
comparabilidad con la literatura, que es lo único que justifica usar una
escala publicada en vez de inventarla. Se declara como limitación y queda
fijado en una prueba para que nadie lo «arregle».

### Limitación que tiene que constar en la memoria

RIASEC se diseñó para separar ocupaciones de **todo** el mercado laboral
—enfermera contra mecánico contra artista—, no diez especialidades dentro de
la informática. Por eso las diez comparten un perfil alto en Convencional e
Investigativo: son todas trabajo técnico con datos.

Lo que las separa son las dimensiones minoritarias. La separación existe y es
medible (distancia mínima 0,90, media 2,64), pero es **más fina** que la que
RIASEC produce entre familias profesionales distintas. Afirmar que RIASEC por
sí solo distingue estas diez ramas sería exagerado; lo correcto es decir que
aporta una estructura externa que antes no existía.

---

## Fase 2.bis — Reescribir el banco de ítems ✅ HECHA

**Es la intervención de mayor retorno de todo el plan** y no depende de
ninguna otra. Ningún refinamiento bayesiano compensa un banco que no
discrimina.

### Qué está roto, con ejemplos del banco actual

Las 100 preguntas son 4 plantillas × 10 temas. Los 10 ítems de Ciberseguridad
ilustran los cuatro defectos:

| Ítem actual | Defecto |
|---|---|
| «A nivel académico, destaco ampliamente al tener que **usar Kali Linux**» | Mide **exposición previa**, no interés. Un alumno de tercer ciclo no ha tocado Kali. Y la exposición depende de qué cursos le tocaron — el mal motivo de elección que REVO dice corregir |
| «Me considero **extremadamente hábil** para encontrar vulnerabilidades» | Autoevaluación de **competencia**, contaminada por confianza. Hay diferencias sistemáticas por género: apartaría de las ramas técnicas a quien tiene menos confianza, no menos interés. Es un problema de equidad, no de ruido |
| «**Mi personalidad metódica** encaja perfectamente con analizar malware» | **Doble cañón**: afirma un rasgo y pregunta por la tarea. Quien no es metódico pero ama el malware no tiene respuesta |
| Todos | **Intensificadores** («profundo», «ampliamente», «en el nivel más avanzado») que comprimen la varianza justo donde hace falta discriminación |

> **Cuidado con el α de Cronbach.** Con ítems generados por plantilla, los 10
> de una rama son casi duplicados: el α saldrá ~0,90 y **no será buena
> noticia**. Es la paradoja de la atenuación — la redundancia sube el α y baja
> la validez. El diagnóstico correcto aquí **no es α**, es la **correlación
> cruzada entre ramas**.

### La estrategia: cambiar la capa, no reescribir 100 ítems

| Capa | Qué | Origen | Trabajo |
|---|---|---|---|
| **A — RIASEC** | **Mini-IP** de O\*NET: 30 ítems, 5 por escala, α .74–.81, κ .73 contra la versión larga. Diseñado para móvil y respuesta rápida | Adoptar | Ninguno |
| **B — Dominio** | Mapeo interés general → 10 ramas de Ingeniería de Sistemas | **Propio** | Reescribir |
| **C — Big Five** | Mini-IPIP, 20 ítems, dominio público | Adoptar | Traducir |

La capa B es donde está la aportación original: ese mapeo no lo tiene hecho
nadie. Las otras dos son gratis y citables.

### Reglas de redacción para la capa B

- [x] **Actividad, no autoevaluación** (forma del O\*NET IP)
      – Antes: «Me considero extremadamente hábil para encontrar vulnerabilidades en mi día a día»
      – Después: «Buscar fallos de seguridad en un sistema antes de que alguien los aproveche»
- [x] **Sin intensificadores**
- [x] **Nada que exija experiencia previa**: fuera los nombres de herramienta
      (Kali, SAP, Selenium), dentro la actividad que la herramienta realiza
- [x] **Una redacción por ítem**, no una plantilla por categoría

### Elección forzada: lo que de verdad lo hace Akinator

Pares entre ramas confundibles:

> *Un sistema se cayó anoche. ¿Qué prefieres hacer?*
> **(a)** Encontrar por qué falló y evitar que se repita → Infraestructura
> **(b)** Averiguar si alguien provocó la caída → Ciberseguridad

- [x] Construir pares para las combinaciones que `S` marque como similares

Tres ventajas que el Likert no puede dar: **mata la aquiescencia** (no existe
«5 a todo», y `θ_u` deja de hacer falta), **mata la deseabilidad social**
(ambas opciones son atractivas) y **da evidencia directa sobre la frontera
A-vs-B**, que es justo lo que la ganancia de información busca.

Y encaja de forma natural con el motor: **`S` dice qué ramas se confunden y el
motor elige qué par preguntar.** Eso es literalmente cómo Akinator estrecha el
campo.

> **Contrapartida honesta:** la elección forzada produce datos **ipsativos**
> (relativos dentro de la persona). Complica algunas estadísticas, pero para
> un producto que entrega un **ranking top-3** es lo correcto: quieres
> preferencia relativa. Hay que declararlo en la memoria.

### Lo hecho (migraciones 28 y 29)

| | Antes | Ahora |
|---|---|---|
| Forma del ítem | «Me considero extremadamente hábil para…» | «Buscar fallos de seguridad antes de que alguien los aproveche» |
| Qué mide | Competencia autopercibida y exposición previa | Preferencia por una actividad |
| Categorías | 4, una por plantilla | 3 con significado (40 *skills*, 30 *interests*, 30 *academic*) |
| `personality` | 20 ítems Likert de rama | Retirada: medir personalidad es trabajo del Mini-IPIP |
| Elección forzada | No existía | **21 ítems sobre los 7 pares confundibles** |

**Los 100 ítems viejos no se borraron**, se marcaron `is_active = FALSE`.
Hay 7 043 respuestas apuntando a esos `question_id`: reescribir el texto en
su sitio habría hecho que el historial de 655 sesiones dijera algo que nadie
contestó.

**Los 7 pares de elección forzada no se eligieron a ojo.** Salen de la matriz
RIASEC/O\*NET tomando similitud ≥ 0,40: el dato externo dice dónde el Likert
se va a quedar corto, y ahí va el ítem que sí discrimina.

| Similitud | Par |
|---|---|
| 0,70 | Data Science ↔ Sistemas Empresariales |
| 0,61 | Infraestructura ↔ Ciberseguridad |
| 0,60 | Desarrollo ↔ Investigación |
| 0,57 | Ciberseguridad ↔ QA |
| 0,42 | Desarrollo ↔ Ciberseguridad |
| 0,42 | Infraestructura ↔ Soporte |
| 0,41 | Ciberseguridad ↔ Investigación |

La migración **verifica que las dos opciones de cada ítem tengan longitud
parecida**: si una es mucho más larga, el ítem mide redacción y no
preferencia.

### Proceso de validación sin psicometrista

- [ ] Escribir **el doble** de ítems de los necesarios, para poder descartar
- [ ] Piloto con n≈30–50 (no hace falta la muestra final)
- [ ] Descartar ítems con correlación ítem-resto `r_it < 0,30`
- [ ] **Descartar los que correlacionen con otra rama tanto como con la suya** — este es el diagnóstico clave, no α
- [ ] Revisión de validez aparente por el asesor y 2–3 personas de cada especialización

Fuentes: [Mini-IP — O\*NET Resource Center](https://www.onetcenter.org/reports/Mini-IP.html) ·
[Interest Profiler](https://www.onetcenter.org/IP.html)

---

## Sobre la base de datos vectorial ✅ HECHO Y VERIFICADO

Pregunta recurrente: ¿conviene convertir la base en vectorial?

> **Decisión del 2026-09-21:** se habilita `pgvector`, a petición expresa del
> autor tras discutirlo. Se hace en la forma que se puede defender: la base
> sigue siendo relacional y se guardan como vectores **solo los datos que ya
> eran vectores**. Ver «Lo que se hizo», al final de esta sección. Lo que
> sigue justo debajo es el razonamiento anterior, que sigue siendo válido
> para las tablas que **no** se tocaron.

**No existe esa operación.** `pgvector` no es un tipo de base de datos: es
una extensión que añade un tipo de columna (`vector(n)`) y unos índices. La
base seguiría siendo PostgreSQL relacional con RLS y claves ajenas. Lo que
se decide es **en qué columnas** tiene sentido, y la respuesta es: en muy
pocas.

Los vectores sirven para buscar **por significado en texto**. `users`,
`answers`, `questionnaire_sessions` y `user_consents` no tienen semántica
que capturar, y sí necesitan lo que un vector quita: igualdad exacta,
unicidad e integridad referencial. Buscar un usuario «parecido» a un correo
no es una consulta con sentido.

### Prueba hecha el 2026-09-21: TF-IDF para derivar la matriz `S`

El generador del dataset tiene la matriz de similitud entre ramas escrita a
mano (`BLOQUES` + `SIMILITUD_EN_BLOQUE = 0.72`). Es un criterio propio y por
tanto atacable en sustentación. Se probó derivarla del texto que ya existe:
`description` + `career_paths` + las 100 preguntas agrupadas por rama
(~160 palabras por rama), con TF-IDF de scikit-learn.

**Resultado: no sirve.**

| | |
|---|---|
| Aciertos | ~50 % (Infraestructura↔Soporte y Gestión↔Empresariales bien; Data Science↔Ciberseguridad mal) |
| Rango de similitud fuera de la diagonal | 0,042 – 0,124, **media 0,065** |

El problema no son los aciertos sino el **rango**: sin separación, usar esos
valores obligaría a reescalarlos, y ese reescalado sería otra decisión a
mano. Se cambiaría un criterio explícito por uno escondido tras un cálculo,
que es peor.

**Causa:** TF-IDF mide solapamiento **léxico**. Las diez ramas casi no
comparten palabras porque cada una usa su vocabulario técnico, y lo que sí
comparten son las muletillas de las 4 plantillas del banco (ver Fase 2.bis).

### Cuándo entra entonces

Con la **Fase 2**, y por dos motivos a la vez:

1. **Texto suficiente.** Las descripciones ocupacionales de O\*NET son mucho
   más ricas que 160 palabras de plantilla.
2. **Fuente externa.** La similitud deja de derivarse de texto propio, que
   es circular, y pasa a derivarse de un catálogo oficial.

Y hará falta un modelo **semántico**, no TF-IDF: uno entiende que «analizar
malware» y «auditar sistemas» se parecen aunque no compartan una palabra.

- [ ] `CREATE EXTENSION vector` — requiere cambiar la imagen a `pgvector/pgvector:pg16`; `postgres:16-alpine` **no lo trae**
- [ ] `onet_occupations.embedding` — el único caso con búsqueda por similitud de verdad (~1000 ocupaciones)
- [ ] `specializations.embedding` — para casar las 10 ramas con O\*NET de forma reproducible
- [ ] Derivar `S` de esos embeddings y retirar `BLOQUES` del generador

> **Los embeddings se calculan fuera de línea.** Se guardan los vectores y en
> ejecución solo se hace distancia coseno. El contenedor de producción no
> carga ningún modelo, que es lo que hace esto viable en un VPS modesto.

### Lo que se hizo (migraciones 36 y 37)

No hizo falta ningún modelo de embeddings: los datos que importan **ya eran
vectores numéricos**. Un perfil RIASEC son 6 números y las afinidades son 10.

| Columna | Qué guarda | Para qué |
|---|---|---|
| `onet_ocupaciones.forma_riasec` | 923 ocupaciones reales de O\*NET (tabla nueva) | Ocupaciones afines a cada alumno |
| `specializations.forma_riasec` | El perfil de cada rama | Estimar el perfil del alumno |
| `student_profiles.forma_riasec` | El perfil del Mini-IP | Se rellena sola cuando se administre el instrumento |
| `ml_training_data.afinidades` | Las 10 afinidades de cada muestra | Vecindario: detectar perfiles poco vistos |

**La «forma» es el perfil centrado.** El encaje RIASEC se mide con Pearson, y
Pearson es exactamente el coseno entre perfiles centrados. Así el operador de
coseno de pgvector (`<=>`) calcula la métrica de la literatura, con índice
HNSW. La migración lo comprueba contra el `corr()` de PostgreSQL.

**Validado con los datos reales antes de escribirlo:** buscando por perfil
entre las 923 ocupaciones, las que se mapearon a mano a cada rama aparecen
entre las 3 primeras en 6 ramas y entre las 14 primeras en todas. En QA &
Testing, la más cercana es literalmente «Software Quality Assurance Analysts»
(r = 1,000). El seed usa eso como comprobación de que las columnas no se
cargaron desordenadas.

**Dos usos, los dos ya en `/predict/`:**

1. **Vecindario** (incertidumbre epistémica, pendiente en la Fase 5): distancia
   media a los 10 alumnos más parecidos del dataset. Si supera el percentil 95
   de lo visto al entrenar, el perfil es «poco visto». Una función
   `SECURITY DEFINER` lee el dataset protegido y devuelve **una cifra, nunca
   filas**; activa el contexto de servicio solo mientras se ejecuta.
2. **Ocupaciones afines:** las 5 ocupaciones con el perfil de intereses más
   parecido al que el modelo atribuye al alumno (media de los perfiles de las
   ramas ponderada por las probabilidades calibradas).

**Limitación:** RIASEC mide el *tipo* de trabajo, no el sector. «Afín»
significa «intereses parecidos», no «de tu rama».

**Infraestructura:** imagen propia `postgres:16-alpine` + pgvector v0.8.6
compilado (`infraestructura/postgres/Dockerfile`). No se usó la oficial de
pgvector porque es Debian: cambiar de libc sobre un volumen con datos puede
alterar el orden de los índices de texto sin dar error.

- [x] Imagen con pgvector, migración 36 (esquema) y 37 (datos, generados desde el CSV)
- [x] Umbral de vecindario calculado al entrenar y guardado con el modelo
- [x] `/predict/` devuelve `vecindario` y `ocupaciones_afines`; si pgvector falla, la predicción sigue y lo dice
- [x] **Verificado contra PostgreSQL** (2026-09-21): imagen reconstruida sobre el volumen existente (copia previa con `pg_dump`; datos intactos), 36 y 37 aplicadas dos veces, 33 reaplicada sin que `revo_agente` alcance la tabla nueva. Pearson por coseno = `corr()` de PostgreSQL: 0,979944 en los dos
- [x] Como `revo_ml` en contexto de alumno: 0 filas del dataset visibles, la función de vecindario devuelve una cifra y el contexto sigue siendo `student` al salir
- [x] La búsqueda de vecinos usa el índice HNSW: 0,8 ms sobre 2001 muestras
- [x] Recorrido completo por la pasarela y 14 pruebas de integración contra Postgres y Redis reales

### Dos cosas que salieron al verificarlo

**1. El resultado completo nunca había llegado a la pantalla.** La pantalla
carga la predicción con `GET /predict/{id}`, y esa ruta solo devolvía lo que
había en la tabla. La calibración, la incertidumbre, el conjunto conformal y
`all_probabilities` se calculaban en el `POST` y se perdían: la gráfica de
barras de resultados salía vacía. Migración 38: el resultado se guarda entero
en `predictions.detalle` en el momento de predecir, y el `GET` lo devuelve tal
cual. No se recalcula al leer: si el modelo se reentrena, la recomendación de
un alumno cambiaría sola.

**2. El conjunto bootstrap tiene un punto ciego, y el vecindario lo cubre.**
Caso real, predicción 296: 99,9 % de confianza, conjunto conformal de una
rama, y los 30 modelos bootstrap de acuerdo (desacuerdo 0,005). Pero el alumno
estaba a 0,79 de sus vecinos, con un umbral de 0,60. Los 30 modelos son
regresiones logísticas: lejos de las fronteras todas extrapolan igual y
«coinciden» aunque nadie haya visto ese perfil. Ahora el vecindario entra en
la lectura (`perfil_poco_visto`, con `fuentes_epistemicas` diciendo qué medida
lo detectó) y la pantalla pide cautela en vez de decir «apuntan claramente a
una rama». Verificado en la predicción 298.
- [x] Mostrar las ocupaciones afines y el aviso de «perfil poco visto» en la pantalla de resultado (`frontend/src/pages/resultadoConfianza.js`, probado con capturas a 1366 y 360 px). La afinidad se muestra como etiqueta («muy parecido»), no como porcentaje: una correlación de 0,98 no es un 98 % y se confundiría con el de compatibilidad
- [ ] Usar `student_profiles.forma_riasec` en vez del perfil estimado cuando el Mini-IP se administre
- [ ] Embeddings semánticos de texto (descripciones de O\*NET, cursos del agente): solo si hace falta, calculados fuera de línea

---

## Fase 3 — Motor adaptativo (el «Akinator») 🟡 EL MOTOR FUNCIONA

Sustituir «5 preguntas al azar por finalista» por «la pregunta que más reduce
la incertidumbre, dada la creencia actual». En la literatura esto es
**Computerized Adaptive Testing (CAT)**, el campo establecido para
instrumentos psicométricos adaptativos — se puede citar y defender en vez de
improvisarlo.

### 3.a — El cambio que quita la tautología

**Con motor adaptativo, la fase 2 deja de restringirse al top-3 de la fase 1.**
Las 90 preguntas restantes pasan a ser candidatas.

Esa restricción era precisamente lo que hacía que `aff` fuera circular: las 7
ramas no exploradas quedaban bajas **por construcción**, no porque el alumno
no encajara en ellas. Quitarla es un cambio de una línea conceptual con más
efecto que cualquier algoritmo.

### 3.b — Modelo de creencia: ~150 parámetros, no 5.000

Clase latente discreta sobre las 10 ramas, con verosimilitud ordinal tipo
*graded response*. La clave es **no** usar un naive Bayes tabular: sería
100 preguntas × 10 ramas × 5 niveles = **5.000 parámetros** para 200–400
alumnos, unas 0,05 observaciones por celda. Inviable.

| Parámetro | Qué es | Cuántos |
|---|---|---|
| `δ_q` | discriminación del ítem | 100 |
| `b_cat` | atractivo por categoría | 4 |
| `τ_1..4` | umbrales de la escala Likert | 4 |
| **`S`** | **similitud entre ramas** | 45 |
| `θ_u` | sesgo de aquiescencia del alumno | 1 por sesión |

**`S` es lo que convierte esto en Akinator.** Con `S = I` el motor degenera
en «sumar puntos con probabilidades». Con `S` bien puesta, una sola pregunta
descarta un **grupo** de ramas, que es exactamente lo que hace Akinator.

`θ_u` merece una nota: quien contesta 4-5 a todo hace que un «5» sea
evidencia débil; quien contesta 2-3, un «5» es evidencia fuerte. El modelo
actual (`aff = suma/30`) no puede distinguir eso, y por eso está dominado por
**estilo de respuesta** más que por contenido.

### 3.c — Selección y parada

Ganancia de información esperada, en bits:

```
EIG(q) = H(p_t) − Σ_k  p̃(k) · H( p^(k) )
```

**Coste: < 1 ms** con NumPy sobre las 100 candidatas. Es despreciable frente
a un viaje a PostgreSQL (10–30 ms), así que no hay que optimizarlo — aplica
YAGNI.

- [x] **No elegir el argmax puro:** elegir uniformemente entre los 3 mejores
      (*randomesque*, Kingsbury–Zara). Sin esto, los 100 ítems se reducen a
      los mismos 6 para todo el mundo y — crítico para la tesis — **el
      dataset resultante es degenerado y no permite recalibrar nada**
- [x] Tope de 4 preguntas por rama
- [ ] Cobertura de categorías cuando queda poco presupuesto (no implementada)
- [x] Descuento `λ ≈ 0,75` por preguntas repetidas de la misma rama: las 10
      preguntas de una rama están correlacionadas, y tratarlas como
      independientes produce posteriors de 0,999 que son **falsas**
- [x] Suelo `ε` para que ninguna rama muera de forma irrecuperable

**El criterio de parada correcto es el margen entre el 3.º y el 4.º, no entre
el 1.º y el 2.º.** El producto entrega un **top-3**, así que la frontera que
importa es la del puesto 3. Puede haber un top-1 clarísimo y un empate
caótico entre los puestos 3 y 6, que es justo lo que el alumno va a ver.

Valores v0: `T_min = 6`, `T_max = 15` (**paridad exacta con la fase 2
actual**, para poder comparar adaptativo-15 contra aleatorio-15 de forma
limpia), `H_stop = 1,0 bit`, `margen₃₄ ≥ 0,08`.

### 3.d — Reparto entre servicios: artefacto versionado

El conflicto: el motor necesita el modelo (de `ml-service`) para elegir la
pregunta (de `survey-service`), y `revo_ml` no puede leer `answers`.

**Decisión: `ml-service` publica un artefacto versionado; el motor se ejecuta
dentro de `survey-service`. Cero HTTP por pregunta.**

Se descartó una llamada HTTP por pregunta: con el arranque en frío de Render,
si `ml-service` duerme a mitad del cuestionario, **una pregunta tarda 30–60
segundos**. Inaceptable.

El artefacto lleva el **tensor de log-verosimilitudes ya evaluado**
(100×10×5 ≈ 60 KB, 15 KB comprimido), no los parámetros. Así
`survey-service` no contiene ni una línea de modelado psicométrico: solo
busca en una tabla y suma en log-espacio. **El modelo sigue siendo de
`ml-service`; `survey` solo lo ejecuta.**

- [ ] `GET /interno/modelo-adaptativo/actual` con ETag
- [x] Artefacto v0 **empaquetado en el repositorio** como respaldo: `survey` nunca se bloquea esperando a `ml`
- [x] `hash_banco` para detectar desincronización; si no cuadra, **degradar** a un artefacto calculado en caliente, no rechazar el arranque
- [ ] Al cerrar la sesión, `survey` **empuja** el registro seudonimizado a `ml` por HTTP (mismo mecanismo que hoy). **Ningún permiso nuevo de base de datos**

### 3.e — Reescopar `ml-service` (no es opcional)

Objeción legítima: si `survey` calcula la creencia, ¿para qué sirve `ml`? Si
solo rehace el `argmax` de la posterior, la tautología no desaparece, **solo
se muda de sitio**. Nuevo rol, con tres funciones reales:

1. Calibrar y publicar el artefacto (el trabajo psicométrico)
2. **Re-ranking final** combinando posterior + perfil de trabajo + contexto, con confianza calibrada contra `prediction_feedbacks`
3. **Explicabilidad**: qué preguntas movieron más la posterior de cada rama — que es justo el XAI de la Fase 6

### 3.f — Arranque en frío

- [x] `δ_q` por categoría, deducido del propio generador de preguntas. Las
      plantillas no discriminan igual: *interests* («siento un profundo
      interés por…») separa bien; *personality* es casi idéntica entre ramas
      y mide metodicidad, no rama. Propuesta: interests 1,00 · skills 0,90 ·
      academic 0,70 · personality 0,45
- [x] ~~`S` por juicio experto + TF-IDF~~ → **superada**: `S` sale de los perfiles RIASEC de O\*NET (Fase 2). El intento con TF-IDF se midió y se descartó
- [ ] Con alumnos reales, calibrar **sin etiquetas**: `τ` desde las
      marginales, `δ_q` desde la correlación ítem-resto `r_it`, y α de
      Cronbach por rama para detectar bancos incoherentes

> **El elefante:** no existe la etiqueta verdadera. No se sabe cuál es la
> rama «correcta» de cada alumno. Con n≈200 y 10 clases, ajustar el modelo
> completo **no es identificable**. Recomendación: mantener `S` fija por
> juicio experto durante toda la tesis y usar los datos reales solo para
> `τ`, `δ_q` y α. Prometer más sería insostenible en la defensa.

### 3.g — Despliegue por etapas

| Etapa | Qué | Riesgo |
|---|---|---|
| **v0 — sombra** | El motor corre **en paralelo** al cuestionario actual: registra qué *habría* preguntado, pero se sigue sirviendo el flujo de hoy | **Cero** |
| **v1** | Selección adaptativa en vivo, 15 preguntas fijas | Bajo: mismo número que hoy |
| **v2** | Parada temprana, tras validar el criterio con los datos de v1 | Medio |
| **v3** | Recalibración con datos reales | Bajo |

La **etapa sombra** es la recomendación operativa más importante: permite
escribir el capítulo de resultados comparando adaptativo contra aleatorio
**sobre los mismos alumnos** — diseño experimental mucho más fuerte que dos
grupos separados — sin arriesgar la recolección de datos de la tesis.

### 3.h — Auditoría

- [ ] Nueva tabla `decisiones_adaptativas` (la escribe solo `revo_survey`):
      posterior antes y después, entropía, EIG elegida y top-5, respuesta y
      latencia. ~9 KB por sesión; 500 alumnos = 4,5 MB
- [ ] Semilla del generador aleatorio + `modelo_version` + `hash_banco` ⇒ **replay determinista**
- [x] Prueba de determinismo en la suite: reejecutar sesiones grabadas y exigir igualdad
- [ ] **Ley 29733:** esa tabla contiene datos personales de la misma categoría que `answers`. La rutina de borrado tiene que cubrirla desde el primer día

> La pregunta de la defensa va a ser literalmente *«¿por qué le hizo esa
> pregunta a ese alumno?»*. Este registro es la respuesta.

### 3.i — El riesgo mayor, dicho claro

**El cuello de botella no es el algoritmo: es la calidad de las 100
preguntas.** Ver la **Fase 2.bis**, que es donde se ataca. Un motor
adaptativo sobre un banco que no discrimina es un algoritmo caro para elegir
entre ítems que todos miden lo mismo.

> Y una distinción que hay que tener clara en la memoria: el motor adaptativo
> mejora la **eficiencia de medición**, no la **validez predictiva**. La
> tesis no puede afirmar que predice éxito profesional. Sí puede demostrar:
> menos ítems para igual o mayor fiabilidad. Confundir ambas cosas es el
> fallo más probable de la defensa.

---

## Fase 4 — Dataset honesto ✅ HECHA (paso intermedio)

[`database/generar_dataset.py`](database/generar_dataset.py) sustituye a
`simulate_ml_data.py`, que elegía la etiqueta **primero** y luego fabricaba
las afinidades para que esa rama ganara.

- [x] Modelar la persona antes que sus respuestas
- [x] Solapamiento real entre ramas (matriz de similitud por bloques)
- [x] Estilo de respuesta: aquiescencia y contraste individuales
- [x] **Sesgo de deseabilidad por rama** — el mecanismo que de verdad rompe el
      `argmax`
- [x] Incluir el perfil de trabajo en la generación
- [x] Guardarraíl: el generador **avisa** si el `argmax` vuelve a acertar >95 %

### Por qué el sesgo de deseabilidad era la pieza que faltaba

El primer intento dio un `argmax` del **96,7 %** — seguía siendo circular. El
error era conceptual: la aquiescencia suma lo mismo a todas las ramas, así que
**no cambia cuál es el máximo**. Tampoco el contraste, que multiplica.

Lo que sí lo cambia es que no todas las ramas suenan igual de bien: «Data
Science e IA» y «Ciberseguridad» tienen prestigio; «Soporte Técnico» y «QA»
suenan a trabajo ingrato. El alumno infla su afinidad declarada hacia las
primeras. Eso hace que el `argmax` se equivoque en una dirección
**sistemática y predecible** — justo el tipo de estructura que un modelo puede
aprender a descontar y una regla trivial no.

### Resultado medido (validación cruzada 5×3)

| | Acierto | Lift sobre `argmax` |
|---|---|---|
| Regla trivial `argmax` | 65,8 % | — |
| Modelo, solo afinidades | 74,8 % | **+9,1 pts** |
| Modelo + perfil de fase 3 | 77,2 % | **+11,4 pts** |

El perfil de la fase 3 que se estaba tirando a la basura vale **+2,3 puntos**
por sí solo.

- [ ] Pendiente: generar a partir del modelo RIASEC→ocupación (Fase 2)

> **Sigue siendo sintético.** Que el modelo supere al `argmax` aquí demuestra
> que el pipeline **aprende**, no que acierte con alumnos reales: la etiqueta
> sale de un supuesto del generador, no de una fuente externa. Eso lo arregla
> la Fase 2. Este fichero es el paso intermedio honesto, no el destino.

---

## Fase 5 — La capa de autoconciencia

Aquí es donde «que sepa si está bien o mal» se convierte en algo medible.
Cada pieza tiene método, umbral y motivo.

### 5.a — Calibración: que el porcentaje no mienta

Hoy la pantalla enseña «87 % de confianza» tomado directo de
`predict_proba`. Eso no es una probabilidad honesta por dos motivos
acumulados: el dataset es sintético **y** `class_weight="balanced"`
([`trainer.py:60`](services/ml-service/model/trainer.py#L60)) deforma la
superficie de decisión respecto a las proporciones reales.

- [x] **Temperature scaling multiclase.** Un solo parámetro *T*: es lo más
      barato y lo más defendible con ~1000 filas y 10 clases. Platt e
      isotónica necesitan bastantes más datos por clase
- [x] Partición de calibración **separada** de la de entrenamiento (idealmente *out-of-fold*)
- [x] Métricas y umbrales: **ECE < 0.05** (ideal < 0.03) con binning adaptativo, **MCE < 0.15**, Brier multiclase contra el uniforme, y diagrama de fiabilidad por clase
- [x] Persistir *T* junto al artefacto versionado (depende de 1.a)

> **Advertencia que tiene que constar en la memoria:** calibrar sobre un
> dataset donde la etiqueta es `argmax(aff)` por construcción es
> **calibración circular**. El ECE bajo que salga de ahí no dice nada sobre
> alumnos reales. Hay que etiquetarlo así explícitamente.

### 5.b — Los dos tipos de «no sé»

- [x] **Aleatoria** (el alumno de verdad encaja en dos ramas): entropía normalizada y margen top1−top2. Coste prácticamente nulo
- [x] **Epistémica** (nunca vimos a nadie así): *ensemble* por *bootstrap* de 25–50 regresiones logísticas. Barato, es *bagging* estándar y por tanto citable, y de paso sirve para los intervalos de confianza de la Fase 7
- [ ] Opcional: distancia al conjunto de entrenamiento (kNN o Mahalanobis)

### 5.c — Abstención y conjuntos de predicción

- [x] **Conformal prediction** (*split conformal* con APS), aplicado **después** de calibrar. Viable con ~150–200 ejemplos de calibración conformal
- [x] Regla de producto: conjunto de tamaño 1 → se muestra top-1; 2–3 → «tu perfil encaja en varias»; >3 → el sistema **admite que necesita más preguntas** (y con la Fase 3 puede pedirlas)

> **Qué garantiza de verdad:** cobertura **marginal**, o sea promediada
> sobre muchos alumnos. **No** garantiza nada sobre un alumno concreto. Y
> sobre datos sintéticos la garantía es sobre el proceso generador, no sobre
> personas. Decirlo tal cual es parte del rigor, no una debilidad.

### 5.d — «¿Es la mejor recomendación para esta persona?»

- [ ] **Contrafactual mínimo**: qué cambio más pequeño en las respuestas
      cambiaría el resultado. En una logística multinomial la frontera es
      lineal, así que sale en forma cerrada — es barato
- [ ] **Estabilidad**: perturbar las respuestas 200 veces con ruido gaussiano; se considera robusta si el resultado aguanta en ≥ 80 % de las réplicas
- [ ] **Vecindario**: distancia a alumnos reales parecidos (esperar a tener masa crítica de filas `source='human'`)
- [ ] Decidir qué se enseña: **nunca** los coeficientes ni el contrafactual exacto — eso es la receta para responder el test a medida. Sí categorías cualitativas de confianza y el conjunto conformal

### 5.e — Romper el bucle de realimentación

Es el punto más urgente de toda la fase.

- [x] Cuando `diagnostic_affinity = False`, **preguntar cuál sí lo representa** e inyectarlo como `source='human_corrected'`
- [ ] Tope de proporción `human` / `synthetic` por reentrenamiento
- [ ] **Conjunto de oro** de validación humana que **nunca** entra al entrenamiento
- [ ] Opcional: seguimiento a 3–6 meses como señal de verdad tardía

> `affinity_rate` mide **acuerdo con el diagnóstico**, no calidad de la
> decisión de carrera. No debe llamarse «accuracy en producción» en ningún
> sitio del panel.

### 5.f — Deriva y monitorización

- [ ] PSI por afinidad: < 0.1 correcto · 0.1–0.25 vigilar · > 0.25 alerta
- [ ] Deriva de la distribución de especialización predicha
- [ ] Media y percentil 10 de la confianza, semanal
- [ ] Tasa de realimentación recibida; alerta si < 20 % en 7 días
- [ ] Mantener visible el ratio `human`/`synthetic` que ya existe, con su advertencia

---

## Fase 6 — XAI: explicabilidad local

La ficha promete «Inteligencia Artificial Explicable». Hoy lo único que hay
es la media de `|coef_|` de la regresión: **importancia global**, no
explicación individual, y además restringida a administradores. Un alumno no
puede saber por qué le salió su resultado.

- [ ] Explicación local por alumno (SHAP o equivalente defendible)
- [ ] Traducir la explicación a lenguaje del alumno, no a nombres de variables
- [ ] Decidir qué se muestra sin regalar la receta del modelo
- [ ] Contrafactual accionable: «si además te interesara X, tu segunda ruta pasaría a primera»

---

## Fase 7 — Evaluación defendible

- [ ] Líneas base **obligatorias**: `argmax` (ya existe), clase mayoritaria, y una regla de negocio explícita
- [ ] Sustituir el `train_test_split` único y fijo de
      [`trainer.py:52`](services/ml-service/model/trainer.py#L52) por
      **k-fold estratificado repetido** para el informe de la memoria
- [ ] Reportar **media ± desviación**, nunca el número de una sola partición
- [ ] Informe de calibración (ECE, Brier, diagrama de fiabilidad)
- [ ] Documentar las limitaciones sin adornos

### Lo que NO se puede afirmar con el dataset sintético

Conviene tenerlo escrito antes de redactar la memoria, porque es lo que el
jurado va a preguntar:

- ❌ Que el modelo **prediga bien** la especialización real de un alumno
- ❌ Que el porcentaje de confianza que se le muestra sea **honesto**
- ❌ Que la cobertura conformal **aplique a alumnos reales**
- ❌ Que el aprendizaje automático **supere a la regla trivial** — hoy el `lift_over_baseline` es ≈ 0, y el propio código ya lo dice

**Encuadre recomendado para la tesis:** el pipeline sintético demuestra la
**infraestructura de extremo a extremo**, no que el modelo recomiende bien.
Son dos afirmaciones muy distintas y solo una es defendible hoy. La Fase 2
(anclaje O\*NET/RIASEC) es lo que permite empezar a sostener la segunda.

---

## Agente de cursos 🟡 FUNCIONA — FALTA LA RUTA DE APROBACIÓN

Lo pedido: un agente que viva en el sistema y busque los mejores cursos para
el roadmap de la rama que le sale al alumno. Con dos condiciones expresas:
**en español** y **gratuitos**, sin fuentes que exijan clave ni registro.

### Qué hace y qué no

Recorre los 30 huecos del roadmap (10 ramas × 3 niveles), busca, puntúa,
filtra y deja propuestas en `curso_candidatos`. **No escribe en `courses`.**
Una mala recomendación le cuesta tiempo a un alumno, y un proceso automático
no debería poder causar eso sin que nadie lo revise.

```
docker compose --profile tareas run --rm agente-cursos              # pasada real
docker compose --profile tareas run --rm agente-cursos \
    python -m agente_cursos --simular --ramas 3 6                   # solo mirar
```

En el VPS, una vez al día por cron (la línea está en
[`agente_cursos/__main__.py`](services/ml-service/agente_cursos/__main__.py)).
Cada pasada queda en `agente_cursos_ejecuciones`, y si falla sale con código 1
para que cron avise.

### Dónde corre, y por qué ahí

**No dentro de `ml-service`.** Se intentó y falló la primera pasada real:
`revo_interna` es `internal: true`, sin salida a internet, y el agente no
resolvía ni `api.github.com`. Esa red existe para que un servicio
comprometido no pueda sacar datos de alumnos, así que abrirla no era la
solución.

El agente es además el componente más expuesto del sistema: procesa texto que
escribe cualquiera. Por eso tiene:

- **Su propio contenedor** (`agente-cursos`, perfil `tareas`), el único con
  salida a internet aparte de la pasarela, por la red `revo_salida`.
- **Su propio rol**, `revo_agente`, que solo alcanza sus dos tablas. La
  migración 33 lo comprueba contra **todo** el esquema, no contra una lista
  escrita a mano. Si se viera comprometido, lo peor que podría hacer es
  proponer cursos malos, que es justo lo que la revisión humana frena.
- **Sesión sin contexto RLS.** Antes usaba la de servicio, que da lectura al
  dataset completo de los alumnos. No la necesita.

### La fuente: GitHub, y por qué

| Fuente | Resultado |
|---|---|
| YouTube Data API | Descartada: exige clave y cuenta de Google Cloud |
| UNED Abierta | API abierta, pero ni un curso de las diez ramas |
| MéxicoX, Miriadax, learn.lat, UPM, UC3M | No exponen el catálogo |
| MIT Learn | En inglés y de nivel universitario: alimenta **solo el nivel Experto** (ver más abajo) |
| **GitHub Search API** | Sin clave (10 búsquedas/min), gratuito por definición, y con señales de calidad comprobables: estrellas, archivado, última actividad |

### Cinco condiciones necesarias, no pesos

Un curso que incumple una no es peor: es el equivocado. Ninguna media
ponderada lo compensa, así que son filtros.

| Condición | El caso real que obligó a hacerla filtro |
|---|---|
| Gratuito | «Contenido del Curso de React Avanzado para Platzi»: el repositorio es gratis, las clases no |
| Idioma del escalón | Español en los tres; inglés **solo en Experto**. Como sumando, un curso brasileño quedó **primero** en Infraestructura, con 0,766 |
| Relevante para la rama | «Hello python» salía primero con relevancia 0,08 |
| Material formativo | Buscando «odoo» salieron 17 candidatos: los 17 eran módulos de software |
| Nivel no contradictorio | «Curso de Introducción al Hacking» acabó en el nivel Experto |

### Defectos encontrados al ejecutarlo contra datos reales

Ninguno lo habría detectado una prueba escrita de antemano: salieron de mirar
lo que el agente proponía y de ejecutarlo donde va a vivir. Cada uno tiene
ahora su prueba, con el texto real que lo destapó.

**De calidad:**

- Consultas largas («curso de linux administracion») dejaban Infraestructura y QA **a cero**
- «para» y «desde» contaban como español, pero existen en portugués
- Entró un repositorio en chino: GitHub casa «curso» con «Cursor»
- La relevancia comparaba subcadenas: «ux» está dentro de «linux», «api» dentro de «capítulo»
- **El mismo curso salía en los tres niveles** de una rama: la cobertura aparentaba 27/30
- «avanzada» no contaba como avanzado, solo «avanzado»; «desde cero» no contaba como básico

**De operación:**

- **Fallaba en silencio.** Sin red, cada búsqueda devolvía lista vacía y la
  pasada terminaba «bien», con 0 propuestas y sin error. Una fila así de una
  sesión anterior seguía en la tabla. Ahora «no hay cursos» y «no se pudo
  preguntar» son cosas distintas (`FuenteNoDisponible`), y si ninguna
  consulta llega, la pasada falla y queda registrada
- Un 403 por el cupo de GitHub hacía perder la consulta. Ahora espera lo que
  indican las cabeceras y reintenta una vez
- Una pasada cortada (Docker detenido) dejaba su fila abierta para siempre,
  aparentando estar en curso. Pasó tres veces en un día. Ahora cada pasada
  cierra al empezar las abandonadas

### Cómo se eligieron las consultas

Se midieron 97 consultas y se quedaron, por rama, las tres que dejan pasar
más cursos **distintos** en español. Dos lecciones:

- GitHub no ignora las tildes, así que una palabra que el portugués escribe
  distinto filtra el idioma: «curso java» da 15 de 31 en portugués;
  «curso programación», 31 de 31 en español.
- Por eso «ciberseguridad» o «sistemas operativos» funcionan sin «curso»: no
  existen en portugués. Pasaron de 2 y 0 cursos útiles a 19 y 9.

### Resultado medido (pasada real, 2026-09-21)

| Rama | Fundamentos | Construcción | Experto |
|---|:-:|:-:|:-:|
| 1 · Desarrollo de Software | 3 | 3 | 3 |
| 2 · Data Science & IA | 3 | 3 | 3 |
| 3 · Infraestructura & Cloud | 2 | 3 | **0** |
| 4 · Ciberseguridad | 2 | 3 | 2 |
| 5 · Soporte Técnico & IT Ops | 3 | 3 | **0** |
| 6 · QA & Testing | 1 | 3 | **0** |
| 7 · Gestión y Producto | **0** | 1 | **0** |
| 8 · Diseño UX/UI | 1 | 3 | **0** |
| 9 · Sistemas Empresariales | **0** | **0** | **0** |
| 10 · Investigación e Innovación | 3 | 3 | 3 |

**54 cursos distintos, 21 de 30 huecos con al menos uno, 15 completos.** Todos
gratuitos y en español (o sin marca de idioma, que puntúa menos). Ninguno
propuesto en dos niveles.

Al empezar, la cifra era «27 de 30», pero contaba el mismo curso repetido en
los tres niveles y algún repositorio de Platzi como gratuito. 21 es menos y es
verdad.

Verificado también el ciclo entre pasadas: con un rechazo simulado y una
segunda pasada, el rechazado no reapareció en ningún nivel, y los repositorios
de Platzi y Cod3r que la primera había propuesto pasaron a `retirado`.

### Pendiente

- [ ] Ruta de administración para aprobar `curso_candidatos` → `courses`
- [ ] **Rama 9 (Sistemas Empresariales):** en GitHub no hay material en español; lo de SAP, Odoo o Power BI está en inglés o es software. Necesita otra fuente o curación manual
- [x] **Nivel Experto vacío en cinco ramas (3, 5, 6, 7, 8).** Decisión del autor (2026-09-21): se admite inglés **solo** en ese nivel. El idioma sigue puntuando, así que el inglés rellena y no desplaza al español. Entra el catálogo del MIT, que solo alimenta Experto: en simulación llenó 9 de los 10 huecos de ese nivel (QA sigue sin nada)
- [ ] Calidad desigual del MIT en Experto: *Advanced Algorithms* o *User Interface Design* encajan; «Leadership in Planning» (urbanismo) en Gestión u «Operations Management» (empresa, no TI) en Soporte no. La revisión humana los frena; si se repiten, afinar `TERMINOS_RAMA` de esas ramas
- [ ] **Rama 7 (Gestión y Producto):** un solo curso en toda la rama
- [ ] Programar el cron en el VPS
- [ ] Segunda fuente en español: Wikiversidad responde (237 resultados para «programacion»), sin evaluar todavía
- [ ] Los pesos de `puntuacion.py` son un punto de partida declarado. Ajustarlos con el historial de aprobaciones y rechazos cuando exista

---

## Prueba de carga y tamaño del VPS ✅ MEDIDO (2026-09-21)

Pregunta a responder: **qué VPS mínimo necesita REVO**. No se responde con
latencias sueltas, así que se midió lo que el sistema **consume**: segundos de
CPU de cada contenedor (contador del kernel, `cgroup cpu.stat`), pico de RAM
muestreado, y bytes que deja cada alumno en la base.

El arnés está en [`infraestructura/carga/`](infraestructura/carga/): `aula.py`
(un contenedor por aula, con su propia IP, como un salón detrás de su router)
y `ejecutar_prueba.py` (orquesta y mide). Los informes completos quedan en
`infraestructura/carga/resultados/`.

**Cómo se simuló a los alumnos.** Cada uno hace el recorrido entero: entra
(registro el primer ciclo, inicio de sesión los siguientes), mira su panel y
su historial, contesta las dos fases con respuestas aleatorias, ve el
resultado y los cursos, valora («¿la IA te leyó bien?», el 70 %) y vuelve a
mirar su progreso. Las pausas de lectura y respuesta se comprimieron a 1/5 del
tiempo real: **la prueba es más dura que un aula de verdad**. Se ejecutó sobre
la **pila de producción** (sin recarga automática, 2 workers por servicio) y
una base recién instalada, en un proyecto Docker aparte.

### Lo que cuesta un alumno

| Concepto | Medido |
|---|---|
| CPU por alumno y ciclo (recorrido completo) | **0,75 s** |
| — de eso, cifrado de contraseña (bcrypt coste 12) | 0,27 s |
| — survey-service | 0,17 s · ml-service 0,15 s · PostgreSQL 0,09 s |
| Espacio en la base por alumno y ciclo | **~9 KiB** |
| Peticiones por recorrido completo | ~17 |
| CPU de un reentrenamiento | **5 s** (23 s antes de fijar el hilo único) |
| Espacio de una versión del modelo | ~60 KiB |

### Capacidad medida por tamaño de máquina

Alumnos que **entran a la vez** (llegadas repartidas en 1 minuto, pausas 5×
más rápidas que la realidad). La CPU se limitó con `cpuset` para emular el VPS.

| Máquina | 45 | 135 | 270 | 450 |
|---|---|---|---|---|
| 1 vCPU | ✅ p95 0,54 s | ⚠️ p95 2,74 s | — | — |
| **2 vCPU** | ✅ p95 0,30 s | ✅ **p95 0,34 s** | ❌ 21 fallos, p95 10,8 s | — |
| **4 vCPU** | — | — | ✅ **p95 0,52 s** | ❌ 49 fallos, p95 14,8 s |
| 16 hilos (la máquina de desarrollo) | ✅ 0,22 s | ✅ 0,31 s | ✅ 0,63 s | ✅ p95 1,59 s |

**Dónde se rompe:** siempre en la **entrada**, nunca en el modelo. Cuando
falla, el test sigue respondiendo en 0,25 s y la predicción en 0,5 s; lo que
se atasca es el cifrado de contraseñas (270 ms de CPU cada una, a propósito,
para resistir fuerza bruta). El límite práctico es **entradas por minuto**:
~135 con 2 vCPU y ~270 con 4 vCPU.

### Con tiempos REALES, 2 vCPU sobran

La tabla anterior comprime las pausas a 1/5 y concentra las llegadas en un
minuto: es una prueba de estrés, no un aula. Repetida con **tiempos reales**
(fase 1 de ~1 min, fase 2 de ~1,5, llegadas repartidas en 5 minutos) sobre un
VPS emulado de **2 vCPU y 1,8 GB de límite de memoria**:

| Alumnos a la vez | Completos | p95 | Predicción p95 | CPU media | RAM pico |
|---|---|---|---|---|---|
| 270 (6 aulas) | **270/270** | 0,231 s | 0,123 s | **0,35 núcleos** | 882 MiB |
| 450 (10 aulas) | **450/450** | 0,238 s | 0,165 s | **0,54 núcleos** | 894 MiB |

Cero errores, cero contenedores muertos por memoria, y ninguno pasó del 65 %
de su límite. Los mismos 270 alumnos que **tumbaban** esta máquina con los
tiempos comprimidos (21 fallos, p95 de 10,8 s) la dejan al 17 % de CPU cuando
llegan al ritmo de un aula de verdad.

**Conclusión:** lo que dimensiona el servidor no es cuántos alumnos hay
conectados, sino **cuántos entran en el mismo minuto**.

### Ciclos: el progreso del alumno no degrada nada

270 alumnos repitiendo el test en los ciclos 2, 3 y 4, con su historial cada
vez más largo: p95 de 0,35 s, 0,29 s y 0,29 s. **1.890 recorridos completos
sin un solo error.** Un alumno que vuelve ocupa menos (6–8 KiB) que uno nuevo
(10 KiB): ya no crea cuenta ni consentimientos.

### Memoria y disco

| | Medido |
|---|---|
| RAM en reposo, todo levantado | **685 MiB** (ml 279, survey 166, auth 156, Postgres 46, nginx 33, Redis 3) |
| RAM pico con 450 alumnos | **~1,0 GiB** |
| Imágenes Docker | ~1,9 GB (ml 718 MB, Postgres+pgvector 420, survey 341, auth 338, nginx 74, Redis 56) |
| Base de datos | ~12 MiB recién instalada, +9 KiB por alumno-ciclo |
| Logs | ~170 B por petición, y ~200 MB/año solo de comprobaciones de salud |

**Proyección de la base** (2 ciclos al año, un test por ciclo):

| Alumnos | Al año | A 5 años |
|---|---|---|
| 500 | 9 MB | 45 MB |
| 1.000 | 18 MB | 90 MB |
| 2.000 | 36 MB | 180 MB |
| 3.000 | 54 MB | 270 MB |

Ni con 3.000 alumnos durante cinco años la base llega a 1 GB contando índices
y sobrecarga. **El disco lo ocupa el sistema y las imágenes, no los datos.**

### Recomendación

| | Mínimo | Recomendado |
|---|---|---|
| vCPU | 2 | **4** |
| RAM | 2 GB (+2 GB de swap) | **4 GB** |
| Disco | 25 GB SSD | **40 GB SSD** |
| Aguanta | ~135 alumnos entrando en el mismo minuto | ~270 en el mismo minuto |

Con 2 vCPU y 2 GB el sistema atiende **450 alumnos a ritmo real** (10 aulas
empezando en la misma franja de cinco minutos) con 0,24 s de percentil 95 y el
27 % de la CPU. Se recomiendan 4 vCPU y 4 GB para el caso que sí lo aprieta:
una matrícula masiva donde cientos de alumnos se registran en el **mismo
minuto**, y para dejar sitio a lo que no es tráfico de alumnos —
reentrenamientos, copias de seguridad, el agente de cursos y las
actualizaciones del sistema.

**Construir las imágenes en el VPS** pide más RAM y disco temporal que
ejecutarlas. Con 2 GB conviene construirlas fuera y subirlas, o añadir swap.

### Defectos que encontró la prueba (todos corregidos)

1. **Tormenta de reentrenamientos.** Cada predicción programaba una
   comprobación en segundo plano y, superadas las 50 nuevas, **todas** las
   siguientes arrancaban su propio entrenamiento. Con 135 alumnos: 12
   entrenamientos a la vez, CPU por alumno de 0,8 → 4,2 s, predicción a 8,9 s.
   Con 270: solo 129 de 270 terminaron, con errores 504. Ahora hay un cerrojo
   de proceso y otro de PostgreSQL (`pg_try_advisory_lock`).
2. **Hilos numéricos.** OpenBLAS abría un hilo por núcleo para matrices
   diminutas: 23 s de CPU por reentrenamiento en vez de 5 s, y peor bajo
   carga. Fijado a un hilo en el `Dockerfile` de ml-service.
3. **La realimentación del alumno nunca se guardaba.** Cada «¿la IA te leyó
   bien?» devolvía 503: el ORM insertaba con `RETURNING id`, y `RETURNING`
   exige poder LEER la fila, cosa que la política del dataset niega a los
   alumnos con razón. **El bucle de realimentación (`human`,
   `human_corrected`) no había recibido ni un dato.** Corregido con un INSERT
   sin `RETURNING`; en la prueba entraron 856 muestras reales.
4. **Modelo viejo en la imagen.** `model/saved/decision_tree.pkl` viajaba
   dentro y, con el volumen vacío, una instalación nueva lo adoptaba como
   «v0-heredada»: sin calibrar, sin conjunto conformal y sin umbral de
   vecindario. Excluido en `.dockerignore`; ahora el arranque entrena el
   modelo actual.
5. **Modelo desactualizado en el segundo worker.** La caché era
   `lru_cache(maxsize=1)` y solo la limpiaba el proceso que entrenaba: el otro
   siguió sirviendo un modelo retirado durante más de dos minutos y varias
   promociones. Ahora la caché va por versión y lee el puntero compartido.
6. **Logs sin rotación.** `json-file` sin límite crece hasta llenar el disco.
   Ahora 3 ficheros de 10 MB por contenedor.

### Pendiente

- [ ] **Límites por IP si el campus sale por una sola IP pública:** 80 altas
      cada 10 minutos, 250 al día y 400 inicios de sesión por hora se
      aplicarían a TODA la universidad. Con NAT de campus hay que subirlos o
      exceptuar el rango de la universidad
- [ ] Los dos workers de ml-service entrenan **cada uno** su primer modelo al
      arrancar en una instalación nueva (inofensivo, segundos de CPU)
- [ ] Copias de seguridad: `pg_dump` diario comprimido, unos pocos MB

---

## Por dónde empezar

El orden importa, porque hay dependencias duras:

1. **Fase 1.a** — sin versionado de artefactos no hay dónde guardar una
   calibración, y sin `model_version` real no se puede medir nada. Bloquea
   las Fases 5 y 7 enteras.
2. **Fase 3.g etapa sombra** — se puede montar en paralelo a todo lo demás y
   empieza a acumular evidencia desde el primer alumno. Cuanto antes arranque,
   mejor capítulo de resultados.
3. **Fase 2 + 2.bis** — la más larga y la que más cambia la tesis. No depende
   de las anteriores, así que puede ir en paralelo. Y **2.bis puede empezar
   hoy mismo**: reescribir ítems no necesita que nada esté construido.
4. El resto en orden.

**Riesgo de calendario:** las Fases 2, 2.bis, 3 y 5 son cada una un trabajo
sustancial. Si el plazo aprieta, las dos que **no** se pueden recortar son la
**2** (anclaje externo) y la **2.bis** (banco de ítems), porque sin ellas las
demás pulen un modelo que sigue siendo un espejo. Un motor adaptativo
precioso sobre una etiqueta circular y un banco que no discrimina sigue
siendo circular y sin discriminar.

**Y si hubiera que elegir una sola cosa:** la 2.bis. Es la más barata, no
depende de nada, y sin ella ninguna de las otras puede funcionar.

---

## Registro de decisiones

| Fecha | Decisión | Motivo |
|---|---|---|
| 2026-09-20 | El motor adaptativo se ejecuta en `survey-service`, no en `ml-service` | Una llamada HTTP por pregunta más el arranque en frío de Render daría 30–60 s por pregunta |
| 2026-09-20 | `ml-service` publica un tensor de log-verosimilitudes, no sus parámetros | `survey` no contiene modelado psicométrico: solo aritmética. El modelo sigue siendo de `ml` |
| 2026-09-20 | La fase 2 deja de restringirse al top-3 de la fase 1 | Esa restricción era la causa de que las afinidades fueran circulares |
| 2026-09-20 | Selección *randomesque* top-3 en vez de argmax puro | Un motor voraz produce un dataset degenerado del que no se puede recalibrar nada |
| 2026-09-20 | El criterio de parada mira el margen 3.º–4.º, no 1.º–2.º | El producto entrega un top-3: la frontera que importa es la del puesto 3 |
| 2026-09-20 | `S` (similitud entre ramas) se fija por juicio experto y **no** se aprende | Con n≈200 y 10 clases el modelo completo no es identificable |
| 2026-09-20 | Despliegue con etapa sombra antes de tocar el flujo del alumno | Permite comparar adaptativo contra aleatorio sobre los mismos alumnos, sin arriesgar la recolección |
| 2026-09-20 | RIASEC y Big Five se **adoptan** (Mini-IP, Mini-IPIP), no se escriben | Son gratis, validados y citables. El trabajo propio es el mapeo a las 10 ramas, no reinventar instrumentos |
| 2026-09-20 | El banco de dominio se reescribe como **actividades**, no como autoevaluación de competencia | La autoevaluación arrastra sesgo de confianza con diferencias por género: es un problema de equidad en un recomendador de carrera |
| 2026-09-20 | Se añaden ítems de **elección forzada** entre ramas confundibles | Eliminan aquiescencia y deseabilidad social, y dan evidencia directa sobre la frontera que el motor quiere resolver |
| 2026-09-20 | El diagnóstico del banco **no** es el α de Cronbach | Con ítems de plantilla el α sale inflado por redundancia (paradoja de la atenuación). El diagnóstico es la correlación cruzada entre ramas |
| 2026-09-21 | La regla «sin lift no se despliega» **avisa** por defecto, no bloquea | Con el dataset circular el lift era ~0 siempre: bloquear dejaría al servicio sin ningún modelo y a los alumnos sin resultado. Se vuelve bloqueante con `EXIGIR_LIFT_POSITIVO` cuando el dataset deje de serlo |
| 2026-09-21 | El perfil de fase 3 en el modelo queda **apagado** aunque esté implementado | Entrenar con esas columnas solo tiene sentido si en inferencia también llegan, y `survey-service` aún no las envía. Encenderlo antes daría un modelo que recibe relleno neutro en 4 de sus 14 entradas |
| 2026-09-21 | APS conformal **aleatorizado** | Sin aleatorizar sobre-cubría: 100 % real frente al 90 % nominal, con conjuntos de 3,06 ramas. Aleatorizado da 98 % con 2,04, y un 25 % de conjuntos de una sola rama en vez de un 1,75 % |
| 2026-09-21 | El catálogo de empleos se retira **entero** | La migración 20 eliminó la tabla pero el modelo ORM, el router y el helper del frontend seguían vivos. Lo detectaron las pruebas de integración contra la base real |
| 2026-09-21 | Se retira la tolerancia al **arranque en frío** del frontend | El despliegue pasa a un VPS: los servicios no se duermen. Se quitan el cartel «Despertando el servidor», los 3 pings de precalentamiento por carga y los 3 reintentos de 4/8/15 s. Queda **un** reintento de 1,2 s para la ventana en que nginx da 502 al reiniciar un contenedor |
| 2026-09-21 | ~~**No** se habilita pgvector todavía~~ (revertida el mismo día, ver la fila de pgvector más abajo) | Hoy no hay nada que guardar dentro: sería una columna vacía más un cambio de imagen de Postgres sobre un volumen con datos. Entra con la Fase 2, cuando llegue O\*NET. Ver «Sobre la base de datos vectorial» |
| 2026-09-21 | La matriz `S` **no** se deriva con TF-IDF | Probado y medido: ~50 % de aciertos y todo el rango entre 0,042 y 0,124. Sin separación, habría que reescalar a mano, que es peor que el criterio explícito que ya hay |
| 2026-09-21 | La matriz `S` **sí** se deriva de los perfiles RIASEC de O\*NET | Es lo que TF-IDF no podía dar: RIASEC mide **cómo es el trabajo**, no qué palabras usa. Confirmó los bloques hechos a mano y corrigió dos. `BLOQUES` y `SIMILITUD_EN_BLOQUE = 0.72` se retiran del generador |
| 2026-09-21 | El mapeo rama → ocupaciones SOC es **juicio experto y está escrito** | No se deriva de ningún cálculo. Se deja en una constante legible en `mapeo_ramas_onet.py` porque es lo que hay que defender en la sustentación, y tenerlo a la vista es parte de poder defenderlo. Los **números** (los perfiles) sí son objetivos: los mide O\*NET |
| 2026-09-21 | Varias ocupaciones por rama, no una | Con una sola, el perfil de la rama depende de la idiosincrasia de ese puesto concreto |
| 2026-09-21 | Los ítems se guardan **en inglés y en español** en la misma fila | La traducción no está revalidada. Tener el original al lado hace que cualquiera pueda comprobar la fidelidad, y pone la limitación en los datos y no solo en una nota a pie de página |
| 2026-09-21 | El encaje se mide con **correlación de Pearson**, no distancia | Los perfiles van en escalas distintas (0–20 y 1–7). La correlación compara la forma, no el nivel, y de paso neutraliza la aquiescencia |
| 2026-09-21 | El desequilibrio de Apertura en el Mini-IPIP **no se corrige** | Es así en el instrumento publicado. Añadir un ítem rompería la comparabilidad con la literatura, que es lo único que justifica no inventarse las preguntas |
| 2026-09-20 | Conservar `email_verification_codes`, `password_reset_tokens` y sus funciones | Se van a conectar los endpoints; no son código muerto sino infraestructura a la espera |
| 2026-09-20 | Conservar `specializations.description` y `career_paths` | No están vacías: están duplicadas en el frontend. Se arregla haciendo que el front las lea, no borrando el original |
| 2026-09-20 | Conservar la vista `user_consent_state` | Única expresión del consentimiento vigente; la Ley 29733 obliga a poder responder esa pregunta |
| 2026-09-20 | `duration_seconds` se rellena en SQL y no en Python | Para que ambas marcas de tiempo salgan del mismo reloj |
| 2026-09-20 | No sobrescribir `README.md` | Es la presentación pública del proyecto. Este documento es el de trabajo |
| 2026-09-21 | El agente de cursos **propone**, no publica | Escribe en `curso_candidatos`; un administrador aprueba. Una mala recomendación le cuesta tiempo a un alumno, y un proceso automático no debe poder causar eso sin revisión |
| 2026-09-21 | Única fuente activa: **GitHub**. YouTube se descarta | Condición expresa: gratuito, en español y sin clave ni registro. YouTube exige cuenta de Google Cloud. GitHub responde sin clave y trae señales de calidad comprobables |
| 2026-09-21 | Gratuito, español, relevancia, material formativo y nivel son **filtros**, no pesos | Cada uno se volvió filtro por un caso real en el que la media ponderada dejaba pasar el curso equivocado, a veces en primer puesto |
| 2026-09-21 | El agente corre en **su propio contenedor y con su propio rol** (`revo_agente`) | `revo_interna` no tiene internet a propósito. El agente procesa texto de cualquiera: con las credenciales de `revo_ml` tendría a la vez datos de alumnos y salida para sacarlos |
| 2026-09-21 | «No hay cursos» y «no se pudo preguntar» son cosas distintas | Sin red, la pasada terminaba «bien» con 0 propuestas y sin error. Ahora falla, queda registrada y cron avisa |
| 2026-09-21 | Lo que el agente deja de proponer se **retira**, no se borra ni se acumula | La cola del administrador refleja la última pasada; un curso no queda propuesto en dos niveles; lo que un humano decidió no se vuelve a proponer |
| 2026-09-21 | **Se habilita pgvector**, solo en columnas que ya eran vectores | Decisión del autor. Se hace en la forma defendible: perfiles RIASEC (6) y afinidades (10), sin modelo de embeddings. Pearson calculado como coseno de perfiles centrados. Dos usos reales: vecindario (incertidumbre epistémica) y ocupaciones afines de O\*NET |
| 2026-09-21 | La predicción se **guarda completa** (`predictions.detalle`) y no se recalcula al leer | El `GET` que usa la pantalla perdía calibración, incertidumbre y conjunto conformal. Recalcular daría otro resultado tras cada reentrenamiento |
| 2026-09-21 | El vecindario **entra en la lectura** de incertidumbre y en el mensaje | El desacuerdo entre 30 regresiones logísticas no detecta perfiles lejanos: lejos de las fronteras todas coinciden. Caso real: 99,9 % de confianza a 0,79 de los vecinos con umbral 0,60 |
| 2026-09-21 | Imagen propia de Postgres (Alpine + pgvector compilado), no la oficial de pgvector | La base usa `en_US.utf8` sobre musl. La oficial es Debian (glibc): el mismo nombre de collation ordena distinto y los índices de texto quedarían inconsistentes sin dar error |
| 2026-09-21 | El agente admite **inglés solo en el nivel Experto** | Decisión del autor. El material avanzado gratuito está casi todo en inglés y cinco ramas no tenían nada en ese nivel. En Fundamentos y Construcción no: quien empieza necesita entender sin traducir |
| 2026-09-21 | Los instaladores de Supabase van en `database/supabase/` | Docker ejecuta todo `.sql` de `database/`: con ellos ahí, una instalación limpia abortaba después de aplicar bien las 38 migraciones |
| 2026-09-21 | Toda migración numerada es **reaplicable** sin tocar datos de alumnos | Es lo que permite actualizar una base existente con un solo script. La 25 (dataset) es la única excepción declarada: empieza con `TRUNCATE` |
| 2026-09-21 | Un solo reentrenamiento a la vez, y con **un hilo numérico** | Medido: sin cerrojo, 12 entrenamientos en paralelo tumbaban el servicio (504 y 129 de 270 alumnos). Con 16 hilos, un reentrenamiento costaba 23 s de CPU en vez de 5 |
| 2026-09-21 | El VPS mínimo es **2 vCPU / 2 GB**; el recomendado, **4 vCPU / 4 GB** | Medido emulando cada tamaño: 2 vCPU aguanta 135 alumnos entrando en el mismo minuto con p95 de 0,34 s; 4 vCPU aguanta 270 con 0,52 s. El disco lo ocupan las imágenes, no los datos (9 KiB por alumno-ciclo) |
| 2026-09-21 | Los `.sh` de `database/` van en **LF** | `16_asignar_passwords.sh` estaba en CRLF y abortaba la inicialización de Postgres (`set: pipefail: invalid option name`). `database/` está fuera de git, así que `core.autocrlf` no lo normaliza |
