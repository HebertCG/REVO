"""
Pruebas de los cupos de acceso del auth-service.

Viven aqui y no en la libreria compartida a proposito: son decisiones de
producto de ESTE servicio. La libreria aporta el mecanismo de conteo; el
numero concreto lo decide y lo defiende quien lo usa.

El caso que gobierna todos estos numeros: un aula de 50 alumnos comparte una
sola IP publica y llega en el mismo minuto.
"""
from politicas import POLITICAS
from revo_comun.limites.politicas import Scope


class TestElAulaEntra:
    def test_el_registro_admite_un_aula_completa_de_golpe(self):
        # Medido contra la instalacion real: con 80 en 10 minutos, los 50
        # alumnos se registran y sobra margen para reintentos.
        registro = POLITICAS["register"]

        assert registro.limit >= 50
        assert registro.window_seconds <= 600

    def test_el_login_por_ip_deja_entrar_a_un_aula_con_reintentos(self):
        assert POLITICAS["login_por_ip"].limit >= 150

    def test_ningun_cupo_de_acceso_se_cierra_si_redis_cae(self):
        # Cerrar el acceso porque Redis tuvo un problema es negarle la clase
        # entera a los alumnos por un fallo de infraestructura.
        for nombre in ("login", "login_por_ip", "register", "register_diario"):
            assert POLITICAS[nombre].fail_open is True, nombre


class TestElAtacanteNo:
    def test_la_fuerza_bruta_contra_una_cuenta_se_frena(self):
        login = POLITICAS["login"]

        assert login.scope is Scope.CREDENTIAL
        assert login.limit <= 10

    def test_el_rociado_de_credenciales_tambien(self):
        # Solo por credencial, un atacante prueba tres claves contra mil
        # cuentas distintas y ningun cupo se entera. Hace falta el de IP.
        assert POLITICAS["login_por_ip"].scope is Scope.IP

    def test_el_registro_masivo_topa_con_el_cupo_sostenido(self):
        rafaga = POLITICAS["register"]
        sostenido = POLITICAS["register_diario"]

        assert sostenido.window_seconds >= 86_400
        # El sostenido tiene que morder: si permitiera tantas cuentas como
        # la rafaga repetida todo el dia, no serviria de nada.
        rafagas_por_dia = 86_400 / rafaga.window_seconds
        assert sostenido.limit < rafaga.limit * rafagas_por_dia


class TestSeparacionDeResponsabilidades:
    def test_este_servicio_no_declara_cupos_ajenos(self):
        # Si aparecen aqui, es que alguien puso en auth un cupo que pertenece
        # al cuestionario o al modelo.
        for ajeno in ("answers", "submit_phase", "predict"):
            assert ajeno not in POLITICAS, ajeno
