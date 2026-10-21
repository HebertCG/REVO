# Trabajo en equipo

## Ramas

| Rama | Responsable / finalidad |
|---|---|
| `WilsonCollantesAponte` | @WilsonCollantesAponte |
| `AlexisMH30` | @AlexisMH30 |
| `SolanoDieg0` | @SolanoDieg0 |
| `stevenferive` | @stevenferive |
| `stating` | Integracion y pruebas conjuntas del equipo |
| `main` | Version aprobada, promovida manualmente desde `stating` |

El nombre acordado de la rama central es `stating`. El entorno de despliegue
existente se llama `staging`: son nombres distintos y no se renombran secretos
ni entornos. La rama `design/cuestionario-cartas` se conserva; cualquier cambio
que se quiera recuperar de ella pasa primero por un PR hacia `stating`.
Las ramas `codex/**` permiten preparar tareas tecnicas con las mismas pruebas.

## Trabajo diario

La primera vez, sustituir el nombre del ejemplo por la rama propia:

```bash
git fetch origin
git switch --track origin/WilsonCollantesAponte
```

Antes de empezar, comprobar `git status` y actualizar la rama con
`git pull --ff-only`. Guardar los cambios pendientes antes de cambiar de rama.
Hacer commits con archivos elegidos expresamente; no incluir `.env`, copias
de secretos ni datos personales.

```bash
git add ruta/al/archivo
git commit -m "feat: describir el cambio"
git push origin WilsonCollantesAponte
```

En GitHub, abrir un PR con base `stating` y origen la rama personal. Los pushes
siguientes actualizan ese mismo PR. Cada push ejecuta el CI existente y compara
la rama contra la version actual de `stating` mediante `git merge-tree`, sin
integrar cambios ni modificar archivos. Un PR sin conflictos ejecuta las
pruebas sobre la combinacion propuesta por GitHub. Si hay conflictos, GitHub
bloquea la integracion; su workflow de PR puede no llegar a ejecutarse.

Para integrar, deben aprobar `Flujo de ramas` y `Validacion completa`, obtener
una revision aprobada y estar actualizado respecto a la base. Si otro PR cambia
`stating`, volver a actualizar la rama y comprobar el resultado antes de integrar.
La actualizacion que combine ramas tambien requiere la autorizacion acordada;
no se ejecutan merges automaticos. Elegir **Create a merge commit** al integrar
las ramas personales y al promover `stating` a `main`, para conservar el historial
compartido de estas ramas permanentes. No borrarlas tras combinar el PR.

El nombre de una rama identifica a su responsable; no restringe por si solo
quien puede escribir en ella. Los permisos de colaboradores se gestionan en
GitHub y no se cambian al crear ramas.

## Promocion a main y despliegue

Cuando el equipo valide el conjunto en `stating`, abrir un PR con base `main`
y origen `stating` del mismo repositorio. El CI rechaza otros origenes hacia
`main`. Revisar los cambios, los conflictos y las pruebas, solicitar autorizacion
expresa para ese merge y combinarlo manualmente desde GitHub.

Se mantiene el despliegue existente: un push a `main`, incluido el creado por
ese merge, pasa las pruebas y despliega primero al entorno `staging` y luego
a `Production`, sujeto a las reglas de esos entornos. Hacer ese merge implica
activar el despliegue existente y debe contemplarse al autorizarlo. Los pushes
a `stating`, a ramas personales y los eventos de PR no despliegan.

Si un cambio debe retirarse, preparar un PR de reversion en `stating`, verificarlo
y promoverlo a `main` con la misma autorizacion. No usar force-push sobre las
ramas centrales. Una recuperacion urgente del servicio se coordina por separado;
crear estas ramas no autoriza despliegues ni reversiones de produccion.

## Protecciones de GitHub

Las ramas centrales deben exigir PR, una aprobacion, descartar aprobaciones
antiguas al recibir commits nuevos y los checks `Flujo de ramas` y
`Validacion completa`, con la rama actualizada antes del merge. Las reglas se
aplican tambien a administradores y bloquean force-push y borrado.

Estas reglas se configuran en GitHub; este documento y el YAML por si solos no
las activan. Su configuracion reproducible esta en
`.github/protecciones-ramas.json` (cuerpo de la API de proteccion de ramas de
GitHub para `main` y `stating`). La comprobacion de origen depende del workflow versionado, por lo
que los cambios a `.github/` requieren especial atencion en la revision.

## Comprobar las reglas localmente

Requisitos: Node 24 y Git 2.38 o posterior.

```bash
node --test .github/scripts/validar-ramas.test.mjs
```

Las pruebas crean repositorios temporales para comprobar cambios compatibles,
conflictos, ausencia de la rama central y origenes de PR validos e invalidos.
El checkout del proyecto permanece intacto.
