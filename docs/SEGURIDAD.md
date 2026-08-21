# Modelo de seguridad de REVO

Este documento explica **contra que** protege cada capa y **por que** esta
donde esta. No es una lista de buenas practicas: es el mapa de las decisiones
que se tomaron y de lo que pasaria si se quitaran.

---

## 1. Capas, de fuera hacia dentro

```
Internet
   │
   ▼
[ Cloudflare / TLS ]          volumetrico, DDoS de capa 3-4
   │
   ▼
[ Pasarela Nginx ]            freno grueso por IP, Slowloris, tamano de cuerpo,
   │                          cierre de /docs, cabeceras de seguridad
   ▼
[ Middlewares del servicio ]  secreto de pasarela, limite de cuerpo, CORS estricto
   │
   ▼
[ Verificacion del token ]    firma, emisor, audiencia, proposito, rol
   │
   ▼
[ Rate limit con Redis ]      cupo por ALUMNO, no por IP
   │
   ▼
[ Validacion Pydantic ]       tipos, longitudes, rangos, listas cerradas
   │
   ▼
[ Logica del endpoint ]       filtros WHERE user_id
   │
   ▼
[ RLS de PostgreSQL ]         la ultima palabra: la fila no sale de la base
```

La propiedad que importa: **si una capa falla, la siguiente sigue en pie**.
Un endpoint al que se le olvide el `WHERE user_id` no filtra datos, porque
RLS no devuelve las filas. Un puerto que quede publicado por error no da
acceso, porque falta el secreto de pasarela.

---

## 2. Ninguna API expuesta

**Como se consigue**

1. En el compose, los servicios no declaran `ports`. Solo la pasarela publica
   uno. Los servicios viven en una red marcada `internal: true`, que ademas
   les niega la salida a internet.
2. `PasarelaMiddleware` exige la cabecera `X-Revo-Gateway` con un secreto
   compartido, comparado con `hmac.compare_digest` (tiempo constante).
3. `/docs`, `/redoc` y `/openapi.json` no se generan cuando
   `ENVIRONMENT=production`, y ademas la pasarela devuelve 404 para esas
   rutas venga de donde venga.

**Por que la segunda capa** — El aislamiento por red se rompe con un `ports:`
que alguien reanade para depurar y se olvida de quitar. Ha pasado en todos
los proyectos. El secreto convierte ese descuido en un 403 en vez de en una
fuga.

**Verificado en** `infraestructura/verificar_despliegue.sh`, seccion
"Superficie expuesta" (7 comprobaciones).

---

## 3. Aislamiento entre alumnos (RLS)

**El problema original** — Los tres servicios se conectaban como duenos de la
base de datos. Cualquier fallo de logica (un `WHERE` olvidado, un id que
llega por la URL sin comprobar) exponia las filas de cualquier alumno.

**La solucion**

- Dos roles de conexion sin privilegios: `revo_app` para peticiones,
  `revo_service` para tareas de fondo. **Ninguno es dueno de las tablas**, asi
  que las politicas les aplican.
- `FORCE ROW LEVEL SECURITY` en todas las tablas con datos de alumnos: la
  politica aplica incluso al dueno.
- La identidad viaja a la base con
  `SELECT set_config('revo.user_id', :user_id, true)` — funcion con parametros
  ligados, no concatenacion de texto. El tercer argumento en `true` hace el
  valor local a la transaccion: sin eso, la siguiente peticion que reciba esa
  conexion del pool heredaria la identidad de la anterior.
- El contexto se reaplica en **cada** transaccion mediante el evento
  `after_begin` de SQLAlchemy. Un `commit()` a mitad de peticion abre una
  transaccion nueva; sin reaplicar, las consultas siguientes correrian sin
  identidad.

**Dos operaciones no tienen identidad todavia** y se resuelven con funciones
acotadas `SECURITY DEFINER`, no abriendo las tablas:

| Operacion | Funcion | Que garantiza |
|---|---|---|
| Login | `revo_credenciales_por_email` | Una fila, por email exacto, solo las columnas para autenticar. No acepta comodines. |
| Registro | `revo_crear_alumno` | El rol queda fijado a `student` dentro de la funcion: crear un administrador desde el registro es imposible por construccion. |

Ambas fijan `search_path` explicitamente. Sin eso, un esquema controlado por
el atacante que este antes en el path puede suplantar a las tablas que la
funcion nombra.

**Verificado en** `database/pruebas/verificar_rls.sql` — 20 comprobaciones
contra un Postgres real, incluida la lectura de la sesion ajena por id
directo.

---

## 4. Rate limit: el caso del aula

**El requisito** — 50 alumnos de un salon comparten una sola IP publica. Un
limite por IP haria que el alumno 11 recibiera 429 y el examen se cayera para
toda la clase.

**La regla que lo resuelve** — Cuando hay alumno identificado, se cuenta **por
alumno**. La IP solo se usa cuando no hay token.

| Ruta | Cupo | Contra que |
|---|---|---|
| `answers` | 120 / min por alumno | Cubre las 25 respuestas mas guardado masivo y reintentos |
| `submit_phase`, `predict` | 20 / 5 min por alumno | Operaciones caras |
| `read` | 240 / min por alumno | Lecturas de catalogo |
| `login` | 8 / 15 min **por cuenta atacada** | Fuerza bruta. Contar por IP castigaria al aula |
| `register` | 60 / hora por IP | Aun no hay identidad. El techo cubre un aula registrandose el primer dia |
| `admin` | 120 / min, **fail-closed** | Poco trafico, mucho valor |
| `global` | 1200 / min por IP | Techo anti-flood. Un aula normal ni se acerca |

**Ventana deslizante y no ventana fija** — Con ventana fija, un alumno gasta
el cupo al final de un minuto y otra vez al principio del siguiente, doblando
el pico real justo cuando toda el aula envia a la vez.

**Un rechazo no consume cupo** — Si contara, un cliente en bucle mantendria la
ventana llena para siempre y el alumno legitimo nunca saldria del bloqueo.

**Si Redis cae** — Las rutas de juego siguen sirviendo con un respaldo local
por worker (`fail_open`), porque tumbar la clase por un fallo de
infraestructura es peor que aflojar el limite un rato. Las rutas de
administracion se cierran (`fail_open=False`). El respaldo local sigue
frenando un flood, con un techo relajado.

**Verificado en** `pruebas/test_contador_limite.py` (aula de 50 alumnos) y en
`verificar_despliegue.sh` (fuerza bruta real contra la pila levantada).

---

## 5. Anti-DDoS

| Ataque | Donde se para |
|---|---|
| Flood volumetrico (capa 3-4) | Cloudflare. Ningun servidor propio absorbe esto |
| Flood HTTP por IP | `limit_req_zone` de Nginx: 30 r/s con rafaga de 60 |
| Muchas conexiones por IP | `limit_conn` de Nginx: 100 simultaneas |
| Slowloris (clientes lentos) | `client_body_timeout` y `client_header_timeout` a 10 s |
| Cuerpo gigante | 256 KB en Nginx y otra vez en el middleware del servicio |
| Consulta que no termina | `statement_timeout` de 10 s en Postgres |
| Transaccion abierta y olvidada | `idle_in_transaction_session_timeout` de 30 s |
| Pool de conexiones agotado | Tamano acotado, `pool_recycle` de 240 s, `pool_pre_ping` |

Los dos timeouts de Postgres son limites del **servidor**: cortan la consulta
y liberan la conexion aunque el proceso de Python siga esperando. Es la
diferencia entre una consulta lenta y un servicio caido.

---

## 6. Inyeccion

| Vector | Defensa |
|---|---|
| SQL en filtros | ORM con parametros ligados. El `text()` que queda usa `:parametro`, nunca formato de cadena |
| SQL via contexto RLS | `set_config(...)` con parametros; ademas `ContextoSeguridad` fuerza el id a entero antes de salir de Python |
| Parametros de ruta | Validados con `Path(ge=..., le=...)` y listas cerradas (categorias, tipos de documento) antes de tocar la base |
| Escalada de rol | El rol se fija dentro de `revo_crear_alumno`; el schema de perfil no acepta `role` ni `is_active` |
| XSS en documentos legales | El markdown se convierte a elementos de React, no con `dangerouslySetInnerHTML` |
| XSS via avatar | Solo se aceptan URLs `http://` o `https://`: `javascript:` y `data:` se rechazan |
| Inyeccion de formulas en CSV | `csv.writer` para escapar, y prefijo defensivo en valores que empiezan por `= + - @` |
| Falsificacion de IP | `X-Forwarded-For` solo se lee si hay proxies declarados, y se toman los **ultimos** saltos |

---

## 7. Tokens

- `HS256` con lista fija de algoritmos. Pasar el algoritmo del propio token a
  la verificacion permite elegir `none` y firmar cualquier cosa.
- Se verifican `iss`, `aud` y `typ`. Sin ellos, un token de cualquier otro
  sistema que comparta secreto vale aqui, y un token emitido para otro
  proposito (reset de password) sirve para llamar a la API.
- `sub` debe ser un entero positivo: es lo que acaba en un `WHERE user_id`.
- El rol se valida contra una lista cerrada aunque venga firmado.
- `jti` unico por token, para poder revocar uno concreto en el futuro.
- El secreto debe tener 32 caracteres como minimo y se rechazan los valores de
  ejemplo conocidos. La comprobacion corre **al arrancar**, no en la primera
  peticion.
- Las llamadas entre servicios usan un token propio de **60 segundos**. Si
  acaba en un log, deja de servir casi de inmediato; el del alumno duraria 24
  horas.

---

## 8. Contrasenas

- `bcrypt` con coste 12, usado directamente. Se quito `passlib` porque su
  ultima version es de 2020 y no arranca con `bcrypt >= 4.1`, lo que obligaba
  a congelar en `bcrypt==4.0.1` — es decir, a renunciar a las correcciones de
  seguridad de la libreria que guarda las contrasenas.
- Minimo 10 caracteres, no puede ser solo numeros ni solo letras, no puede
  estar en la lista de las mas comunes, no puede ser igual al correo.
- El login responde **igual** exista o no la cuenta, y verifica contra un hash
  de descarte cuando no existe, para que el tiempo de respuesta no delate que
  correos estan registrados.

---

## 9. Lo que queda pendiente

Honestidad sobre los limites de lo hecho:

1. **El token vive en `sessionStorage`**, legible por JavaScript. Se eligio
   frente a `localStorage` porque los alumnos usan equipos compartidos y la
   sesion debe morir al cerrar la pestana. Lo correcto frente a XSS es una
   cookie `httpOnly`, que exige que frontend y API compartan dominio y anadir
   proteccion CSRF. Es el siguiente paso.
2. **No hay revocacion de tokens.** Hay `jti`, pero no lista de revocados. Un
   token robado sirve hasta que caduca (24 h). Se resuelve con un conjunto en
   Redis consultado en la verificacion.
3. **El registro revela si un correo existe.** Es inherente a un formulario de
   alta sin verificacion por correo. El cupo de registro (60/hora/IP) limita
   la enumeracion masiva, pero no la elimina.
4. **No hay verificacion de correo ni recuperacion de contrasena.** El enlace
   "¿La olvidaste?" del login no hace nada.
5. **No hay 2FA para administradores.** La cuenta con mas poder del sistema se
   protege solo con contrasena.
6. **Los textos legales son un borrador tecnico** y necesitan revision de un
   abogado antes de vender datos.
7. **Los cuatro problemas de certeza del modelo** siguen abiertos por decision
   explicita de alcance: la Fase 3 no se persiste, hay desempates aleatorios,
   el bucle de retroalimentacion se autoconfirma y el modelo no supera a una
   regla `argmax`. Nada de eso es un problema de seguridad, pero si de calidad
   del producto.

---

## 10. Como comprobar que todo esto sigue siendo cierto

```bash
bash database/pruebas/verificar_rls.sh              # 20 comprobaciones de aislamiento
cd services/comun && pytest                         # libreria compartida
PUERTO=8080 bash infraestructura/verificar_despliegue.sh   # 40 comprobaciones sobre la pila viva
```

Estas comprobaciones no son documentacion: se ejecutan. Si alguna falla, la
propiedad que describe este documento ha dejado de cumplirse.
