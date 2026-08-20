# revo-common

Preocupaciones transversales compartidas por `auth-service`, `survey-service`
y `ml-service`.

## Por que existe

Los tres servicios repetian la misma funcion `extract_user_id` de seis lineas,
cada uno con su propia copia. Tres copias son tres sitios donde arreglar el
mismo fallo, y ninguna verificaba emisor, audiencia ni proposito del token.

Aqui solo vive infraestructura **transversal**: tokens, rate limit, cabeceras,
IP de cliente, sesion de base de datos. Nada de dominio. Las reglas de negocio
de cada servicio se quedan en su servicio: eso es lo que mantiene el
acoplamiento bajo aunque el codigo se comparta.

## Modulos

| Modulo | Responsabilidad |
|---|---|
| `security.tokens` | Emision y verificacion de JWT (iss, aud, typ, rol, jti) |
| `security.client_ip` | IP real del cliente respetando los proxies de confianza |
| `ratelimit.policy` | Que cupo aplica y bajo que llave se cuenta (logica pura) |
| `ratelimit.backend` | Contador de ventana deslizante sobre Redis + respaldo local |

## Instalacion

Docker: el `Dockerfile` de cada servicio copia `shared/` e instala el paquete.

Render: `buildCommand: pip install -r requirements.txt && pip install ../shared`

Local:

```bash
pip install -e services/shared
```

## Pruebas

```bash
cd services/shared
pip install -e ".[test]"
pytest
```
