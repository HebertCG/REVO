-- ============================================================
-- REVO DB - Script 15: un rol de base de datos por servicio
-- ============================================================
-- Hasta ahora los tres servicios entraban con el mismo rol, revo_app, que
-- tenia permisos sobre las 19 tablas. La regla de "cada tabla la escribe un
-- solo servicio" era una convencion del codigo, no una frontera: comprobado
-- ejecutando dentro del contenedor del cuestionario un SELECT sobre users,
-- ml_training_data y user_consents. Las tres consultas funcionaron.
--
-- Eso tiene dos consecuencias:
--
--   Arquitectura. El dia que alguien tenga prisa escribira un SELECT a users
--   dentro de survey-service porque funciona, y nadie se enterara hasta que
--   auth-service cambie el esquema y el cuestionario se rompa sin motivo
--   aparente. La frontera solo es real si el motor la impone.
--
--   Seguridad. El radio de dano de comprometer cualquier servicio era la base
--   entera. Con roles separados, entrar en ml-service da las tablas de ML y
--   nada mas.
--
-- Esto NO parte la base de datos. Sigue habiendo una sola instancia de
-- PostgreSQL; lo que se anade es la frontera dentro de ella.
--
-- Reparto, deducido de los modelos que declara cada servicio:
--
--   revo_auth    users, user_consents, legal_documents,
--                email_verification_codes, admin_actions_log
--   revo_survey  questionnaire_sessions, answers, questions,
--                courses, jobs, psychometric_questions
--   revo_ml      predictions, prediction_feedbacks, ml_training_data,
--                model_training_logs, specializations
--   revo_service (ya existia) tareas de fondo: entrenamiento del modelo
-- ============================================================

-- ------------------------------------------------------------
-- 1. Los tres roles
-- ------------------------------------------------------------
-- Sin contrasena aqui: la asigna 16_asignar_passwords.sh desde el entorno.
DO $roles$
DECLARE
    rol TEXT;
BEGIN
    FOREACH rol IN ARRAY ARRAY['revo_auth', 'revo_survey', 'revo_ml'] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = rol) THEN
            EXECUTE format(
                'CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS',
                rol
            );
        END IF;
    END LOOP;
END
$roles$;

GRANT USAGE ON SCHEMA public TO revo_auth, revo_survey, revo_ml;
REVOKE CREATE ON SCHEMA public FROM revo_auth, revo_survey, revo_ml;

-- ------------------------------------------------------------
-- 2. auth-service: identidad y consentimiento
-- ------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE ON users             TO revo_auth;
GRANT SELECT, INSERT, UPDATE ON user_consents     TO revo_auth;
GRANT SELECT                  ON user_consent_state TO revo_auth;
GRANT SELECT, INSERT, UPDATE ON legal_documents   TO revo_auth;
GRANT SELECT, INSERT, UPDATE ON email_verification_codes TO revo_auth;
GRANT SELECT, INSERT          ON admin_actions_log TO revo_auth;

GRANT USAGE, SELECT ON SEQUENCE users_id_seq                     TO revo_auth;
GRANT USAGE, SELECT ON SEQUENCE user_consents_id_seq             TO revo_auth;
GRANT USAGE, SELECT ON SEQUENCE legal_documents_id_seq           TO revo_auth;
GRANT USAGE, SELECT ON SEQUENCE email_verification_codes_id_seq  TO revo_auth;
GRANT USAGE, SELECT ON SEQUENCE admin_actions_log_id_seq         TO revo_auth;

-- password_reset_tokens NO se concede: su politica esta cerrada y todo pasa
-- por funciones SECURITY DEFINER. El rol solo necesita ejecutarlas.
GRANT EXECUTE ON FUNCTION revo_credenciales_por_email(TEXT)                     TO revo_auth;
GRANT EXECUTE ON FUNCTION revo_crear_alumno(TEXT, TEXT, TEXT, TEXT, INTEGER)    TO revo_auth;
GRANT EXECUTE ON FUNCTION revo_entrar_con_google(TEXT, TEXT, TEXT, TEXT)        TO revo_auth;
GRANT EXECUTE ON FUNCTION revo_cuenta_para_recuperar(TEXT)                      TO revo_auth;
GRANT EXECUTE ON FUNCTION revo_emitir_token_recuperacion(INTEGER, TEXT, INTEGER, TEXT) TO revo_auth;
GRANT EXECUTE ON FUNCTION revo_consumir_token_recuperacion(TEXT, TEXT)          TO revo_auth;
GRANT EXECUTE ON FUNCTION revo_recuperaciones_recientes(INTEGER)                TO revo_auth;

-- ------------------------------------------------------------
-- 3. survey-service: el cuestionario y sus catalogos
-- ------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE ON questionnaire_sessions TO revo_survey;
GRANT SELECT, INSERT, UPDATE ON answers                TO revo_survey;
GRANT SELECT                  ON questions             TO revo_survey;
GRANT SELECT                  ON courses               TO revo_survey;
GRANT SELECT                  ON jobs                  TO revo_survey;
GRANT SELECT                  ON psychometric_questions TO revo_survey;

GRANT USAGE, SELECT ON SEQUENCE questionnaire_sessions_id_seq TO revo_survey;
GRANT USAGE, SELECT ON SEQUENCE answers_id_seq                TO revo_survey;

-- Nada de users, predictions, ml_training_data ni user_consents: el
-- cuestionario recibe la identidad ya verificada en el token y no necesita
-- consultar la tabla de usuarios para nada.

-- ------------------------------------------------------------
-- 4. ml-service: el modelo
-- ------------------------------------------------------------
GRANT SELECT, INSERT ON predictions          TO revo_ml;
GRANT SELECT, INSERT ON prediction_feedbacks TO revo_ml;
GRANT SELECT, INSERT ON ml_training_data     TO revo_ml;
GRANT SELECT, INSERT ON model_training_logs  TO revo_ml;
GRANT SELECT         ON specializations      TO revo_ml;

GRANT USAGE, SELECT ON SEQUENCE predictions_id_seq          TO revo_ml;
GRANT USAGE, SELECT ON SEQUENCE prediction_feedbacks_id_seq TO revo_ml;
GRANT USAGE, SELECT ON SEQUENCE ml_training_data_id_seq     TO revo_ml;
GRANT USAGE, SELECT ON SEQUENCE model_training_logs_id_seq  TO revo_ml;

-- El panel de administracion cuenta consentimientos vigentes para saber
-- cuantos alumnos autorizaron el uso de sus datos. Solo lectura de la vista,
-- que ya esta filtrada por RLS.
GRANT SELECT ON user_consent_state TO revo_ml;

-- ------------------------------------------------------------
-- 5. Cerrar el rol antiguo
-- ------------------------------------------------------------
-- revo_app deja de tener acceso. No se borra el rol para no romper una
-- conexion viva durante el despliegue, pero se queda sin permisos: si algo
-- lo sigue usando, fallara de forma ruidosa y visible en vez de seguir
-- funcionando con permisos de mas.
DO $cerrar$
DECLARE
    t RECORD;
BEGIN
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE format('REVOKE ALL ON %I FROM revo_app', t.tablename);
    END LOOP;

    FOR t IN SELECT sequencename FROM pg_sequences WHERE schemaname = 'public' LOOP
        EXECUTE format('REVOKE ALL ON SEQUENCE %I FROM revo_app', t.sequencename);
    END LOOP;

    FOR t IN SELECT viewname FROM pg_views WHERE schemaname = 'public' LOOP
        EXECUTE format('REVOKE ALL ON %I FROM revo_app', t.viewname);
    END LOOP;
END
$cerrar$;

REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM revo_app;

-- ------------------------------------------------------------
-- 6. Comprobacion: la frontera existe de verdad
-- ------------------------------------------------------------
-- No basta con haber escrito los GRANT. Se comprueba que cada rol NO alcanza
-- lo que no le toca, porque un GRANT olvidado no da error, da acceso.
DO $verificacion$
DECLARE
    problemas TEXT := '';

    -- (rol, tabla) que NO deben tener ningun privilegio.
    prohibido CONSTANT TEXT[][] := ARRAY[
        ['revo_survey', 'users'],
        ['revo_survey', 'user_consents'],
        ['revo_survey', 'ml_training_data'],
        ['revo_survey', 'predictions'],
        ['revo_ml',     'users'],
        ['revo_ml',     'answers'],
        ['revo_ml',     'questionnaire_sessions'],
        ['revo_ml',     'user_consents'],
        ['revo_auth',   'answers'],
        ['revo_auth',   'ml_training_data'],
        ['revo_auth',   'predictions'],
        ['revo_app',    'users']
    ];

    -- (rol, tabla) que SI deben funcionar.
    necesario CONSTANT TEXT[][] := ARRAY[
        ['revo_auth',   'users'],
        ['revo_auth',   'user_consents'],
        ['revo_survey', 'answers'],
        ['revo_survey', 'questions'],
        ['revo_ml',     'predictions'],
        ['revo_ml',     'ml_training_data']
    ];

    i INTEGER;
BEGIN
    FOR i IN 1 .. array_length(prohibido, 1) LOOP
        IF has_table_privilege(prohibido[i][1], prohibido[i][2], 'SELECT') THEN
            problemas := problemas || format(
                E'\n  - %s alcanza %s y no deberia', prohibido[i][1], prohibido[i][2]
            );
        END IF;
    END LOOP;

    FOR i IN 1 .. array_length(necesario, 1) LOOP
        IF NOT has_table_privilege(necesario[i][1], necesario[i][2], 'SELECT') THEN
            problemas := problemas || format(
                E'\n  - %s NO alcanza %s y lo necesita', necesario[i][1], necesario[i][2]
            );
        END IF;
    END LOOP;

    IF problemas <> '' THEN
        RAISE EXCEPTION 'Los permisos por servicio no quedaron bien:%', problemas;
    END IF;

    RAISE NOTICE 'Frontera por servicio activa: cada rol solo alcanza sus tablas';
END
$verificacion$;
