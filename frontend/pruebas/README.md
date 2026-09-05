# Pruebas de interfaz de REVO

Bateria de Playwright sobre el frontend. Cubre responsividad, accesibilidad,
enrutado, formularios, el cuestionario completo y el comportamiento ante
fallos de red.

## Ejecutar

```bash
npm run prueba              # todo
npm run prueba:responsivo   # solo maquetacion, en diez anchos
npm run prueba:carga        # 6 sesiones concurrentes en movil, tableta y escritorio
npm run prueba:movil        # las funcionales en un movil real (Pixel 7)
npm run prueba:escritorio   # las funcionales a 1440x900
npm run prueba:informe      # abre el informe HTML del ultimo pase
npm run prueba:fallos       # lista los fallos por consola, sin abrir nada
```

No hace falta levantar los microservicios: Playwright arranca Vite solo y
toda la red se responde desde `utiles/apiSimulada.js`.

## Por que la API va simulada

Una bateria que necesita los tres servicios arriba no falla cuando el
frontend se rompe, falla cuando alguien apago Docker. Ademas, los casos que
mas informacion dan (429, 500, sin conexion, JSON malformado, respuesta
lenta) no se pueden provocar contra un backend real sin romperlo.

Los datos de `utiles/datos.js` copian la forma exacta de los esquemas
Pydantic de cada servicio. Si un campo cambia en el backend y no aqui, las
pruebas siguen pasando contra un contrato que ya no existe: por eso cada
bloque anota de que endpoint sale.

Cualquier ruta que el frontend pida y no este simulada se responde con un 404
y se apunta en `registro.noReconocidas`. La prueba
`resiliencia.spec.js > ninguna pantalla pide una ruta de API que no existe`
la convierte en un fallo, de modo que una llamada nueva sin cubrir se nota.

## Estructura

| Fichero | Que cubre |
|---|---|
| `responsividad.spec.js` | Desbordes, objetivos tactiles, texto recortado e imagenes en 10 anchos (320 → 1920) |
| `carga.spec.js` | Carga sintetica: 6 clientes concurrentes recorren las vistas privadas mas pesadas |
| `accesibilidad.spec.js` | axe-core (WCAG 2.1 A/AA) mas jerarquia de encabezados, nombres accesibles, teclado y foco |
| `navegacion.spec.js` | Rutas protegidas, roles, enlaces del pie, enlaces profundos |
| `autenticacion.spec.js` | Login, registro, consentimiento Ley 29733, sesion caducada |
| `panel.spec.js` | Panel del alumno: vacio, con historial, cargando, con el servicio caido |
| `historial.spec.js` | Lectura del patron y el grafico de trayectoria |
| `resultados.spec.js` | Resultado, graficos, cursos, valoracion, fuentes que fallan |
| `cuestionario.spec.js` | Sorteo de minijuego, fases 1-2-3, atajos, minijuegos alternativos |
| `admin.spec.js` | Laboratorio del modelo, reentrenamiento, descarga del dataset, refresco |
| `resiliencia.spec.js` | 401, 429, 500, sin conexion, respuestas malformadas |

### Utilidades

- **`apiSimulada.js`** — interceptor de red y reglas de error (`reglaError`,
  `reglaSinRed`). Filtra por origen, no solo por ruta: la API publica de
  empleos que consulta la pantalla de resultado tambien vive bajo `/api/` en
  su propio dominio.
- **`inspector.js`** — sondas de maquetacion que corren dentro del navegador.
  Devuelven la lista de elementos culpables con su selector y los pixeles que
  sobran, no un booleano.
- **`fixtures.js`** — `paginaPublica`, `paginaAlumno`, `paginaAdmin`, y el
  `vigilante`, que recoge errores de consola, excepciones y peticiones
  fallidas en todas las pruebas.
- **`cuestionario.js`** — fija el sorteo del minijuego y resuelve la ruta del
  coche simulando la misma maquina de estados que usa la pantalla.
- **`localizadores.js`** — los pocos selectores que no pueden ir por rol,
  cada uno con el motivo.

## Decisiones que conviene conocer

**Movimiento reducido en todas las pruebas.** La opcion `reducedMotion` del
fichero de configuracion no llega al navegador en esta version de Playwright
(comprobado consultando `matchMedia` desde la pagina). Se emula en el fixture
`movimientoReducido`. Importa: el cuestionario tiene temporizadores de 3,2 s
que bajan a 350 ms con la preferencia activa.

**El cuestionario se ancla al marcador.** Entre pregunta y pregunta hay
animaciones; mirar "hay una pregunta en pantalla" puede estar viendo la
anterior saliendo. El `aria-label` del marcador (`Carta 3 de 10`) es el unico
dato que identifica sin ambiguedad en que pregunta estamos.

**Nada de capturas comparadas.** Fallan por el antialiasing de la fuente y
acaban desactivadas. Lo que se mide es geometria: pixeles que se salen, texto
que se corta, dedos que no alcanzan.

**Las sondas aplican las excepciones de la WCAG.** El minimo de 24x24 px
(criterio 2.5.8) no se aplica a un enlace dentro de una frase ni a una
casilla envuelta en su etiqueta, porque la norma los exceptua. Sin esas dos
excepciones la sonda marca como fallo cosas que no lo son y el ruido entierra
los hallazgos reales.

## Estado

**La bateria pasa entera: 321 de 321.** Los quince defectos que describia
estan corregidos; el diagnostico de cada uno y como se cerro quedan en
[`docs/INFORME_PRUEBAS_FRONTEND.md`](../../docs/INFORME_PRUEBAS_FRONTEND.md).

Tres de esas correcciones fueron a la propia bateria, porque el defecto
estaba aqui y no en la aplicacion:

- `esperarEstable` espera ahora a que desaparezca el hueco de carga de las
  rutas diferidas. Ese hueco es un DOM pequeno y estatico, asi que el
  criterio de "ha dejado de crecer" se cumplia de inmediato y las sondas
  median el cargador creyendo que era la pantalla.
- La sonda de texto recortado exceptua el texto reservado a lectores de
  pantalla (caja de 1px con `clip`), que esta recortado a proposito, igual
  que ya exceptuaba `text-overflow: ellipsis`.
- `iniciarSesion` siembra el token una sola vez. Con `addInitScript` a secas
  se reescribia en cada carga de documento, lo que hacia imposible de cumplir
  la ultima afirmacion de la prueba de cierre de sesion.

## Proyectos que no afirman nada

`capturas.spec.js` guarda imagenes de las pantallas y
`contraste.diagnostico.spec.js` vuelca el color de texto y de fondo real de
cada elemento que incumple contraste, con su ratio. Los dos viven en el
proyecto `capturas` y quedan fuera de la bateria: un fichero que siempre pasa
falsea el recuento.

```bash
npm run prueba:capturas
```
