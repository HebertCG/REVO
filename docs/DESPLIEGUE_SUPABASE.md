# Base de datos en Supabase (plan gratuito)

Supabase da un PostgreSQL gestionado gratis. Es suficiente para sacar REVO
a internet sin pagar nada, y encaja con el diseño del proyecto sin tocar
código.

## Por qué encaja

Antes de recomendarlo comprobé las tres cosas que suelen romperse:

| Lo que REVO necesita | Supabase |
|---|---|
| Extensiones `uuid-ossp` y `pgcrypto` (`01_init.sql`) | Disponibles |
| `CREATE ROLE ... NOSUPERUSER` para los cuatro roles por servicio | El rol `postgres` puede crear roles |
| `ALTER DEFAULT PRIVILEGES FOR ROLE` (`10_rls.sql`) | Funciona como propietario |
| Conexión cifrada | Obligatoria; `DB_REQUIRE_SSL=true` ya la pide |

Y lo más importante: el contexto de RLS se fija con
`set_config('revo.user_id', ..., true)`. Ese tercer argumento lo hace
**local a la transacción**, no a la sesión. Es lo que permite usar el
*pooler* de Supabase sin que un alumno herede la identidad del anterior
cuando el pool recicla la conexión.

---

## 1. Crear el proyecto

En [supabase.com](https://supabase.com) → **New project**. Anota la
contraseña del rol `postgres`: solo se muestra una vez.

Elige la región más cercana a tus usuarios. Con Render en Oregon, `us-west`
evita cruzar el continente en cada consulta.

## 2. Ejecutar la instalación

En el panel, **SQL Editor** -> **New query**. Pega entero el contenido de
[`database/INSTALAR_SUPABASE.sql`](../database/INSTALAR_SUPABASE.sql) y pulsa
**Run**.

Ese fichero reúne las 17 migraciones en el orden correcto. El orden no es
alfabético y no es decorativo: `01b_schema_sync` va después de `01_init`
porque toca tablas que aquel crea, y `18_compatibilidad_gestionado` cierra.

Ese último es **imprescindible aquí**. En un Postgres local el dueño de la
base es superusuario y se salta RLS; en Supabase no lo es, y sin la
migración 18 las funciones `SECURITY DEFINER` devuelven cero filas. El
síntoma es que **nadie puede iniciar sesión**, sin error y sin traza:
simplemente ninguna contraseña funciona.

### Antes de pulsar Run

Baja al bloque **PASO FINAL** del fichero y sustituye las cuatro contraseñas
de ejemplo. El script se niega a terminar si no lo haces, si repites alguna
o si alguna baja de 20 caracteres.

Para generarlas, en tu terminal:

    python -c "import secrets; print(secrets.token_urlsafe(36))"

Tienen que ser **cuatro distintas**. Si repites la misma, quien consiga una
credencial las tiene todas y la separación de `15_roles_por_servicio.sql`
deja de significar nada.

### Se puede volver a ejecutar

Todo el fichero es idempotente: crea lo que falta y respeta lo que ya
existe. Si algo falla a mitad, corrige y vuelve a lanzarlo entero.

### Probado antes de publicarlo

El fichero se ejecutó contra un PostgreSQL 16 limpio en Docker:

| Comprobación | Resultado |
|---|---|
| Instalación completa sobre base vacía | código de salida 0 |
| Tablas con RLS activo | 18 de 18 |
| Roles sin superusuario ni `BYPASSRLS` | 5 de 5 |
| `revo_app` sin poder conectarse | correcto |
| Segunda ejecución seguida | 0 errores |
| `revo_survey` leyendo `users` | `permission denied` |
| `revo_survey` leyendo `courses` | `permission denied` |
| `revo_ml` leyendo `courses` | 30 filas |
| Bloque final con las contraseñas sin editar | se niega a terminar |

Lo único que no se puede reproducir fuera de Supabase es `CREATE EXTENSION`
con un dueño que no sea superusuario: en un Postgres vanilla hace falta
serlo, y en Supabase `uuid-ossp` y `pgcrypto` están permitidas para el rol
`postgres`.

## 3. Construir las cadenas de conexión

**Settings → Database → Connection string.** Supabase muestra tres modos;
copia la plantilla del que elijas y sustituye el usuario y la contraseña por
los del rol que toque.

| Modo | Puerto | Cuándo |
|---|---|---|
| **Session pooler** | 5432 | **Recomendado.** Admite roles propios y no limita lo que se puede hacer en la sesión |
| Transaction pooler | 6543 | Más conexiones simultáneas. Funciona porque el contexto RLS es transaccional, pero verifica que acepte los roles propios antes de fiarte |
| Directa | 5432 | Pocas conexiones en el plan gratuito; se agota con cuatro servicios |

Queda una cadena por servicio, **cada una con su rol**:

```
revo-auth-service    →  postgresql://revo_auth:CLAVE1@<host-supabase>:5432/postgres
revo-survey-service  →  postgresql://revo_survey:CLAVE2@<host-supabase>:5432/postgres
revo-ml-service      →  postgresql://revo_ml:CLAVE3@<host-supabase>:5432/postgres
```

Nunca uses la cadena del rol `postgres` en un servicio. `postgres` es el
dueño de las tablas y **se salta las políticas RLS**: con ella, el
cuestionario podría leer la tabla de usuarios y el aislamiento entre alumnos
desaparecería sin que nada fallara de forma visible.

## 4. Pegarlas en Render

En cada servicio, **Environment**, la variable `DATABASE_URL` con la cadena
que le corresponde. `render.yaml` las declara con `sync: false` justamente
para que no viajen al repositorio.

Añade también, si no están:

| Variable | Valor |
|---|---|
| `DB_REQUIRE_SSL` | `true` |
| `JWT_SECRET` | uno largo, el mismo en los tres servicios |
| `GATEWAY_SECRET` | uno largo, el mismo en los tres y en la pasarela |
| `REQUIRE_GATEWAY` | `true` |
| `CORS_ORIGINS` | la URL de tu frontend en Vercel |

## 5. Redis: no hace falta

`REDIS_URL` vacía deja el control de cupos **en memoria del proceso**. Con
una sola instancia por servicio funciona correctamente.

Solo hace falta Redis de verdad cuando haya más de una réplica del mismo
servicio, porque entonces cada una llevaría su cuenta por separado y el
límite real sería el doble. Si llegas a ese punto, Upstash tiene plan
gratuito.

---

## Comprobar que funcionó

```sql
-- Los cuatro roles existen y ninguno se salta RLS
SELECT rolname, rolsuper, rolbypassrls
FROM pg_roles WHERE rolname LIKE 'revo_%';

-- Las tablas con datos de alumnos tienen RLS activo
SELECT tablename, rowsecurity
FROM pg_tables WHERE schemaname = 'public';
```

`rolsuper` y `rolbypassrls` deben salir en `false` en los cuatro. Si alguno
sale `true`, ese servicio puede leerlo todo y RLS no te protege.

El proyecto trae una verificación automatizada del aislamiento:

```bash
cd services/survey-service && pytest pruebas/
```

## Aviso del plan gratuito

Supabase **pausa el proyecto tras una semana sin actividad**. Se reactiva a
mano desde el panel, pero mientras está pausado la aplicación no responde.
Si es para una sustentación, entra el día antes y comprueba que está
despierto.
