"""
Pruebas del emisor y verificador de tokens.

Hoy cada microservicio repite su propio `extract_user_id` y solo comprueba
firma y expiracion. Esa comprobacion minima deja pasar tokens emitidos para
otro proposito, tokens sin `sub` utilizable y tokens firmados con un
algoritmo elegido por el atacante.
"""
import base64
import json
import time

import pytest
from jose import jwt

from revo_common.security.tokens import (
    ACCESS_TOKEN_TYPE,
    TokenError,
    TokenIssuer,
)

SECRET = "un-secreto-de-pruebas-suficientemente-largo-para-hs256"
OTRO_SECRET = "otro-secreto-distinto-igual-de-largo-para-la-prueba"


@pytest.fixture
def issuer():
    return TokenIssuer(secret=SECRET, issuer="revo-auth", audience="revo-api", expire_hours=24)


class TestEmision:
    def test_el_token_identifica_al_alumno_y_su_rol(self, issuer):
        token = issuer.issue(user_id=42, role="student")

        principal = issuer.verify(token)

        assert principal.user_id == 42
        assert principal.role == "student"

    def test_cada_token_lleva_un_identificador_unico(self, issuer):
        # Sin jti no se puede revocar un token concreto ni detectar replay.
        primero = issuer.verify(issuer.issue(user_id=1, role="student"))
        segundo = issuer.verify(issuer.issue(user_id=1, role="student"))

        assert primero.jti != segundo.jti

    def test_el_administrador_se_reconoce_como_tal(self, issuer):
        principal = issuer.verify(issuer.issue(user_id=1, role="admin"))

        assert principal.is_admin is True

    def test_el_alumno_no_se_reconoce_como_administrador(self, issuer):
        principal = issuer.verify(issuer.issue(user_id=1, role="student"))

        assert principal.is_admin is False

    def test_un_rol_desconocido_se_rechaza_al_emitir(self, issuer):
        with pytest.raises(ValueError):
            issuer.issue(user_id=1, role="superadmin")


class TestVerificacion:
    def test_rechaza_un_token_con_otra_firma(self, issuer):
        ajeno = TokenIssuer(secret=OTRO_SECRET, issuer="revo-auth", audience="revo-api")
        token = ajeno.issue(user_id=1, role="admin")

        with pytest.raises(TokenError):
            issuer.verify(token)

    def test_rechaza_un_token_caducado(self, issuer):
        vencido = jwt.encode(
            {
                "sub": "1",
                "role": "student",
                "iss": "revo-auth",
                "aud": "revo-api",
                "typ": ACCESS_TOKEN_TYPE,
                "exp": int(time.time()) - 10,
                "iat": int(time.time()) - 100,
                "jti": "x",
            },
            SECRET,
            algorithm="HS256",
        )

        with pytest.raises(TokenError):
            issuer.verify(vencido)

    def test_rechaza_un_token_emitido_por_otro_sistema(self, issuer):
        forastero = TokenIssuer(secret=SECRET, issuer="otra-app", audience="revo-api")

        with pytest.raises(TokenError):
            issuer.verify(forastero.issue(user_id=1, role="admin"))

    def test_rechaza_un_token_dirigido_a_otra_audiencia(self, issuer):
        otra_audiencia = TokenIssuer(secret=SECRET, issuer="revo-auth", audience="otra-api")

        with pytest.raises(TokenError):
            issuer.verify(otra_audiencia.issue(user_id=1, role="admin"))

    def test_rechaza_un_token_de_otro_proposito(self, issuer):
        # Un token de refresco o de reset de password no debe servir para
        # llamar a la API.
        otro_proposito = jwt.encode(
            {
                "sub": "1",
                "role": "admin",
                "iss": "revo-auth",
                "aud": "revo-api",
                "typ": "password_reset",
                "exp": int(time.time()) + 600,
                "iat": int(time.time()),
                "jti": "x",
            },
            SECRET,
            algorithm="HS256",
        )

        with pytest.raises(TokenError):
            issuer.verify(otro_proposito)

    def test_rechaza_un_token_sin_firma(self, issuer):
        # El ataque clasico: alg "none" y firma vacia. Se construye a mano
        # porque ninguna libreria seria acepta firmarlo.
        def b64(obj):
            crudo = json.dumps(obj, separators=(",", ":")).encode("utf-8")
            return base64.urlsafe_b64encode(crudo).rstrip(b"=").decode("ascii")

        sin_firma = "{}.{}.".format(
            b64({"alg": "none", "typ": "JWT"}),
            b64(
                {
                    "sub": "1",
                    "role": "admin",
                    "iss": "revo-auth",
                    "aud": "revo-api",
                    "typ": ACCESS_TOKEN_TYPE,
                    "exp": int(time.time()) + 600,
                    "iat": int(time.time()),
                    "jti": "x",
                }
            ),
        )

        with pytest.raises(TokenError):
            issuer.verify(sin_firma)

    def test_rechaza_un_sub_que_no_es_un_identificador(self, issuer):
        raro = jwt.encode(
            {
                "sub": "'; DROP TABLE users;--",
                "role": "student",
                "iss": "revo-auth",
                "aud": "revo-api",
                "typ": ACCESS_TOKEN_TYPE,
                "exp": int(time.time()) + 600,
                "iat": int(time.time()),
                "jti": "x",
            },
            SECRET,
            algorithm="HS256",
        )

        with pytest.raises(TokenError):
            issuer.verify(raro)

    def test_rechaza_un_rol_inventado_dentro_del_token(self, issuer):
        # Aunque venga firmado, un rol fuera del catalogo no escala privilegios.
        inventado = jwt.encode(
            {
                "sub": "1",
                "role": "superadmin",
                "iss": "revo-auth",
                "aud": "revo-api",
                "typ": ACCESS_TOKEN_TYPE,
                "exp": int(time.time()) + 600,
                "iat": int(time.time()),
                "jti": "x",
            },
            SECRET,
            algorithm="HS256",
        )

        with pytest.raises(TokenError):
            issuer.verify(inventado)

    def test_rechaza_basura(self, issuer):
        for entrada in ["", "   ", "no.es.un.token", "Bearer algo", None]:
            with pytest.raises(TokenError):
                issuer.verify(entrada)


class TestSecretoDebil:
    def test_un_secreto_corto_no_arranca_el_servicio(self):
        with pytest.raises(ValueError):
            TokenIssuer(secret="corto", issuer="revo-auth", audience="revo-api")

    def test_un_secreto_de_ejemplo_no_arranca_el_servicio(self):
        with pytest.raises(ValueError):
            TokenIssuer(secret="cambia_esta_password" * 3, issuer="revo-auth", audience="revo-api")


class TestExtraccionDeCabecera:
    def test_lee_el_esquema_bearer(self, issuer):
        token = issuer.issue(user_id=5, role="student")

        assert issuer.verify_header(f"Bearer {token}").user_id == 5

    def test_acepta_bearer_en_cualquier_capitalizacion(self, issuer):
        token = issuer.issue(user_id=5, role="student")

        assert issuer.verify_header(f"bearer {token}").user_id == 5

    def test_rechaza_una_cabecera_sin_esquema(self, issuer):
        token = issuer.issue(user_id=5, role="student")

        with pytest.raises(TokenError):
            issuer.verify_header(token)

    def test_rechaza_una_cabecera_ausente(self, issuer):
        with pytest.raises(TokenError):
            issuer.verify_header(None)
