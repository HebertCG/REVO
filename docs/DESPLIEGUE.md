# Despliegue de REVO

Guia para poner REVO en produccion. Cubre las dos formas de desplegarlo con
el mismo codigo: Docker Compose en un servidor propio, o Render.

---

## 1. Antes de nada: generar los secretos

REVO no arranca con secretos vacios ni con valores de ejemplo. Es
deliberado: un secreto publicado en el repositorio es un secreto publico.

```bash
cp .env.example .env

# Genera un valor DISTINTO para cada uno de estos:
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

| Variable | Para que sirve | Si se filtra |
|---|---|---|
| `JWT_SECRET` | Firma los tokens de sesion | Cualquiera puede firmar un token de administrador |
| `GATEWAY_SECRET` | Prueba que la peticion viene de la pasarela | Se puede llamar a los servicios saltandose la pasarela |
| `POSTGRES_PASSWORD` | Dueno de las tablas, solo migraciones | Acceso total a la base de datos, saltandose RLS |
| `APP_DB_PASSWORD` | Rol `revo_app` de los servicios | Acceso a la base, pero sujeto a las politicas RLS |
| `SERVICE_DB_PASSWORD` | Rol `revo_service` del entrenamiento | Lectura del dataset de entrenamiento |
| `REDIS_PASSWORD` | Contadores de rate limit | Se pueden borrar los contadores y anular los cupos |

**Los cinco valores deben ser distintos entre si.** Reutilizar uno convierte
una filtracion en varias.

---

## 2. Opcion A — Docker Compose (servidor propio)

Es la opcion con mejor aislamiento: los servicios, Postgres y Redis viven en
una red interna sin salida a internet, y solo la pasarela publica un puerto.

```bash
docker compose up -d --build
docker compose ps          # los seis deben salir healthy
```

Verificar que quedo bien:

```bash
PUERTO=8080 bash infraestructura/verificar_despliegue.sh
```

Ese script comprueba, contra la pila realmente levantada, que ningun puerto
de servicio esta expuesto, que la documentacion de la API no se sirve, que un
alumno no alcanza los datos de otro, que el rate limit corta y que los
errores no devuelven trazas. **Debe salir con 0 fallidas antes de abrir el
sistema a alumnos reales.**

### TLS

El compose sirve HTTP en el puerto que diga `PUERTO_PUBLICO`. En produccion
hay que poner TLS delante. Dos caminos:

- **Cloudflare por delante** (lo mas rapido): apunta el dominio a Cloudflare
  en modo proxy, activa "Full (strict)" y deja el origen solo accesible desde
  las IP de Cloudflare. Sube `TRUSTED_PROXY_COUNT` a `2`.
- **Certbot en el propio servidor**: anade un contenedor de certbot y monta
  los certificados en la pasarela, con un `listen 443 ssl` adicional.

Con TLS activo hay que poner `ENVIRONMENT=production`, que activa HSTS y
cierra la documentacion de la API.

### Firewall del servidor

```bash
ufw default deny incoming
ufw allow 22/tcp        # SSH
ufw allow 80,443/tcp    # solo la pasarela
ufw enable
```

Sin esto, Docker publica el puerto saltandose las reglas de `ufw` por su
manipulacion directa de iptables: hay que comprobarlo con
`nmap -p- <ip-del-servidor>` desde fuera.

---

## 3. Opcion B — Render

Render no ofrece red privada en los planes bajos: **cada servicio tiene URL
publica**. El aislamiento entonces no lo da la red, sino el secreto de
pasarela. Por eso `REQUIRE_GATEWAY=true` no es opcional en Render.

Pasos:

1. Crear en el panel un **PostgreSQL** y un **Redis** (o Upstash).
2. Aplicar las migraciones en orden contra ese Postgres:

   ```bash
   for f in database/0*.sql database/1*.sql; do
       psql "$DATABASE_URL_DUENO" -v ON_ERROR_STOP=1 -f "$f"
   done
   ```

3. Crear las contrasenas de los roles de aplicacion:

   ```sql
   ALTER ROLE revo_app     WITH PASSWORD '...';
   ALTER ROLE revo_service WITH PASSWORD '...';
   ```

4. Desplegar el `render.yaml` y rellenar en el panel todas las variables
   marcadas como `sync: false`.
5. `DATABASE_URL` de los servicios debe usar **`revo_app`**, no el dueno. Si
   se usa el dueno, RLS deja de aplicar y todo el aislamiento entre alumnos
   desaparece sin que nada falle visiblemente.

Verificacion:

```bash
PUERTO=443 bash infraestructura/verificar_despliegue.sh
```

(Ajustando `BASE` en el script al dominio de la pasarela.)

---

## 4. Frontend

El frontend habla con **un solo origen**: la pasarela.

```bash
# frontend/.env.production
VITE_API_URL=https://api.turdominio.pe/api
```

```bash
cd frontend
npm ci
npm run build      # genera dist/
```

En Vercel, la variable de entorno es `VITE_API_URL` y hay que anadir ese
dominio a `CORS_ORIGINS` en los tres servicios.

---

## 5. Comprobaciones antes de abrir a alumnos

```bash
# 1. Aislamiento en base de datos (20 comprobaciones, Postgres desechable)
bash database/pruebas/verificar_rls.sh

# 2. Libreria compartida
cd services/comun && pip install -e ".[test]" && pytest

# 3. Servicios contra una base real
REVO_TEST_DATABASE_URL="postgresql://revo_app:...@host/revo_db" \
    pytest services/auth-service/pruebas services/survey-service/pruebas

# 4. Frontend
cd frontend && npm run build && node --test src/**/*.test.mjs

# 5. Despliegue completo (40 comprobaciones)
PUERTO=8080 bash infraestructura/verificar_despliegue.sh
```

Lista corta de lo que hay que confirmar a mano:

- [ ] `ENVIRONMENT=production` en los tres servicios.
- [ ] `DATABASE_URL` usa `revo_app`, no el dueno de las tablas.
- [ ] `CORS_ORIGINS` contiene solo dominios `https://` exactos, sin comodines.
- [ ] `TRUSTED_PROXY_COUNT` coincide con el numero real de proxies delante.
- [ ] `nmap` desde fuera muestra unicamente 80 y 443 abiertos.
- [ ] Los documentos legales estan revisados por un abogado (ver seccion 6).
- [ ] Hay copia de seguridad automatica de Postgres y esta probada la
      restauracion.

---

## 6. Aviso sobre la parte legal

Los cuatro documentos de `database/12_consentimiento.sql` son un **borrador
tecnico**, no un texto validado juridicamente. Estan escritos siguiendo la
Ley 29733 y su reglamento, y separan lo obligatorio de lo opcional como esa
ley exige, pero antes de cobrar por los datos o de firmar con una universidad
tienen que pasar por un abogado.

Lo que el sistema ya garantiza tecnicamente:

- El consentimiento comercial y el de entrenamiento son **opt-in separados** y
  desmarcados por defecto.
- Rechazarlos **no impide** usar la plataforma.
- Cada aceptacion guarda version del texto, fecha e IP.
- Se puede revocar desde el perfil, y la revocacion se registra.
- El servicio de entrenamiento solo alcanza a quien lo autorizo (verificado en
  `database/pruebas/verificar_rls.sql`, comprobacion 20).

---

## 7. Operacion diaria

```bash
# Estado
docker compose ps

# Registros de un servicio
docker compose logs -f auth-service

# Peticiones rechazadas por rate limit
docker compose logs pasarela | grep 'lim=' | grep -v 'lim=-'

# Reiniciar sin perder datos
docker compose restart auth-service

# Copia de seguridad
docker compose exec postgres pg_dump -U revo_user revo_db | gzip > copia_$(date +%F).sql.gz
```

### Que mirar cuando algo va mal

| Sintoma | Sitio donde mirar |
|---|---|
| Los alumnos reciben 429 en masa | `docker compose logs pasarela \| grep lim=` y `TRUSTED_PROXY_COUNT` |
| Un alumno no ve sus datos | Contexto RLS: buscar "set_config" en los logs del servicio |
| El rate limit no frena nada | `docker compose logs auth-service \| grep "Rate limit degradado"` |
| 503 al cerrar el cuestionario | El ml-service no responde: `docker compose logs ml-service` |
| Errores 500 | Buscar el `error_id` que devolvio la API en los logs del servicio |

El `error_id` es la pieza clave: el alumno lo ve en la respuesta, y aparece
en el log del servidor junto a la traza completa.
