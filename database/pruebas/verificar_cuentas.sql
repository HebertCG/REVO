-- Verificacion de la migracion 14: verificacion de correo, recuperacion de
-- contrasena y acceso con Google.
--
-- Se ejecuta como revo_verificacion, un rol de PRUEBAS que reune los
-- permisos de los tres servicios (ver verificar_rls.sh). No existe en
-- produccion: alli cada servicio tiene su propio rol acotado. Se usa aqui
-- porque estas comprobaciones cruzan los tres dominios, para que las politicas
-- RLS apliquen. Cada bloque afirma un comportamiento; si alguno falla,
-- RAISE EXCEPTION y el guion sale con error.
--
-- CUIDADO al escribir comprobaciones aqui: leer `users` sin contexto RLS no
-- da error, da CERO FILAS, y un `SELECT ... INTO` sobre cero filas deja la
-- variable en NULL. Un `IF NOT variable_nula THEN ... fallo ...` nunca salta,
-- asi que la prueba pasa sin haber comprobado nada. Por eso toda lectura de
-- `users` fija antes contexto de admin y afirma que la variable no es nula.
\set ON_ERROR_STOP on

-- Este guion corre despues del de RLS sobre la misma base, asi que empieza
-- limpiando. No se usa ON CONFLICT: sobre una tabla con RLS, PostgreSQL
-- necesita ver la fila en conflicto para resolverlo, y sin contexto la
-- politica de SELECT no deja ver nada.
SELECT set_config('revo.role', 'admin', false);
TRUNCATE users CASCADE;
SELECT set_config('revo.role', '', false);

-- El dueno tiene que ser miembro del rol para poder asumirlo. Un dueno
-- superusuario puede hacer SET ROLE hacia cualquiera y esto no hacia falta;
-- en un Postgres gestionado el dueno no es superusuario y sin esto falla con
-- 'permission denied to set role'.
DO $membresia$
BEGIN
    EXECUTE format('GRANT revo_verificacion TO %I', current_user);
EXCEPTION WHEN OTHERS THEN
    NULL;  -- ya es miembro, o es superusuario y no lo necesita
END
$membresia$;

SET ROLE revo_verificacion;

DO $verificar$
DECLARE
    r          RECORD;
    v_ana      INTEGER;
    v_google   INTEGER;
    v_antes    INTEGER;
    v_despues  INTEGER;
    n          INTEGER;
    v_bool     BOOLEAN;
    v_texto    TEXT;
    v_hash     TEXT := encode(sha256('token-de-prueba'::bytea), 'hex');
    v_segundo  TEXT := encode(sha256('segundo-token'::bytea), 'hex');
BEGIN
    -- ── Preparacion ─────────────────────────────────────────
    -- (La limpieza previa la hace el guion que invoca a este.)
    SELECT * INTO r FROM revo_crear_alumno('ana.cuentas@uni.pe', 'hash', 'Ana', NULL, 7);
    v_ana := r.nuevo_id;

    -- Verificar el correo lo hace el propio alumno tras meter su codigo, asi
    -- que se simula con SU contexto: sin identidad, RLS no deja tocar la fila.
    PERFORM set_config('revo.user_id', v_ana::text, true);
    PERFORM set_config('revo.role', 'student', true);
    UPDATE users SET email_verified = TRUE WHERE id = v_ana;
    PERFORM set_config('revo.user_id', '', true);
    PERFORM set_config('revo.role', '', true);

    PERFORM set_config('revo.role', 'admin', true);
    SELECT email_verified INTO v_bool FROM users WHERE id = v_ana;
    PERFORM set_config('revo.role', '', true);
    IF v_bool IS NOT TRUE THEN
        RAISE EXCEPTION 'La preparacion fallo: Ana no quedo verificada, el resto no valdria';
    END IF;

    -- Un correo ajeno registrado por alguien que NO lo controla.
    PERFORM revo_crear_alumno('victima.cuentas@uni.pe', 'hash', 'Impostor', NULL, 7);

    -- ══ Google ══════════════════════════════════════════════

    SELECT * INTO r FROM revo_entrar_con_google('g-nuevo', 'nuevo.cuentas@uni.pe', 'Nuevo', NULL);
    IF NOT r.es_nuevo OR r.motivo <> 'creada' THEN
        RAISE EXCEPTION 'FALLO 1: Google no creo la cuenta (%)', r.motivo;
    END IF;
    v_google := r.user_id;
    RAISE NOTICE 'OK 1  - Google crea la cuenta';

    PERFORM set_config('revo.role', 'admin', true);
    SELECT email_verified INTO v_bool FROM users WHERE id = v_google;
    PERFORM set_config('revo.role', '', true);
    IF v_bool IS NULL THEN RAISE EXCEPTION 'FALLO 2a: no se pudo leer la fila'; END IF;
    IF NOT v_bool THEN
        RAISE EXCEPTION 'FALLO 2: la cuenta de Google no quedo verificada';
    END IF;
    RAISE NOTICE 'OK 2  - no se pide codigo a quien llega verificado por Google';

    PERFORM set_config('revo.role', 'admin', true);
    SELECT count(*) INTO n FROM users WHERE id = v_google AND password_hash IS NOT NULL;
    PERFORM set_config('revo.role', '', true);
    IF n <> 0 THEN
        RAISE EXCEPTION 'FALLO 3: se invento una contrasena para una cuenta de Google';
    END IF;
    RAISE NOTICE 'OK 3  - una cuenta de Google vive sin contrasena';

    SELECT * INTO r FROM revo_entrar_con_google('g-nuevo', 'nuevo.cuentas@uni.pe', 'Nuevo', NULL);
    IF r.es_nuevo OR r.user_id <> v_google THEN
        RAISE EXCEPTION 'FALLO 4: reentrar duplico la cuenta';
    END IF;
    RAISE NOTICE 'OK 4  - reentrar reconoce la cuenta, no la duplica';

    SELECT * INTO r FROM revo_entrar_con_google('g-ana', 'ana.cuentas@uni.pe', 'Ana', NULL);
    IF r.motivo <> 'vinculada' OR r.user_id <> v_ana THEN
        RAISE EXCEPTION 'FALLO 5: no vinculo un correo verificado (%)', r.motivo;
    END IF;
    RAISE NOTICE 'OK 5  - se vincula al correo verificado y conserva el historial';

    PERFORM set_config('revo.role', 'admin', true);
    SELECT auth_provider INTO v_texto FROM users WHERE id = v_ana;
    PERFORM set_config('revo.role', '', true);
    IF v_texto IS NULL THEN RAISE EXCEPTION 'FALLO 6a: no se pudo leer la fila'; END IF;
    IF v_texto <> 'password+google' THEN
        RAISE EXCEPTION 'FALLO 6: la cuenta vinculada quedo como %', v_texto;
    END IF;
    RAISE NOTICE 'OK 6  - la cuenta vinculada admite las dos formas de entrar';

    -- El caso que decide el diseno: sin esta regla, cualquiera registra un
    -- correo ajeno sin verificarlo y hereda la cuenta cuando el dueno real
    -- entra con Google.
    SELECT * INTO r FROM revo_entrar_con_google('g-atacante', 'victima.cuentas@uni.pe', 'X', NULL);
    IF r.motivo <> 'correo_sin_verificar' THEN
        RAISE EXCEPTION 'FALLO 7: APROPIACION POSIBLE, vinculo un correo sin verificar (%)', r.motivo;
    END IF;
    RAISE NOTICE 'OK 7  - no se hereda una cuenta cuyo correo nadie verifico';

    BEGIN
        PERFORM set_config('revo.user_id', v_ana::text, true);
        PERFORM set_config('revo.role', 'student', true);
        UPDATE users SET google_sub = 'g-nuevo' WHERE id = v_ana;
        RAISE EXCEPTION 'FALLO 8: dos cuentas comparten el mismo Google';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'OK 8  - un Google solo puede estar en una cuenta';
    END;
    PERFORM set_config('revo.user_id', '', true);
    PERFORM set_config('revo.role', '', true);

    -- ══ Recuperacion de contrasena ══════════════════════════

    SELECT c.id INTO n FROM revo_cuenta_para_recuperar('ana.cuentas@uni.pe') c;
    IF n IS NULL THEN RAISE EXCEPTION 'FALLO 9: no localiza la cuenta'; END IF;
    RAISE NOTICE 'OK 9  - se localiza la cuenta sin tener sesion';

    SELECT count(*) INTO n FROM revo_cuenta_para_recuperar('noexiste@uni.pe');
    IF n <> 0 THEN RAISE EXCEPTION 'FALLO 10'; END IF;
    RAISE NOTICE 'OK 10 - un correo inexistente no devuelve nada';

    -- Con contexto de admin: sin identidad RLS no devuelve la fila y
    -- v_antes seria NULL, con lo que la comprobacion de abajo compararia
    -- nulos y pasaria sin comprobar nada.
    PERFORM set_config('revo.role', 'admin', true);
    SELECT token_version INTO v_antes FROM users WHERE id = v_ana;
    PERFORM set_config('revo.role', '', true);

    IF v_antes IS NULL THEN
        RAISE EXCEPTION 'FALLO 11a: no se pudo leer token_version, la prueba no valdria';
    END IF;

    IF NOT revo_emitir_token_recuperacion(v_ana, v_hash, 30, '200.60.1.1') THEN
        RAISE EXCEPTION 'FALLO 11: no emitio el token';
    END IF;
    RAISE NOTICE 'OK 11 - se emite el token de recuperacion';

    -- Cada correo antiguo que quede en un buzon dejaria de ser una llave.
    PERFORM revo_emitir_token_recuperacion(v_ana, v_segundo, 30, NULL);
    SELECT * INTO r FROM revo_consumir_token_recuperacion(v_hash, 'x');
    IF r.motivo <> 'token_invalido' THEN
        RAISE EXCEPTION 'FALLO 12: el token viejo sigue valiendo tras pedir otro';
    END IF;
    RAISE NOTICE 'OK 12 - pedir un token nuevo anula el anterior';

    SELECT * INTO r FROM revo_consumir_token_recuperacion(v_segundo, 'hash-nuevo');
    IF r.motivo <> 'ok' THEN RAISE EXCEPTION 'FALLO 13 (%)', r.motivo; END IF;
    RAISE NOTICE 'OK 13 - el token vigente cambia la contrasena';

    PERFORM set_config('revo.role', 'admin', true);
    SELECT token_version INTO v_despues FROM users WHERE id = v_ana;
    PERFORM set_config('revo.role', '', true);

    IF v_despues IS NULL THEN
        RAISE EXCEPTION 'FALLO 14a: no se pudo releer token_version';
    END IF;
    IF v_despues <= v_antes THEN
        RAISE EXCEPTION 'FALLO 14: token_version no subio; un token robado seguiria valiendo 24h';
    END IF;
    RAISE NOTICE 'OK 14 - token_version sube % a %: los tokens robados caducan al instante', v_antes, v_despues;

    SELECT * INTO r FROM revo_consumir_token_recuperacion(v_segundo, 'y');
    IF r.motivo <> 'token_invalido' THEN RAISE EXCEPTION 'FALLO 15: reutilizable'; END IF;
    RAISE NOTICE 'OK 15 - el token es de un solo uso';

    PERFORM revo_emitir_token_recuperacion(v_ana, encode(sha256('cad'::bytea),'hex'), 1, NULL);
    -- Para envejecer el token hay que salirse de revo_app: la politica cierra
    -- la tabla incluso al dueno, que es justo lo que afirma la prueba 19.
    EXECUTE 'RESET ROLE';
    UPDATE password_reset_tokens SET expires_at = NOW() - INTERVAL '1 minute'
    WHERE token_hash = encode(sha256('cad'::bytea),'hex');
    EXECUTE 'SET ROLE revo_verificacion';
    SELECT * INTO r FROM revo_consumir_token_recuperacion(encode(sha256('cad'::bytea),'hex'), 'z');
    IF r.motivo <> 'token_invalido' THEN RAISE EXCEPTION 'FALLO 16: acepto uno caducado'; END IF;
    RAISE NOTICE 'OK 16 - un token caducado no sirve';

    PERFORM set_config('revo.role', 'admin', true);
    SELECT email_verified INTO v_bool FROM users WHERE id = v_ana;
    PERFORM set_config('revo.role', '', true);
    IF v_bool IS NULL THEN RAISE EXCEPTION 'FALLO 17a: no se pudo leer la fila'; END IF;
    IF NOT v_bool THEN
        RAISE EXCEPTION 'FALLO 17: recuperar no conto como verificar el correo';
    END IF;
    RAISE NOTICE 'OK 17 - recuperar por correo demuestra el control del buzon';

    IF revo_recuperaciones_recientes(v_ana) < 3 THEN
        RAISE EXCEPTION 'FALLO 18: no cuenta las solicitudes recientes';
    END IF;
    RAISE NOTICE 'OK 18 - se pueden contar las recuperaciones pedidas (%)',
        revo_recuperaciones_recientes(v_ana);

    -- ══ Aislamiento de los secretos ═════════════════════════

    -- Doble cierre: la politica RLS devuelve cero filas Y ningun rol de
    -- servicio tiene privilegio sobre la tabla. Cualquiera de los dos vale;
    -- lo que no puede pasar es que se lean tokens.
    BEGIN
        SELECT count(*) INTO n FROM password_reset_tokens;
        IF n <> 0 THEN
            RAISE EXCEPTION 'FALLO 19: los tokens de recuperacion se pueden leer (% filas)', n;
        END IF;
        RAISE NOTICE 'OK 19 - la politica deja la tabla de tokens en cero filas';
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE 'OK 19 - ningun rol tiene siquiera permiso sobre la tabla de tokens';
    END;

    PERFORM set_config('revo.user_id', v_google::text, true);
    PERFORM set_config('revo.role', 'student', true);
    INSERT INTO email_verification_codes (user_id, code_hash, expires_at)
    VALUES (v_google, encode(sha256('123456'::bytea),'hex'), NOW() + INTERVAL '10 minutes');

    PERFORM set_config('revo.user_id', v_ana::text, true);
    SELECT count(*) INTO n FROM email_verification_codes;
    IF n <> 0 THEN
        RAISE EXCEPTION 'FALLO 20: un alumno ve los codigos de verificacion de otro';
    END IF;
    RAISE NOTICE 'OK 20 - los codigos de verificacion de otro alumno son invisibles';

    PERFORM set_config('revo.user_id', '', true);
    PERFORM set_config('revo.role', 'admin', true);
    SELECT count(*) INTO n FROM email_verification_codes;
    IF n <> 0 THEN
        RAISE EXCEPTION 'FALLO 21: un administrador puede leer codigos y entrar en cualquier cuenta';
    END IF;
    RAISE NOTICE 'OK 21 - ni un administrador puede leer los codigos ajenos';

    RAISE NOTICE '--- CUENTAS: GOOGLE, VERIFICACION Y RECUPERACION CORRECTAS ---';
END
$verificar$;
