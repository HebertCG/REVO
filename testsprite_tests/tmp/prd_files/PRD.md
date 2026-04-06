# 📄 Documento de Requerimientos del Producto (PRD) - REVO v2.0

**Nombre del Proyecto:** REVO (Recomendador Evolutivo de Orientación)  
**Visión:** Transformar la orientación vocacional en Ingeniería de Sistemas mediante Machine Learning adaptativo y gamificación evolutiva.  
**Estado:** Fase de Pruebas / Sustentación Académica  

---

## 1. Objetivo del Producto
REVO es un ecosistema diseñado para estudiantes de Ingeniería de Sistemas que utiliza un modelo de **Machine Learning (Árbol de Decisión)** para recomendar especializaciones profesionales. A diferencia de tests estáticos, REVO evoluciona con los datos de la comunidad y permite al estudiante trackear su madurez vocacional a lo largo de su carrera.

---

## 2. Público Objetivo
*   **Estudiantes:** Buscan claridad sobre su futura especialización (Software, Data Science, Ciberseguridad, etc.).
*   **Administradores/Docentes:** Monitorean el crecimiento de la IA y el perfilado masivo del alumnado.
*   **Empresas (Visión a futuro):** Identificación de talento técnico basado en datos reales.

---

## 3. Arquitectura del Sistema (Microservicios)
*   **Frontend:** React (Vite) + Recharts + Vanilla CSS + Glassmorphism.
*   **Auth Service:** Gestión de usuarios (JWT).
*   **Survey Service:** Lógica adaptativa de las 3 fases del test.
*   **ML Service:** Entrenamiento, predicción y analítica de datos.
*   **Database:** MySQL (Relacional) con SQLAlchemy ORM.

---

## 4. Requerimientos Funcionales (Core Features)

### 4.1. Motor Adaptativo de Evaluación (Cuestionario)
*   **Fase 1 (Pre-calibración):** 10 preguntas (1 por cada rama) para detectar intereses iniciales.
*   **Fase 2 (Profundización):** Algoritmo que selecciona 15 preguntas (5 de cada una de las Top 3 ramas detectadas) para validar precisión.
*   **Fase 3 (Psicometría):** 4 preguntas de escenario real para determinar el **Arquetipo Profesional** (Analítico, Ejecutor, Colaborador, Perfeccionista).

### 4.2. Inteligencia Artificial y ML
*   **Modelo:** `DecisionTreeClassifier` (Scikit-Learn).
*   **Automatización:** Re-entrenamiento automático de fondo cada 50 nuevas encuestas resueltas.
*   **Métricas en Vivo:** Cálculo de Accuracy, F1 Score y profundidad del árbol en tiempo real en el Admin Panel.

### 4.3. Dashboard y Gamificación (User Experience)
*   **REVO Score:** Puntaje dinámico basado en: `(evaluaciones * 100) + (confianza_promedio * 2) + bonus_consistencia`.
*   **Niveles Estudiantiles:** 4 niveles visuales (🌱 Explorador Inicial, 🔥 Perfil Emergente, ⚡ Técnico en Consolidación, 🏆 Perfil Elite).
*   **Gráfica Evolutiva:** Visualización de la trayectoria técnica del alumno mediante series de tiempo en el Historial.

### 4.4. Resultados y Plan de Acción
*   **Visualización:** Gráficas de radar (Aptitudes) y barras (Probabilidades del árbol).
*   **Action Plan:** 4 pasos concretos y personalizados por especialidad: *Esta Semana, Este Mes, En 3 Meses y Al Graduarte*.
*   **Nexus:** Bolsa de empleo (Jobs) de GetonBoard Latam y Cursos sugeridos de Udemy/Coursera.

---

## 5. Requerimientos No Funcionales
*   **Seguridad:** Encriptación de contraseñas y tokens JWT para cada petición.
*   **Rendimiento:** Tiempo de respuesta de predicción < 500ms.
*   **Diseño Premium:** Interfaz Glassmorphism, animaciones suaves y modo oscuro integrado.
*   **Didáctica Académica:** Admin Panel con explicaciones flotantes para jurados sobre términos de IA.

---

## 6. Criterios de Aceptación (Checklist de Pruebas)

### ✅ Test de IA
1. [ ] El modelo debe predecir una especialización tras completar las 3 fases.
2. [ ] El porcentaje de "Confianza" debe variar según las respuestas (no ser siempre 100%).
3. [ ] El botón de re-entrenamiento manual debe funcionar y actualizar la versión del modelo.

### ✅ Test de UX/UI
1. [ ] El Dashboard debe mostrar el REVO Score y la barra de progreso al nivel siguiente.
2. [ ] Se deben mostrar las 4 tarjetas del "Plan de Acción" al final de los Resultados.
3. [ ] El Historial debe graficar al menos 2 puntos si el alumno ha hecho 2 tests.

### ✅ Test de Fase 3
1. [ ] Tras la Fase 2, debe aparecer el mensaje "Fase 3 Desbloqueada".
2. [ ] El Arquetipo Profesional debe mostrarse correctamente en la página de Resultados (ej: El Arquitecto Analítico).

---

## 7. Glosario para la Sustentación
*   **Accuracy:** Qué tan bien clasifica el árbol en general.
*   **F1 Score:** El balance real de la precisión del modelo (lo que el jurado querrá ver).
*   **Arquetipo:** Perfil conductual del alumno frente al trabajo técnico.
*   **Polling:** El sistema actualiza el Admin Panel cada 5 segundos sin recargar (Tiempo Real).
