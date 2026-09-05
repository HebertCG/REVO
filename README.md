# REVO

**Recomendador Evolutivo de Orientación** — orientación de especialización para estudiantes de Ingeniería de Sistemas.

---

## El problema

Un estudiante de Ingeniería de Sistemas tiene que elegir especialización sin haber trabajado nunca en ninguna de ellas. En la práctica elige por tres motivos malos: el curso que le tocó un buen profesor, lo que hacen sus amigos, o lo que suena mejor pagado en LinkedIn.

Los tests vocacionales que existen no ayudan porque fallan en lo mismo:

- **Devuelven una sentencia, no una lectura.** «Eres perfil Data Science.» Sin margen, sin porcentaje, sin decir cuánta confianza hay detrás. Un test que se equivoca con seguridad es peor que uno que duda en voz alta.
- **Son genéricos.** Miden si te gusta «resolver problemas» o «trabajar en equipo», no si prefieres depurar un modelo que falla en producción o rediseñar un flujo que confunde a la gente. Son las tareas reales las que distinguen una rama de otra.
- **Son una foto.** Se hacen una vez, en segundo ciclo, y nadie los repite. Pero los intereses de alguien de 19 años no son los mismos a los 22, y esa evolución es justo el dato que importa.
- **Se quedan en el diagnóstico.** Aunque acierten, el estudiante termina con un nombre y ninguna acción concreta para el lunes siguiente.

## Qué hace REVO

Convierte **29 preguntas adaptativas** en las **tres especializaciones** que más se parecen al estudiante, cada una con su porcentaje de confianza, y en un plan de acción para ponerlas a prueba.

Cuatro decisiones lo separan de un test tradicional:

**1. El cuestionario se cierra sobre ti.** De un banco de 100 preguntas el estudiante solo ve 29, en tres fases que van descartando:

| Fase | Preguntas | Qué hace | Rutas que siguen vivas |
|------|-----------|----------|------------------------|
| Explora | 10 | Una señal por cada especialización | 10 → 3 |
| Afina | 15 | Cinco preguntas por cada finalista, sobre tareas reales | 3 |
| Revela | 4 escenarios | Cómo analiza, colabora, ejecuta y cuida el detalle | 1 |

**2. Devuelve la duda junto al resultado.** No dice «eres Data Science». Dice «62 % Data Science, 24 % Desarrollo, 14 % QA» y explica que ese 62 % significa que sus respuestas se parecen a las de quien trabaja con datos, no que deba dedicarse a ello.

**3. Termina en acciones, no en una etiqueta.** Cada resultado trae qué hacer esta semana, este mes, en tres meses y al graduarse, más cursos y vacantes reales de la rama.

**4. Se puede repetir.** Cada semestre. El historial muestra qué intereses se sostienen y cuáles eran curiosidad pasajera, que es la señal más útil de todas.

### Las diez rutas

Agrupadas por el verbo que describe el trabajo:

| | Especializaciones |
|---|---|
| **Crear** | Desarrollo de Software · Diseño UX/UI |
| **Entender** | Data Science e IA · Investigación e Innovación |
| **Sostener** | Infraestructura y Cloud · Soporte Técnico e IT Ops |
| **Proteger** | Ciberseguridad · QA y Testing |
| **Coordinar** | Gestión y Producto · Sistemas Empresariales |

Cada ruta está anclada al catálogo ocupacional **O\*NET** del Departamento de Trabajo de EE. UU., para que no sean categorías inventadas.

---

## Cómo funciona por dentro

El motor es una **regresión logística multinomial** (scikit-learn) entrenada con las respuestas acumuladas. Se eligió sobre un árbol de decisión porque el árbol concentraba las predicciones en pocas hojas y sesgaba el resultado hacia las ramas más frecuentes; la regresión reparte la probabilidad entre las diez clases, que es exactamente lo que la pantalla necesita mostrar.

### Arquitectura

```
                    ┌──────────────┐
   navegador ──────▶│   pasarela   │  nginx · único puerto público
                    └──────┬───────┘
                           │  /api/...
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
      ┌────────────┐ ┌───────────┐ ┌───────────┐
      │    auth    │ │  survey   │ │    ml     │   FastAPI
      │  sesiones  │ │   test    │ │  modelo   │
      │consentimien│ │ adaptativo│ │ predicción│
      └──────┬─────┘ └─────┬─────┘ └─────┬─────┘
             └─────────────┼─────────────┘
                    ┌──────┴──────┐
                    │ PostgreSQL  │  RLS · un rol por servicio
                    │   Redis     │  cupos de peticiones
                    └─────────────┘
```

| Componente | Tecnología | Responsabilidad |
|---|---|---|
| `frontend/` | React 19 · Vite · React Router · Recharts | Interfaz del alumno y del docente |
| `pasarela` | nginx 1.27 | Único origen público; enruta por recurso |
| `services/auth-service` | FastAPI | Registro, sesión JWT, consentimiento |
| `services/survey-service` | FastAPI | Lógica adaptativa de las tres fases |
| `services/ml-service` | FastAPI · scikit-learn | Entrenamiento y predicción |
| `services/comun` | Librería Python | Seguridad, cupos, errores, contexto RLS |
| `database/` | PostgreSQL 16 | Esquema, RLS y datos de arranque |

El frontend habla con **un solo origen**, la pasarela. Antes apuntaba a tres URLs distintas, lo que obligaba a publicar los tres microservicios en internet y dejaba la topología escrita en el JavaScript que cualquiera puede leer.

### Privacidad y seguridad

El sistema trata datos de menores de edad y personas en formación, bajo la **Ley 29733** de protección de datos personales del Perú:

- **Row Level Security en PostgreSQL**: un alumno no puede leer las respuestas de otro ni aunque la consulta se equivoque. La frontera la impone la base, no el código de aplicación.
- **Un rol de base de datos por servicio**: `auth` no puede tocar las tablas de `ml`.
- **Consentimiento separado por finalidad**: usar la plataforma, ceder datos agregados y entrenar el modelo son tres casillas distintas. Las dos opcionales nacen desmarcadas — una casilla premarcada no es consentimiento.
- **Cupos de peticiones por alumno** en Redis, no por IP: en un aula todos comparten la misma IP.

---

## Poner en marcha

**Requisitos:** Docker y Docker Compose.

```bash
git clone https://github.com/HebertCG/REVO.git
cd REVO
cp .env.example .env        # rellena las contraseñas antes de seguir
docker compose up -d
```

La aplicación queda en `http://localhost:8080`. `.env.example` documenta cada variable.

**Solo el frontend**, contra una API ya levantada:

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

---

## Pruebas

```bash
cd frontend
npm run prueba:unidad       # lógica pura (node:test)
npm run prueba              # interfaz completa (Playwright)
npm run prueba:responsivo   # de 320px a 1920px
npm run prueba:movil        # Pixel 7
```

La batería de interfaz **no necesita el backend**: habla con una API simulada. Una suite que solo pasa cuando los microservicios están arriba no mide el frontend, mide el estado del laboratorio.

Cubre accesibilidad (axe-core contra WCAG 2.1 AA), contraste real de cada elemento pintado, resiliencia con el backend caído y sin red, y que ninguna pantalla se salga de la ventana entre 320 y 1920 px.

Los servicios Python se prueban con `pytest` desde `services/`.

---

## Despliegue

| Documento | Contenido |
|---|---|
| [`docs/DESPLIEGUE.md`](docs/DESPLIEGUE.md) | Despliegue con Docker Compose |
| [`docs/DESPLIEGUE_NUBE.md`](docs/DESPLIEGUE_NUBE.md) | Postgres gestionado y verificación remota |
| [`docs/DESPLIEGUE_SUPABASE.md`](docs/DESPLIEGUE_SUPABASE.md) | Base de datos gratuita en Supabase |
| [`docs/SEGURIDAD.md`](docs/SEGURIDAD.md) | Modelo de amenazas y decisiones de seguridad |
| [`render.yaml`](render.yaml) | Definición de servicios para Render |
| [`frontend/vercel.json`](frontend/vercel.json) | Frontend en Vercel — ver nota abajo |

**Sobre Vercel:** Vercel sirve el frontend, que es una SPA estática. Los tres microservicios y PostgreSQL **no** corren en Vercel: necesitan un proceso permanente y una base de datos, y van en Render (`render.yaml`) o en cualquier host con Docker. `frontend/vercel.json` reenvía `/api/*` a la pasarela para que el navegador siga viendo un solo origen y no haga falta CORS.

---

## Estado

Proyecto académico de Ingeniería de Sistemas. El motor de recomendación es funcional y está en uso de prueba; la ficha del proyecto menciona instrumentos (RIASEC, Big Five, explicabilidad del modelo) que todavía **no** están implementados en el código.
