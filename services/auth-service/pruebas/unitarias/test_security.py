"""Pruebas unitarias del almacenamiento seguro de contrasenas."""
import bcrypt

from security import BCRYPT_MAX_BYTES, hash_password, verify_password


class TestHashDeContrasenas:
    def test_el_hash_no_guarda_la_contrasena_en_claro(self):
        contrasena = "ClaveSegura2026!"

        resultado = hash_password(contrasena)

        assert resultado != contrasena
        assert resultado.startswith("$2b$")
        assert verify_password(contrasena, resultado) is True

    def test_la_contrasena_incorrecta_no_verifica(self):
        resultado = hash_password("ClaveCorrecta2026!")

        assert verify_password("ClaveIncorrecta2026!", resultado) is False

    def test_dos_hashes_de_la_misma_contrasena_no_son_iguales(self):
        contrasena = "ClaveSegura2026!"

        primero = hash_password(contrasena)
        segundo = hash_password(contrasena)

        assert primero != segundo
        assert verify_password(contrasena, primero) is True
        assert verify_password(contrasena, segundo) is True

    def test_acepta_un_hash_bcrypt_ya_existente(self):
        contrasena = "ClaveMigrada2026!"
        existente = bcrypt.hashpw(
            contrasena.encode("utf-8"), bcrypt.gensalt(rounds=4)
        ).decode("ascii")

        assert verify_password(contrasena, existente) is True

    def test_un_hash_vacio_o_corrupto_se_trata_como_login_fallido(self):
        for hash_invalido in ("", "no-es-bcrypt", "$2b$12$incompleto"):
            assert verify_password("ClaveSegura2026!", hash_invalido) is False

    def test_una_contrasena_multibyte_larga_no_supera_el_limite_de_bcrypt(self):
        # Cada enie ocupa dos bytes en UTF-8. bcrypt solo admite 72 bytes.
        contrasena = "n" * (BCRYPT_MAX_BYTES - 2) + "ñ" + "texto-adicional"

        resultado = hash_password(contrasena)

        assert verify_password(contrasena, resultado) is True
