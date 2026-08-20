-- Verificacion de las politicas RLS contra un Postgres real.
-- Cada bloque afirma un comportamiento; si alguno falla, RAISE EXCEPTION.
\set ON_ERROR_STOP on

-- ---- Datos de partida (como dueno, antes de asumir revo_app) ----
INSERT INTO users (id, email, password_hash, full_name, role)
VALUES (1, 'ana@uni.pe', 'hash-ana', 'Ana Alumna', 'student'),
       (2, 'beto@uni.pe', 'hash-beto', 'Beto Alumno', 'student')
ON CONFLICT (id) DO NOTHING;

-- El admin se inserta con contexto de admin, porque la politica de alta
-- solo deja crear alumnos sin contexto.
SELECT set_config('revo.role', 'admin', false);
INSERT INTO users (id, email, password_hash, full_name, role)
VALUES (3, 'admin@uni.pe', 'hash-admin', 'Admin', 'admin')
ON CONFLICT (id) DO NOTHING;
SELECT set_config('revo.role', '', false);

SELECT setval('users_id_seq', 10);

INSERT INTO questionnaire_sessions (id, user_id, status, phase)
VALUES (100, 1, 'in_progress', 1), (200, 2, 'in_progress', 1)
ON CONFLICT (id) DO NOTHING;
SELECT setval('questionnaire_sessions_id_seq', 300);

-- answers tambien tiene FORCE RLS, asi que ni el dueno inserta sin
-- contexto: hay que sembrar cada respuesta como su propio alumno.
SELECT set_config('revo.user_id', '1', false);
SELECT set_config('revo.role', 'student', false);
INSERT INTO answers (session_id, question_id, value)
SELECT 100, q.id, 4 FROM questions q ORDER BY q.id LIMIT 1;

SELECT set_config('revo.user_id', '2', false);
INSERT INTO answers (session_id, question_id, value)
SELECT 200, q.id, 5 FROM questions q ORDER BY q.id LIMIT 1;

SELECT set_config('revo.user_id', '', false);
SELECT set_config('revo.role', '', false);

INSERT INTO ml_training_data (aff_1, specialization_id, source)
VALUES (0.9, 1, 'synthetic');

-- Ana rechaza el entrenamiento; Beto lo autoriza. Es el caso que decide si
-- el consentimiento opcional sirve de algo.
INSERT INTO user_consents (user_id, doc_type, doc_version, granted, ip_address)
VALUES (1, 'terms', '1.0', true, '200.60.1.1'),
       (1, 'ai_training', '1.0', false, '200.60.1.1'),
       (2, 'terms', '1.0', true, '200.60.1.2'),
       (2, 'ai_training', '1.0', true, '200.60.1.2')
ON CONFLICT DO NOTHING;

-- ============================================================
SET ROLE revo_app;
-- ============================================================

DO $verificar$
DECLARE
    visto INTEGER;
BEGIN
    -- ---- 1. Sin contexto no se ve ningun alumno ----
    PERFORM set_config('revo.user_id', '', true);
    PERFORM set_config('revo.role', '', true);
    SELECT count(*) INTO visto FROM users;
    IF visto <> 0 THEN
        RAISE EXCEPTION 'FALLO 1: sin contexto se ven % usuarios (debia ser 0)', visto;
    END IF;
    RAISE NOTICE 'OK 1  - sin contexto no se ve ningun usuario';

    -- ---- 2. Ana solo se ve a si misma ----
    PERFORM set_config('revo.user_id', '1', true);
    PERFORM set_config('revo.role', 'student', true);
    SELECT count(*) INTO visto FROM users;
    IF visto <> 1 THEN
        RAISE EXCEPTION 'FALLO 2: Ana ve % usuarios (debia ser 1)', visto;
    END IF;
    SELECT count(*) INTO visto FROM users WHERE email = 'beto@uni.pe';
    IF visto <> 0 THEN
        RAISE EXCEPTION 'FALLO 2b: Ana puede leer la fila de Beto';
    END IF;
    RAISE NOTICE 'OK 2  - un alumno solo se ve a si mismo';

    -- ---- 3. El admin los ve a todos ----
    PERFORM set_config('revo.user_id', '3', true);
    PERFORM set_config('revo.role', 'admin', true);
    SELECT count(*) INTO visto FROM users;
    IF visto < 3 THEN
        RAISE EXCEPTION 'FALLO 3: el admin solo ve % usuarios', visto;
    END IF;
    RAISE NOTICE 'OK 3  - el admin ve a todos los usuarios';

    -- ---- 4. Ana no ve la sesion de Beto ----
    PERFORM set_config('revo.user_id', '1', true);
    PERFORM set_config('revo.role', 'student', true);
    SELECT count(*) INTO visto FROM questionnaire_sessions;
    IF visto <> 1 THEN
        RAISE EXCEPTION 'FALLO 4: Ana ve % sesiones (debia ser 1)', visto;
    END IF;
    RAISE NOTICE 'OK 4  - un alumno solo ve sus propias sesiones';

    -- ---- 5. Aunque pida la sesion de Beto por id, no aparece ----
    SELECT count(*) INTO visto FROM questionnaire_sessions WHERE id = 200;
    IF visto <> 0 THEN
        RAISE EXCEPTION 'FALLO 5: Ana alcanza la sesion 200 de Beto por id directo';
    END IF;
    RAISE NOTICE 'OK 5  - pedir la sesion ajena por id no la devuelve';

    -- ---- 6. Las respuestas siguen a la sesion ----
    SELECT count(*) INTO visto FROM answers;
    IF visto <> 1 THEN
        RAISE EXCEPTION 'FALLO 6: Ana ve % respuestas (debia ser 1)', visto;
    END IF;
    RAISE NOTICE 'OK 6  - un alumno solo ve las respuestas de sus sesiones';

    -- ---- 7. Ana no puede escribir respuestas en la sesion de Beto ----
    BEGIN
        INSERT INTO answers (session_id, question_id, value)
        SELECT 200, q.id, 1 FROM questions q OFFSET 1 LIMIT 1;
        RAISE EXCEPTION 'FALLO 7: Ana pudo escribir en la sesion de Beto';
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE 'OK 7  - escribir en la sesion ajena queda bloqueado';
    END;

    -- ---- 8. Ana no puede crear una sesion a nombre de Beto ----
    BEGIN
        INSERT INTO questionnaire_sessions (user_id, status, phase) VALUES (2, 'in_progress', 1);
        RAISE EXCEPTION 'FALLO 8: Ana pudo crear una sesion para Beto';
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE 'OK 8  - crear una sesion a nombre de otro queda bloqueado';
    END;

    -- ---- 9. Ningun alumno lee el dataset que se quiere monetizar ----
    SELECT count(*) INTO visto FROM ml_training_data;
    IF visto <> 0 THEN
        RAISE EXCEPTION 'FALLO 9: un alumno lee % filas del dataset', visto;
    END IF;
    RAISE NOTICE 'OK 9  - el dataset de entrenamiento es invisible para el alumno';

    -- ---- 10. El servicio de entrenamiento si lo lee ----
    PERFORM set_config('revo.user_id', '0', true);
    PERFORM set_config('revo.role', 'service', true);
    SELECT count(*) INTO visto FROM ml_training_data;
    IF visto < 1 THEN
        RAISE EXCEPTION 'FALLO 10: el servicio no puede leer el dataset';
    END IF;
    RAISE NOTICE 'OK 10 - el rol de servicio si lee el dataset';

    -- ---- 11. Nadie se da de alta como administrador ----
    PERFORM set_config('revo.user_id', '', true);
    PERFORM set_config('revo.role', '', true);
    BEGIN
        INSERT INTO users (email, password_hash, full_name, role)
        VALUES ('atacante@uni.pe', 'x', 'Atacante', 'admin');
        RAISE EXCEPTION 'FALLO 11: se pudo crear un usuario admin desde el registro';
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE 'OK 11 - el registro no permite crear administradores';
    END;

    -- ---- 12. El registro normal si funciona ----
    INSERT INTO users (email, password_hash, full_name, role)
    VALUES ('nuevo@uni.pe', 'x', 'Nuevo Alumno', 'student');
    RAISE NOTICE 'OK 12 - el registro de un alumno sigue funcionando';

    -- ---- 13. El login lee credenciales sin abrir la tabla ----
    SELECT count(*) INTO visto FROM revo_credenciales_por_email('ana@uni.pe');
    IF visto <> 1 THEN
        RAISE EXCEPTION 'FALLO 13: el login no puede recuperar credenciales';
    END IF;
    RAISE NOTICE 'OK 13 - el login recupera credenciales sin contexto previo';

    -- ---- 14. Esa funcion no sirve para volcar la tabla ----
    SELECT count(*) INTO visto FROM revo_credenciales_por_email('%');
    IF visto <> 0 THEN
        RAISE EXCEPTION 'FALLO 14: la funcion de login acepta comodines';
    END IF;
    RAISE NOTICE 'OK 14 - la funcion de login no acepta comodines';

    -- ---- 15. Los catalogos publicos se leen sin identidad ----
    SELECT count(*) INTO visto FROM specializations;
    IF visto < 1 THEN
        RAISE EXCEPTION 'FALLO 15: no se pueden leer las especializaciones';
    END IF;
    RAISE NOTICE 'OK 15 - los catalogos publicos se leen sin identidad';

    -- ---- 16. Pero un alumno no los modifica ----
    PERFORM set_config('revo.user_id', '1', true);
    PERFORM set_config('revo.role', 'student', true);
    BEGIN
        UPDATE specializations SET name = 'Secuestrada' WHERE id = 1;
        IF FOUND THEN
            RAISE EXCEPTION 'FALLO 16: un alumno modifico el catalogo';
        END IF;
        RAISE NOTICE 'OK 16 - un alumno no modifica el catalogo';
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE 'OK 16 - un alumno no modifica el catalogo';
    END;

    -- ---- 17. Los consentimientos son privados ----
    PERFORM set_config('revo.user_id', '1', true);
    PERFORM set_config('revo.role', 'student', true);
    SELECT count(*) INTO visto FROM user_consents WHERE user_id = 2;
    IF visto <> 0 THEN
        RAISE EXCEPTION 'FALLO 17: Ana alcanza los consentimientos de Beto';
    END IF;
    RAISE NOTICE 'OK 17 - los consentimientos ajenos son invisibles';

    -- ---- 18. Nadie consiente en nombre de otro ----
    BEGIN
        INSERT INTO user_consents (user_id, doc_type, doc_version, granted)
        VALUES (2, 'data_commercial', '1.0', true);
        RAISE EXCEPTION 'FALLO 18: Ana consintio en nombre de Beto';
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE 'OK 18 - nadie puede consentir en nombre de otro';
    END;

    -- ---- 19. Los documentos legales se leen sin cuenta ----
    -- Hay que poder leerlos ANTES de registrarse: se aceptan en el alta.
    PERFORM set_config('revo.user_id', '', true);
    PERFORM set_config('revo.role', '', true);
    SELECT count(*) INTO visto FROM legal_documents WHERE is_current;
    IF visto <> 4 THEN
        RAISE EXCEPTION 'FALLO 19: se ven % documentos vigentes (debian ser 4)', visto;
    END IF;
    RAISE NOTICE 'OK 19 - los 4 documentos legales se leen sin tener cuenta';

    -- ---- 20. El entrenamiento solo alcanza a quien lo autorizo ----
    -- Es la comprobacion que hace real al consentimiento opcional: si el
    -- servicio viera a Ana, la casilla no serviria de nada.
    PERFORM set_config('revo.user_id', '0', true);
    PERFORM set_config('revo.role', 'service', true);
    SELECT count(*) INTO visto
    FROM user_consent_state WHERE doc_type = 'ai_training' AND vigente;
    IF visto <> 1 THEN
        RAISE EXCEPTION 'FALLO 20: el servicio ve % autorizaciones de entrenamiento (debia ser 1)', visto;
    END IF;
    RAISE NOTICE 'OK 20 - el entrenamiento solo alcanza a quien lo autorizo';

    RAISE NOTICE '--- TODAS LAS COMPROBACIONES DE RLS PASARON ---';
END
$verificar$;
