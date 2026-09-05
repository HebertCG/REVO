# Desplegar el frontend en Vercel

Vercel sirve **solo el frontend**. Los tres microservicios y PostgreSQL no
caben ahí: necesitan un proceso permanente y una base de datos con estado,
y Vercel ejecuta funciones sin estado que se apagan entre peticiones.

El reparto que funciona:

| Pieza | Dónde | Por qué |
|---|---|---|
| `frontend/` | **Vercel** | Es una SPA estática: HTML, JS y CSS |
| pasarela + 3 servicios + Postgres + Redis | **Render** (`render.yaml`), o cualquier host con Docker | Necesitan proceso vivo y estado |

## Pasos

### 1. Levanta primero el backend

Sin una pasarela publicada, el frontend desplegado no tiene con quién
hablar. Sigue [`DESPLIEGUE_NUBE.md`](DESPLIEGUE_NUBE.md) y anota la URL
pública que te quede, por ejemplo `https://revo-pasarela.onrender.com`.

### 2. Apunta el reenvío a esa URL

En `frontend/vercel.json`, sustituye el marcador:

```json
{
  "source": "/api/:ruta*",
  "destination": "https://CAMBIAME-pasarela.onrender.com/api/:ruta*"
}
```

por tu dominio real.

**Por qué un reenvío y no una variable de entorno.** Si el frontend llamara
directamente a `https://revo-pasarela.onrender.com/api`, el navegador vería
dos orígenes distintos y exigiría CORS: cabeceras `Access-Control-*` en cada
respuesta, peticiones `OPTIONS` de comprobación antes de cada llamada real, y
la lista de orígenes permitidos duplicada en el backend. Con el reenvío de
Vercel, el navegador solo ve `/api/...` en su propio dominio. Es una petición
del mismo origen y CORS no entra en juego.

`src/services/api.js` ya usa `/api` por defecto, así que no hay que tocar
código.

### 3. Importa el proyecto

En Vercel, **Add New → Project**, elige el repositorio y configura:

| Campo | Valor |
|---|---|
| Root Directory | `frontend` |
| Framework Preset | Vite (se detecta solo) |
| Build Command | `npm run build` |
| Output Directory | `dist` |

`Root Directory` es el importante: sin él Vercel busca un `package.json` en
la raíz del repositorio y no lo encuentra.

### 4. Comprueba que el enrutado sobrevive a un refresco

Entra a una ruta interna, por ejemplo `/history`, y **recarga la página**.

Si sale un 404, el reenvío de SPA no se aplicó. React Router resuelve las
rutas en el navegador, pero un refresco pide `/history` al servidor, que no
tiene ningún fichero ahí. La regla de `vercel.json` devuelve `index.html`
para cualquier ruta que no sea un recurso de `/assets/`, y entonces el
router se encarga.

## Qué trae ya configurado `vercel.json`

- **Reenvío de SPA** para que cualquier ruta recargada devuelva `index.html`.
- **Reenvío de `/api`** hacia la pasarela, evitando CORS.
- **Caché de un año** para `/assets/*`. Vite pone un hash en cada nombre de
  fichero, así que un cambio genera un nombre nuevo: se puede cachear para
  siempre sin arriesgar servir código viejo.
- **Cabeceras de seguridad**: `nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy` y `Permissions-Policy` cerrando cámara, micrófono y
  ubicación, que la aplicación no usa.

## Lo que falta si quieres una nota alta de rendimiento

El CSS pide cuatro familias tipográficas (Geist, Space Grotesk, Plus Jakarta
Sans y JetBrains Mono) que **ahora mismo no se cargan desde ningún sitio**:
todo se pinta con la fuente del sistema. Antes se cargaban con un `@import`
dentro del CSS, que bloquea el renderizado, y se retiraron.

Hay que decidir entre dos caminos:

1. **Cargarlas** con `<link>` en el `<head>` de `index.html` y
   `font-display: swap`. Cuesta ancho de banda y una petición a un tercero.
2. **Retirar las referencias** del CSS, para que deje de pedir familias que
   nunca llegan y el diseño se defina sobre la fuente del sistema.

Cualquiera de las dos es defendible. Dejarlo como está no: el CSS miente
sobre lo que pide.
