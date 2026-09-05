# Informe de pruebas del frontend

Resultado de la bateria de Playwright sobre `frontend/`. La bateria y como
ejecutarla estan descritas en [`frontend/pruebas/README.md`](../frontend/pruebas/README.md).

**Linea base: 276 pruebas, 248 pasaban y 28 fallaban**, correspondientes a
15 defectos distintos (algunos se repiten en escritorio y en movil). Ninguno
era un fallo de la propia bateria: cada prueba en rojo describia algo que la
aplicacion no hacia y deberia hacer.

**Estado al 4 sep. 2026: los quince defectos estan corregidos y la bateria
pasa entera — 321 de 321.** La bateria crecio de 276 a 321 casos: la matriz
responsiva cubre ahora diez anchos (320 a 1920 px) y se anadieron una prueba
de seis clientes concurrentes y la carga diferida por ruta.

Cada apartado conserva el diagnostico original, porque explica por que
fallaba, y termina con la linea **Corregido** que dice como se cerro. El
recorrido hasta el verde fue 28 -> 22 -> 4 -> 1 -> 0 fallos.

Dos apuntes de honestidad sobre ese recorrido:

- **Dos de los fallos los introdujo la propia correccion.** Reordenar las
  pantallas del cuestionario dejo el aviso de conexion duplicado, y el limite
  de error se puso con `key={pathname}`, que remonta el arbol entero en cada
  navegacion y devolvia la pantalla a su hueco de carga. Los dos estan
  corregidos y anotados donde corresponde.
- **Tres correcciones fueron a la bateria y no a la aplicacion**, porque el
  defecto estaba ahi: `esperarEstable` medía el hueco de carga de las rutas
  diferidas en vez de la pantalla; la sonda de texto recortado marcaba el
  texto reservado a lectores de pantalla, que esta recortado a proposito; y
  `iniciarSesion` sembraba el token en cada carga de documento, lo que hacia
  imposible de cumplir la ultima afirmacion de la prueba de cierre de sesion.
  Las tres estan explicadas en su apartado.

---

## Criticos

### 1. Una respuesta malformada del historial deja la aplicacion en blanco

**Prueba:** `resiliencia.spec.js > Respuestas malformadas > un JSON invalido no tumba la pantalla`
**Fichero:** [`src/pages/Dashboard.jsx:21`](../frontend/src/pages/Dashboard.jsx#L21), [`src/theme/specs.js:67`](../frontend/src/theme/specs.js#L67)

Si `GET /predict/user/{id}/history` responde 200 con un cuerpo que no es JSON
valido, axios devuelve el texto crudo. `setHistorial(response.data || [])`
acepta esa cadena porque es un valor verdadero, y despues
`calcularScore` hace `historial.reduce(...)` sobre ella:

```
TypeError: historial.reduce is not a function
  > calcularScore  src/theme/specs.js:67
  > Dashboard      src/pages/Dashboard.jsx:28
```

Como **la aplicacion no tiene ningun error boundary**, React desmonta el
arbol entero. El `<div id="root">` se queda con cadena vacia: desaparece
tambien la barra de navegacion, asi que el alumno no tiene ni un enlace desde
el que salir. La unica salida es recargar a mano.

Son dos arreglos independientes, y conviene hacer los dos:

- Validar la forma, no solo la existencia:
  `setHistorial(Array.isArray(response.data) ? response.data : [])`.
  El mismo patron `?? []` / `|| []` se repite en
  [`History.jsx:90`](../frontend/src/pages/History.jsx#L90).
- Envolver las rutas en un error boundary que deje la barra en pie y ofrezca
  recargar. Sin el, cualquier error de pintado futuro tiene esta misma
  consecuencia.

**Corregido.** Las dos cosas. `Dashboard.jsx` e `History.jsx` comprueban
`Array.isArray(response.data)` en vez de la mera existencia, y las rutas van
envueltas en `components/LimiteDeError.jsx`, que deja la barra en pie y
ofrece recargar o irse al panel.

### 2. Tras un 401 la sesion sigue viva en memoria

**Prueba:** `resiliencia.spec.js > Sesion caducada a mitad de uso > tras el 401, la siguiente navegacion pide entrar de nuevo`
**Fichero:** [`src/services/api.js:55`](../frontend/src/services/api.js#L55), [`src/context/AuthContext.jsx`](../frontend/src/context/AuthContext.jsx)

El interceptor de respuesta borra el token cuando llega un 401, pero nadie
avisa a `AuthContext`, que conserva el objeto `user`. Comprobado:

```
TOKEN = null | URL TRAS NAVEGAR = /history
TEXTO = ... | Dashboard | Cuestionario | Historial | A | Ana | Salir | ...
```

El alumno navega por el panel y el historial como si tuviera sesion, con la
barra mostrando su nombre, mientras **todas** las peticiones responden 401 y
cada pantalla se cae a su estado vacio. Parece que no tiene datos, no que su
sesion caduco. Solo al recargar la pagina se le manda al login.

`borrarToken()` en el interceptor tiene que arrastrar tambien el estado de
sesion: exponer un `cerrarSesion()` desde el contexto y llamarlo ahi, o
disparar un evento que `AuthProvider` escuche.

---

**Corregido.** El interceptor de `services/api.js` emite
`revo:sesion-caducada` al borrar el token, y `AuthProvider` lo escucha para
poner el usuario a null. La siguiente navegacion ya pide entrar de nuevo.

## Altos

### 3. El cuestionario deja al alumno encallado si falla la preparacion

**Pruebas:** `cuestionario.spec.js > Cuando el servidor falla` (los tres casos)
**Fichero:** [`src/pages/Questionnaire.jsx`](../frontend/src/pages/Questionnaire.jsx), [`src/pages/questionnaireMiniGames.js:32`](../frontend/src/pages/questionnaireMiniGames.js#L32)

`resolveQuestionnaireEntryView` decide que pantalla se pinta:

```js
if (stage === 'selecting' || !miniGame) return 'selector'
if (stage === 'selected' || loading)    return 'selected'
if (!hasQuestion)                       return 'error'   // inalcanzable
```

A `stage === 'playing'` solo se llega pulsando **Jugar**, y ese boton esta
deshabilitado justo cuando hay error. La pantalla de error
("No pudimos repartir las cartas. Revisa tu conexion y vuelve a cargar la
pagina") esta escrita, traducida y maquetada, y **no se puede alcanzar
nunca**.

Lo que el alumno ve en cada caso:

| Situacion | Pantalla real | Problema |
|---|---|---|
| `POST /sessions/` responde 500 | Selector, boton apagado con "No se pudo preparar" | No dice que hacer |
| Sin conexion | Igual | No dice que hacer |
| La sesion devuelve 0 preguntas | Boton "Preparando preguntas…" **para siempre** | No hay ni aviso de error |

El tercero es el peor: no hay error que mostrar (`error` esta vacio), solo
`questions` vacio, asi que el alumno espera indefinidamente ante un boton que
dice que se estan preparando preguntas que no van a llegar.

Que la vista de error se pinte en cuanto haya `error` o la partida se quede
sin preguntas, sin depender de `stage`, y que incluya un boton de reintentar.

**Corregido.** `resolveQuestionnaireEntryView` comprueba el error antes que
el sorteo del minijuego, de modo que la pantalla de fallo ya se alcanza, y
lleva un boton de reintentar que relanza la partida sin recargar la pagina.
Los tres casos de la tabla estan cubiertos, incluido el de cero preguntas.

Al hacerlo se introdujo un fallo nuevo: el cuerpo del mensaje y el aviso
decian los dos "Revisa tu conexion", asi que la frase aparecia dos veces en
pantalla. Tambien corregido.

### 4. Resuelto: las metricas del panel se salian de la pantalla en movil

**Prueba:** `responsividad.spec.js > Elementos dentro de la ventana` (320px y 375px)
**Fichero:** [`src/pages/Dashboard.css:176`](../frontend/src/pages/Dashboard.css#L176)

```
panel a 320px: elementos fuera de la ventana (6):
  - dl.dash-metricas > div > dt "REVO Score"      sobra 57px, ancho 361
  - dl.dash-metricas > div > dd.rv-dato "461"     sobra 57px, ancho 361
  - dl.dash-metricas > div > dt "Confianza media" sobra 43px, ancho 185
```

Por debajo de 620px la rejilla pasa a `1fr 1fr` con el tercer bloque ocupando
las dos columnas, pero no hay ningun punto de ruptura por debajo. A 320px
quedan 288px utiles (`.rv-ancho` reserva 16px a cada lado) y los bloques no
bajan de 361px: los elementos de rejilla tienen `min-width: auto`, asi que su
contenido mas ancho — `"Promedio de tus evaluaciones"` en una fila flex que
no envuelve — fija el suelo.

A 375px todavia sobran 2px. La pagina no llega a desplazarse en horizontal
porque un ancestro lo recorta, pero la cifra queda cortada por el borde.

Se anadio `min-width: 0` a `.dash-metricas > div`, columnas con
`minmax(0, 1fr)` y una regla a una columna por debajo de 380px.

### 5. Errores de red sin capturar en dos pantallas

**Pruebas:** `admin.spec.js > un 500 en las estadisticas no deja la pantalla cargando para siempre`, `resiliencia.spec.js > resultado sigue diciendo algo con todo el backend en 500` y `> sin conexion`
**Ficheros:** [`src/pages/Admin.jsx:53`](../frontend/src/pages/Admin.jsx#L53), [`src/pages/Results.jsx:290`](../frontend/src/pages/Results.jsx#L290)

```js
// Admin.jsx
Promise.all([mlApi.overview(), mlApi.trainingHistory()])
  .then(([o, t]) => { setOverview(o.data); setTrainHistory(t.data) })
  .finally(() => setLoading(false))          // sin .catch

// Results.jsx
mlApi.getPrediction(id).then(r => { ... }).finally(() => setLoading(false))
```

Ninguna de las dos cadenas captura el rechazo. Vite lo registra tal cual:

```
[vite] (client) [Unhandled rejection] AxiosError: Request failed with status code 500
```

Dos consecuencias. La primera es que el fallo es silencioso: la pantalla se
queda con los datos vacios y no explica nada. La segunda es de volumen — el
laboratorio de administracion refresca cada 5 segundos
([`Admin.jsx:62`](../frontend/src/pages/Admin.jsx#L62)), asi que con el
servicio caido acumula 12 rechazos por minuto; con un reportador de errores
en produccion, eso es una alerta cada cinco segundos.

Anadir `.catch` en las dos y mostrar el estado de fallo en pantalla.

---

**Corregido.** Las dos cadenas capturan el rechazo y lo cuentan en pantalla:
el laboratorio con un aviso propio y el resultado con la pantalla de
"Resultado no encontrado", que ademas ofrece ir al historial o hacer una
evaluacion nueva.

## Medios

### 6. Contraste insuficiente en las cuatro pantallas principales

**Pruebas:** `accesibilidad.spec.js > Analisis automatico (axe-core)` (portada, login, registro, resultado)

31 elementos incumplen en la portada, 2 en login, 4 en registro y 4 en el
resultado. Casi todo sale de tres tokens:

| Token | Valor | Sobre | Ratio | Minimo |
|---|---|---|---|---|
| `--purple` en `.btn-ghost` | `#6C63FF` | `#33364D` | **2.74** | 4.5 |
| `--lp-muted` | `#687185` | `#ECE8DE` | **4.00** | 4.5 |
| `--lp-blue` en `.lp-route-number` | `#4F7DF3` | `#ECE8DE` | **3.08** | 4.5 |
| `#8a93a6` (pie del formulario) | `#8A93A6` | `#FFFFFF` | **3.08** | 4.5 |
| `.btn-apply` | `#FFFFFF` | `#10B981` | **2.53** | 4.5 |

Son cinco cambios de color, no treinta y uno: la mayoria de los elementos
repiten el mismo token. Ojo con `.btn-apply`, que ademas es un boton de
accion.

**Corregido**, y eran mas de cinco tokens: axe reportaba 25 nodos. Se midio
el color de texto y de fondo REAL de cada uno (con capas translucidas casi
nunca coincide con lo que declara el CSS) y se calculo cada reemplazo con la
formula de la norma. En cada caso se separo el color de relleno, que sigue
siendo el de marca, del de texto.

Dos no se podian arreglar desde el CSS porque el color viene del dato: el
boton "Ver oferta" usa el color de la rama como fondo con texto blanco, y el
porcentaje del top 3 lo usa como texto sobre la tarjeta oscura. Nueve de las
diez especializaciones no llegaban a 4,5:1 con blanco encima. Lo resuelve
`src/theme/contraste.js`, que ajusta el color al pintarlo conservando el
tono, con pruebas unitarias propias.

### 7. Un enlace solo se distingue por el color

**Prueba:** `accesibilidad.spec.js > resultado cumple WCAG 2.1 A y AA` (regla `link-in-text-block`)

El enlace a Remotive dentro de un parrafo tiene un contraste de **1.01:1**
con el texto que lo rodea (`#10B981` sobre `#94A3B8`) y ningun subrayado ni
otro distintivo. Quien no distinga esos dos tonos no ve que ahi hay un
enlace. Basta con subrayarlo.

**Corregido.** El enlace a Remotive va subrayado.

### 8. La barra de navegacion no tiene nombre accesible

**Prueba:** `accesibilidad.spec.js > las regiones de navegacion se distinguen entre si`
**Fichero:** [`src/components/Navbar.jsx:43`](../frontend/src/components/Navbar.jsx#L43)

La portada tiene cuatro elementos `<nav>`: la barra superior y las tres
columnas del pie. Las tres del pie declaran `aria-labelledby`; la barra no
declara nada. Un lector de pantalla anuncia cuatro regiones de "navegacion" y
solo tres tienen nombre, asi que no hay forma de saltar al menu principal.

Es tambien la razon por la que la bateria tiene que buscar la barra por clase
en vez de por rol (ver `pruebas/utiles/localizadores.js`). Con
`aria-label="Navegacion principal"` se arreglan las dos cosas.

**Corregido.** La barra declara `aria-label="Navegacion principal"`.

### 9. La pagina de resultado salta de h1 a h3

**Prueba:** `accesibilidad.spec.js > resultado tiene un solo h1 y no se salta niveles`
**Fichero:** [`src/pages/Results.jsx`](../frontend/src/pages/Results.jsx)

```
{"de":"h1","a":"h3","texto":"Top 3 Especializaciones"}
```

Todos los titulos de panel del resultado son `h3` colgando directamente del
`h1` del heroe. Quien navegue por encabezados no encuentra el nivel
intermedio. Pasarlos a `h2`.

**Corregido.** Los titulos de panel pasaron a `h2` y los de ficha (curso y
empleo) a `h3`, de modo que la jerarquia no salta ningun nivel.

### 10. Resuelto: tres controles estaban por debajo del area tactil minima

**Pruebas:** `responsividad.spec.js > Objetivos tactiles` (375px, 414px, 768px)

El criterio 2.5.8 de la WCAG 2.2 (nivel AA) pide 24x24 px CSS. La sonda ya
aplica las dos excepciones de la norma — enlace dentro de una frase y control
envuelto en su etiqueta — asi que lo que queda son incumplimientos reales:

| Control | Medida | Donde |
|---|---|---|
| `a.hist-text-link` "Ver ultimo resultado" | 293 x **22** | Historial, 375px y 414px |
| Etiqueta "Mantener sesion abierta" | 392 x **22** | Login, 768px |

El del historial es un enlace en bloque (`width: 100%` en movil,
[`History.css:547`](../frontend/src/pages/History.css#L547)) junto al boton
principal, no un enlace dentro de una frase: la excepcion no le aplica.
Ambas zonas interactivas declaran ahora una altura minima de 24px.

### 11. El laboratorio pide datos que no llega a pintar

**Prueba:** `admin.spec.js > la distribucion por especializacion que se pide llega a la pantalla`
**Fichero:** [`src/pages/Admin.jsx:92`](../frontend/src/pages/Admin.jsx#L92)

```js
const dist = overview?.specialization_dist || []   // no se usa en ningun sitio
```

`GET /stats/overview` calcula `specialization_dist` con un `GROUP BY` sobre
`predictions` unido a `specializations`
([`ml-service/routers/stats.py:75`](../services/ml-service/routers/stats.py#L75)),
y el frontend lo guarda en una variable que nunca lee. Con el refresco cada
5 segundos, esa consulta se ejecuta 12 veces por minuto por cada
administrador con la pantalla abierta, para nada.

O se pinta la distribucion (los datos ya estan ahi y son los mas
interesantes de la pantalla), o se quita del endpoint.

---

**Corregido pintandola**, que era la opcion util: el laboratorio muestra el
reparto de predicciones por especializacion con su barra y su porcentaje. La
consulta que ya se hacia cada cinco segundos ahora se ve.

## Bajos

### 12. Salir desde una pantalla protegida acaba en el login

**Prueba:** `navegacion.spec.js > salir borra la sesion y devuelve a la portada`
**Fichero:** [`src/components/Navbar.jsx:37`](../frontend/src/components/Navbar.jsx#L37)

`handleLogout` hace `logout(); navigate('/')`. La secuencia real de URLs es:

```
/dashboard  →  /  →  /login
```

El `navigate('/')` se cumple, pero `PrivateRoute` ya habia pintado su
`<Navigate to="/login" />` con el usuario a null, y ese redirigido se aplica
despues. El alumno acaba en el formulario de login en vez de en la portada.
Salir desde la portada si funciona.

**Corregido**, al tercer intento. Reordenar las llamadas no bastaba, y
`flushSync` tampoco: React Router marca la navegacion como transicion y
`flushSync` no fuerza a que una transicion se confirme. Lo que funciona es
meter el cierre de sesion y la navegacion en la MISMA transicion, para que
React las confirme juntas y no exista el render intermedio en el que la ruta
sigue siendo privada con el usuario ya en null.

La ultima afirmacion de esa prueba, ademas, era imposible de cumplir: el
fixture `iniciarSesion` sembraba el token con `addInitScript`, que corre en
cada carga de documento, asi que volver a una ruta privada tras salir
restauraba la sesion por la puerta de atras. Se corrigio en la bateria con un
centinela para que el token se siembre solo la primera vez.

### 13. El atajo de retroceso del cuestionario no funciona en la practica

**Prueba:** `cuestionario.spec.js > la flecha izquierda vuelve a la pregunta anterior`
**Fichero:** [`src/pages/Questionnaire.jsx:1082`](../frontend/src/pages/Questionnaire.jsx#L1082)

`manejarTecla` descarta cualquier tecla que no sea 1-5 mientras la pregunta
siga escondida tras el minijuego:

```js
if (!preguntaVisible) {
  if (miniGame === CARDS && estadoActivoMano === 'lista' && e.key >= '1' && e.key <= '5') { ... }
  return                       // ArrowLeft muere aqui
}
```

Al avanzar, la pregunta siguiente **siempre** nace escondida. Asi que
`ArrowLeft` solo llega a `prev()` si el alumno destapa primero la carta de la
pregunta a la que acaba de llegar, que es justo lo contrario de lo que quiere
hacer. El boton "Anterior" si funciona.

**Corregido.** `ArrowLeft` retrocede aunque la pregunta siga tapada por el
minijuego, que es el unico caso en que el alumno lo pulsa.

### 14. El aviso de consentimiento escribe "Terminos" sin tilde

**Fichero:** [`src/pages/Auth.jsx:72`](../frontend/src/pages/Auth.jsx#L72)

> "Para crear tu cuenta necesitas aceptar los Terminos y la Politica de
> Privacidad."

El resto de la interfaz acentua las dos palabras. La prueba acepta las dos
grafias para comprobar el comportamiento y no la ortografia, pero el texto
deberia decir "Terminos" y "Politica" con tilde.

---

**Corregido.** "Terminos" y "Politica" van acentuadas.

## Nota aparte: el linter ya avisaba de dos de estos

**Los ocho errores estan corregidos: `npm run lint` termina limpio.** El
aviso de recarga rapida se cerro sacando el contexto y el hook de sesion a
`src/context/contextoAuth.js`, porque un fichero que exporta a la vez un
componente y otras cosas rompe la recarga en caliente de Vite.


`npm run lint` termina con 8 errores en `src/`, anteriores a esta bateria.
Dos coinciden con hallazgos de arriba y sirven de confirmacion independiente:

- `Admin.jsx:92  'dist' is assigned a value but never used` → hallazgo 11.
- `Navbar.jsx:35  Calling setState synchronously within an effect can trigger
  cascading renders` → el mismo efecto que interviene en el hallazgo 12.

Los otros seis son variables e importaciones sin usar en `Admin.jsx`
(`authApi`, `loading`) y `Results.jsx` (`useAuth`, `importances`,
`setArchetype`), mas un aviso de recarga rapida en `AuthContext.jsx`.
`importances` llama la atencion: se piden los pesos del modelo a
`/predict/model/importances` en cada visita al resultado — una ruta que
solo responde a administradores — y la respuesta no se usa para nada.

---

## Lo que si funciona

Vale la pena decir que paso, porque acota donde NO hay que buscar:

- **Sin desplazamiento horizontal en ningun ancho.** Los diez tamanos (320 a
  1920) en las seis pantallas: ninguna se desplaza en horizontal.
- **Control de acceso.** Las rutas privadas redirigen sin sesion; un alumno
  no entra en `/admin` **y ademas** el navegador no llega a pedir las rutas de
  `/stats/`; el enlace de administracion no aparece para alumnos.
- **Consentimiento (Ley 29733).** Las dos casillas opcionales nacen
  desmarcadas; sin aceptar los Terminos no sale ni una peticion al servidor;
  las tres finalidades viajan como tres campos separados en el cuerpo del
  registro.
- **La sesion no sobrevive al cierre de pestana** y el token nunca acaba en
  `localStorage`.
- **La descarga del dataset lleva la cabecera `Authorization`** (el fallo que
  arreglo el paso a `mlApi.descargarDataset` no ha vuelto).
- **El limitador de peticiones** compone el mensaje con los segundos reales
  de `retry-after` y cae a 60 sin NaN cuando la cabecera no viene.
- **El intervalo de refresco del laboratorio se limpia al desmontar.**
- **Todos los graficos de recharts se dibujan con tamano real** en historial,
  resultado y laboratorio: ningun `ResponsiveContainer` colapsado.
- **Las 10 preguntas de fase 1, las de fase 2 y el perfil profesional** se
  completan de principio a fin, incluida la caida al banco de reserva cuando
  las preguntas psicometricas fallan.
- **Ninguna pantalla pide una ruta de API inexistente.**
- **Todas las imagenes cargan, declaran `alt` y reservan su hueco** (sin CLS).
- **Todos los enlaces externos llevan `rel="noopener"`.**
