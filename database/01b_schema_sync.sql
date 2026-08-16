-- ============================================================
-- REVO DB - Script 01b: Sincronización de esquema
-- ============================================================
-- 01_init.sql quedó desincronizado respecto a los modelos
-- SQLAlchemy de los servicios. Este script añade lo que falta.
-- Es idempotente: se puede ejecutar sobre una BD existente.
--
-- Sin este script:
--   * 03_seed_questions.sql falla  -> questions queda en 0 filas
--     (el INSERT usa specialization_id, columna que no existía)
--   * 04_seed_training_data.sql falla -> el ML no puede entrenar
--     (la tabla ml_training_data no existía)
--   * survey-service rompe al leer session.phase / session.phase_data
--   * /predict/{id}/feedback rompe (prediction_feedbacks no existía)
--   * courses / jobs / psychometric quedan sin tabla
-- ============================================================


-- ─── questions: falta la columna que usa el motor adaptativo ───
-- survey-service/database.py:20 -> specialization_id (1..10)
ALTER TABLE questions
    ADD COLUMN IF NOT EXISTS specialization_id INTEGER NOT NULL DEFAULT 1;

-- Índice necesario: se filtra por specialization_id en CADA fase del test
-- (sessions.py:69 fase 1, sessions.py:82-85 fase 2)
CREATE INDEX IF NOT EXISTS idx_questions_spec ON questions(specialization_id);


-- ─── questionnaire_sessions: faltan las columnas de fases ──────
-- survey-service/database.py:36-37 -> phase, phase_data
ALTER TABLE questionnaire_sessions
    ADD COLUMN IF NOT EXISTS phase      SMALLINT DEFAULT 1;
ALTER TABLE questionnaire_sessions
    ADD COLUMN IF NOT EXISTS phase_data JSONB    DEFAULT '{}'::jsonb;


-- ─── answers: índice del JOIN con questions ────────────────────
-- submit_phase agrega respuestas por question_id
CREATE INDEX IF NOT EXISTS idx_answers_question ON answers(question_id);


-- ============================================================
-- TABLA: ml_training_data   (ml-service/database.py:12)
-- Dataset de entrenamiento del modelo.
-- ============================================================
CREATE TABLE IF NOT EXISTS ml_training_data (
    id                SERIAL PRIMARY KEY,
    aff_1             NUMERIC(5,4),
    aff_2             NUMERIC(5,4),
    aff_3             NUMERIC(5,4),
    aff_4             NUMERIC(5,4),
    aff_5             NUMERIC(5,4),
    aff_6             NUMERIC(5,4),
    aff_7             NUMERIC(5,4),
    aff_8             NUMERIC(5,4),
    aff_9             NUMERIC(5,4),
    aff_10            NUMERIC(5,4),
    specialization_id INTEGER     NOT NULL,
    source            VARCHAR(50) NOT NULL DEFAULT 'synthetic'
                                  CHECK (source IN ('synthetic','human')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- stats.py:100-105 cuenta por source en cada poll del admin
CREATE INDEX IF NOT EXISTS idx_mltraining_source ON ml_training_data(source);


-- ============================================================
-- TABLA: prediction_feedbacks   (ml-service/database.py:65)
-- Retroalimentación del alumno sobre su predicción.
-- ============================================================
CREATE TABLE IF NOT EXISTS prediction_feedbacks (
    id                  SERIAL PRIMARY KEY,
    prediction_id       INTEGER     NOT NULL UNIQUE
                                    REFERENCES predictions(id) ON DELETE CASCADE,
    user_id             INTEGER     NOT NULL,
    session_id          INTEGER,
    diagnostic_affinity BOOLEAN     NOT NULL,
    discovery_level     VARCHAR(50) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_predfeedback_user ON prediction_feedbacks(user_id);


-- NOTA: courses, jobs y psychometric_questions NO se crean aquí.
-- Sus propios seeds (07/08/09) ya las crean con CREATE TABLE IF NOT EXISTS,
-- y esa definición es la canónica. Solo faltaba montarlos en docker-compose.


-- ─── Índices que faltaban en tablas ya existentes ──────────────
-- stats.py:95 filtra predictions por created_at en cada poll (cada 5s)
CREATE INDEX IF NOT EXISTS idx_predictions_created ON predictions(created_at);
-- stats.py:74 / predict.py:29 ordenan por trained_at DESC
CREATE INDEX IF NOT EXISTS idx_trainlogs_trained  ON model_training_logs(trained_at DESC);


DO $$ BEGIN
    RAISE NOTICE '✅ Esquema REVO sincronizado con los modelos de los servicios';
END $$;
