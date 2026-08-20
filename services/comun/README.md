# revo-comun

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
| `seguridad.tokens` | Emision y verificacion de JWT (iss, aud, typ, rol, jti) |
| `seguridad.ip_cliente` | IP real del cliente respetando los proxies de confianza |
| `limites.politicas` | Que cupo aplica y bajo que llave se cuenta (logica pura) |
| `limites.contador` | Contador de ventana deslizante sobre Redis + respaldo local |

## Instalacion

Docker: el `Dockerfile` de cada servicio copia `comun/` e instala el paquete.

Render: `buildCommand: pip install -r requirements.txt && pip install ../comun`

Local:

```bash
pip install -e services/comun
```

## Pruebas

```bash
cd services/comun
pip install -e ".[test]"
pytest
```
