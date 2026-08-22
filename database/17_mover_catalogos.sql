-- ============================================================
-- REVO DB - Script 17: cursos y empleos pasan a ml-service
-- ============================================================
-- Auditoria de cohesion: survey-service servia los catalogos de cursos y
-- empleos ademas de ejecutar el cuestionario. Esas rutas no leen sesiones ni
-- respuestas; van indexadas por especializacion, que es lo que produce y ya
-- posee ml-service.
--
-- Los permisos tienen que moverse con el codigo. Si no, quedarian dos
-- mentiras a la vez: survey pudiendo leer tablas que ya no usa, y ml sin
-- poder leer las que ahora sirve.
-- ============================================================

-- ml-service pasa a servirlos.
GRANT SELECT ON courses TO revo_ml;
GRANT SELECT ON jobs    TO revo_ml;

-- survey-service deja de necesitarlos.
REVOKE ALL ON courses FROM revo_survey;
REVOKE ALL ON jobs    FROM revo_survey;

-- ------------------------------------------------------------
-- Comprobacion
-- ------------------------------------------------------------
DO $verificacion$
DECLARE
    problemas TEXT := '';
BEGIN
    IF NOT has_table_privilege('revo_ml', 'courses', 'SELECT') THEN
        problemas := problemas || ' revo_ml-no-alcanza-courses';
    END IF;
    IF NOT has_table_privilege('revo_ml', 'jobs', 'SELECT') THEN
        problemas := problemas || ' revo_ml-no-alcanza-jobs';
    END IF;
    IF has_table_privilege('revo_survey', 'courses', 'SELECT') THEN
        problemas := problemas || ' revo_survey-sigue-alcanzando-courses';
    END IF;
    IF has_table_privilege('revo_survey', 'jobs', 'SELECT') THEN
        problemas := problemas || ' revo_survey-sigue-alcanzando-jobs';
    END IF;

    IF problemas <> '' THEN
        RAISE EXCEPTION 'El traslado de catalogos no quedo bien:%', problemas;
    END IF;

    RAISE NOTICE 'Cursos y empleos ahora los sirve ml-service';
END
$verificacion$;
