-- ============================================================
-- REVO DB - Script 13: alta de alumnos bajo RLS
-- ============================================================
-- Problema que resuelve, encontrado por las pruebas de integracion:
--
--   El registro ocurre SIN identidad (el alumno todavia no existe), asi que
--   la sesion no tiene contexto RLS. Un INSERT plano pasa, porque la
--   politica users_insert solo exige role = 'student'. Pero SQLAlchemy no
--   hace un INSERT plano: hace INSERT ... RETURNING id para recuperar la
--   clave. Y PostgreSQL aplica tambien la politica de SELECT a las filas que
--   devuelve un RETURNING. Sin contexto, users_select es falsa, y el alta
--   revienta con "new row violates row-level security policy".
--
--   Quitar el RETURNING no es opcion (el ORM lo necesita) y relajar
--   users_select tampoco (es lo que impide que un alumno lea a otro).
--
-- Solucion: una unica primitiva privilegiada para el alta, igual que
-- revo_credenciales_por_email lo es para el login. Todo lo demas del
-- registro (el consentimiento) sigue pasando por RLS normal.
--
-- Ventaja adicional: el rol queda fijado a 'student' DENTRO de la funcion.
-- Ya no depende de que la aplicacion se acuerde de no mandar 'admin': es
-- estructuralmente imposible crear un administrador desde el registro.
-- ============================================================

CREATE OR REPLACE FUNCTION revo_crear_alumno(
    p_email         TEXT,
    p_password_hash TEXT,
    p_full_name     TEXT,
    p_student_code  TEXT DEFAULT NULL,
    -- INTEGER y no SMALLINT: psycopg2 manda los enteros de Python como
    -- integer, y PostgreSQL no reduce el tipo al resolver que funcion
    -- llamar. Con SMALLINT la llamada falla con "function does not exist",
    -- que es un mensaje que no lleva a ninguna parte. El rango real lo
    -- sigue imponiendo el CHECK de la columna.
    p_semester      INTEGER DEFAULT NULL
)
RETURNS TABLE (nuevo_id INTEGER, motivo TEXT)
LANGUAGE plpgsql SECURITY DEFINER AS
$fn$
DECLARE
    v_email TEXT := lower(trim(p_email));
    v_id    INTEGER;
BEGIN
    IF v_email IS NULL OR v_email = '' THEN
        RETURN QUERY SELECT NULL::INTEGER, 'email_invalido'::TEXT;
        RETURN;
    END IF;

    IF EXISTS (SELECT 1 FROM users u WHERE lower(u.email) = v_email) THEN
        RETURN QUERY SELECT NULL::INTEGER, 'email_duplicado'::TEXT;
        RETURN;
    END IF;

    IF p_student_code IS NOT NULL AND EXISTS (
        SELECT 1 FROM users u WHERE u.student_code = p_student_code
    ) THEN
        RETURN QUERY SELECT NULL::INTEGER, 'codigo_duplicado'::TEXT;
        RETURN;
    END IF;

    -- El rol va escrito aqui, no llega como parametro. Es la razon principal
    -- de que esta funcion exista.
    INSERT INTO users (email, password_hash, full_name, student_code, semester, role)
    VALUES (v_email, p_password_hash, p_full_name, p_student_code,
            p_semester::SMALLINT, 'student')
    RETURNING id INTO v_id;

    RETURN QUERY SELECT v_id, NULL::TEXT;
END
$fn$;

-- SECURITY DEFINER corre con los permisos del dueno. Sin fijar search_path,
-- un esquema controlado por el atacante que este antes en el path puede
-- suplantar a la tabla users que la funcion nombra.
ALTER FUNCTION revo_crear_alumno(TEXT, TEXT, TEXT, TEXT, INTEGER)
    SET search_path = public, pg_temp;

REVOKE ALL ON FUNCTION revo_crear_alumno(TEXT, TEXT, TEXT, TEXT, INTEGER) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION revo_crear_alumno(TEXT, TEXT, TEXT, TEXT, INTEGER) TO revo_app;

DO $verificacion$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'revo_crear_alumno'
    ) THEN
        RAISE EXCEPTION 'La funcion de alta no se creo';
    END IF;
    RAISE NOTICE 'Alta de alumnos disponible bajo RLS';
END
$verificacion$;
