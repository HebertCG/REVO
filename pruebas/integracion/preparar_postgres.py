"""Prepara una base efimera y minima para las pruebas de integracion.

La base real y sus migraciones no forman parte del repositorio publico. Esta
fixture crea solo el contrato que ejercitan las suites: tablas declaradas por
los modelos, catalogos sinteticos, roles por servicio y politicas RLS. No
contiene usuarios reales, contrasenas de produccion ni datos del sistema.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from sqlalchemy import create_engine


RAIZ = Path(__file__).resolve().parents[2]
URL_ADMIN = os.environ.get(
    "REVO_ADMIN_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/revo_test",
)


def cargar_modelos(nombre: str, ruta: Path):
    """Carga cada ``database.py`` con un nombre aislado y devuelve su Base."""
    especificacion = importlib.util.spec_from_file_location(nombre, ruta)
    if especificacion is None or especificacion.loader is None:
        raise RuntimeError(f"No se pudieron cargar los modelos de {ruta}")
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo.Base


DDL_SEGURIDAD = r"""
CREATE EXTENSION IF NOT EXISTS vector;

-- ``revo_crear_alumno`` inserta con SQL, no mediante el ORM. Los defaults
-- de Python no intervienen en esa ruta, por eso el contrato real de la tabla
-- tambien debe existir como defaults del servidor.
ALTER TABLE users ALTER COLUMN role SET DEFAULT 'student';
ALTER TABLE users ALTER COLUMN is_active SET DEFAULT true;

DO $roles$
DECLARE
    rol text;
BEGIN
    FOREACH rol IN ARRAY ARRAY['revo_auth', 'revo_survey', 'revo_ml'] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = rol) THEN
            EXECUTE format(
                'CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS',
                rol, 'revo_ci_password'
            );
        ELSE
            EXECUTE format('ALTER ROLE %I PASSWORD %L', rol, 'revo_ci_password');
        END IF;
    END LOOP;
END
$roles$;

CREATE OR REPLACE FUNCTION revo_user_id() RETURNS integer
LANGUAGE sql STABLE AS $fn$
    SELECT NULLIF(current_setting('revo.user_id', true), '')::integer
$fn$;

CREATE OR REPLACE FUNCTION revo_role() RETURNS text
LANGUAGE sql STABLE AS $fn$
    SELECT COALESCE(NULLIF(current_setting('revo.role', true), ''), 'anon')
$fn$;

CREATE OR REPLACE FUNCTION revo_es_admin() RETURNS boolean
LANGUAGE sql STABLE AS $fn$ SELECT revo_role() = 'admin' $fn$;

CREATE OR REPLACE FUNCTION revo_es_servicio() RETURNS boolean
LANGUAGE sql STABLE AS $fn$ SELECT revo_role() = 'service' $fn$;

CREATE OR REPLACE FUNCTION revo_es_alumno(fila_user_id integer) RETURNS boolean
LANGUAGE sql STABLE AS $fn$
    SELECT revo_user_id() IS NOT NULL AND fila_user_id = revo_user_id()
$fn$;

CREATE OR REPLACE FUNCTION revo_credenciales_por_email(p_email text)
RETURNS TABLE (id integer, password_hash varchar, role varchar, is_active boolean)
LANGUAGE sql SECURITY DEFINER STABLE AS $fn$
    SELECT u.id, u.password_hash, u.role, u.is_active
    FROM users u
    WHERE lower(u.email) = lower(trim(p_email))
    LIMIT 1
$fn$;
ALTER FUNCTION revo_credenciales_por_email(text)
    SET search_path = public, pg_temp;

CREATE OR REPLACE FUNCTION revo_crear_alumno(
    p_email text,
    p_password_hash text,
    p_full_name text,
    p_student_code text DEFAULT NULL,
    p_semester integer DEFAULT NULL
)
RETURNS TABLE (nuevo_id integer, motivo text)
LANGUAGE plpgsql SECURITY DEFINER AS $fn$
DECLARE
    v_email text := lower(trim(p_email));
    v_id integer;
BEGIN
    IF v_email IS NULL OR v_email = '' THEN
        RETURN QUERY SELECT NULL::integer, 'email_invalido'::text;
        RETURN;
    END IF;
    IF EXISTS (SELECT 1 FROM users u WHERE lower(u.email) = v_email) THEN
        RETURN QUERY SELECT NULL::integer, 'email_duplicado'::text;
        RETURN;
    END IF;
    IF p_student_code IS NOT NULL AND EXISTS (
        SELECT 1 FROM users u WHERE u.student_code = p_student_code
    ) THEN
        RETURN QUERY SELECT NULL::integer, 'codigo_duplicado'::text;
        RETURN;
    END IF;

    INSERT INTO users (email, password_hash, full_name, student_code, semester, role)
    VALUES (
        v_email, p_password_hash, p_full_name, p_student_code,
        p_semester::smallint, 'student'
    )
    RETURNING id INTO v_id;

    RETURN QUERY SELECT v_id, NULL::text;
END
$fn$;
ALTER FUNCTION revo_crear_alumno(text, text, text, text, integer)
    SET search_path = public, pg_temp;

REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO revo_auth, revo_survey, revo_ml;
REVOKE CREATE ON SCHEMA public FROM revo_auth, revo_survey, revo_ml;

REVOKE ALL ON FUNCTION revo_credenciales_por_email(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION revo_crear_alumno(text, text, text, text, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION revo_credenciales_por_email(text) TO revo_auth;
GRANT EXECUTE ON FUNCTION revo_crear_alumno(text, text, text, text, integer) TO revo_auth;

GRANT SELECT, INSERT, UPDATE ON users, user_consents, legal_documents TO revo_auth;
GRANT USAGE, SELECT ON SEQUENCE users_id_seq, user_consents_id_seq,
    legal_documents_id_seq TO revo_auth;

GRANT SELECT, INSERT, UPDATE ON questionnaire_sessions, answers,
    psychometric_answers TO revo_survey;
GRANT SELECT ON questions, psychometric_questions TO revo_survey;
GRANT USAGE, SELECT ON SEQUENCE questionnaire_sessions_id_seq,
    answers_id_seq, psychometric_answers_id_seq TO revo_survey;

GRANT SELECT, INSERT ON predictions, prediction_feedbacks, ml_training_data,
    model_training_logs TO revo_ml;
GRANT SELECT ON specializations, courses TO revo_ml;
GRANT USAGE, SELECT ON SEQUENCE predictions_id_seq,
    prediction_feedbacks_id_seq, ml_training_data_id_seq,
    model_training_logs_id_seq TO revo_ml;

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
CREATE POLICY users_select ON users FOR SELECT
    USING (revo_es_alumno(id) OR revo_es_admin());
CREATE POLICY users_update ON users FOR UPDATE
    USING (revo_es_alumno(id) OR revo_es_admin())
    WITH CHECK (revo_es_alumno(id) OR revo_es_admin());

ALTER TABLE legal_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE legal_documents FORCE ROW LEVEL SECURITY;
CREATE POLICY legales_lectura ON legal_documents FOR SELECT USING (true);
CREATE POLICY legales_escritura ON legal_documents FOR ALL
    USING (revo_es_admin()) WITH CHECK (revo_es_admin());

ALTER TABLE user_consents ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_consents FORCE ROW LEVEL SECURITY;
CREATE POLICY consentimientos_propios ON user_consents FOR ALL
    USING (revo_es_alumno(user_id) OR revo_es_admin())
    WITH CHECK (revo_es_alumno(user_id));

ALTER TABLE questionnaire_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE questionnaire_sessions FORCE ROW LEVEL SECURITY;
CREATE POLICY sesiones_propias ON questionnaire_sessions FOR ALL
    USING (revo_es_alumno(user_id) OR revo_es_admin())
    WITH CHECK (revo_es_alumno(user_id));

ALTER TABLE answers ENABLE ROW LEVEL SECURITY;
ALTER TABLE answers FORCE ROW LEVEL SECURITY;
CREATE POLICY respuestas_de_mis_sesiones ON answers FOR ALL
    USING (
        revo_es_admin() OR EXISTS (
            SELECT 1 FROM questionnaire_sessions s
            WHERE s.id = answers.session_id AND revo_es_alumno(s.user_id)
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM questionnaire_sessions s
            WHERE s.id = answers.session_id AND revo_es_alumno(s.user_id)
        )
    );

ALTER TABLE psychometric_answers ENABLE ROW LEVEL SECURITY;
ALTER TABLE psychometric_answers FORCE ROW LEVEL SECURITY;
CREATE POLICY fase3_de_mis_sesiones ON psychometric_answers FOR ALL
    USING (
        revo_es_admin() OR EXISTS (
            SELECT 1 FROM questionnaire_sessions s
            WHERE s.id = psychometric_answers.session_id
              AND revo_es_alumno(s.user_id)
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM questionnaire_sessions s
            WHERE s.id = psychometric_answers.session_id
              AND revo_es_alumno(s.user_id)
        )
    );

ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions FORCE ROW LEVEL SECURITY;
CREATE POLICY predicciones_propias ON predictions FOR ALL
    USING (revo_es_alumno(user_id) OR revo_es_admin() OR revo_es_servicio())
    WITH CHECK (revo_es_alumno(user_id));

ALTER TABLE prediction_feedbacks ENABLE ROW LEVEL SECURITY;
ALTER TABLE prediction_feedbacks FORCE ROW LEVEL SECURITY;
CREATE POLICY feedback_propio ON prediction_feedbacks FOR ALL
    USING (revo_es_alumno(user_id) OR revo_es_admin() OR revo_es_servicio())
    WITH CHECK (revo_es_alumno(user_id));

ALTER TABLE ml_training_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE ml_training_data FORCE ROW LEVEL SECURITY;
CREATE POLICY dataset_lectura ON ml_training_data FOR SELECT
    USING (revo_es_admin() OR revo_es_servicio());
CREATE POLICY dataset_aporte ON ml_training_data FOR INSERT
    WITH CHECK (revo_user_id() IS NOT NULL OR revo_es_servicio());

ALTER TABLE model_training_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_training_logs FORCE ROW LEVEL SECURITY;
CREATE POLICY entrenamientos_restringidos ON model_training_logs FOR ALL
    USING (revo_es_admin() OR revo_es_servicio())
    WITH CHECK (revo_es_admin() OR revo_es_servicio());

ALTER TABLE specializations ENABLE ROW LEVEL SECURITY;
ALTER TABLE specializations FORCE ROW LEVEL SECURITY;
CREATE POLICY specializations_lectura ON specializations FOR SELECT USING (true);

ALTER TABLE questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE questions FORCE ROW LEVEL SECURITY;
CREATE POLICY questions_lectura ON questions FOR SELECT USING (true);

ALTER TABLE psychometric_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE psychometric_questions FORCE ROW LEVEL SECURITY;
CREATE POLICY psychometric_questions_lectura ON psychometric_questions
    FOR SELECT USING (true);

ALTER TABLE courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE courses FORCE ROW LEVEL SECURITY;
CREATE POLICY courses_lectura ON courses FOR SELECT USING (true);
"""


DATOS_SINTETICOS = r"""
INSERT INTO legal_documents
    (doc_type, version, title, summary, body_md, is_required, is_current)
VALUES
    ('terms', 'ci-1', 'Terminos de prueba', 'Resumen de prueba',
     'Documento sintetico para CI.', true, true),
    ('privacy', 'ci-1', 'Privacidad de prueba', 'Resumen de prueba',
     'Politica sintetica conforme a la Ley 29733.', true, true),
    ('data_commercial', 'ci-1', 'Uso comercial de prueba', 'Resumen de prueba',
     'Documento sintetico para CI.', false, true),
    ('ai_training', 'ci-1', 'Entrenamiento de IA de prueba', 'Resumen de prueba',
     'Documento sintetico para CI.', false, true);

INSERT INTO specializations (id, name, slug, icon, color_hex)
SELECT numero, 'Especializacion ' || numero, 'especializacion-' || numero,
       'code', '#336699'
FROM generate_series(1, 10) AS numero;

INSERT INTO questions
    (text, category, specialization_id, order_index, is_active)
SELECT 'Pregunta sintetica ' || rama || '-' || numero,
       'interests', rama, numero, true
FROM generate_series(1, 10) AS rama
CROSS JOIN generate_series(1, 6) AS numero;
"""


def main() -> None:
    motor = create_engine(URL_ADMIN)
    bases = [
        cargar_modelos(
            "revo_ci_auth_database", RAIZ / "services/auth-service/database.py"
        ),
        cargar_modelos(
            "revo_ci_survey_database", RAIZ / "services/survey-service/database.py"
        ),
        cargar_modelos(
            "revo_ci_ml_database", RAIZ / "services/ml-service/database.py"
        ),
    ]

    for base in bases:
        base.metadata.create_all(motor)

    conexion = motor.raw_connection()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(DDL_SEGURIDAD)
            cursor.execute(DATOS_SINTETICOS)
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()
        motor.dispose()

    print("PostgreSQL de integracion preparado con datos sinteticos y RLS")


if __name__ == "__main__":
    main()
