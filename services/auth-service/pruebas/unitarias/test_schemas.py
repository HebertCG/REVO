"""Pruebas unitarias de los contratos de entrada del auth-service."""
import pytest
from pydantic import ValidationError

from schemas import (
    ActualizarConsentimiento,
    LoginRequest,
    RegisterRequest,
    UpdateProfileRequest,
)


def registro_valido(**cambios):
    datos = {
        "email": "alumno@uni.pe",
        "password": "ClaveSegura2026!",
        "full_name": "Alumno de Prueba",
        "accept_terms": True,
    }
    datos.update(cambios)
    return datos


class TestRegistro:
    def test_normaliza_los_datos_antes_de_guardarlos(self):
        entrada = RegisterRequest(
            **registro_valido(
                email="  Alumno@UNI.PE ",
                full_name="  Alumno   de   Prueba  ",
                student_code="  U2026001  ",
            )
        )

        assert entrada.email == "alumno@uni.pe"
        assert entrada.full_name == "Alumno de Prueba"
        assert entrada.student_code == "U2026001"

    def test_un_codigo_vacio_se_convierte_en_ausente(self):
        entrada = RegisterRequest(**registro_valido(student_code="   "))

        assert entrada.student_code is None

    def test_los_consentimientos_opcionales_nacen_desmarcados(self):
        entrada = RegisterRequest(**registro_valido())

        assert entrada.consent_data_commercial is False
        assert entrada.consent_ai_training is False

    def test_sin_aceptar_los_documentos_obligatorios_no_hay_registro(self):
        with pytest.raises(ValidationError, match="Debes aceptar"):
            RegisterRequest(**registro_valido(accept_terms=False))

    @pytest.mark.parametrize(
        "contrasena",
        [
            "1234567890",
            "soloalfabetica",
            "password1",
            "Corta1!",
        ],
    )
    def test_rechaza_contrasenas_debiles(self, contrasena):
        with pytest.raises(ValidationError):
            RegisterRequest(**registro_valido(password=contrasena))

    def test_la_contrasena_no_puede_ser_el_correo(self):
        correo = "alumno2026@uni.pe"

        with pytest.raises(ValidationError, match="igual a tu correo"):
            RegisterRequest(**registro_valido(email=correo, password=correo.upper()))

    @pytest.mark.parametrize("semestre", [0, 13])
    def test_el_semestre_debe_pertenecer_al_plan_de_estudios(self, semestre):
        with pytest.raises(ValidationError):
            RegisterRequest(**registro_valido(semester=semestre))


class TestLogin:
    def test_normaliza_el_correo(self):
        entrada = LoginRequest(email="  Alumno@UNI.PE ", password="x")

        assert entrada.email == "alumno@uni.pe"


class TestActualizacionDePerfil:
    @pytest.mark.parametrize(
        "url",
        ["javascript:alert(1)", "data:image/svg+xml;base64,PHN2Zz4=", "ftp://sitio.test/a.png"],
    )
    def test_rechaza_esquemas_peligrosos_para_el_avatar(self, url):
        with pytest.raises(ValidationError, match="http"):
            UpdateProfileRequest(avatar_url=url)

    def test_acepta_y_limpia_una_url_https(self):
        entrada = UpdateProfileRequest(avatar_url="  https://cdn.test/avatar.png  ")

        assert entrada.avatar_url == "https://cdn.test/avatar.png"

    def test_un_avatar_vacio_se_convierte_en_ausente(self):
        assert UpdateProfileRequest(avatar_url="  ").avatar_url is None


class TestActualizacionDeConsentimiento:
    @pytest.mark.parametrize("tipo", ["terms", "privacy", "inventado"])
    def test_solo_permite_cambiar_finalidades_opcionales(self, tipo):
        with pytest.raises(ValidationError):
            ActualizarConsentimiento(doc_type=tipo, granted=False)

    @pytest.mark.parametrize("tipo", ["data_commercial", "ai_training"])
    def test_permite_cambiar_cada_finalidad_opcional(self, tipo):
        entrada = ActualizarConsentimiento(doc_type=tipo, granted=True)

        assert entrada.doc_type == tipo
        assert entrada.granted is True
