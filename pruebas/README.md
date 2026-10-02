# Pruebas de REVO

Las pruebas estan separadas por el alcance que tendran en el pipeline. Una
etapa no debe ejecutar silenciosamente pruebas de otra categoria.

## 1. Unitarias

No usan servicios externos ni una base de datos real. Son la primera puerta
del CI y deben terminar en pocos minutos.

| Componente | Ubicacion | Comando desde el componente |
|---|---|---|
| Frontend | `frontend/src/**/*.test.mjs` | `npm run prueba:unidad` |
| Comun | `services/comun/pruebas/unitarias/` | `python -m pytest -q` |
| Auth | `services/auth-service/pruebas/unitarias/` | `python -m pytest -q` |
| Survey | `services/survey-service/pruebas/unitarias/` | `python -m pytest -q` |
| ML | `services/ml-service/pruebas/unitarias/` | `python -m pytest -q` |

Cada configuracion de pytest apunta por defecto a `pruebas/unitarias`. Por
eso un `python -m pytest` no puede aprobar el bloque unitario ocultando una
integracion omitida.

## 2. Integracion

Comprueban cada API contra PostgreSQL real y sus politicas RLS. Requieren
`REVO_TEST_DATABASE_URL` y se ejecutan explicitamente:

```bash
cd services/auth-service
python -m pytest pruebas/integracion -q

cd ../survey-service
python -m pytest pruebas/integracion -q

cd ../ml-service
python -m pytest pruebas/integracion -q
```

Si falta la base de pruebas, estas suites se omiten. El CI debera considerar
una omision como configuracion incompleta y no como autorizacion para desplegar.

## 3. End to end

Hay dos niveles diferentes:

- `frontend/pruebas/e2e/`: recorridos Playwright del navegador con API
  simulada. La primera vez requiere `npx playwright install chromium` y se
  ejecutan con `npm run prueba:e2e` desde `frontend/`.
- `pruebas/e2e/sistema/`: recorrido contra la pila real levantada. Se ejecuta
  con `python pruebas/e2e/sistema/flujo_completo.py` desde la raiz.

La puerta E2E del despliegue debe ejecutar ambos niveles. El segundo necesita
la pasarela, los tres microservicios, PostgreSQL y Redis activos.

## Fuera de estas puertas

Las pruebas de carga permanecen en `infraestructura/carga/`. No son unitarias
ni E2E funcionales y se usaran durante la observacion prolongada de staging.
Los recorridos manuales, como el cliente HTTP de autenticacion, viven en
`services/*/pruebas/manuales/` y tampoco forman parte de una puerta automatica.
