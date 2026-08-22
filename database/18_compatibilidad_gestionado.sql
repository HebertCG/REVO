-- ============================================================
-- REVO DB - Script 18: compatibilidad con Postgres gestionado
-- ============================================================
-- PROBLEMA QUE RESUELVE
--
-- En un Postgres local, el dueno de la base (revo_user) es SUPERUSUARIO, y
-- los superusuarios se saltan RLS siempre. En un Postgres gestionado
-- (Supabase, Neon, RDS) el usuario que te dan NO es superusuario.
--
-- Eso rompe las funciones SECURITY DEFINER, que corren con los permisos del
-- dueno: con FORCE ROW LEVEL SECURITY activo, las politicas les aplican y
-- devuelven cero filas. El sintoma es que revo_credenciales_por_email no
-- encuentra nunca las credenciales y NADIE PUEDE INICIAR SESION. Sin error,
-- sin traza: simplemente ninguna contrasena funciona.
--
-- Detectado simulando un dueno sin superusuario antes de desplegar.
--
-- POR QUE QUITAR FORCE ES CORRECTO Y NO UN PARCHE
--
-- FORCE sirve para que las politicas apliquen tambien al dueno. Eso tenia
-- sentido cuando los servicios se conectaban como dueno; desde la migracion
-- 15 cada servicio entra con su propio rol, que no es dueno y no tiene
-- BYPASSRLS, asi que las politicas le aplican igual.
--
-- Contra el dueno, FORCE no aporta seguridad real: quien puede conectarse
-- como dueno puede ejecutar DROP POLICY o DISABLE ROW LEVEL SECURITY. La
-- proteccion frente a ese nivel de acceso no es RLS, es no repartir esa
-- credencial.
--
-- Se quita SOLO en las tres tablas que las funciones SECURITY DEFINER
-- necesitan alcanzar. En el resto, FORCE se queda.
-- ============================================================

-- users: la tocan revo_credenciales_por_email, revo_crear_alumno,
-- revo_entrar_con_google, revo_cuenta_para_recuperar y
-- revo_consumir_token_recuperacion.
ALTER TABLE users NO FORCE ROW LEVEL SECURITY;

-- password_reset_tokens: su politica es USING(false), asi que TODA operacion
-- pasa por revo_emitir_token_recuperacion y revo_consumir_token_recuperacion.
ALTER TABLE password_reset_tokens NO FORCE ROW LEVEL SECURITY;

-- email_verification_codes: mismo caso cuando se conecten los endpoints de
-- verificacion, que tambien iran por funcion acotada.
ALTER TABLE email_verification_codes NO FORCE ROW LEVEL SECURITY;

-- ------------------------------------------------------------
-- Comprobacion
-- ------------------------------------------------------------
DO $verificacion$
DECLARE
    problemas TEXT := '';
    t         RECORD;
BEGIN
    -- Las tres siguen con RLS ACTIVO: lo que cambia es solo si aplica al
    -- dueno, no si aplica a los servicios.
    FOR t IN
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname IN ('users', 'password_reset_tokens', 'email_verification_codes')
    LOOP
        IF NOT t.relrowsecurity THEN
            problemas := problemas || format(' %s-sin-RLS', t.relname);
        END IF;
        IF t.relforcerowsecurity THEN
            problemas := problemas || format(' %s-sigue-con-FORCE', t.relname);
        END IF;
    END LOOP;

    -- El resto de tablas de alumnos conserva FORCE.
    FOR t IN
        SELECT c.relname
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname IN ('questionnaire_sessions', 'answers', 'predictions',
                            'ml_training_data', 'user_consents')
          AND NOT c.relforcerowsecurity
    LOOP
        problemas := problemas || format(' %s-perdio-FORCE', t.relname);
    END LOOP;

    IF problemas <> '' THEN
        RAISE EXCEPTION 'La compatibilidad no quedo bien:%', problemas;
    END IF;

    RAISE NOTICE 'Compatible con Postgres gestionado: RLS activo, funciones internas operativas';
END
$verificacion$;
