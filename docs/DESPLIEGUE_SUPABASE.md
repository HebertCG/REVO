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

## 2. Aplicar las migraciones

En el panel, **SQL Editor**. Pega y ejecuta el contenido de `database/`
**en orden numérico**, uno por uno:

```
01_init.sql
01b_schema_sync.sql
02_seed_specializations.sql
03_seed_questions.sql
04_seed_training_data.sql
05_seed_users.sql
06_fix_passwords.sql
07_seed_courses.sql
08_seed_jobs.sql
09_psychometric_questions.sql
10_rls.sql
12_consentimiento.sql
13_registro.sql
14_cuentas.sql
15_roles_por_servicio.sql
```

El orden no es decorativo: `10_rls.sql` crea los roles que `15` reparte, y
las políticas dependen de tablas que crean los anteriores.

## 3. Dar contraseña a los cuatro roles

Las migraciones **crean** los roles pero los dejan sin contraseña. Genera
cuatro distintas y ejecútalas en el SQL Editor:

```sql
ALTER ROLE revo_auth    WITH PASSWORD 'una-larga-y-distinta-1';
ALTER ROLE revo_survey  WITH PASSWORD 'una-larga-y-distinta-2';
ALTER ROLE revo_ml      WITH PASSWORD 'una-larga-y-distinta-3';
ALTER ROLE revo_service WITH PASSWORD 'una-larga-y-distinta-4';
```

**Distintas de verdad, una por rol.** Si las cuatro son la misma, el
aislamiento entre servicios se cae: cualquiera que consiga una credencial
las tiene todas, y toda la separación de `15_roles_por_servicio.sql` deja de
significar nada.

Para generarlas:

```bash
python -c "import secrets; print(secrets.token_urlsafe(36))"
```

## 4. Construir las cadenas de conexión

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

## 5. Pegarlas en Render

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

## 6. Redis: no hace falta

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
