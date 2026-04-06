# Test Report — REVO (TestSprite)

## 1️⃣ Document Metadata
- **Project Name:** REVO
- **Date:** 2026-04-05
- **Prepared by:** TestSprite AI
- **Server Mode:** development
- **Proxy URL:** (provisioned during run)
- **Total tests executed:** 3
- **Passed:** 2
- **Failed:** 1

---

## 2️⃣ Requirement Validation Summary

### Test: t1-login — Login Flow
- **File:** `testsprite_tests/t1-login_Login_Flow.py`
- **Status:** ✅ Passed
- **What it verifies:** Inicio de sesión con credenciales válidas y redirección al dashboard.
- **Observed outcome:** La secuencia de navegación, relleno de inputs y envío se completó correctamente. Playwright detectó la navegación posterior.
- **Recommendations:** Mantener credenciales de prueba estables (cuenta demo) y preferir selectores con `data-testid` en lugar de XPaths largos.

---

### Test: t2-start-questionnaire — Start Questionnaire
- **File:** `testsprite_tests/t2-start-questionnaire_Start_Questionnaire.py`
- **Status:** ✅ Passed
- **What it verifies:** Iniciar el cuestionario desde el dashboard después de autenticación.
- **Observed outcome:** El flujo para iniciar el cuestionario se ejecutó y el formulario fue detectado.
- **Recommendations:** Consolidar los selectores usados para localizar el control "Nuevo cuestionario"; añadir verificación explícita de que el usuario está autenticado antes de intentar el inicio.

---

### Test: t3-view-results — View Results
- **File:** `testsprite_tests/t3-view-results_View_Results.py`
- **Status:** ❌ Failed
- **What it verifies:** Completar el cuestionario (10 preguntas) y ver la página de resultados (`#results`).
- **Observed outcome:** La ejecución falló durante la secuencia de interacción con las preguntas/ navegación y no se confirmó la aparición del selector `#results` al final.
- **Likely root causes:**
  - Selectores frágiles (XPaths absolutos) que no coinciden con la estructura actual de la página.
  - Flujos dependientes de estado (autenticación/session) que no siempre se conservan entre pasos.
  - Timeouts demasiado cortos o esperas implícitas insuficientes al avanzar múltiples preguntas.
- **Suggested fixes:**
  - Reemplazar XPaths largos por selectores estables (`data-testid`, clases semánticas o IDs).
  - Añadir comprobación explícita de estado autenticado antes de comenzar el cuestionario.
  - Incrementar timeouts y usar `waitForSelector` antes de acciones críticas.
  - Si el cuestionario usa pasos asíncronos/animaciones, sincronizar con la interfaz (esperar elementos visibles/enabled).

---

## 3️⃣ Coverage & Matching Metrics

- **Pass rate:** 66.67% (2/3)

| Requirement ID | Title | Total Tests | Passed | Failed |
|----------------|-------|-------------:|:-----:|:-----:|
| REQ-1 | Authentication | 2 | 2 | 0 |
| REQ-2 | Questionnaire Flow | 1 | 0 | 1 |

Notes:
- Authentication flows are covered by the Login and Start Questionnaire tests and passed.
- Full questionnaire completion and results rendering needs additional attention (selectors/timeouts).

---

## 4️⃣ Key Gaps / Risks
- **Flaky UI selectors:** Uso de XPaths largos hace tests frágiles ante pequeños cambios de estructura.
- **Auth/session fragility:** Tests que requieren login pueden fallar si la cuenta demo no existe o la sesión expira.
- **End-to-end sequence complexity:** Tests que realizan muchas iteraciones (10 preguntas) son propensos a fallos por timeouts o animaciones.
- **Environment dependency:** Tests requieren que servicios backend (auth, ml-service) estén disponibles y el frontend sirviendo en `http://localhost:5173`.

Prioridad de acciones recomendadas:
1. Añadir `data-testid` a elementos clave (botones, inputs, controles de cuestionario).
2. Crear/asegurar una cuenta demo con credenciales fijas para pruebas y documentar su uso.
3. Mejorar selectores en `t3-view-results` y agregar `waitForSelector` antes de cada interacción crítica.
4. Re-ejecutar la suite en modo `production` (build + preview) para mayor estabilidad.

---

Report generated and saved at `testsprite_tests/testsprite-mcp-test-report.md`.
