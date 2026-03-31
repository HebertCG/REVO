-- ============================================================
-- REVO DB - Sistema de Recomendación de Especialización
-- Script 01: Inicialización del esquema completo
-- DB: revo_db | Schema: public
-- ============================================================

-- Habilitar extensiones
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- TABLA: specializations
-- ============================================================
CREATE TABLE IF NOT EXISTS specializations (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    slug        VARCHAR(80)  NOT NULL UNIQUE,
    description TEXT         NOT NULL,
    icon        VARCHAR(20)  NOT NULL DEFAULT '🎓',
    color_hex   VARCHAR(7)   NOT NULL DEFAULT '#6C63FF',
    career_paths JSONB       NOT NULL DEFAULT '[]',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ============================================================
-- TABLA: users
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(150) NOT NULL,
    student_code  VARCHAR(30)  UNIQUE,
    semester      SMALLINT     CHECK (semester BETWEEN 1 AND 12),
    role          VARCHAR(20)  NOT NULL DEFAULT 'student'
                               CHECK (role IN ('student','admin')),
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    avatar_url    VARCHAR(500),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role  ON users(role);

-- ============================================================
-- TABLA: questions
-- ============================================================
CREATE TABLE IF NOT EXISTS questions (
    id            SERIAL PRIMARY KEY,
    text          TEXT         NOT NULL,
    category      VARCHAR(30)  NOT NULL
                               CHECK (category IN ('academic','skills','interests','personality')),
    question_type VARCHAR(30)  NOT NULL DEFAULT 'scale'
                               CHECK (question_type IN ('scale','multiple_choice','boolean')),
    options       JSONB,                          -- para multiple_choice
    min_label     VARCHAR(50)  DEFAULT 'Muy bajo',
    max_label     VARCHAR(50)  DEFAULT 'Muy alto',
    weight        NUMERIC(4,2) NOT NULL DEFAULT 1.00,
    order_index   SMALLINT     NOT NULL DEFAULT 0,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_questions_category ON questions(category);
CREATE INDEX IF NOT EXISTS idx_questions_active   ON questions(is_active, order_index);

-- ============================================================
-- TABLA: questionnaire_sessions
-- ============================================================
CREATE TABLE IF NOT EXISTS questionnaire_sessions (
    id               SERIAL PRIMARY KEY,
    user_id          INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status           VARCHAR(20)  NOT NULL DEFAULT 'in_progress'
                                  CHECK (status IN ('in_progress','completed','abandoned')),
    started_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    completed_at     TIMESTAMPTZ,
    duration_seconds INTEGER,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON questionnaire_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status  ON questionnaire_sessions(status);

-- ============================================================
-- TABLA: answers
-- ============================================================
CREATE TABLE IF NOT EXISTS answers (
    id          SERIAL PRIMARY KEY,
    session_id  INTEGER      NOT NULL REFERENCES questionnaire_sessions(id) ON DELETE CASCADE,
    question_id INTEGER      NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    value       NUMERIC(4,2) NOT NULL,   -- 1.0 - 5.0 para scale
    answered_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (session_id, question_id)
);

CREATE INDEX IF NOT EXISTS idx_answers_session ON answers(session_id);

-- ============================================================
-- TABLA: predictions
-- ============================================================
CREATE TABLE IF NOT EXISTS predictions (
    id                         SERIAL PRIMARY KEY,
    session_id                 INTEGER      NOT NULL REFERENCES questionnaire_sessions(id) ON DELETE CASCADE,
    user_id                    INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    primary_specialization_id  INTEGER      NOT NULL REFERENCES specializations(id),
    confidence_score           NUMERIC(5,4) NOT NULL CHECK (confidence_score BETWEEN 0 AND 1),
    secondary_specializations  JSONB        NOT NULL DEFAULT '[]',
    -- [{"specialization_id": 2, "name": "Data Science", "score": 0.25}, ...]
    feature_vector             JSONB,
    -- {q1: 4, q2: 5, ...} snapshot para auditoría
    model_version              VARCHAR(30)  NOT NULL DEFAULT 'v1.0',
    created_at                 TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_predictions_user_id     ON predictions(user_id);
CREATE INDEX IF NOT EXISTS idx_predictions_session_id  ON predictions(session_id);
CREATE INDEX IF NOT EXISTS idx_predictions_spec_id     ON predictions(primary_specialization_id);

-- ============================================================
-- TABLA: model_training_logs
-- ============================================================
CREATE TABLE IF NOT EXISTS model_training_logs (
    id               SERIAL PRIMARY KEY,
    model_version    VARCHAR(30)      NOT NULL,
    algorithm        VARCHAR(50)      NOT NULL DEFAULT 'DecisionTreeClassifier',
    accuracy         NUMERIC(6,4),
    precision_score  NUMERIC(6,4),
    recall_score     NUMERIC(6,4),
    f1_score         NUMERIC(6,4),
    training_samples INTEGER,
    test_samples     INTEGER,
    max_depth        INTEGER,
    features_used    JSONB,           -- lista de features
    hyperparams      JSONB,           -- todos los parámetros del modelo
    model_path       VARCHAR(500),    -- ruta al archivo .pkl guardado
    trained_by       INTEGER REFERENCES users(id),
    trained_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes            TEXT
);

-- ============================================================
-- TABLA: feedback
-- ============================================================
CREATE TABLE IF NOT EXISTS feedback (
    id                  SERIAL PRIMARY KEY,
    prediction_id       INTEGER      NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    user_id             INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rating              SMALLINT     NOT NULL CHECK (rating BETWEEN 1 AND 5),
    agrees_with_result  BOOLEAN      NOT NULL,
    comment             TEXT,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (prediction_id, user_id)
);

-- ============================================================
-- TABLA: admin_actions_log (auditoría del admin)
-- ============================================================
CREATE TABLE IF NOT EXISTS admin_actions_log (
    id          SERIAL PRIMARY KEY,
    admin_id    INTEGER      NOT NULL REFERENCES users(id),
    action      VARCHAR(100) NOT NULL,
    target_type VARCHAR(50),          -- 'user', 'question', 'model', etc.
    target_id   INTEGER,
    details     JSONB,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ============================================================
-- FUNCIÓN: auto-update updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER set_updated_at_users
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE OR REPLACE TRIGGER set_updated_at_specializations
    BEFORE UPDATE ON specializations
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- ============================================================
-- VISTA: v_prediction_summary (útil para el dashboard admin)
-- ============================================================
CREATE OR REPLACE VIEW v_prediction_summary AS
SELECT
    p.id                          AS prediction_id,
    u.full_name                   AS student_name,
    u.student_code,
    u.semester,
    s.name                        AS specialization,
    s.color_hex,
    ROUND(p.confidence_score * 100, 1) AS confidence_pct,
    p.model_version,
    p.created_at                  AS predicted_at,
    f.rating                      AS feedback_rating,
    f.agrees_with_result          AS feedback_agrees
FROM predictions p
JOIN users u         ON u.id = p.user_id
JOIN specializations s ON s.id = p.primary_specialization_id
LEFT JOIN feedback f ON f.prediction_id = p.id;

-- ============================================================
-- VISTA: v_specialization_stats
-- ============================================================
CREATE OR REPLACE VIEW v_specialization_stats AS
SELECT
    s.id,
    s.name,
    s.color_hex,
    s.icon,
    COUNT(p.id)                            AS total_predictions,
    ROUND(AVG(p.confidence_score) * 100, 1) AS avg_confidence_pct,
    COUNT(CASE WHEN f.agrees_with_result = TRUE THEN 1 END) AS positive_feedbacks
FROM specializations s
LEFT JOIN predictions p ON p.primary_specialization_id = s.id
LEFT JOIN feedback f    ON f.prediction_id = p.id
GROUP BY s.id, s.name, s.color_hex, s.icon
ORDER BY total_predictions DESC;

-- Confirmación
DO $$ BEGIN
    RAISE NOTICE '✅ Schema REVO creado correctamente en revo_db';
END $$;
