-- ============================================================
-- REVO DB - Script 10: Seguridad a nivel de fila (RLS)
-- ============================================================
-- Hasta ahora los tres microservicios se conectaban como duenos de la base
-- de datos. Cualquier fallo de logica en un endpoint (un WHERE user_id que
-- se olvida, un id que llega por la URL sin comprobar) dejaba leer las filas
-- de cualquier alumno. RLS mueve esa comprobacion de la aplicacion a la base
-- de datos: aunque la consulta pida todo, Postgres solo devuelve lo que a
-- ese alumno le corresponde.
--
-- Dos roles de conexion, ninguno dueno de las tablas:
--   revo_app     - peticiones de alumnos y administradores
--   revo_service - tareas de fondo (reentrenamiento del modelo)
--
-- Importante: el DUENO de una tabla se salta RLS por defecto. Por eso las
-- tablas siguen siendo de revo_user (que solo se usa para migraciones), los
-- servicios entran con revo_app, y ademas se activa FORCE ROW LEVEL SECURITY
-- para que la politica se aplique incluso al dueno.
-- ============================================================

-- ------------------------------------------------------------
-- 1. Roles de conexion
-- ------------------------------------------------------------
-- Se crean sin contrasena a proposito: un secreto escrito en un fichero
-- versionado es un secreto publico. Las contrasenas las asigna
-- database/aplicar_rls.sql tomandolas del entorno.
DO $roles$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'revo_app') THEN
        CREATE ROLE revo_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'revo_service') THEN
        CREATE ROLE revo_service LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
    END IF;
END
$roles$;

-- NOBYPASSRLS es explicito y no redundante: deja escrito que estos roles no
-- pueden saltarse las politicas.

-- ------------------------------------------------------------
-- 2. Funciones que leen el contexto de la transaccion
-- ------------------------------------------------------------
-- La aplicacion fija estos valores con set_config(..., true) al empezar cada
-- transaccion (ver revo_comun/basedatos/contexto.py). El segundo argumento
-- de current_setting en true evita el error cuando el valor no esta puesto.

CREATE OR REPLACE FUNCTION revo_user_id() RETURNS INTEGER
LANGUAGE sql STABLE AS
$fn$
    SELECT NULLIF(current_setting('revo.user_id', true), '')::INTEGER
$fn$;

CREATE OR REPLACE FUNCTION revo_role() RETURNS TEXT
LANGUAGE sql STABLE AS
$fn$
    SELECT COALESCE(NULLIF(current_setting('revo.role', true), ''), 'anon')
$fn$;

CREATE OR REPLACE FUNCTION revo_es_admin() RETURNS BOOLEAN
LANGUAGE sql STABLE AS
$fn$
    SELECT revo_role() = 'admin'
$fn$;

CREATE OR REPLACE FUNCTION revo_es_servicio() RETURNS BOOLEAN
LANGUAGE sql STABLE AS
$fn$
    SELECT revo_role() = 'service'
$fn$;

-- Un alumno identificado. Sin contexto, revo_user_id() es NULL y esto da
-- false: sin identidad no se ve nada.
CREATE OR REPLACE FUNCTION revo_es_alumno(fila_user_id INTEGER) RETURNS BOOLEAN
LANGUAGE sql STABLE AS
$fn$
    SELECT revo_user_id() IS NOT NULL AND fila_user_id = revo_user_id()
$fn$;

-- ------------------------------------------------------------
-- 3. Permisos base
-- ------------------------------------------------------------
-- Se parte de cero: PUBLIC no tiene nada. Cada rol recibe solo lo que usa.
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO revo_app, revo_service;

-- Sin CREATE: los servicios no crean ni alteran tablas. Las migraciones las
-- corre revo_user.
REVOKE CREATE ON SCHEMA public FROM revo_app, revo_service;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO revo_app, revo_service;

-- Lo anterior solo cubre las secuencias que existen AHORA. Sin esto, la
-- primera tabla que anada una migracion posterior tendra su secuencia sin
-- permisos y el INSERT fallara con "permission denied for sequence", que es
-- un error que no apunta a la causa real. Lo detectaron las pruebas de
-- integracion del registro tras anadir user_consents en la migracion 12.
ALTER DEFAULT PRIVILEGES FOR ROLE revo_user IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO revo_app, revo_service;

-- ------------------------------------------------------------
-- 4. users
-- ------------------------------------------------------------
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE ON users TO revo_app;

-- Un alumno solo se ve a si mismo. Un administrador ve a todos.
DROP POLICY IF EXISTS users_select ON users;
CREATE POLICY users_select ON users FOR SELECT
    USING (revo_es_alumno(id) OR revo_es_admin());

-- El alta ocurre antes de que exista identidad, asi que el registro entra
-- sin contexto. Se permite insertar solo filas con rol de alumno: nadie
-- puede darse de alta directamente como administrador.
DROP POLICY IF EXISTS users_insert ON users;
CREATE POLICY users_insert ON users FOR INSERT
    WITH CHECK (role = 'student' OR revo_es_admin());

DROP POLICY IF EXISTS users_update ON users;
CREATE POLICY users_update ON users FOR UPDATE
    USING (revo_es_alumno(id) OR revo_es_admin())
    WITH CHECK (revo_es_alumno(id) OR revo_es_admin());

-- El login necesita leer el hash de una cuenta que todavia no tiene sesion.
-- Se resuelve con una funcion acotada en vez de abriendo la tabla: devuelve
-- una sola fila, por email exacto, y solo las columnas justas para autenticar.
CREATE OR REPLACE FUNCTION revo_credenciales_por_email(p_email TEXT)
RETURNS TABLE (id INTEGER, password_hash VARCHAR, role VARCHAR, is_active BOOLEAN)
LANGUAGE sql SECURITY DEFINER STABLE AS
$fn$
    SELECT u.id, u.password_hash, u.role, u.is_active
    FROM users u
    WHERE lower(u.email) = lower(trim(p_email))
    LIMIT 1
$fn$;

-- SECURITY DEFINER corre con los permisos del dueno, asi que hay que fijar
-- el search_path: sin esto, un esquema controlado por el atacante que este
-- antes en el path puede suplantar a las tablas que la funcion nombra.
ALTER FUNCTION revo_credenciales_por_email(TEXT) SET search_path = public, pg_temp;

REVOKE ALL ON FUNCTION revo_credenciales_por_email(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION revo_credenciales_por_email(TEXT) TO revo_app;

-- ------------------------------------------------------------
-- 5. questionnaire_sessions
-- ------------------------------------------------------------
ALTER TABLE questionnaire_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE questionnaire_sessions FORCE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE ON questionnaire_sessions TO revo_app;

DROP POLICY IF EXISTS sesiones_propias ON questionnaire_sessions;
CREATE POLICY sesiones_propias ON questionnaire_sessions FOR ALL
    USING (revo_es_alumno(user_id) OR revo_es_admin())
    WITH CHECK (revo_es_alumno(user_id));

-- ------------------------------------------------------------
-- 6. answers
-- ------------------------------------------------------------
-- answers no tiene user_id: cuelga de la sesion, asi que la politica navega
-- la relacion. El indice idx_answers_session ya existe y es el que evita que
-- este EXISTS cueste una pasada completa por cada fila.
ALTER TABLE answers ENABLE ROW LEVEL SECURITY;
ALTER TABLE answers FORCE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE ON answers TO revo_app;

DROP POLICY IF EXISTS respuestas_de_mis_sesiones ON answers;
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

-- ------------------------------------------------------------
-- 7. predictions
-- ------------------------------------------------------------
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions FORCE ROW LEVEL SECURITY;

GRANT SELECT, INSERT ON predictions TO revo_app;
-- El entrenamiento cuenta cuantas predicciones nuevas hay desde el ultimo.
GRANT SELECT ON predictions TO revo_service;

DROP POLICY IF EXISTS predicciones_propias ON predictions;
CREATE POLICY predicciones_propias ON predictions FOR ALL
    USING (revo_es_alumno(user_id) OR revo_es_admin() OR revo_es_servicio())
    WITH CHECK (revo_es_alumno(user_id));

-- ------------------------------------------------------------
-- 8. prediction_feedbacks y feedback
-- ------------------------------------------------------------
ALTER TABLE prediction_feedbacks ENABLE ROW LEVEL SECURITY;
ALTER TABLE prediction_feedbacks FORCE ROW LEVEL SECURITY;

GRANT SELECT, INSERT ON prediction_feedbacks TO revo_app;
GRANT SELECT ON prediction_feedbacks TO revo_service;

DROP POLICY IF EXISTS feedback_prediccion_propio ON prediction_feedbacks;
CREATE POLICY feedback_prediccion_propio ON prediction_feedbacks FOR ALL
    USING (revo_es_alumno(user_id) OR revo_es_admin() OR revo_es_servicio())
    WITH CHECK (revo_es_alumno(user_id));

ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback FORCE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE ON feedback TO revo_app;

DROP POLICY IF EXISTS feedback_propio ON feedback;
CREATE POLICY feedback_propio ON feedback FOR ALL
    USING (revo_es_alumno(user_id) OR revo_es_admin())
    WITH CHECK (revo_es_alumno(user_id));

-- ------------------------------------------------------------
-- 9. ml_training_data
-- ------------------------------------------------------------
-- Es el activo que se quiere monetizar: el dataset completo. Ningun alumno
-- puede leerlo. Puede APORTAR una fila (cuando confirma su diagnostico),
-- pero no ver ni una sola.
ALTER TABLE ml_training_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE ml_training_data FORCE ROW LEVEL SECURITY;

GRANT SELECT, INSERT ON ml_training_data TO revo_app;
GRANT SELECT, INSERT ON ml_training_data TO revo_service;

DROP POLICY IF EXISTS dataset_lectura ON ml_training_data;
CREATE POLICY dataset_lectura ON ml_training_data FOR SELECT
    USING (revo_es_admin() OR revo_es_servicio());

DROP POLICY IF EXISTS dataset_aporte ON ml_training_data;
CREATE POLICY dataset_aporte ON ml_training_data FOR INSERT
    WITH CHECK (revo_user_id() IS NOT NULL OR revo_es_servicio());

-- ------------------------------------------------------------
-- 10. model_training_logs y admin_actions_log
-- ------------------------------------------------------------
ALTER TABLE model_training_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_training_logs FORCE ROW LEVEL SECURITY;

GRANT SELECT, INSERT ON model_training_logs TO revo_app, revo_service;

DROP POLICY IF EXISTS entrenamientos_restringidos ON model_training_logs;
CREATE POLICY entrenamientos_restringidos ON model_training_logs FOR ALL
    USING (revo_es_admin() OR revo_es_servicio())
    WITH CHECK (revo_es_admin() OR revo_es_servicio());

ALTER TABLE admin_actions_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_actions_log FORCE ROW LEVEL SECURITY;

GRANT SELECT, INSERT ON admin_actions_log TO revo_app;

DROP POLICY IF EXISTS auditoria_admin ON admin_actions_log;
CREATE POLICY auditoria_admin ON admin_actions_log FOR ALL
    USING (revo_es_admin())
    WITH CHECK (revo_es_admin());

-- ------------------------------------------------------------
-- 11. Catalogos publicos
-- ------------------------------------------------------------
-- Preguntas, especializaciones, cursos y empleos los ve cualquiera; solo un
-- administrador los cambia. Se activa RLS igualmente para que la escritura
-- quede cerrada por politica y no solo por permisos.
DO $catalogos$
DECLARE
    tabla TEXT;
BEGIN
    FOREACH tabla IN ARRAY ARRAY[
        'specializations', 'questions', 'courses', 'jobs', 'psychometric_questions'
    ] LOOP
        IF EXISTS (SELECT 1 FROM information_schema.tables
                   WHERE table_schema = 'public' AND table_name = tabla) THEN

            EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tabla);
            EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', tabla);
            EXECUTE format('GRANT SELECT ON %I TO revo_app, revo_service', tabla);
            EXECUTE format('GRANT INSERT, UPDATE, DELETE ON %I TO revo_app', tabla);

            EXECUTE format('DROP POLICY IF EXISTS %I ON %I', tabla || '_lectura', tabla);
            EXECUTE format(
                'CREATE POLICY %I ON %I FOR SELECT USING (true)',
                tabla || '_lectura', tabla
            );

            EXECUTE format('DROP POLICY IF EXISTS %I ON %I', tabla || '_escritura', tabla);
            EXECUTE format(
                'CREATE POLICY %I ON %I FOR ALL USING (revo_es_admin()) WITH CHECK (revo_es_admin())',
                tabla || '_escritura', tabla
            );
        END IF;
    END LOOP;
END
$catalogos$;

-- ------------------------------------------------------------
-- 12. Comprobacion final
-- ------------------------------------------------------------
-- Si alguna tabla con datos de alumnos se queda sin RLS, el arranque falla
-- en vez de desplegar en silencio con un agujero.
DO $verificacion$
DECLARE
    sin_proteger TEXT;
BEGIN
    SELECT string_agg(c.relname, ', ')
    INTO sin_proteger
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relkind = 'r'
      AND c.relname IN (
          'users', 'questionnaire_sessions', 'answers', 'predictions',
          'prediction_feedbacks', 'feedback', 'ml_training_data',
          'model_training_logs', 'admin_actions_log'
      )
      AND NOT c.relrowsecurity;

    IF sin_proteger IS NOT NULL THEN
        RAISE EXCEPTION 'Tablas sin RLS activo: %', sin_proteger;
    END IF;

    RAISE NOTICE 'RLS activo y politicas aplicadas en todas las tablas de alumnos';
END
$verificacion$;
