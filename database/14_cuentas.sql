-- ============================================================
-- REVO DB - Script 14: verificacion de correo, recuperacion de
--                      contrasena y acceso con Google
-- ============================================================
-- Tres funciones nuevas que comparten la misma necesidad: emitir un secreto
-- de un solo uso, entregarlo por un canal aparte (el correo) y consumirlo.
--
-- Reglas que se aplican a todos los secretos de este fichero:
--
--   1. NUNCA se guardan en claro. Se guarda el SHA-256. Si alguien se lleva
--      un volcado de la base, no se lleva codigos utilizables.
--   2. Caducan. Un codigo de recuperacion que vale para siempre es una
--      contrasena permanente que el alumno no sabe que tiene.
--   3. Son de un solo uso. Se marcan como consumidos al usarlos.
--   4. Se cuentan los intentos fallidos. Un codigo de 6 digitos son un
--      millon de combinaciones; sin limite de intentos se agota en minutos.
-- ============================================================

-- ------------------------------------------------------------
-- 1. Columnas nuevas en users
-- ------------------------------------------------------------

-- Un usuario que entra solo con Google no tiene contrasena. La columna era
-- NOT NULL, asi que sin esto no cabe en el esquema.
ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ,
    -- 'password', 'google', o 'password+google' cuando la cuenta esta
    -- vinculada a las dos formas de entrar.
    ADD COLUMN IF NOT EXISTS auth_provider VARCHAR(20) NOT NULL DEFAULT 'password',
    -- El identificador estable de Google. NO se usa el correo como clave:
    -- un correo se puede reasignar dentro de una organizacion, el `sub` no
    -- cambia nunca para la misma cuenta.
    ADD COLUMN IF NOT EXISTS google_sub VARCHAR(64),
    -- Se incrementa al cambiar la contrasena. Los tokens llevan esta version
    -- dentro; cuando no coincide, dejan de valer.
    --
    -- Sin esto, una recuperacion de contrasena no expulsa a nadie: los JWT
    -- son autocontenidos y el token robado sigue funcionando hasta 24 horas
    -- despues de que la victima crea haber recuperado su cuenta.
    ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 1;

-- Dos cuentas no pueden compartir el mismo Google. El indice es parcial
-- porque la mayoria de filas tendran google_sub nulo.
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub
    ON users(google_sub) WHERE google_sub IS NOT NULL;

DO $comprobar_proveedor$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'users_auth_provider_valido'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT users_auth_provider_valido
            CHECK (auth_provider IN ('password', 'google', 'password+google'));
    END IF;

    -- Una cuenta tiene que poder entrar de alguna forma: o tiene contrasena,
    -- o tiene Google. Sin esta regla, un fallo de logica puede dejar cuentas
    -- a las que nadie puede acceder nunca.
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'users_puede_entrar'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT users_puede_entrar
            CHECK (password_hash IS NOT NULL OR google_sub IS NOT NULL);
    END IF;
END
$comprobar_proveedor$;

-- Las cuentas que ya existian se dan por verificadas: se crearon antes de
-- que existiera la verificacion y bloquearlas ahora seria expulsar a gente
-- que lleva meses usando la plataforma.
-- Mismo motivo que en la migracion 12: users tiene FORCE ROW LEVEL SECURITY,
-- asi que sin contexto de admin este UPDATE no toca ninguna fila cuando el
-- dueno no es superusuario. No daria error, simplemente no haria nada, y las
-- cuentas antiguas quedarian sin verificar sin que nadie se entere.
SELECT set_config('revo.role', 'admin', false);

UPDATE users
SET email_verified = TRUE, email_verified_at = created_at
WHERE email_verified = FALSE AND created_at < NOW();

SELECT set_config('revo.role', '', false);

-- ------------------------------------------------------------
-- 2. Codigos de verificacion de correo
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_verification_codes (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- SHA-256 del codigo de 6 digitos. Nunca el codigo.
    code_hash   CHAR(64)    NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    attempts    SMALLINT    NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address  INET
);

-- La consulta de siempre: el codigo vigente de este alumno.
CREATE INDEX IF NOT EXISTS idx_verif_vigente
    ON email_verification_codes(user_id, expires_at)
    WHERE consumed_at IS NULL;

-- ------------------------------------------------------------
-- 3. Tokens de recuperacion de contrasena
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- Aqui el secreto es largo y aleatorio (no 6 digitos): viaja en un
    -- enlace, asi que no hay que teclearlo y no tiene sentido acortarlo.
    token_hash  CHAR(64)    NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address  INET
);

CREATE INDEX IF NOT EXISTS idx_reset_hash
    ON password_reset_tokens(token_hash) WHERE consumed_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_reset_usuario
    ON password_reset_tokens(user_id, created_at DESC);

-- ------------------------------------------------------------
-- 4. Limpieza de secretos caducados
-- ------------------------------------------------------------
-- Un codigo caducado ya no sirve para nada, pero sigue siendo un dato
-- asociado a una persona. Se borra, no se conserva "por si acaso".
CREATE OR REPLACE FUNCTION revo_limpiar_secretos_caducados()
RETURNS TABLE (codigos_borrados INTEGER, tokens_borrados INTEGER)
LANGUAGE plpgsql SECURITY DEFINER AS
$fn$
DECLARE
    v_codigos INTEGER;
    v_tokens  INTEGER;
BEGIN
    DELETE FROM email_verification_codes
    WHERE expires_at < NOW() - INTERVAL '1 day';
    GET DIAGNOSTICS v_codigos = ROW_COUNT;

    DELETE FROM password_reset_tokens
    WHERE expires_at < NOW() - INTERVAL '1 day';
    GET DIAGNOSTICS v_tokens = ROW_COUNT;

    RETURN QUERY SELECT v_codigos, v_tokens;
END
$fn$;

ALTER FUNCTION revo_limpiar_secretos_caducados() SET search_path = public, pg_temp;
REVOKE ALL ON FUNCTION revo_limpiar_secretos_caducados() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION revo_limpiar_secretos_caducados() TO revo_app, revo_service;

-- ------------------------------------------------------------
-- 5. Alta o vinculacion de una cuenta de Google
-- ------------------------------------------------------------
-- La politica de vinculacion, decidida a proposito:
--
--   - Si el `sub` de Google ya esta en una cuenta, se entra a esa.
--   - Si el correo existe Y ESTA VERIFICADO, se vincula.
--   - Si el correo existe pero NO esta verificado, se rechaza.
--
-- La tercera regla es la que importa. Sin ella, cualquiera registra
-- "director@universidad.pe" sin verificarlo, espera a que el dueno real
-- entre con Google, y hereda una cuenta preparada de antemano.
CREATE OR REPLACE FUNCTION revo_entrar_con_google(
    p_google_sub TEXT,
    p_email      TEXT,
    p_full_name  TEXT,
    p_avatar_url TEXT DEFAULT NULL
)
RETURNS TABLE (user_id INTEGER, es_nuevo BOOLEAN, motivo TEXT)
LANGUAGE plpgsql SECURITY DEFINER AS
$fn$
DECLARE
    v_email TEXT := lower(trim(p_email));
    v_id       INTEGER;
    v_verified BOOLEAN;
    v_activo   BOOLEAN;
BEGIN
    IF p_google_sub IS NULL OR p_google_sub = '' OR v_email IS NULL OR v_email = '' THEN
        RETURN QUERY SELECT NULL::INTEGER, FALSE, 'datos_incompletos'::TEXT;
        RETURN;
    END IF;

    -- ¿Ya conocemos esta cuenta de Google?
    SELECT u.id, u.is_active INTO v_id, v_activo
    FROM users u WHERE u.google_sub = p_google_sub;

    IF v_id IS NOT NULL THEN
        IF NOT v_activo THEN
            RETURN QUERY SELECT NULL::INTEGER, FALSE, 'cuenta_desactivada'::TEXT;
            RETURN;
        END IF;
        UPDATE users SET updated_at = NOW() WHERE id = v_id;
        RETURN QUERY SELECT v_id, FALSE, 'ok'::TEXT;
        RETURN;
    END IF;

    -- ¿Existe ya una cuenta con ese correo?
    SELECT u.id, u.email_verified, u.is_active INTO v_id, v_verified, v_activo
    FROM users u WHERE lower(u.email) = v_email;

    IF v_id IS NOT NULL THEN
        IF NOT v_activo THEN
            RETURN QUERY SELECT NULL::INTEGER, FALSE, 'cuenta_desactivada'::TEXT;
            RETURN;
        END IF;

        IF NOT v_verified THEN
            -- Se niega la vinculacion automatica: ver el comentario de arriba.
            RETURN QUERY SELECT NULL::INTEGER, FALSE, 'correo_sin_verificar'::TEXT;
            RETURN;
        END IF;

        UPDATE users
        SET google_sub = p_google_sub,
            auth_provider = CASE
                WHEN password_hash IS NOT NULL THEN 'password+google'
                ELSE 'google'
            END,
            avatar_url = COALESCE(users.avatar_url, p_avatar_url),
            updated_at = NOW()
        WHERE id = v_id;

        RETURN QUERY SELECT v_id, FALSE, 'vinculada'::TEXT;
        RETURN;
    END IF;

    -- Cuenta nueva. Google ya ha verificado el correo, asi que entra
    -- verificado: pedirle un codigo al alumno seria repetir una prueba que
    -- Google acaba de hacer.
    INSERT INTO users (
        email, password_hash, full_name, role, google_sub,
        auth_provider, email_verified, email_verified_at, avatar_url
    )
    VALUES (
        v_email, NULL, COALESCE(NULLIF(trim(p_full_name), ''), 'Alumno'),
        'student', p_google_sub, 'google', TRUE, NOW(), p_avatar_url
    )
    RETURNING id INTO v_id;

    RETURN QUERY SELECT v_id, TRUE, 'creada'::TEXT;
END
$fn$;

ALTER FUNCTION revo_entrar_con_google(TEXT, TEXT, TEXT, TEXT)
    SET search_path = public, pg_temp;
REVOKE ALL ON FUNCTION revo_entrar_con_google(TEXT, TEXT, TEXT, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION revo_entrar_con_google(TEXT, TEXT, TEXT, TEXT) TO revo_app;

-- ------------------------------------------------------------
-- 6. Buscar una cuenta para recuperar la contrasena
-- ------------------------------------------------------------
-- Igual que el login: la tabla users esta cerrada sin contexto, asi que hace
-- falta una funcion acotada. Devuelve lo justo y solo por correo exacto.
CREATE OR REPLACE FUNCTION revo_cuenta_para_recuperar(p_email TEXT)
RETURNS TABLE (id INTEGER, full_name VARCHAR, is_active BOOLEAN, tiene_password BOOLEAN)
LANGUAGE sql SECURITY DEFINER STABLE AS
$fn$
    SELECT u.id, u.full_name, u.is_active, (u.password_hash IS NOT NULL)
    FROM users u
    WHERE lower(u.email) = lower(trim(p_email))
    LIMIT 1
$fn$;

ALTER FUNCTION revo_cuenta_para_recuperar(TEXT) SET search_path = public, pg_temp;
REVOKE ALL ON FUNCTION revo_cuenta_para_recuperar(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION revo_cuenta_para_recuperar(TEXT) TO revo_app;

-- ------------------------------------------------------------
-- 6b. Emitir un token de recuperacion
-- ------------------------------------------------------------
-- Quien pide recuperar la contrasena no tiene sesion, asi que no hay
-- contexto RLS y la tabla esta cerrada. Toda escritura pasa por aqui.
--
-- Se anulan los tokens anteriores sin consumir: si se pueden pedir varios y
-- todos siguen valiendo, cada correo antiguo que quede en un buzon sigue
-- siendo una llave de la cuenta.
CREATE OR REPLACE FUNCTION revo_emitir_token_recuperacion(
    p_user_id    INTEGER,
    p_token_hash TEXT,
    p_minutos    INTEGER DEFAULT 30,
    p_ip         TEXT DEFAULT NULL
)
RETURNS BOOLEAN
LANGUAGE plpgsql SECURITY DEFINER AS
$fn$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM users WHERE id = p_user_id AND is_active) THEN
        RETURN FALSE;
    END IF;

    UPDATE password_reset_tokens
    SET consumed_at = NOW()
    WHERE user_id = p_user_id AND consumed_at IS NULL;

    INSERT INTO password_reset_tokens (user_id, token_hash, expires_at, ip_address)
    VALUES (
        p_user_id,
        p_token_hash,
        NOW() + make_interval(mins => GREATEST(1, LEAST(p_minutos, 120))),
        p_ip::INET
    );

    RETURN TRUE;
END
$fn$;

ALTER FUNCTION revo_emitir_token_recuperacion(INTEGER, TEXT, INTEGER, TEXT)
    SET search_path = public, pg_temp;
REVOKE ALL ON FUNCTION revo_emitir_token_recuperacion(INTEGER, TEXT, INTEGER, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION revo_emitir_token_recuperacion(INTEGER, TEXT, INTEGER, TEXT) TO revo_app;

-- Cuantos tokens se han pedido para esta cuenta en la ultima hora. El rate
-- limit de la aplicacion cuenta por IP y por correo, pero esto cierra el
-- caso de pedir recuperacion desde muchas IPs para inundar un buzon.
CREATE OR REPLACE FUNCTION revo_recuperaciones_recientes(p_user_id INTEGER)
RETURNS INTEGER
LANGUAGE sql SECURITY DEFINER STABLE AS
$fn$
    SELECT count(*)::INTEGER FROM password_reset_tokens
    WHERE user_id = p_user_id AND created_at > NOW() - INTERVAL '1 hour'
$fn$;

ALTER FUNCTION revo_recuperaciones_recientes(INTEGER) SET search_path = public, pg_temp;
REVOKE ALL ON FUNCTION revo_recuperaciones_recientes(INTEGER) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION revo_recuperaciones_recientes(INTEGER) TO revo_app;

-- ------------------------------------------------------------
-- 7. Consumir un token de recuperacion y cambiar la contrasena
-- ------------------------------------------------------------
-- Todo en una sola funcion y una sola transaccion a proposito: comprobar el
-- token, cambiar la contrasena, marcarlo consumido, invalidar los demas
-- tokens y subir token_version. Si esto se hiciera en varios pasos desde la
-- aplicacion, una carrera entre dos peticiones podria dejar un token vivo.
CREATE OR REPLACE FUNCTION revo_consumir_token_recuperacion(
    p_token_hash    TEXT,
    p_password_hash TEXT
)
RETURNS TABLE (user_id INTEGER, motivo TEXT)
LANGUAGE plpgsql SECURITY DEFINER AS
$fn$
DECLARE
    v_id INTEGER;
BEGIN
    SELECT t.user_id INTO v_id
    FROM password_reset_tokens t
    WHERE t.token_hash = p_token_hash
      AND t.consumed_at IS NULL
      AND t.expires_at > NOW()
    -- FOR UPDATE: si llegan dos peticiones con el mismo token a la vez,
    -- la segunda espera y encuentra el token ya consumido.
    FOR UPDATE;

    IF v_id IS NULL THEN
        RETURN QUERY SELECT NULL::INTEGER, 'token_invalido'::TEXT;
        RETURN;
    END IF;

    UPDATE users
    SET password_hash = p_password_hash,
        -- Aqui se expulsa a quien tuviera un token robado.
        token_version = token_version + 1,
        auth_provider = CASE
            WHEN google_sub IS NOT NULL THEN 'password+google'
            ELSE 'password'
        END,
        -- Recuperar la contrasena por correo demuestra que se controla el
        -- buzon, que es exactamente lo que verifica el codigo de alta.
        email_verified = TRUE,
        email_verified_at = COALESCE(email_verified_at, NOW()),
        updated_at = NOW()
    WHERE id = v_id;

    -- Se cualifica la columna: el parametro de salida tambien se llama
    -- user_id y sin el prefijo PostgreSQL no sabe a cual se refiere.
    UPDATE password_reset_tokens t
    SET consumed_at = NOW()
    WHERE t.user_id = v_id AND t.consumed_at IS NULL;

    RETURN QUERY SELECT v_id, 'ok'::TEXT;
END
$fn$;

ALTER FUNCTION revo_consumir_token_recuperacion(TEXT, TEXT)
    SET search_path = public, pg_temp;
REVOKE ALL ON FUNCTION revo_consumir_token_recuperacion(TEXT, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION revo_consumir_token_recuperacion(TEXT, TEXT) TO revo_app;

-- ------------------------------------------------------------
-- 8. RLS de las tablas nuevas
-- ------------------------------------------------------------
ALTER TABLE email_verification_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_verification_codes FORCE ROW LEVEL SECURITY;
ALTER TABLE password_reset_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE password_reset_tokens FORCE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE ON email_verification_codes TO revo_app;
GRANT SELECT, INSERT, UPDATE ON password_reset_tokens TO revo_app;
GRANT USAGE, SELECT ON SEQUENCE email_verification_codes_id_seq TO revo_app;
GRANT USAGE, SELECT ON SEQUENCE password_reset_tokens_id_seq TO revo_app;

-- El alumno puede ver y consumir sus propios codigos. Nadie mas, ni siquiera
-- un administrador: un admin que pudiera leer los codigos de verificacion
-- podria entrar en cualquier cuenta.
DROP POLICY IF EXISTS codigos_propios ON email_verification_codes;
CREATE POLICY codigos_propios ON email_verification_codes FOR ALL
    USING (revo_es_alumno(user_id))
    WITH CHECK (revo_es_alumno(user_id));

-- Los tokens de recuperacion se emiten y consumen SIN sesion (el alumno no
-- puede entrar, por eso los pide). Toda la manipulacion pasa por las
-- funciones SECURITY DEFINER de arriba, asi que la politica de la tabla
-- puede cerrarse del todo: nadie los lee directamente.
DROP POLICY IF EXISTS tokens_cerrados ON password_reset_tokens;
CREATE POLICY tokens_cerrados ON password_reset_tokens FOR ALL
    USING (false) WITH CHECK (false);

-- ------------------------------------------------------------
-- 9. Comprobacion
-- ------------------------------------------------------------
DO $verificacion$
DECLARE
    faltan TEXT := '';
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='users' AND column_name='token_version') THEN
        faltan := faltan || 'users.token_version ';
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='users' AND column_name='password_hash'
                 AND is_nullable='NO') THEN
        faltan := faltan || 'password_hash sigue siendo NOT NULL ';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'revo_entrar_con_google') THEN
        faltan := faltan || 'revo_entrar_con_google ';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'revo_consumir_token_recuperacion') THEN
        faltan := faltan || 'revo_consumir_token_recuperacion ';
    END IF;

    IF faltan <> '' THEN
        RAISE EXCEPTION 'La migracion 14 no quedo completa: %', faltan;
    END IF;

    RAISE NOTICE 'Cuentas listas: verificacion de correo, recuperacion y Google';
END
$verificacion$;
