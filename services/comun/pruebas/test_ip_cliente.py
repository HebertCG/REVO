"""
Extraer la IP del cliente es una decision de seguridad, no una utilidad.

Si se confia en X-Forwarded-For sin condiciones, cualquiera manda
"X-Forwarded-For: 1.2.3.4" y estrena un cupo de rate limit en cada peticion,
lo que anula por completo el limite por IP.
"""
from revo_comun.seguridad.ip_cliente import extract_client_ip


class PeticionFalsa:
    def __init__(self, remote_addr, headers=None):
        self.client = type("C", (), {"host": remote_addr})() if remote_addr else None
        self.headers = headers or {}


class TestSinProxy:
    def test_usa_la_ip_del_socket(self):
        req = PeticionFalsa("200.60.1.1")

        assert extract_client_ip(req, trusted_proxy_count=0) == "200.60.1.1"

    def test_ignora_la_cabecera_falsificada(self):
        req = PeticionFalsa("200.60.1.1", {"x-forwarded-for": "1.2.3.4"})

        assert extract_client_ip(req, trusted_proxy_count=0) == "200.60.1.1"

    def test_sin_socket_devuelve_un_valor_seguro_y_no_revienta(self):
        req = PeticionFalsa(None)

        assert extract_client_ip(req, trusted_proxy_count=0) == "unknown"


class TestDetrasDeUnProxy:
    def test_toma_el_ultimo_salto_no_el_primero(self):
        # Cadena: cliente real -> proxy. Nginx anade la IP que el vio.
        # Si el cliente inyecta saltos falsos por delante, quedan a la
        # izquierda y deben descartarse.
        req = PeticionFalsa("10.0.0.5", {"x-forwarded-for": "1.2.3.4, 200.60.1.1"})

        assert extract_client_ip(req, trusted_proxy_count=1) == "200.60.1.1"

    def test_con_un_solo_salto_real_usa_ese(self):
        req = PeticionFalsa("10.0.0.5", {"x-forwarded-for": "200.60.1.1"})

        assert extract_client_ip(req, trusted_proxy_count=1) == "200.60.1.1"

    def test_tolera_espacios_en_la_cadena(self):
        req = PeticionFalsa("10.0.0.5", {"x-forwarded-for": "  200.60.1.1  "})

        assert extract_client_ip(req, trusted_proxy_count=1) == "200.60.1.1"


class TestDetrasDeDosProxies:
    def test_salta_cloudflare_y_nginx(self):
        # Cliente -> Cloudflare -> Nginx -> app: dos saltos de confianza.
        req = PeticionFalsa("10.0.0.5", {"x-forwarded-for": "200.60.1.1, 172.71.1.1"})

        assert extract_client_ip(req, trusted_proxy_count=2) == "200.60.1.1"

    def test_una_cadena_mas_corta_de_lo_declarado_no_revienta(self):
        req = PeticionFalsa("10.0.0.5", {"x-forwarded-for": "200.60.1.1"})

        assert extract_client_ip(req, trusted_proxy_count=2) == "200.60.1.1"


class TestEntradaHostil:
    def test_descarta_una_ip_sintacticamente_invalida(self):
        req = PeticionFalsa("10.0.0.5", {"x-forwarded-for": "no-soy-una-ip"})

        assert extract_client_ip(req, trusted_proxy_count=1) == "10.0.0.5"

    def test_no_deja_que_la_cabecera_haga_crecer_las_llaves_de_redis(self):
        req = PeticionFalsa("10.0.0.5", {"x-forwarded-for": "A" * 5000})

        assert extract_client_ip(req, trusted_proxy_count=1) == "10.0.0.5"

    def test_acepta_ipv6(self):
        req = PeticionFalsa("10.0.0.5", {"x-forwarded-for": "2001:db8::1"})

        assert extract_client_ip(req, trusted_proxy_count=1) == "2001:db8::1"

    def test_una_cabecera_vacia_cae_al_socket(self):
        req = PeticionFalsa("10.0.0.5", {"x-forwarded-for": ""})

        assert extract_client_ip(req, trusted_proxy_count=1) == "10.0.0.5"
