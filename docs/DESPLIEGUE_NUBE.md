# Desplegar REVO en la nube (pruebas)

Runbook para poner REVO en internet con servicios gestionados. Pensado para
una fase de pruebas con usuarios reales, no para produccion final: falta TLS
propio, copias automaticas y el registro de acciones de administrador (ver
la auditoria de seguridad).

## Por que este reparto

| Pieza | Servicio | Motivo |
|---|---|---|
| Frontend | **Vercel** | Es estatico. Encaje perfecto y plan gratuito suficiente. |
| Pasarela + 3 microservicios | **Render** | Procesos largos con estado en memoria (pool de conexiones, contadores). |
| PostgreSQL | **Supabase** | Postgres gestionado de verdad, con la version y las extensiones que usamos. |
| Redis | **Upstash** | Los cupos de peticiones necesitan estado compartido entre workers. |

**Vercel no puede alojar el backend.** Sus funciones son serverless y de vida
corta: cada invocacion abriria su propia conexion a la base (agotando el
limite en minutos), los contadores en memoria del rate limit no sobrevivirian
entre llamadas, y no hay forma de correr Nginx. No es una limitacion de plan,
es el modelo de ejecucion.

---

## 1. Base de datos en Supabase

### 1.1 Crear el proyecto

En [supabase.com](https://supabase.com) → *New project*. Guarda la contrasena
de la base: se muestra una sola vez.

En *Project Settings → Database* encontraras dos cadenas de conexion:

- **Session pooler** (puerto 5432) — la que usamos.
- **Transaction pooler** (puerto 6543) — tambien vale, ver la nota del final.

### 1.2 Aplicar las migraciones

Desde tu maquina, con `psql` apuntando a Supabase. **El orden importa**:

```bash
export SUPA="postgresql://postgres.XXXX:CLAVE@aws-0-REGION.pooler.supabase.com:5432/postgres"

for f in 01_init 01b_schema_sync 02_seed_specializations 03_seed_questions \
         04_seed_training_data 05_seed_users 06_fix_passwords \
         07_seed_courses 08_seed_jobs 09_psychometric_questions \
         10_rls 12_consentimiento 13_registro 14_cuentas \
         15_roles_por_servicio 17_mover_catalogos 18_compatibilidad_gestionado; do
    echo "== $f"
    psql "$SUPA" -v ON_ERROR_STOP=1 -f "database/$f.sql" || break
done
```

Las migraciones **ya estan probadas contra un Postgres sin superusuario**,
que es lo que da Supabase. Si alguna falla, no sigas: el error es real.

### 1.3 Dar contrasena a los roles de servicio

Cada servicio entra con el suyo. Genera cuatro contrasenas distintas:

```bash
for i in 1 2 3 4; do python -c "import secrets; print(secrets.token_urlsafe(36))"; done
```

```sql
ALTER ROLE revo_auth    WITH PASSWORD 'la-primera';
ALTER ROLE revo_survey  WITH PASSWORD 'la-segunda';
ALTER ROLE revo_ml      WITH PASSWORD 'la-tercera';
ALTER ROLE revo_service WITH PASSWORD 'la-cuarta';
ALTER ROLE revo_app NOLOGIN;
```

### 1.4 Comprobar que la frontera quedo puesta

```sql
-- Debe devolver 6, 6 y 6, no 19.
SELECT grantee, count(DISTINCT table_name)
FROM information_schema.role_table_grants
WHERE grantee IN ('revo_auth','revo_survey','revo_ml') AND table_schema='public'
GROUP BY grantee;

-- Debe devolver 1 fila. Si devuelve 0, NADIE PODRA INICIAR SESION.
SELECT count(*) FROM revo_credenciales_por_email('admin@revo.edu');
```

Esa segunda consulta es la que detecta el fallo mas grave de portabilidad.
Si da 0, falta aplicar `18_compatibilidad_gestionado.sql`.

---

## 2. Redis en Upstash

[upstash.com](https://upstash.com) → *Create database*. Elige la region **mas
cercana a la de Render**: cada peticion consulta Redis, y cruzar el Atlantico
son 100 ms por peticion.

Copia la URL en formato `rediss://...` (con doble ese: es TLS).

Sin Redis el sistema arranca igual, pero cada worker cuenta por su cuenta y
el limite real se multiplica por el numero de workers.

---

## 3. Backend en Render

### 3.1 Secretos compartidos

```bash
python -c "import secrets; print('JWT_SECRET   =', secrets.token_urlsafe(48))"
python -c "import secrets; print('GATEWAY_SECRET=', secrets.token_urlsafe(48))"
```

El **mismo** `JWT_SECRET` en los tres servicios: cada uno valida los tokens
que emiten los otros. El **mismo** `GATEWAY_SECRET` en los tres y en la
pasarela.

### 3.2 Crear los servicios

*New → Blueprint*, apunta al repositorio y Render leera `render.yaml`. Crea
cuatro servicios. Los valores marcados `sync: false` se escriben a mano en el
panel, que es la razon de que no haya secretos en el repositorio.

**Para cada microservicio:**

| Variable | Valor |
|---|---|
| `DATABASE_URL` | La de Supabase, **con el rol de ESE servicio** |
| `REDIS_URL` | La de Upstash (`rediss://...`) |
| `JWT_SECRET` | El mismo en los tres |
| `GATEWAY_SECRET` | El mismo en los tres y en la pasarela |
| `ENVIRONMENT` | `production` |
| `REQUIRE_GATEWAY` | `true` |
| `TRUSTED_PROXY_COUNT` | `1` |
| `DB_REQUIRE_SSL` | `true` |
| `CORS_ORIGINS` | La URL de Vercel, con https |
| `WORKERS` | `2` |

El `DATABASE_URL` cambia por servicio:

```
auth    postgresql://revo_auth:CLAVE@HOST:5432/postgres
survey  postgresql://revo_survey:CLAVE@HOST:5432/postgres
ml      postgresql://revo_ml:CLAVE@HOST:5432/postgres
```

**Para la pasarela**, ademas: `URL_AUTH`, `URL_SURVEY` y `URL_ML` con las URLs
internas de los tres servicios.

### 3.3 Lo que el servicio comprueba solo al arrancar

Con `ENVIRONMENT=production` el servicio **se niega a arrancar** si detecta
una configuracion insegura: sin Redis, sin pasarela exigida, con CORS en http
o con comodin, sin SSL a la base, o con un presupuesto de conexiones que no
cabe en el `max_connections` del servidor.

Si Render dice que el arranque fallo, lee el log: el mensaje dice exactamente
que falta.

---

## 4. Frontend en Vercel

*New Project* → importa el repositorio.

| Ajuste | Valor |
|---|---|
| Root Directory | `frontend` |
| Framework | Vite |
| Build Command | `npm run build` |
| Output Directory | `dist` |

Variable de entorno:

```
VITE_API_URL = https://revo-pasarela.onrender.com/api
```

Apunta **a la pasarela**, nunca a un microservicio: los servicios rechazan
con 403 lo que no venga de ella.

Cuando Vercel te de la URL final, vuelve a Render y ponla en `CORS_ORIGINS`
de los tres servicios.

---

## 5. Comprobar el despliegue

```bash
PUERTO=443 BASE=https://revo-pasarela.onrender.com \
    bash infraestructura/verificar_despliegue.sh

API=https://revo-pasarela.onrender.com/api \
    python infraestructura/prueba_flujo_completo.py
```

Y a mano: entra a la URL de Vercel, registra una cuenta, haz el test completo
y comprueba que sale la recomendacion.

---

## Notas que ahorran horas

**El plan gratuito de Render duerme los servicios** tras 15 minutos sin
trafico, y despertar tarda ~30 segundos. El frontend ya reintenta hasta tres
veces con espera creciente, asi que el alumno ve un mensaje en vez de un
error, pero la primera visita del dia sera lenta. Con trafico de aula real,
el plan `starter` de pago evita el problema.

**El pooler de transacciones de Supabase (puerto 6543) tambien vale.** El
contexto RLS se fija con `set_config(..., true)`, que es local a la
transaccion, asi que es compatible. Lo que NO funcionaria es un contexto de
sesion. Si usas ese puerto, anade `?prepared_statement_cache_size=0` a la URL.

**El presupuesto de conexiones.** Supabase gratuito da 60 conexiones directas.
Con 3 servicios x 2 workers x (5+5) son 60: justo en el limite. El servicio lo
comprueba al arrancar y avisa. Si te quedas corto, baja `WORKERS` a 1 o usa el
pooler de transacciones, que multiplica la capacidad.

**Lo que sigue faltando para produccion de verdad**, del informe de auditoria:
TLS propio con tu dominio (Render y Vercel dan HTTPS, asi que para pruebas
estas cubierto), registro de acciones de administrador, copias de seguridad
automaticas y recuperacion de contrasena.
