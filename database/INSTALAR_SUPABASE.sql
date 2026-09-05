-- ============================================================================
--  REVO - INSTALACION COMPLETA
--  Pegar entero en el editor SQL de Supabase y pulsar Run.
-- ============================================================================
--
--  QUE HACE
--    Crea el esquema completo, las politicas de seguridad por filas, los
--    cuatro roles de base de datos y los datos de arranque. Reune las 17
--    migraciones de database/ en el orden correcto.
--
--  ANTES DE EJECUTAR
--    Baja hasta el final del fichero, al bloque PASO FINAL, y sustituye las
--    cuatro contrasenas de ejemplo por otras de verdad. El script se niega a
--    terminar si no lo haces.
--
--    Para generarlas:
--        python -c "import secrets; print(secrets.token_urlsafe(36))"
--
--    Tienen que ser CUATRO DISTINTAS. Si repites la misma, cualquiera que
--    consiga una credencial las tiene todas y la separacion entre servicios
--    deja de significar nada.
--
--  SE PUEDE VOLVER A EJECUTAR
--    Todo el fichero es idempotente: crea lo que falta y respeta lo que ya
--    existe. Si algo falla a mitad, corrige y vuelve a ejecutarlo entero.
--
--  DESPUES
--    Al final se imprimen dos comprobaciones. Los cuatro roles tienen que
--    salir con rolsuper = false y rolbypassrls = false. Si alguno sale true,
--    ese servicio puede leerlo todo y RLS no protege nada.
-- ============================================================================




-- ############################################################################
--   01_init.sql
--   Tablas base, extensiones e indices
-- ############################################################################

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

-- ############################################################################
--   01b_schema_sync.sql
--   Columnas anadidas despues de la version inicial
-- ############################################################################

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

-- ############################################################################
--   02_seed_specializations.sql
--   Las diez especializaciones
-- ############################################################################

-- ============================================================
-- REVO DB - Script 02: Seed de Especializaciones (10 Macro)
-- ============================================================

INSERT INTO specializations (id, name, slug, description, icon, color_hex, career_paths)
VALUES
(
    1,
    'Desarrollo de Software',
    'desarrollo-software',
    'Diseña y construye la próxima generación de aplicaciones. Combina creatividad con lógica para desarrollar sistemas web, móviles o de escritorio interactivos.',
    '💻',
    '#3B82F6',
    '["Frontend Developer", "Backend Developer", "Full Stack Developer", "Mobile Developer", "Software Architect"]'::jsonb
),
(
    2,
    'Data Science & IA',
    'data-science-ia',
    'Extrae conocimiento de los datos usando modelos matemáticos y Machine Learning. Construye inteligencias artificiales que transformarán el futuro.',
    '🧠',
    '#10B981',
    '["Data Scientist", "Machine Learning Engineer", "Data Analyst", "AI Engineer", "Computer Vision Engineer"]'::jsonb
),
(
    3,
    'Infraestructura & Cloud',
    'infraestructura-cloud',
    'Diseña arquitecturas en la nube escalables (AWS, Azure, GCP). Automatiza despliegues y mantén redes completas funcionando 24/7.',
    '☁️',
    '#8B5CF6',
    '["DevOps Engineer", "Cloud Engineer", "SysAdmin", "Network Engineer", "SRE"]'::jsonb
),
(
    4,
    'Ciberseguridad',
    'ciberseguridad',
    'Protege redes, sistemas y datos de amenazas digitales. Anticipa ciberataques y actúa como la primera barrera de defensa informática.',
    '🔐',
    '#EF4444',
    '["Ethical Hacker / Pentester", "Security Analyst (SOC)", "Digital Forensics", "Security Engineer"]'::jsonb
),
(
    5,
    'Soporte Técnico & IT Ops',
    'soporte-tecnico-it',
    'El puente entre la tecnología y las personas. Resuelve problemas críticos de hardware y software operando mesas de ayuda y redes de la empresa.',
    '🛠️',
    '#F59E0B',
    '["IT Support Specialist", "Soporte Técnico", "Field Support Technician", "IT Operations"]'::jsonb
),
(
    6,
    'QA & Testing',
    'qa-testing',
    'Garantiza la máxima calidad del software. Encuentra errores, automatiza pruebas y asegurar de que los productos lleguen perfectos al usuario final.',
    '🧪',
    '#EC4899',
    '["QA Automation Engineer", "Performance Tester", "SDET", "QA Analyst"]'::jsonb
),
(
    7,
    'Gestión y Producto',
    'gestion-producto',
    'Lidera equipos tecnológicos y agiliza procesos de software. Define la visión estratégica de los productos y gestiona su éxito.',
    '📈',
    '#6366F1',
    '["Product Manager", "Scrum Master", "Project Manager (PM)", "Product Owner"]'::jsonb
),
(
    8,
    'Diseño UX/UI',
    'diseno-ux-ui',
    'Da vida a las interfaces y mejora la experiencia del usuario. Traduce la complejidad técnica en pantallas intuitivas y estéticas.',
    '🎨',
    '#F43F5E',
    '["UX Designer", "UI Designer", "Product Designer", "UX Researcher"]'::jsonb
),
(
    9,
    'Sistemas Empresariales',
    'sistemas-empresariales',
    'Optimiza los flujos de negocio mediante grandes ecosistemas ERP (SAP, Oracle) o CRM. Ideal si te gusta mezclar tecnología y administración de negocios.',
    '🏢',
    '#14B8A6',
    '["ERP Consultant (SAP/Oracle)", "CRM Specialist", "Business Intelligence", "IT Consultant"]'::jsonb
),
(
    10,
    'Investigación e Innovación',
    'investigacion-innovacion',
    'Explora las tecnologías del mañana: Blockchain, IoT, Realidad Extendida y desarrollo de bajo nivel para compiladores y kernels.',
    '🔬',
    '#64748B',
    '["Blockchain Developer", "IoT Engineer", "AR/VR Developer", "Investigador en IA"]'::jsonb
)
ON CONFLICT (id) DO UPDATE SET 
    name = EXCLUDED.name,
    slug = EXCLUDED.slug,
    description = EXCLUDED.description,
    icon = EXCLUDED.icon,
    color_hex = EXCLUDED.color_hex,
    career_paths = EXCLUDED.career_paths;

-- Reset sequence to ensure future inserts work properly
SELECT setval('specializations_id_seq', (SELECT MAX(id) FROM specializations));

DO $$ BEGIN
    RAISE NOTICE '✅ 10 especializaciones agregadas a revo_db';
END $$;

-- ############################################################################
--   03_seed_questions.sql
--   Banco de preguntas del cuestionario
-- ############################################################################

-- ============================================================
-- Script 03: Seed de Preguntas ADAPTATIVAS (100 preguntas)
-- ============================================================

TRUNCATE TABLE questions CASCADE;
ALTER SEQUENCE questions_id_seq RESTART WITH 1;

INSERT INTO questions (text, category, specialization_id, min_label, max_label, order_index)
VALUES
('Mi personalidad metódica encaja perfectamente con la tarea de conectar Arduino y sensores.', 'personality', 10, 'Desacuerdo', 'Totalmente', 93),
('Siento un profundo interés por aprender a investigar ataques cibernéticos en el nivel más avanzado.', 'interests', 4, 'Desacuerdo', 'Totalmente', 36),
('Me considero extremadamente hábil para planificar sprints en mi día a día.', 'skills', 7, 'Desacuerdo', 'Totalmente', 65),
('A nivel académico, destaco ampliamente al tener que usar Linux a fondo.', 'academic', 3, 'Desacuerdo', 'Totalmente', 28),
('Me considero extremadamente hábil para atender tickets de servicio en mi día a día.', 'skills', 5, 'Desacuerdo', 'Totalmente', 45),
('A nivel académico, destaco ampliamente al tener que escribir casos de prueba.', 'academic', 6, 'Desacuerdo', 'Totalmente', 54),
('Me considero extremadamente hábil para automatizar despliegues en mi día a día.', 'skills', 3, 'Desacuerdo', 'Totalmente', 25),
('Mi personalidad metódica encaja perfectamente con la tarea de ser meticuloso.', 'personality', 6, 'Desacuerdo', 'Totalmente', 53),
('Siento un profundo interés por aprender a automatizar pruebas en el nivel más avanzado.', 'interests', 6, 'Desacuerdo', 'Totalmente', 52),
('Siento un profundo interés por aprender a revisar flujos críticos en el nivel más avanzado.', 'interests', 6, 'Desacuerdo', 'Totalmente', 60),
('Siento un profundo interés por aprender a usar Python/R en el nivel más avanzado.', 'interests', 2, 'Desacuerdo', 'Totalmente', 16),
('Siento un profundo interés por aprender a trabajar con bases de datos relacionales en el nivel más avanzado.', 'interests', 1, 'Desacuerdo', 'Totalmente', 10),
('Me considero extremadamente hábil para programar en bajo nivel en mi día a día.', 'skills', 10, 'Desacuerdo', 'Totalmente', 91),
('A nivel académico, destaco ampliamente al tener que documentar fallas comunes.', 'academic', 5, 'Desacuerdo', 'Totalmente', 48),
('Siento un profundo interés por aprender a entrenar modelos en el nivel más avanzado.', 'interests', 2, 'Desacuerdo', 'Totalmente', 12),
('Mi personalidad metódica encaja perfectamente con la tarea de entrevistar usuarios.', 'personality', 8, 'Desacuerdo', 'Totalmente', 77),
('Me considero extremadamente hábil para verificar accesibilidad en mi día a día.', 'skills', 6, 'Desacuerdo', 'Totalmente', 59),
('Siento un profundo interés por aprender a monitorear tiempos de actividad en el nivel más avanzado.', 'interests', 3, 'Desacuerdo', 'Totalmente', 26),
('Siento un profundo interés por aprender a orquestar contenedores en el nivel más avanzado.', 'interests', 3, 'Desacuerdo', 'Totalmente', 22),
('A nivel académico, destaco ampliamente al tener que usar Selenium/Cypress.', 'academic', 6, 'Desacuerdo', 'Totalmente', 58),
('Mi personalidad metódica encaja perfectamente con la tarea de escribir código limpio.', 'personality', 1, 'Desacuerdo', 'Totalmente', 3),
('Me considero extremadamente hábil para aplicar estadística en mi día a día.', 'skills', 2, 'Desacuerdo', 'Totalmente', 15),
('A nivel académico, destaco ampliamente al tener que usar Kali Linux.', 'academic', 4, 'Desacuerdo', 'Totalmente', 38),
('Me considero extremadamente hábil para gestionar inventarios digitales en mi día a día.', 'skills', 9, 'Desacuerdo', 'Totalmente', 85),
('Me considero extremadamente hábil para construir APIs en mi día a día.', 'skills', 1, 'Desacuerdo', 'Totalmente', 9),
('Siento un profundo interés por aprender a actuar como hacker ético en el nivel más avanzado.', 'interests', 4, 'Desacuerdo', 'Totalmente', 32),
('Me considero extremadamente hábil para encontrar vulnerabilidades en mi día a día.', 'skills', 4, 'Desacuerdo', 'Totalmente', 31),
('Mi personalidad metódica encaja perfectamente con la tarea de resolver problemas de red locales.', 'personality', 5, 'Desacuerdo', 'Totalmente', 47),
('A nivel académico, destaco ampliamente al tener que crear prototipos interactivos.', 'academic', 8, 'Desacuerdo', 'Totalmente', 78),
('Me considero extremadamente hábil para combinar colores armónicamente en mi día a día.', 'skills', 8, 'Desacuerdo', 'Totalmente', 75),
('Siento un profundo interés por aprender a instalar software de ofimática en el nivel más avanzado.', 'interests', 5, 'Desacuerdo', 'Totalmente', 50),
('Me considero extremadamente hábil para medir el rendimiento de la app en mi día a día.', 'skills', 6, 'Desacuerdo', 'Totalmente', 55),
('A nivel académico, destaco ampliamente al tener que hacer diagramas de Gantt.', 'academic', 7, 'Desacuerdo', 'Totalmente', 68),
('Mi personalidad metódica encaja perfectamente con la tarea de analizar malware.', 'personality', 4, 'Desacuerdo', 'Totalmente', 33),
('Me considero extremadamente hábil para soldar microcontroladores en mi día a día.', 'skills', 10, 'Desacuerdo', 'Totalmente', 99),
('Siento un profundo interés por aprender a mejorar la accesibilidad visual en el nivel más avanzado.', 'interests', 8, 'Desacuerdo', 'Totalmente', 80),
('Me considero extremadamente hábil para ayudar a usuarios en mi día a día.', 'skills', 5, 'Desacuerdo', 'Totalmente', 41),
('Siento un profundo interés por aprender a automatizar contabilidad en el nivel más avanzado.', 'interests', 9, 'Desacuerdo', 'Totalmente', 86),
('Me considero extremadamente hábil para analizar datos en mi día a día.', 'skills', 2, 'Desacuerdo', 'Totalmente', 11),
('Siento un profundo interés por aprender a entender flujos financieros en el nivel más avanzado.', 'interests', 9, 'Desacuerdo', 'Totalmente', 82),
('Siento un profundo interés por aprender a reparar computadoras en el nivel más avanzado.', 'interests', 5, 'Desacuerdo', 'Totalmente', 42),
('Me considero extremadamente hábil para configurar servidores en mi día a día.', 'skills', 3, 'Desacuerdo', 'Totalmente', 21),
('A nivel académico, destaco ampliamente al tener que proteger datos sensibles.', 'academic', 4, 'Desacuerdo', 'Totalmente', 34),
('Me considero extremadamente hábil para parametrizar SAP/Oracle en mi día a día.', 'skills', 9, 'Desacuerdo', 'Totalmente', 81),
('A nivel académico, destaco ampliamente al tener que investigar computación cuántica.', 'academic', 10, 'Desacuerdo', 'Totalmente', 98),
('Mi personalidad metódica encaja perfectamente con la tarea de usar machine learning.', 'personality', 2, 'Desacuerdo', 'Totalmente', 13),
('Mi personalidad metódica encaja perfectamente con la tarea de optimizar recursos humanos.', 'personality', 9, 'Desacuerdo', 'Totalmente', 83),
('Me considero extremadamente hábil para balancear cargas de tráfico en mi día a día.', 'skills', 3, 'Desacuerdo', 'Totalmente', 29),
('Me considero extremadamente hábil para trabajar en Realidad Virtual en mi día a día.', 'skills', 10, 'Desacuerdo', 'Totalmente', 95),
('Siento un profundo interés por aprender a diseñar flujos de navegación en el nivel más avanzado.', 'interests', 8, 'Desacuerdo', 'Totalmente', 76),
('Siento un profundo interés por aprender a entender al usuario final en el nivel más avanzado.', 'interests', 8, 'Desacuerdo', 'Totalmente', 72),
('A nivel académico, destaco ampliamente al tener que usar frameworks modernos.', 'academic', 1, 'Desacuerdo', 'Totalmente', 8),
('Me considero extremadamente hábil para crear wireframes en mi día a día.', 'skills', 8, 'Desacuerdo', 'Totalmente', 71),
('Siento un profundo interés por aprender a estructurar algoritmos en el nivel más avanzado.', 'interests', 1, 'Desacuerdo', 'Totalmente', 6),
('Siento un profundo interés por aprender a procesar lenguaje natural en el nivel más avanzado.', 'interests', 2, 'Desacuerdo', 'Totalmente', 20),
('Mi personalidad metódica encaja perfectamente con la tarea de entender el modelo de negocio.', 'personality', 7, 'Desacuerdo', 'Totalmente', 67),
('Siento un profundo interés por aprender a garantizar la calidad total en el nivel más avanzado.', 'interests', 6, 'Desacuerdo', 'Totalmente', 56),
('Mi personalidad metódica encaja perfectamente con la tarea de romper aplicaciones intencionalmente.', 'personality', 6, 'Desacuerdo', 'Totalmente', 57),
('A nivel académico, destaco ampliamente al tener que mantener redes globales.', 'academic', 3, 'Desacuerdo', 'Totalmente', 24),
('Me considero extremadamente hábil para auditar sistemas en mi día a día.', 'skills', 4, 'Desacuerdo', 'Totalmente', 35),
('Mi personalidad metódica encaja perfectamente con la tarea de diseñar experiencias fluidas.', 'personality', 8, 'Desacuerdo', 'Totalmente', 73),
('Me considero extremadamente hábil para aplicar psicología del diseño en mi día a día.', 'skills', 8, 'Desacuerdo', 'Totalmente', 79),
('Me considero extremadamente hábil para modelar flujos de suministro en mi día a día.', 'skills', 9, 'Desacuerdo', 'Totalmente', 89),
('A nivel académico, destaco ampliamente al tener que limpiar bases de datos grandes.', 'academic', 2, 'Desacuerdo', 'Totalmente', 18),
('Me considero extremadamente hábil para liderar equipos técnicos en mi día a día.', 'skills', 7, 'Desacuerdo', 'Totalmente', 61),
('Siento un profundo interés por aprender a escribir código en C/Rust en el nivel más avanzado.', 'interests', 10, 'Desacuerdo', 'Totalmente', 100),
('Mi personalidad metódica encaja perfectamente con la tarea de crear algoritmos matemáticos puros.', 'personality', 10, 'Desacuerdo', 'Totalmente', 97),
('Mi personalidad metódica encaja perfectamente con la tarea de diagnosticar errores de Windows.', 'personality', 5, 'Desacuerdo', 'Totalmente', 43),
('Siento un profundo interés por aprender a traducir leyes a software en el nivel más avanzado.', 'interests', 9, 'Desacuerdo', 'Totalmente', 90),
('A nivel académico, destaco ampliamente al tener que integrar CRMs.', 'academic', 9, 'Desacuerdo', 'Totalmente', 84),
('Siento un profundo interés por aprender a evitar bloqueos del equipo en el nivel más avanzado.', 'interests', 7, 'Desacuerdo', 'Totalmente', 66),
('A nivel académico, destaco ampliamente al tener que configurar impresoras corporativas.', 'academic', 5, 'Desacuerdo', 'Totalmente', 44),
('Siento un profundo interés por aprender a planificar respuestas a incidentes en el nivel más avanzado.', 'interests', 4, 'Desacuerdo', 'Totalmente', 40),
('Me considero extremadamente hábil para programar redes neuronales en mi día a día.', 'skills', 2, 'Desacuerdo', 'Totalmente', 19),
('A nivel académico, destaco ampliamente al tener que leer papers académicos.', 'academic', 10, 'Desacuerdo', 'Totalmente', 94),
('Me considero extremadamente hábil para actuar con paciencia en mi día a día.', 'skills', 5, 'Desacuerdo', 'Totalmente', 49),
('Mi personalidad metódica encaja perfectamente con la tarea de usar AWS/Azure.', 'personality', 3, 'Desacuerdo', 'Totalmente', 23),
('Siento un profundo interés por aprender a explorar Blockchain en el nivel más avanzado.', 'interests', 10, 'Desacuerdo', 'Totalmente', 92),
('Me considero extremadamente hábil para encontrar bugs en mi día a día.', 'skills', 6, 'Desacuerdo', 'Totalmente', 51),
('A nivel académico, destaco ampliamente al tener que crear aplicaciones web.', 'academic', 1, 'Desacuerdo', 'Totalmente', 4),
('A nivel académico, destaco ampliamente al tener que implementar Salesforce.', 'academic', 9, 'Desacuerdo', 'Totalmente', 88),
('Siento un profundo interés por aprender a usar Scrum o Kanban en el nivel más avanzado.', 'interests', 7, 'Desacuerdo', 'Totalmente', 62),
('A nivel académico, destaco ampliamente al tener que hablar con clientes.', 'academic', 7, 'Desacuerdo', 'Totalmente', 64),
('Me considero extremadamente hábil para programar en mi día a día.', 'skills', 1, 'Desacuerdo', 'Totalmente', 1),
('Mi personalidad metódica encaja perfectamente con la tarea de encriptar información.', 'personality', 4, 'Desacuerdo', 'Totalmente', 37),
('Me considero extremadamente hábil para desarrollar apps móviles en mi día a día.', 'skills', 1, 'Desacuerdo', 'Totalmente', 5),
('Mi personalidad metódica encaja perfectamente con la tarea de visualizar métricas numéricas.', 'personality', 2, 'Desacuerdo', 'Totalmente', 17),
('Siento un profundo interés por aprender a gestionar permisos de red en el nivel más avanzado.', 'interests', 3, 'Desacuerdo', 'Totalmente', 30),
('Mi personalidad metódica encaja perfectamente con la tarea de configurar routers físicos.', 'personality', 3, 'Desacuerdo', 'Totalmente', 27),
('Me considero extremadamente hábil para priorizar tareas en mi día a día.', 'skills', 7, 'Desacuerdo', 'Totalmente', 69),
('Mi personalidad metódica encaja perfectamente con la tarea de auditar procesos de negocio.', 'personality', 9, 'Desacuerdo', 'Totalmente', 87),
('A nivel académico, destaco ampliamente al tener que usar Figma.', 'academic', 8, 'Desacuerdo', 'Totalmente', 74),
('Siento un profundo interés por aprender a mantener inventario de IT en el nivel más avanzado.', 'interests', 5, 'Desacuerdo', 'Totalmente', 46),
('Siento un profundo interés por aprender a optimizar compiladores en el nivel más avanzado.', 'interests', 10, 'Desacuerdo', 'Totalmente', 96),
('Siento un profundo interés por aprender a medir KPIs del producto en el nivel más avanzado.', 'interests', 7, 'Desacuerdo', 'Totalmente', 70),
('Mi personalidad metódica encaja perfectamente con la tarea de definir requerimientos.', 'personality', 7, 'Desacuerdo', 'Totalmente', 63),
('Me considero extremadamente hábil para hacer pruebas de penetración en mi día a día.', 'skills', 4, 'Desacuerdo', 'Totalmente', 39),
('Mi personalidad metódica encaja perfectamente con la tarea de depurar código.', 'personality', 1, 'Desacuerdo', 'Totalmente', 7),
('Siento un profundo interés por aprender a diseñar interfaces en el nivel más avanzado.', 'interests', 1, 'Desacuerdo', 'Totalmente', 2),
('A nivel académico, destaco ampliamente al tener que encontrar patrones en datos.', 'academic', 2, 'Desacuerdo', 'Totalmente', 14);

DO $$ BEGIN RAISE NOTICE '✅ 100 preguntas adaptativas sembradas en revo_db'; END $$;

-- ############################################################################
--   04_seed_training_data.sql
--   Datos de arranque para entrenar el modelo
-- ############################################################################

-- ============================================================
-- REVO DB - Script 04: Training Data Generator (10 Afinidades)
-- ============================================================

TRUNCATE TABLE ml_training_data CASCADE;
ALTER SEQUENCE ml_training_data_id_seq RESTART WITH 1;

INSERT INTO ml_training_data (
    aff_1, aff_2, aff_3, aff_4, aff_5, aff_6, aff_7, aff_8, aff_9, aff_10, specialization_id
) VALUES
(0.7333, 0.0667, 0.9333, 0.1667, 0.0333, 0.1, 0.1333, 0.5, 0.0333, 0.0333, 3),
(0.0333, 0.6667, 0.1, 0.6333, 0.1333, 0.9667, 0.1, 0.1, 0.1667, 0.1333, 6),
(0.6333, 0.1667, 0.1667, 0.5667, 0.1, 0.0667, 0.1333, 0.0667, 0.8333, 0.1333, 9),
(0.1333, 0.8667, 0.1667, 0.1667, 0.0333, 0.6333, 0.0333, 0.1667, 0.6667, 0.1, 2),
(0.1667, 0.1667, 0.1333, 0.8333, 0.0667, 0.7333, 0.0333, 0.1667, 0.1, 0.7333, 4),
(0.0667, 0.6333, 0.9333, 0.1333, 0.1333, 0.1667, 0.7, 0.1, 0.1667, 0.0333, 3),
(0.8667, 0.6667, 0.1333, 0.1667, 0.0667, 0.1333, 0.1, 0.6333, 0.0333, 0.1, 1),
(0.1667, 0.9667, 0.1, 0.0667, 0.1667, 0.7, 0.0333, 0.6667, 0.0333, 0.1333, 2),
(0.1667, 0.1333, 0.1333, 0.1, 0.1, 0.6, 0.1, 0.9667, 0.5333, 0.0667, 8),
(0.8667, 0.6, 0.1333, 0.0667, 0.0667, 0.1, 0.1667, 0.0333, 0.1, 0.7, 1),
(0.9, 0.6, 0.0333, 0.1667, 0.1333, 0.1, 0.1, 0.1, 0.0667, 0.4333, 1),
(0.0333, 0.0333, 0.1, 0.1, 0.1667, 0.1, 0.8333, 0.0333, 0.5667, 0.7, 7),
(0.1, 0.1667, 0.1667, 0.6333, 0.9333, 0.0333, 0.6667, 0.1333, 0.1667, 0.0667, 5),
(0.0667, 0.0333, 0.5667, 0.0667, 0.9333, 0.0667, 0.0667, 0.0667, 0.1, 0.4667, 5),
(0.7, 0.0333, 0.0333, 0.0333, 0.0667, 0.8667, 0.1333, 0.6, 0.1333, 0.0333, 6),
(0.1, 0.1667, 0.1667, 0.6667, 0.1333, 0.0667, 0.9333, 0.6, 0.1667, 0.1, 7),
(0.1333, 0.6667, 0.6667, 0.1, 0.1667, 0.8667, 0.1, 0.0667, 0.1667, 0.0667, 6),
(0.1, 0.1667, 0.6, 0.0333, 0.1667, 0.1667, 0.6333, 0.1667, 0.1, 0.8667, 10),
(0.1, 0.0333, 0.0667, 0.0333, 0.0333, 0.9333, 0.7333, 0.0333, 0.1667, 0.6, 6),
(0.1333, 0.1667, 0.5667, 0.0667, 0.8333, 0.1333, 0.7, 0.0333, 0.0667, 0.1, 5),
(0.1333, 0.9, 0.7333, 0.1333, 0.1667, 0.1333, 0.1, 0.7333, 0.0333, 0.0333, 2),
(0.1, 0.6, 0.7333, 0.1, 0.8333, 0.1667, 0.0667, 0.0667, 0.1333, 0.1, 5),
(0.5333, 0.1, 0.1667, 0.6333, 0.0667, 0.1667, 0.8333, 0.1, 0.1333, 0.0333, 7),
(0.0667, 0.9333, 0.6333, 0.0667, 0.0333, 0.1667, 0.1, 0.1667, 0.6, 0.1, 2),
(0.6667, 0.1333, 0.0333, 0.1667, 0.1667, 0.1, 0.6667, 0.1333, 0.8333, 0.1333, 9),
(0.0333, 0.1333, 0.9, 0.1667, 0.0667, 0.1667, 0.7, 0.1, 0.6333, 0.1333, 3),
(0.1333, 0.1333, 0.6333, 0.0333, 0.5333, 0.0667, 0.0667, 0.1, 0.1333, 0.8667, 10),
(0.0667, 0.1333, 0.0333, 0.1333, 0.1667, 0.8333, 0.6333, 0.7, 0.0333, 0.1667, 6),
(0.1333, 0.0333, 0.9667, 0.1667, 0.1333, 0.1, 0.6333, 0.6, 0.1667, 0.1, 3),
(0.6333, 0.1667, 0.1333, 0.0333, 0.0667, 0.1, 0.0333, 0.1333, 0.8, 0.6, 9),
(0.1667, 0.5333, 0.9, 0.1333, 0.0333, 0.1333, 0.0667, 0.6667, 0.0667, 0.1, 3),
(0.0667, 0.1333, 0.1667, 0.1333, 0.1333, 0.6333, 1.0, 0.0333, 0.7, 0.1667, 7),
(0.6667, 0.0333, 0.1667, 0.1667, 0.1333, 0.0667, 0.8667, 0.0333, 0.7, 0.1667, 7),
(0.0333, 0.9333, 0.1, 0.7, 0.0333, 0.0333, 0.6667, 0.0333, 0.1667, 0.0333, 2),
(0.1333, 0.1, 0.6, 0.1667, 0.1, 0.7, 0.8333, 0.1667, 0.0667, 0.1667, 7),
(0.7333, 0.0333, 0.8333, 0.0333, 0.1667, 0.0667, 0.0667, 0.0333, 0.6667, 0.1667, 3),
(0.5333, 0.0333, 0.0333, 0.1333, 0.9, 0.1333, 0.0667, 0.1667, 0.0667, 0.6333, 5),
(0.1667, 0.5667, 0.1667, 0.0667, 0.0333, 0.1667, 0.1333, 0.9, 0.7333, 0.0333, 8),
(0.1, 0.0667, 0.1333, 0.5667, 0.1667, 0.1667, 0.1, 0.7, 0.8333, 0.1333, 9),
(0.7, 0.1667, 0.1, 0.8667, 0.0667, 0.7, 0.1667, 0.1333, 0.1667, 0.1667, 4),
(0.0333, 0.0667, 0.6667, 0.1667, 0.1667, 0.1333, 0.1667, 0.0667, 0.9667, 0.6, 9),
(0.7333, 0.1333, 0.1333, 0.1667, 0.0667, 0.6667, 0.0333, 0.8333, 0.0333, 0.1333, 8),
(0.0333, 0.5667, 0.1, 0.1, 0.1, 0.1333, 0.5667, 0.0667, 0.9333, 0.1667, 9),
(0.6667, 0.1333, 0.1, 0.1333, 0.1, 0.1333, 0.8667, 0.6667, 0.0333, 0.1667, 7),
(0.5333, 0.9, 0.1667, 0.6, 0.1667, 0.1333, 0.0667, 0.0667, 0.1, 0.1, 2),
(0.0667, 0.1333, 0.1, 0.7, 0.8667, 0.0667, 0.7, 0.1667, 0.1667, 0.0667, 5),
(0.0333, 0.1667, 0.1333, 0.6333, 0.6, 0.1333, 0.8333, 0.1333, 0.1667, 0.1667, 7),
(0.1, 0.1333, 0.0333, 0.0333, 0.6333, 0.6, 0.8667, 0.0667, 0.0333, 0.0333, 7),
(0.7, 0.1667, 0.1667, 0.1333, 0.0333, 0.9, 0.1333, 0.6, 0.0333, 0.1333, 6),
(0.0667, 0.8333, 0.0667, 0.1333, 0.6333, 0.1667, 0.0667, 0.0333, 0.7, 0.0667, 2),
(0.8667, 0.6, 0.0667, 0.0333, 0.1667, 0.1667, 0.6333, 0.0667, 0.0333, 0.1667, 1),
(0.1667, 0.0333, 0.1, 0.1, 0.8333, 0.8, 0.7, 0.1333, 0.1667, 0.1, 5),
(0.0667, 0.9667, 0.0667, 0.1667, 0.1667, 0.0333, 0.1, 0.0667, 0.4333, 0.6333, 2),
(0.1, 0.8, 0.1333, 0.0667, 0.0667, 0.0333, 0.7, 0.1333, 0.8667, 0.0667, 9),
(0.1333, 0.9333, 0.1333, 0.5667, 0.0333, 0.0667, 0.1, 0.6, 0.1667, 0.0667, 2),
(0.1667, 0.5333, 0.0333, 0.1667, 0.9, 0.0667, 0.0333, 0.6, 0.0667, 0.1333, 5),
(0.1667, 0.1333, 0.1333, 0.1, 0.1, 0.7, 0.1667, 0.8333, 0.0333, 0.5667, 8),
(0.1, 0.9333, 0.6333, 0.6333, 0.1, 0.1, 0.1, 0.1667, 0.0667, 0.1333, 2),
(0.7, 0.1, 0.1333, 0.9667, 0.0667, 0.0333, 0.1667, 0.0333, 0.8, 0.1, 4),
(0.6333, 0.0667, 0.1667, 0.0667, 0.9, 0.6333, 0.0333, 0.1667, 0.1667, 0.1667, 5),
(0.7333, 0.1667, 0.0333, 0.1, 0.1333, 0.1333, 0.6333, 0.1333, 0.9, 0.0667, 9),
(0.1333, 0.6667, 0.0667, 0.6667, 0.0667, 0.9, 0.1333, 0.0333, 0.1, 0.0667, 6),
(0.1333, 0.0333, 0.8333, 0.1, 0.1667, 0.1, 0.0667, 0.0333, 0.7, 0.5667, 3),
(0.1333, 0.1333, 0.1333, 0.6667, 0.1667, 0.1333, 0.1333, 0.8, 0.7333, 0.1, 8),
(0.1667, 0.0333, 0.1667, 0.9667, 0.7333, 0.0333, 0.5667, 0.1333, 0.0333, 0.1333, 4),
(0.1667, 0.5667, 0.0667, 0.1667, 0.0333, 0.1667, 0.1667, 0.9333, 0.1667, 0.5333, 8),
(0.7333, 0.1333, 0.1, 0.1, 0.0667, 0.6333, 0.9333, 0.0667, 0.1, 0.0333, 7),
(0.5667, 0.0333, 0.1333, 0.0667, 0.1667, 0.6333, 0.1333, 0.0667, 0.8333, 0.0667, 9),
(0.1, 0.1667, 0.0333, 0.1333, 0.1, 0.0333, 0.5667, 0.8667, 0.6333, 0.1667, 8),
(0.0333, 0.6, 0.1333, 0.0667, 0.0667, 0.1, 0.1667, 0.1667, 0.6667, 0.8667, 10),
(0.6667, 0.0667, 0.1667, 0.0667, 0.1667, 0.6, 0.1667, 0.8667, 0.0667, 0.1667, 8),
(0.0667, 0.9333, 0.5333, 0.6333, 0.1667, 0.1, 0.0667, 0.1, 0.0667, 0.0333, 2),
(0.1, 0.8667, 0.0333, 0.5667, 0.1, 0.0667, 0.7333, 0.1667, 0.1, 0.1667, 2),
(0.7333, 0.1, 0.0667, 0.1333, 0.0667, 0.8667, 0.0333, 0.0667, 0.1, 0.5333, 6),
(0.1, 0.1, 0.1, 0.0667, 0.7, 0.1, 0.0333, 0.8, 0.0333, 0.7, 8),
(0.6333, 0.0333, 0.1, 0.1667, 0.8, 0.1, 0.0667, 0.1333, 0.6667, 0.1333, 5),
(0.8667, 0.0333, 0.1, 0.1, 0.1667, 0.6333, 0.1, 0.5667, 0.0333, 0.0667, 1),
(0.8333, 0.5, 0.1667, 0.1333, 0.1, 0.1667, 0.1667, 0.1333, 0.6, 0.1333, 1),
(0.7667, 0.1, 0.0667, 0.9, 0.1333, 0.0333, 0.0333, 0.0667, 0.1333, 0.4333, 4),
(0.0333, 0.1, 0.6, 0.1333, 0.1333, 0.8667, 0.0667, 0.1333, 0.6667, 0.1667, 6),
(0.5667, 0.0333, 0.1333, 0.6, 0.1333, 0.1667, 0.0667, 0.1333, 0.9, 0.1333, 9),
(0.0333, 0.0667, 0.0333, 0.5333, 0.1667, 0.0667, 0.6333, 0.1667, 0.1, 0.9, 10),
(0.1, 0.5667, 0.9, 0.1333, 0.5, 0.0333, 0.1, 0.1667, 0.1, 0.1, 3),
(0.7, 0.1, 0.1333, 0.1, 0.0667, 0.1, 0.1333, 0.1, 0.9, 0.7667, 9),
(0.5667, 0.1333, 0.1333, 0.1667, 0.5333, 0.1333, 0.0333, 0.8667, 0.0333, 0.1667, 8),
(0.0667, 0.0667, 0.6, 0.0333, 0.1, 0.1, 0.1333, 0.1333, 0.8333, 0.5667, 9),
(0.0333, 0.1667, 0.1333, 0.1, 0.9, 0.0333, 0.6667, 0.6333, 0.1667, 0.0333, 5),
(0.0333, 0.1, 0.6333, 0.0333, 0.1333, 0.0667, 0.5333, 0.0333, 0.0667, 0.8667, 10),
(0.0333, 0.0333, 0.0667, 0.1, 0.0333, 0.6667, 0.1, 0.9, 0.1, 0.6, 8),
(0.1333, 0.1, 0.1, 0.8333, 0.0667, 0.1333, 0.6667, 0.1333, 0.0667, 0.6667, 4),
(0.1333, 0.1, 0.4667, 0.6, 0.0333, 0.9, 0.1, 0.1667, 0.1667, 0.1333, 6),
(0.6, 0.1333, 0.1, 0.1667, 0.1333, 0.8333, 0.1333, 0.8, 0.1333, 0.1667, 6),
(0.0333, 0.6667, 0.8667, 0.1333, 0.0667, 0.0667, 0.6333, 0.1667, 0.0667, 0.0667, 3),
(0.7333, 0.0333, 0.1, 0.8667, 0.1667, 0.1667, 0.1333, 0.0667, 0.0333, 0.6333, 4),
(0.1, 0.0333, 0.1667, 0.5333, 0.6667, 0.1667, 0.9333, 0.0333, 0.1667, 0.0667, 7),
(0.7667, 0.1333, 0.1667, 0.6333, 0.0667, 0.0667, 0.1, 0.8667, 0.1, 0.1667, 8),
(0.0667, 0.1667, 0.7, 0.1667, 0.1667, 0.1333, 0.1, 0.5667, 0.8667, 0.0333, 9),
(0.0333, 0.8667, 0.0333, 0.0333, 0.1333, 0.1333, 0.6333, 0.0333, 0.1, 0.4667, 2),
(0.7333, 0.1333, 0.9333, 0.1667, 0.1, 0.6667, 0.1333, 0.1667, 0.0333, 0.1, 3),
(0.0333, 0.9, 0.1667, 0.1, 0.7333, 0.0333, 0.1333, 0.1667, 0.0667, 0.6333, 2),
(0.6333, 0.1333, 0.9333, 0.0667, 0.1, 0.0333, 0.1667, 0.1667, 0.1333, 0.6667, 3),
(0.1, 0.1667, 0.5667, 0.0667, 0.6667, 0.0667, 0.1333, 0.1, 0.1, 0.9333, 10),
(0.1, 0.0333, 0.1333, 0.6333, 0.8667, 0.1, 0.1667, 0.0333, 0.6667, 0.1, 5),
(0.1667, 0.1667, 0.1, 0.1, 0.9, 0.7, 0.1333, 0.0333, 0.0333, 0.6333, 5),
(0.0333, 0.1667, 0.9333, 0.6333, 0.1667, 0.0667, 0.5667, 0.0333, 0.0333, 0.0333, 3),
(0.1667, 0.1333, 0.0333, 0.7, 0.7667, 0.0333, 0.1667, 0.0333, 0.0333, 0.9, 10),
(0.1, 0.0333, 0.6, 0.0667, 0.1667, 0.0333, 0.9333, 0.5667, 0.0333, 0.0333, 7),
(0.0333, 0.1667, 0.8333, 0.1, 0.6, 0.0667, 0.1, 0.1, 0.0333, 0.5667, 3),
(0.6, 0.7, 0.0667, 0.0333, 0.1, 0.1333, 0.9, 0.1667, 0.1, 0.1, 7),
(0.6333, 0.0333, 0.1333, 0.6333, 0.1, 0.1, 0.0667, 0.1667, 0.9, 0.1333, 9),
(0.0333, 0.6333, 0.0333, 0.8333, 0.1, 0.1333, 0.0667, 0.0333, 0.1, 0.6333, 4),
(0.8333, 0.7667, 0.1667, 0.1, 0.6333, 0.1, 0.1333, 0.0333, 0.1333, 0.0333, 1),
(0.1, 0.8667, 0.0667, 0.1667, 0.0667, 0.0333, 0.1667, 0.1, 0.6, 0.6333, 2),
(0.9333, 0.1333, 0.0667, 0.1333, 0.0667, 0.7, 0.0333, 0.1333, 0.0333, 0.4667, 1),
(0.0333, 0.1667, 0.1, 0.1333, 0.1667, 0.0333, 0.6333, 0.5333, 0.9, 0.1667, 9),
(0.0333, 0.1, 0.7667, 0.0667, 0.0333, 0.0333, 0.1, 0.9333, 0.7667, 0.0667, 8),
(0.0333, 0.5333, 0.1667, 0.9333, 0.1333, 0.0667, 0.1667, 0.5667, 0.1333, 0.1667, 4),
(0.8, 0.1667, 0.5667, 0.1, 0.1333, 0.0333, 0.1667, 0.0333, 0.6, 0.1, 1),
(0.6333, 0.0667, 0.9667, 0.1667, 0.0667, 0.0667, 0.1333, 0.1667, 0.1333, 0.5667, 3),
(0.0333, 0.1, 0.9, 0.1333, 0.6333, 0.6, 0.0333, 0.1667, 0.0333, 0.1333, 3),
(0.1, 0.0667, 0.5667, 0.9333, 0.0333, 0.7, 0.0333, 0.0667, 0.1, 0.0333, 4),
(0.5333, 0.0333, 0.0333, 0.6, 0.0333, 0.9333, 0.0333, 0.1667, 0.0333, 0.1667, 6),
(0.1, 0.1333, 0.6, 0.0333, 0.8333, 0.1, 0.1333, 0.1667, 0.6333, 0.0667, 5),
(0.6667, 0.1667, 0.9333, 0.0667, 0.1333, 0.0667, 0.1667, 0.1667, 0.1667, 0.6, 3),
(0.1333, 0.1333, 0.1667, 0.0667, 0.5333, 0.9333, 0.1, 0.0333, 0.5333, 0.0333, 6),
(0.0333, 0.0333, 0.5667, 0.1667, 0.0667, 0.9333, 0.0667, 0.6667, 0.1333, 0.0667, 6),
(0.0667, 0.0667, 0.0667, 0.1333, 0.1333, 0.0667, 0.5333, 0.6333, 0.1333, 0.9, 10),
(0.1667, 0.1, 0.6, 0.1, 0.1667, 0.9333, 0.0667, 0.7, 0.0667, 0.0333, 6),
(0.1333, 0.5333, 0.6333, 0.8333, 0.1333, 0.0333, 0.1333, 0.1333, 0.0333, 0.0333, 4),
(0.0667, 0.6, 0.1, 0.1667, 0.1, 0.0333, 0.6333, 0.1667, 0.9, 0.1667, 9),
(0.1, 0.1667, 0.0667, 0.0333, 0.6667, 0.9, 0.1, 0.0333, 0.5, 0.0333, 6),
(0.0667, 0.1333, 0.1667, 0.8667, 0.1, 0.6333, 0.6667, 0.0333, 0.0667, 0.1, 4),
(0.6333, 0.1333, 0.1333, 0.8333, 0.0333, 0.1, 0.6333, 0.0667, 0.1667, 0.0667, 4),
(0.7, 0.0333, 0.7, 0.9667, 0.1333, 0.0333, 0.0333, 0.0333, 0.1, 0.0667, 4),
(0.0667, 0.0667, 0.1, 0.7, 0.0667, 0.0333, 0.6, 0.8667, 0.1667, 0.1333, 8),
(0.1667, 0.1333, 0.0667, 0.7, 0.1333, 0.8667, 0.0333, 0.0333, 0.1, 0.6667, 6),
(0.6, 0.0667, 0.0333, 0.6667, 0.1333, 0.1333, 0.9333, 0.1, 0.1333, 0.1333, 7),
(0.0667, 0.1, 0.8667, 0.1333, 0.4667, 0.1, 0.4667, 0.1667, 0.0667, 0.0333, 3),
(0.6333, 0.1333, 0.0333, 0.0333, 0.6, 0.1333, 0.0667, 0.0667, 0.8667, 0.0333, 9),
(0.0667, 0.1333, 0.0667, 0.1333, 0.1667, 0.8, 0.1, 0.1, 0.6667, 0.7333, 6),
(0.1667, 0.6667, 0.1667, 0.1667, 0.9667, 0.6667, 0.1333, 0.0667, 0.1, 0.0667, 5),
(0.1667, 0.1, 0.5, 0.6333, 0.1, 0.0667, 0.0667, 0.8667, 0.0667, 0.0667, 8),
(0.0667, 0.5667, 0.1, 0.7, 0.0667, 0.1, 0.0667, 0.0667, 0.0667, 0.9333, 10),
(0.1667, 0.0667, 0.1667, 0.1, 0.8667, 0.5, 0.1667, 0.8, 0.1, 0.1, 5),
(0.5333, 0.0667, 0.1667, 0.0333, 0.9, 0.0667, 0.0667, 0.0333, 0.1333, 0.5333, 5),
(0.8667, 0.1667, 0.1333, 0.1333, 0.6667, 0.6333, 0.0667, 0.1333, 0.0333, 0.0333, 1),
(0.0667, 0.0333, 0.0333, 0.5, 0.0333, 0.1667, 0.0667, 0.5667, 0.1, 0.9, 10),
(0.1667, 0.1333, 0.1667, 0.1333, 0.5, 0.5333, 0.1, 0.1, 0.9667, 0.0333, 9),
(0.1, 0.0333, 0.6333, 0.1333, 0.1333, 0.1, 0.1667, 0.1667, 0.6667, 0.9333, 10),
(0.5333, 0.6667, 0.9667, 0.0333, 0.0667, 0.0667, 0.0333, 0.0333, 0.1333, 0.1333, 3),
(0.0667, 0.0667, 0.1, 0.1, 0.1667, 0.1667, 0.6667, 0.9667, 0.6, 0.1, 8),
(0.1667, 0.6333, 0.1, 0.8333, 0.1, 0.1, 0.1333, 0.6667, 0.0333, 0.1667, 4),
(0.1667, 0.1667, 0.0333, 0.0333, 0.1333, 0.6, 0.9, 0.1, 0.0667, 0.6333, 7),
(0.6, 0.9333, 0.0333, 0.6333, 0.1, 0.0333, 0.0333, 0.1667, 0.0333, 0.0667, 2),
(0.1667, 0.0667, 0.7333, 0.9, 0.1333, 0.5333, 0.1667, 0.0667, 0.1667, 0.1667, 4),
(0.1333, 0.6, 0.0333, 0.0667, 0.9, 0.7, 0.1333, 0.1667, 0.0667, 0.1, 5),
(0.1667, 0.1667, 0.5667, 0.1667, 0.9, 0.1333, 0.1, 0.0667, 0.7333, 0.1667, 5),
(0.0333, 0.7333, 0.1, 0.0333, 0.0667, 0.0333, 0.6333, 0.1667, 0.8667, 0.1333, 9),
(0.0333, 0.1667, 0.1333, 0.1667, 0.7, 0.8333, 0.7, 0.0667, 0.1667, 0.1, 6),
(0.1333, 0.6, 0.1, 0.0667, 0.9, 0.1667, 0.6333, 0.1667, 0.0667, 0.1, 5),
(0.1333, 0.5667, 0.0667, 0.0667, 0.0667, 0.0333, 0.7, 0.1333, 0.8667, 0.1667, 9),
(0.0667, 0.0667, 0.5, 0.1667, 0.1667, 0.1667, 0.1333, 0.1333, 0.5667, 0.9667, 10),
(0.1667, 0.1, 0.1, 0.9, 0.1, 0.1667, 0.6667, 0.1667, 0.6333, 0.1, 4),
(0.0333, 0.7, 0.1667, 0.1667, 0.9333, 0.6, 0.0667, 0.0333, 0.0333, 0.0333, 5),
(0.0333, 0.0667, 0.1, 0.8667, 0.1333, 0.0333, 0.6333, 0.0667, 0.1, 0.6, 4),
(0.1667, 0.9, 0.5667, 0.0667, 0.1, 0.1, 0.6333, 0.0333, 0.1, 0.1, 2),
(0.0333, 0.0333, 0.1, 0.1, 0.1333, 0.1, 0.6667, 0.6, 0.1333, 0.8667, 10),
(0.1, 0.5333, 0.1, 0.1333, 0.1667, 0.9333, 0.7, 0.1333, 0.1, 0.1667, 6),
(0.8667, 0.6333, 0.6, 0.0333, 0.1333, 0.1333, 0.0667, 0.0333, 0.1333, 0.1, 1),
(0.1333, 0.5, 0.9, 0.1, 0.1667, 0.0333, 0.1, 0.1333, 0.1667, 0.6667, 3),
(0.0333, 0.1, 0.0333, 0.0667, 0.6333, 0.0333, 0.9333, 0.0667, 0.6, 0.1333, 7),
(0.1333, 0.1333, 0.0667, 0.1, 0.0333, 0.6333, 0.0667, 0.0667, 0.7333, 0.8667, 10),
(0.9, 0.0667, 0.6667, 0.1, 0.6, 0.0333, 0.1333, 0.1667, 0.1667, 0.0333, 1),
(0.1333, 0.1667, 0.6, 0.6, 0.1667, 0.1333, 0.8333, 0.1333, 0.1333, 0.1667, 7),
(0.8333, 0.1333, 0.0333, 0.1333, 0.1333, 0.5333, 0.7667, 0.1333, 0.1, 0.0333, 1),
(0.8, 0.1333, 0.1667, 0.7333, 0.8667, 0.1667, 0.0667, 0.1, 0.1667, 0.0333, 5),
(0.0333, 0.0333, 0.0333, 0.1667, 0.8333, 0.4667, 0.1333, 0.5667, 0.1, 0.1667, 5),
(0.0333, 0.0333, 0.1667, 0.9, 0.6333, 0.0333, 0.1, 0.1667, 0.1667, 0.6333, 4),
(0.5333, 0.1667, 0.1667, 0.1333, 0.1, 0.1667, 0.0667, 1.0, 0.1, 0.6, 8),
(0.1, 0.0333, 0.6333, 0.1667, 0.0333, 0.1, 0.0667, 0.9333, 0.0333, 0.5333, 8),
(0.8333, 0.6333, 0.1667, 0.1667, 0.0333, 0.1333, 0.1667, 0.0667, 0.5, 0.1, 1),
(0.0333, 0.0333, 0.0333, 0.8, 0.1667, 0.1667, 0.7, 0.8333, 0.0333, 0.0667, 8),
(0.0667, 0.0333, 0.0667, 0.5667, 0.0333, 0.7667, 0.1667, 0.1333, 0.9, 0.0667, 9),
(0.5333, 0.0333, 0.1333, 0.5667, 0.1667, 0.1667, 0.1333, 0.0333, 0.0667, 0.8333, 10),
(0.1333, 0.1, 0.1333, 0.6333, 0.1667, 0.1333, 0.6, 0.1333, 0.8667, 0.1667, 9),
(0.1667, 0.0333, 0.1333, 0.9, 0.7, 0.1, 0.1333, 0.1333, 0.1667, 0.7, 4),
(0.0333, 0.1667, 0.6333, 0.1, 0.1, 0.8333, 0.1333, 0.6, 0.0333, 0.0333, 6),
(0.1, 0.9, 0.1667, 0.0667, 0.0667, 0.6333, 0.0333, 0.1333, 0.1333, 0.6333, 2),
(0.7333, 0.1667, 0.6333, 0.0333, 0.8667, 0.1333, 0.1, 0.0667, 0.0333, 0.1333, 5),
(0.0333, 0.8667, 0.0667, 0.0667, 0.0333, 0.5667, 0.0667, 0.5333, 0.0667, 0.1333, 2),
(0.5667, 0.0667, 0.1, 0.0667, 0.0667, 0.1, 0.6, 0.8333, 0.1, 0.1333, 8),
(0.7, 0.9, 0.1667, 0.1, 0.1333, 0.0667, 0.0667, 0.6333, 0.1, 0.1, 2),
(0.9, 0.1667, 0.6667, 0.1333, 0.6333, 0.0667, 0.1333, 0.0667, 0.0333, 0.1333, 1),
(0.5, 0.0667, 0.0333, 0.7, 0.1333, 0.1667, 0.0667, 0.9, 0.1, 0.0333, 8),
(0.0667, 0.1333, 0.9333, 0.7333, 0.1, 0.6, 0.0333, 0.0333, 0.1, 0.0667, 3),
(0.1333, 0.1, 0.0333, 0.6667, 0.1333, 0.1, 0.1667, 0.9, 0.1333, 0.5667, 8),
(0.0333, 0.6, 0.8667, 0.1333, 0.0333, 0.1, 0.0333, 0.1, 0.1667, 0.6333, 3),
(0.0667, 0.0667, 0.0667, 0.0667, 0.1667, 0.1333, 0.0667, 0.5667, 0.7667, 0.6333, 9),
(0.1667, 0.6333, 0.1, 0.0667, 0.1667, 0.0667, 0.0333, 0.1667, 0.5667, 0.8, 10),
(0.6667, 0.6, 0.0333, 0.1333, 0.1667, 0.0667, 0.1333, 0.0333, 0.9333, 0.0333, 9),
(0.7, 0.0667, 0.1, 0.1333, 0.1333, 0.1, 0.1333, 0.8667, 0.1333, 0.7, 8),
(0.7, 0.1, 0.1333, 0.1333, 0.0667, 0.1333, 0.8667, 0.0333, 0.6, 0.0333, 7),
(0.1333, 0.1667, 0.0667, 0.0333, 0.1667, 0.1333, 0.6667, 0.8667, 0.1667, 0.6667, 8),
(0.0333, 0.1333, 0.1333, 0.8667, 0.7333, 0.0667, 0.0667, 0.6333, 0.0667, 0.1333, 4),
(0.1333, 0.1667, 0.1667, 0.0667, 0.1333, 0.7, 0.6, 0.0333, 0.1667, 0.8667, 10),
(0.1, 0.0667, 0.8333, 0.6, 0.1333, 0.7, 0.1333, 0.1, 0.1333, 0.1333, 3),
(0.6667, 0.0333, 0.0667, 0.1333, 0.1, 0.1, 0.1, 0.5, 0.8333, 0.1, 9),
(0.0667, 0.1, 0.1667, 0.0667, 0.0667, 0.8333, 0.7333, 0.0667, 0.6667, 0.1, 6),
(0.6, 0.1333, 0.8667, 0.0667, 0.1667, 0.0667, 0.0333, 0.1333, 0.7333, 0.0667, 3),
(0.5667, 0.0667, 0.1667, 0.1333, 0.8667, 0.1667, 0.1667, 0.0667, 0.6, 0.1, 5),
(0.0667, 0.0333, 0.1, 0.5, 0.1333, 0.1, 0.1667, 0.5333, 0.8667, 0.1, 9),
(0.0667, 0.8, 0.0333, 0.1667, 0.1, 0.1333, 0.9, 0.1, 0.1667, 0.7, 7),
(0.0333, 0.1333, 0.1667, 0.0333, 0.0333, 0.1667, 0.1, 0.7, 0.8333, 0.6, 9),
(0.0333, 0.0667, 0.0333, 0.0333, 0.1, 0.5667, 0.8333, 0.6333, 0.0667, 0.0333, 7),
(0.1667, 0.1333, 0.6667, 0.1, 0.8333, 0.6333, 0.1333, 0.0667, 0.0333, 0.1333, 5),
(0.0667, 0.1333, 0.9, 0.0333, 0.0333, 0.1333, 0.8, 0.1, 0.6, 0.0667, 3),
(0.1667, 0.1667, 0.0667, 0.7, 0.1333, 0.6, 0.1667, 0.9, 0.0333, 0.1333, 8),
(0.1667, 0.7, 0.5667, 0.1, 0.8667, 0.0333, 0.1333, 0.0333, 0.0333, 0.1667, 5),
(0.1333, 0.1667, 0.1667, 0.0333, 0.0333, 0.8, 0.6667, 0.0333, 0.7333, 0.0667, 6),
(0.1333, 0.6667, 0.0333, 0.7, 0.1, 0.1333, 0.1667, 0.8667, 0.0667, 0.1333, 8),
(0.0333, 0.1667, 0.1333, 0.0333, 0.1333, 0.8667, 0.1667, 0.6333, 0.1, 0.7, 6),
(0.0333, 0.1333, 0.6, 0.0667, 0.4667, 0.1333, 0.0667, 0.0333, 0.8667, 0.0333, 9),
(0.6333, 0.1333, 0.1667, 0.0333, 0.1667, 0.9, 0.0333, 0.1667, 0.1333, 0.5333, 6),
(0.1333, 0.0333, 0.5333, 0.0667, 0.0333, 0.9667, 0.1333, 0.1667, 0.1667, 0.7667, 6),
(0.5, 0.1667, 0.8667, 0.0667, 0.1, 0.0667, 0.0667, 0.6, 0.0333, 0.0667, 3),
(0.0333, 0.0333, 0.1, 0.0333, 0.6333, 0.1667, 0.8667, 0.0667, 0.7333, 0.1667, 7),
(0.1667, 0.1, 0.1333, 0.8667, 0.5333, 0.0333, 0.0667, 0.0333, 0.7333, 0.1, 4),
(0.1333, 0.1, 0.0667, 0.0667, 0.7, 0.0333, 0.0667, 0.0667, 0.5667, 0.9333, 10),
(0.1, 0.1667, 0.1, 0.1, 0.7333, 0.0333, 0.1333, 0.8667, 0.5667, 0.1667, 8),
(0.1, 0.6667, 0.0667, 0.0667, 0.9, 0.1667, 0.1, 0.0333, 0.1333, 0.5333, 5),
(0.1, 0.6667, 0.1333, 0.1, 0.6667, 0.0667, 0.0667, 0.9, 0.1667, 0.1333, 8),
(0.0667, 0.1333, 0.0667, 0.0333, 0.1333, 0.6, 0.0333, 0.5333, 0.0667, 0.9333, 10),
(0.6667, 0.0333, 0.7, 0.0333, 0.1667, 0.1667, 0.8667, 0.0667, 0.0667, 0.1, 7),
(0.0333, 0.1, 0.1, 0.1333, 0.1333, 0.1, 0.8333, 0.5667, 0.6667, 0.0667, 7),
(0.0667, 0.1333, 0.0667, 0.0333, 0.9, 0.0333, 0.5667, 0.6333, 0.1667, 0.1, 5),
(0.1667, 0.1667, 0.1333, 0.0333, 0.8667, 0.6333, 0.0667, 0.7, 0.1333, 0.0667, 5),
(0.1667, 0.0667, 0.0667, 0.9, 0.0333, 0.1333, 0.0333, 0.5333, 0.1667, 0.7, 4),
(0.0667, 0.0667, 0.1, 0.7, 0.1333, 0.1, 0.1667, 0.0333, 0.7, 0.8667, 10),
(0.1667, 0.5667, 0.1, 0.0333, 0.0333, 0.1, 0.9667, 0.6333, 0.1667, 0.1667, 7),
(0.0667, 0.0667, 0.1333, 0.6, 0.0667, 0.1, 0.6667, 0.1, 0.1333, 0.8667, 10),
(0.1333, 0.8333, 0.1667, 0.5667, 0.0667, 0.1667, 0.0667, 0.0667, 0.0667, 0.5667, 2),
(0.6, 0.0667, 0.1, 0.0667, 0.8333, 0.0667, 0.6667, 0.1, 0.1667, 0.1333, 5),
(0.7333, 0.0333, 0.1, 0.1, 0.0667, 0.8667, 0.6667, 0.1333, 0.1, 0.1, 6),
(0.0333, 0.1667, 0.7, 0.1, 0.1667, 0.1333, 0.8667, 0.1667, 0.6, 0.1333, 7),
(0.1667, 0.7333, 0.1667, 0.1, 0.1667, 0.6333, 0.1333, 0.9333, 0.0333, 0.0333, 8),
(0.1667, 0.1, 0.1667, 0.6, 0.1, 0.1333, 0.6667, 0.9, 0.1333, 0.1333, 8),
(0.1667, 0.1, 0.1, 0.0333, 0.7, 0.8667, 0.1333, 0.1667, 0.0333, 0.6667, 6),
(0.0333, 0.1667, 0.1333, 0.1, 1.0, 0.6333, 0.5667, 0.0667, 0.1333, 0.0333, 5),
(0.1333, 0.1667, 0.9, 0.1, 0.1333, 0.1333, 0.0667, 0.6667, 0.0333, 0.6667, 3),
(0.1667, 0.1, 0.9333, 0.1, 0.1667, 0.6333, 0.7, 0.0667, 0.1667, 0.0333, 3),
(0.5667, 0.1667, 0.1667, 0.0667, 0.9333, 0.7, 0.1667, 0.1667, 0.1, 0.0667, 5),
(0.7667, 0.8667, 0.1667, 0.0333, 0.1667, 0.0667, 0.0667, 0.1667, 0.6, 0.1667, 2),
(0.6, 0.1333, 0.0667, 0.1333, 0.1333, 0.1667, 0.7667, 0.0333, 0.7333, 0.0667, 7),
(0.1667, 0.0667, 0.9667, 0.1333, 0.0333, 0.1333, 0.6, 0.1333, 0.6667, 0.1333, 3),
(0.0333, 0.1667, 0.6333, 0.1333, 0.8667, 0.0667, 0.6667, 0.0667, 0.0333, 0.0667, 5),
(0.6667, 0.1, 0.1, 0.5333, 0.1333, 0.9667, 0.0333, 0.1333, 0.0333, 0.1333, 6),
(0.1333, 0.9333, 0.1333, 0.1, 0.4667, 0.0333, 0.1333, 0.1667, 0.7, 0.1333, 2),
(0.7, 0.1, 0.0667, 0.9333, 0.1667, 0.1667, 0.6, 0.1667, 0.0667, 0.0667, 4),
(0.6, 0.1333, 0.6667, 0.1667, 0.1667, 0.9333, 0.1, 0.0333, 0.0333, 0.1, 6),
(0.1, 0.1667, 0.7, 0.0667, 0.0333, 0.0333, 0.0667, 0.0667, 0.8667, 0.6, 9),
(0.8, 0.1667, 0.0667, 0.1, 0.0667, 0.6, 0.6333, 0.1333, 0.0333, 0.0667, 1),
(0.1333, 0.1333, 0.1333, 0.0667, 0.1333, 0.9, 0.0667, 0.6667, 0.6333, 0.0333, 6),
(0.0667, 0.0333, 0.8667, 0.1, 0.1667, 0.0333, 0.6333, 0.7, 0.1333, 0.1333, 3),
(0.0667, 0.8333, 0.1667, 0.0333, 0.1, 0.6333, 0.7, 0.0667, 0.1667, 0.1333, 2),
(0.0667, 0.0667, 0.1, 0.1667, 0.0667, 0.1667, 0.7667, 0.6333, 0.9, 0.1667, 9),
(0.1333, 0.0333, 0.0333, 0.1333, 0.8, 0.6333, 0.6333, 0.1667, 0.1, 0.1667, 5),
(0.1, 0.1333, 0.1667, 0.8333, 0.1667, 0.6667, 0.1333, 0.5667, 0.0333, 0.0667, 4),
(0.7667, 0.1667, 0.0667, 0.9, 0.0333, 0.1, 0.1667, 0.6667, 0.1667, 0.1333, 4),
(0.0667, 0.1333, 0.6667, 0.1, 0.0667, 0.8667, 0.1333, 0.6667, 0.0667, 0.1333, 6),
(0.1333, 0.1667, 0.1, 0.6, 0.9333, 0.1333, 0.1667, 0.1, 0.0333, 0.5667, 5),
(0.0667, 0.7, 0.1333, 0.1, 0.1667, 0.7, 0.1, 0.1667, 0.9, 0.1, 9),
(0.1667, 0.1, 0.1333, 0.6667, 0.1, 0.8333, 0.0667, 0.6667, 0.0333, 0.1333, 6),
(0.1667, 0.9667, 0.5333, 0.1, 0.1333, 0.0333, 0.0667, 0.1, 0.1333, 0.6667, 2),
(0.0333, 0.1333, 0.1, 0.6333, 0.8333, 0.0667, 0.0333, 0.0333, 0.1333, 0.5667, 5),
(0.0333, 0.0667, 0.8667, 0.7, 0.0667, 0.1, 0.1, 0.0333, 0.0667, 0.6333, 3),
(0.1, 0.5333, 0.1667, 0.8, 0.0333, 0.0667, 0.7667, 0.1667, 0.1667, 0.1, 4),
(0.1667, 0.6, 0.1333, 0.0667, 0.1, 0.1667, 0.9667, 0.1, 0.0667, 0.6667, 7),
(0.8, 0.1333, 0.1333, 0.1667, 0.0333, 0.8667, 0.7, 0.0333, 0.1667, 0.0333, 6),
(0.0667, 0.1, 0.1667, 0.5667, 0.0333, 0.0667, 0.0333, 0.0667, 0.8333, 0.6333, 9),
(0.5667, 0.0333, 0.7, 0.1333, 0.9333, 0.1333, 0.0667, 0.0667, 0.0333, 0.1, 5),
(0.0333, 0.0667, 0.1667, 0.6667, 0.0333, 0.0667, 0.8667, 0.0667, 0.0667, 0.6, 7),
(0.1, 0.1333, 0.0333, 0.0667, 0.0667, 0.1333, 0.1, 0.6333, 0.6333, 0.9333, 10),
(0.6667, 0.1667, 0.8333, 0.1, 0.7333, 0.0333, 0.0333, 0.1, 0.1, 0.1667, 3),
(0.6333, 0.0667, 0.1, 0.1667, 0.0667, 0.8667, 0.0333, 0.6667, 0.1333, 0.0667, 6),
(0.0667, 0.0667, 0.1667, 0.7, 0.0667, 0.1667, 0.0667, 0.5333, 0.8667, 0.0667, 9),
(0.1667, 0.6667, 0.1, 0.8, 0.0333, 0.6667, 0.0333, 0.0667, 0.0667, 0.0333, 4),
(0.1333, 0.0333, 0.1667, 0.8667, 0.1667, 0.6333, 0.1333, 0.1, 0.1667, 0.5333, 4),
(0.6333, 0.1667, 0.9, 0.7667, 0.1333, 0.1333, 0.0333, 0.1667, 0.1, 0.0667, 3),
(0.1667, 0.5333, 0.8333, 0.0667, 0.0333, 0.1667, 0.0333, 0.6333, 0.1333, 0.1333, 3),
(0.5667, 0.7, 0.1333, 0.0667, 0.1, 0.1333, 0.8667, 0.1, 0.1333, 0.1333, 7),
(0.0667, 0.0333, 0.0667, 0.5333, 0.1333, 0.0667, 0.1667, 0.1333, 0.8667, 0.6, 9),
(0.0667, 0.1333, 0.1, 0.0667, 0.4667, 0.1333, 0.1667, 0.9, 0.6667, 0.0667, 8),
(0.0333, 0.1667, 0.1333, 0.1, 0.1333, 0.7, 0.8667, 0.6, 0.1, 0.0333, 7),
(0.6333, 0.1667, 0.1333, 0.1333, 0.8667, 0.0333, 0.1333, 0.0667, 0.6333, 0.1, 5),
(0.1333, 0.8667, 0.1667, 0.6667, 0.0667, 0.0333, 0.0667, 0.0333, 0.7, 0.0667, 2),
(0.1333, 0.1, 0.6333, 0.0333, 0.9333, 0.1, 0.1, 0.1, 0.0333, 0.7, 5),
(0.6667, 0.0667, 0.0333, 0.1667, 0.5667, 0.9667, 0.0333, 0.1, 0.0333, 0.1333, 6),
(0.0333, 0.0333, 0.0333, 0.0333, 0.8333, 0.1, 0.0333, 0.6667, 0.0667, 0.5667, 5),
(0.1, 0.1, 0.0333, 0.8, 0.0333, 0.6333, 0.1333, 0.1, 0.1333, 0.5333, 4),
(0.1667, 0.0667, 0.0333, 0.4667, 0.9, 0.6667, 0.1667, 0.0333, 0.1667, 0.1, 5),
(0.6333, 0.6333, 0.0667, 0.0667, 0.1333, 0.1667, 0.8667, 0.0667, 0.1667, 0.0667, 7),
(0.0667, 0.0333, 0.0667, 0.6667, 0.0333, 0.7, 0.1333, 0.1, 0.8667, 0.0333, 9),
(0.1333, 0.0667, 0.0667, 0.7333, 0.9, 0.1333, 0.0333, 0.1667, 0.6333, 0.0667, 5),
(0.6, 0.1333, 0.1, 0.0333, 0.9, 0.0333, 0.6333, 0.0333, 0.1667, 0.0667, 5),
(0.0667, 0.1333, 0.1667, 0.1667, 0.5, 0.7, 0.9333, 0.1667, 0.0333, 0.1667, 7),
(0.0333, 0.0667, 0.1667, 0.5667, 0.0333, 0.1333, 0.5333, 0.1, 0.0667, 0.9667, 10),
(0.7333, 0.1, 0.0333, 0.5667, 0.0667, 0.1, 0.0333, 0.8667, 0.1667, 0.1333, 8),
(0.9333, 0.1667, 0.1, 0.4667, 0.1667, 0.1667, 0.6333, 0.1333, 0.1, 0.1, 1),
(0.0667, 0.5333, 0.7667, 0.1, 0.0333, 0.8333, 0.0667, 0.1667, 0.1667, 0.1, 6),
(0.1667, 0.1333, 0.4667, 0.0333, 0.0667, 0.1, 0.1667, 0.6, 0.8333, 0.0333, 9),
(0.1667, 0.8667, 0.1333, 0.0667, 0.6, 0.0667, 0.7, 0.1667, 0.1, 0.1, 2),
(0.1, 0.1333, 0.0667, 0.1, 0.0667, 0.0667, 0.6667, 0.8333, 0.6333, 0.1333, 8),
(0.0333, 0.0333, 0.8667, 0.0667, 0.0333, 0.1667, 0.1333, 0.6667, 0.6, 0.0333, 3),
(0.0667, 0.0667, 0.1667, 0.1, 0.6, 0.9, 0.6, 0.0667, 0.1333, 0.1, 6),
(0.0333, 0.6667, 0.9, 0.1333, 0.1, 0.1333, 0.0667, 0.6333, 0.1667, 0.1333, 3),
(0.1333, 0.9333, 0.1667, 0.1333, 0.1333, 0.0667, 0.1, 0.7, 0.0667, 0.6667, 2),
(0.9, 0.0333, 0.0667, 0.7, 0.0667, 0.1, 0.0333, 0.1667, 0.7, 0.0667, 1),
(0.6, 0.0667, 0.1667, 0.1667, 0.7667, 0.1, 0.1333, 0.1, 0.8333, 0.1667, 9),
(0.0333, 0.1, 0.1333, 0.1667, 0.1333, 0.6667, 0.0333, 0.1333, 0.6333, 0.8667, 10),
(0.1, 0.1667, 0.0333, 0.1333, 0.8667, 0.0667, 0.6333, 0.1, 0.1333, 0.6667, 5),
(0.0333, 0.0667, 0.1333, 0.0333, 0.0333, 0.8, 0.0667, 0.7, 0.1333, 0.6333, 6),
(0.9, 0.1, 0.1333, 0.5333, 0.0667, 0.0667, 0.0667, 0.4667, 0.1, 0.1, 1),
(0.1, 0.1, 0.7, 0.0667, 0.9333, 0.1667, 0.0333, 0.1, 0.7333, 0.1333, 5),
(0.1667, 0.6, 0.1, 0.0667, 0.0333, 0.1333, 0.1667, 0.0667, 0.9667, 0.6667, 9),
(0.0333, 0.1, 0.8667, 0.0333, 0.6333, 0.0333, 0.1, 0.1333, 0.1333, 0.6333, 3),
(0.1333, 0.1, 0.0333, 0.0667, 0.1333, 0.6, 0.0667, 0.9, 0.6333, 0.0667, 8),
(0.0667, 0.1667, 0.1, 0.8333, 0.4667, 0.1667, 0.7, 0.1333, 0.0667, 0.1333, 4),
(0.0667, 0.1333, 0.6333, 0.0333, 0.1667, 0.1333, 0.6667, 0.9, 0.1667, 0.0333, 8),
(0.6667, 0.1333, 0.1667, 0.0333, 0.1333, 0.8667, 0.0667, 0.1, 0.0667, 0.6667, 6),
(0.0667, 0.1667, 0.1667, 0.9, 0.7, 0.0333, 0.0333, 0.0667, 0.6, 0.1333, 4),
(0.0333, 0.1, 0.7667, 0.1, 0.0667, 0.1333, 0.8667, 0.1333, 0.0667, 0.6, 7),
(0.5667, 0.0667, 0.1, 0.1333, 0.0333, 0.0333, 0.0667, 0.7, 0.1, 0.9, 10),
(0.0333, 0.0333, 0.5667, 0.1, 0.0333, 0.1333, 0.1333, 0.0667, 0.6, 0.8667, 10),
(0.1, 0.1333, 0.8667, 0.0333, 0.1, 0.1333, 0.7667, 0.1333, 0.1, 0.6333, 3),
(0.6, 0.1667, 0.0667, 0.6, 0.1667, 0.0333, 0.9333, 0.1333, 0.1667, 0.1667, 7),
(0.0667, 0.0667, 0.1333, 0.6333, 0.1667, 0.7, 0.9, 0.0667, 0.0333, 0.1, 7),
(0.0667, 0.1333, 0.1, 0.1333, 0.6, 0.5667, 0.8333, 0.0333, 0.1333, 0.0667, 7),
(0.0667, 0.1333, 0.1667, 0.5333, 0.1, 0.0667, 0.8667, 0.6, 0.1333, 0.1667, 7),
(0.1667, 0.0667, 0.8667, 0.0667, 0.1, 0.1667, 0.1, 0.6, 0.1, 0.6333, 3),
(0.0333, 0.1, 0.1, 0.1333, 0.1667, 0.1333, 0.1, 0.5667, 0.8667, 0.5333, 9),
(0.5333, 0.0667, 0.0667, 0.8333, 0.1, 0.0333, 0.1667, 0.6667, 0.0667, 0.0667, 4),
(0.1333, 0.1333, 0.0667, 0.6667, 0.1667, 0.1333, 0.5, 0.1, 0.8667, 0.1333, 9),
(0.6667, 0.1, 0.0667, 0.0333, 0.1667, 0.7333, 0.1667, 0.1667, 0.0333, 0.9667, 10),
(0.7667, 0.5333, 0.6667, 0.1, 0.0667, 0.0667, 0.0667, 0.1, 0.1, 0.1333, 1),
(0.0333, 0.9, 0.1333, 0.5333, 0.1667, 0.1667, 0.1333, 0.0333, 0.0667, 0.6, 2),
(0.0333, 0.1, 0.1, 0.1, 0.6667, 0.8667, 0.1333, 0.1333, 0.0667, 0.7333, 6),
(0.0333, 0.0333, 0.1667, 0.5, 0.0667, 0.0333, 0.6, 0.1667, 0.1, 0.9333, 10),
(0.1333, 0.1333, 0.7, 0.0333, 0.1667, 0.0667, 0.7, 0.0667, 0.8667, 0.1667, 9),
(0.0667, 0.1667, 0.6333, 0.0333, 0.0333, 0.6667, 0.9, 0.0667, 0.1, 0.0333, 7),
(0.1333, 0.0333, 0.5667, 0.0333, 0.1, 0.0667, 0.1, 0.1667, 0.7667, 0.9333, 10),
(0.6667, 0.7, 0.1333, 0.1333, 0.1667, 0.1333, 0.8333, 0.1333, 0.1667, 0.1, 7),
(0.8333, 0.1333, 0.1, 0.6667, 0.0333, 0.6333, 0.1667, 0.0667, 0.1, 0.0667, 1),
(0.1, 0.0667, 0.1, 0.6333, 0.6, 0.1333, 0.8333, 0.1333, 0.0667, 0.1667, 7),
(0.1667, 0.0667, 0.8333, 0.5667, 0.1667, 0.1, 0.1, 0.6667, 0.0333, 0.0333, 3),
(0.1, 0.1667, 0.9667, 0.1667, 0.1333, 0.0333, 0.6, 0.1, 0.0333, 0.6333, 3),
(0.0667, 0.1667, 0.8667, 0.1, 0.7, 0.0667, 0.1, 0.7, 0.0667, 0.0333, 3),
(0.1667, 0.1333, 0.7, 0.0333, 0.0667, 0.0333, 0.1667, 0.8333, 0.6333, 0.1333, 8),
(0.1333, 0.6333, 0.1333, 0.0667, 0.6, 0.8333, 0.1667, 0.1333, 0.1, 0.1333, 6),
(0.1333, 0.1, 0.0667, 0.8667, 0.6667, 0.1, 0.5667, 0.1, 0.1333, 0.1667, 4),
(0.0333, 0.0667, 0.6, 0.6333, 0.1, 0.1667, 0.1333, 0.1667, 0.1333, 0.8333, 10),
(0.1667, 0.5667, 0.6333, 0.0667, 0.0333, 0.1333, 0.0333, 0.1333, 0.9333, 0.0667, 9),
(0.0667, 0.8333, 0.8667, 0.1333, 0.1333, 0.6, 0.0667, 0.1333, 0.0667, 0.1667, 3),
(0.1, 0.1667, 0.0333, 0.1, 0.9, 0.5667, 0.5333, 0.1667, 0.0667, 0.1667, 5),
(0.0667, 0.1333, 0.9, 0.1, 0.6, 0.7, 0.0333, 0.0667, 0.0667, 0.0333, 3),
(0.0667, 0.1, 0.6667, 0.0333, 0.1, 0.1, 0.9333, 0.1667, 0.6333, 0.0667, 7),
(0.1667, 0.6333, 0.1, 0.1667, 0.1, 0.1, 0.1667, 0.1333, 0.7667, 0.6333, 9),
(0.1333, 0.1, 0.1667, 0.8333, 0.5667, 0.1667, 0.0333, 0.0667, 0.7, 0.1667, 4),
(0.0667, 0.5667, 0.1, 0.1, 0.8333, 0.1333, 0.0667, 0.1333, 0.1667, 0.7, 5),
(0.7333, 0.6333, 0.1333, 0.1667, 0.0667, 0.1, 0.1, 0.8667, 0.0333, 0.0333, 8),
(0.0667, 0.0667, 0.1333, 0.5333, 0.8333, 0.1667, 0.0333, 0.0667, 0.6333, 0.0333, 5),
(0.1667, 0.0333, 0.0333, 0.5667, 0.1333, 0.1667, 0.0333, 0.0667, 0.7, 0.9, 10),
(0.0333, 0.5667, 0.0667, 0.5667, 0.1333, 0.0667, 0.0333, 0.1333, 0.9, 0.1, 9),
(0.0667, 0.6667, 0.1667, 0.0667, 0.0333, 0.8333, 0.1667, 0.1667, 0.7333, 0.0667, 6),
(0.1, 0.1667, 0.7667, 0.0667, 0.1, 0.0667, 0.0333, 0.8667, 0.6333, 0.0333, 8),
(0.1, 0.1333, 0.0333, 0.1333, 0.1667, 0.5667, 0.5667, 0.9667, 0.0333, 0.0333, 8),
(0.1, 0.7, 0.7667, 0.1333, 0.5333, 0.1333, 0.0333, 0.0333, 0.0333, 0.1, 3),
(0.1333, 0.6333, 0.8667, 0.0333, 0.1333, 0.1, 0.0667, 0.1, 0.0667, 0.6333, 3),
(0.1667, 0.1667, 0.1667, 0.0667, 0.0333, 0.1, 0.1, 0.7333, 0.7667, 0.8667, 10),
(0.1, 0.9, 0.1, 0.0333, 0.5333, 0.1667, 0.0667, 0.5667, 0.0333, 0.1667, 2),
(0.0667, 0.1333, 0.1667, 0.1, 0.1667, 0.5667, 0.8667, 0.8, 0.1333, 0.1667, 7),
(0.6, 0.7, 0.0667, 0.1, 0.1667, 0.1667, 0.1333, 0.1667, 0.1333, 0.9667, 10),
(0.1333, 0.5667, 0.0333, 0.1, 0.1333, 0.0667, 0.0667, 0.1333, 0.5667, 0.9, 10),
(0.1667, 0.0333, 0.0333, 0.8667, 0.0667, 0.6333, 0.1, 0.1, 0.1, 0.5, 4),
(0.1333, 0.6667, 0.0333, 0.1667, 0.1667, 0.0667, 0.0667, 0.8333, 0.6, 0.1, 8),
(0.0333, 0.0667, 0.7667, 0.9, 0.6, 0.1333, 0.1667, 0.1333, 0.0333, 0.1, 4),
(0.1333, 0.1667, 0.0667, 0.9, 0.7333, 0.1333, 0.5667, 0.1667, 0.1333, 0.0667, 4),
(0.0667, 0.0667, 0.1333, 0.8333, 0.0333, 0.6667, 0.6, 0.1333, 0.0333, 0.0667, 4),
(0.5333, 0.0333, 0.1, 0.9, 0.6, 0.0333, 0.1, 0.0667, 0.1333, 0.0333, 4),
(0.1333, 0.5667, 0.1333, 0.1333, 0.8667, 0.1, 0.0667, 0.1, 0.0667, 0.6, 5),
(0.5333, 0.0333, 0.5667, 0.0333, 0.1333, 0.9667, 0.0667, 0.1667, 0.1667, 0.1, 6),
(0.1, 0.0667, 0.9333, 0.6333, 0.1667, 0.1, 0.1333, 0.0667, 0.6, 0.0667, 3),
(0.7, 0.1, 0.0667, 0.0333, 0.9, 0.1667, 0.1, 0.0333, 0.1333, 0.7333, 5),
(0.0667, 0.4667, 0.1667, 0.1, 0.0667, 0.8, 0.1667, 0.1333, 0.1, 0.7, 6),
(0.1333, 0.1667, 0.6667, 0.1667, 0.5667, 0.1333, 0.0333, 0.1, 0.0333, 0.9, 10),
(0.9, 0.0667, 0.1333, 0.1, 0.6, 0.1667, 0.0667, 0.0667, 0.5, 0.1333, 1),
(0.1, 0.0333, 0.6, 0.1667, 0.6, 0.8667, 0.1667, 0.1333, 0.1667, 0.1, 6),
(0.1, 0.5667, 0.6, 0.0333, 0.9, 0.1, 0.0667, 0.1333, 0.0667, 0.0333, 5),
(0.0333, 0.0667, 0.0667, 0.7, 0.1667, 0.6333, 0.8, 0.0333, 0.1667, 0.0333, 7),
(0.1667, 0.1, 0.0667, 0.0667, 0.6667, 0.9333, 0.1667, 0.1333, 0.7, 0.0333, 6),
(0.0333, 0.0667, 0.5667, 0.9333, 0.0333, 0.1667, 0.1667, 0.1667, 0.1, 0.6333, 4),
(0.8, 0.1, 0.6333, 0.0667, 0.0667, 0.0667, 0.1, 0.1333, 0.5333, 0.1, 1),
(0.1667, 0.0667, 0.0667, 0.1333, 0.8, 0.1667, 0.1667, 0.5, 0.6333, 0.0333, 5),
(0.1333, 0.9333, 0.7, 0.0333, 0.0333, 0.0333, 0.1667, 0.1333, 0.1, 0.7667, 2),
(0.8667, 0.0333, 0.1, 0.1667, 0.1, 0.7, 0.1333, 0.6667, 0.0667, 0.1333, 1),
(0.9, 0.7, 0.1, 0.1333, 0.6, 0.1333, 0.1, 0.0333, 0.1, 0.1, 1),
(0.1667, 0.8, 0.1, 0.1333, 0.1667, 0.0667, 0.5667, 0.0667, 0.1333, 0.5, 2),
(0.0333, 0.0667, 0.7667, 0.1333, 0.1333, 0.6667, 0.8, 0.0333, 0.1667, 0.0667, 7),
(0.1, 0.5667, 0.1, 0.1333, 0.0333, 0.0667, 0.6667, 0.1, 0.9, 0.1667, 9),
(0.0667, 0.1667, 0.6, 0.9333, 0.5667, 0.1667, 0.1333, 0.0333, 0.1333, 0.1333, 4),
(0.6, 0.0667, 0.9667, 0.6, 0.1, 0.1, 0.1, 0.1333, 0.1333, 0.1333, 3),
(0.9, 0.1667, 0.1333, 0.7, 0.0333, 0.1, 0.0333, 0.0333, 0.1333, 0.6, 1),
(0.9, 0.0333, 0.0333, 0.1333, 0.6, 0.8, 0.0333, 0.0667, 0.1667, 0.0667, 1),
(0.1333, 0.0667, 0.0667, 0.0667, 0.7667, 0.6, 0.9333, 0.0333, 0.1, 0.0333, 7),
(0.0333, 0.1, 0.0333, 0.1, 0.1333, 0.1333, 0.0333, 0.8667, 0.7667, 0.6667, 8),
(0.0667, 0.1667, 0.1667, 0.9, 0.1333, 0.6333, 0.1667, 0.6, 0.1667, 0.1, 4),
(0.6667, 0.1333, 0.1333, 0.1, 0.0667, 0.8333, 0.1333, 0.1, 0.6, 0.0667, 6),
(0.1333, 0.1333, 0.6667, 0.1333, 0.1667, 0.0333, 0.0333, 0.9, 0.1, 0.7333, 8),
(0.6333, 0.0333, 0.6333, 0.1333, 0.1, 0.8333, 0.1, 0.1667, 0.1333, 0.0333, 6),
(0.9, 0.1, 0.1, 0.0667, 0.6333, 0.1667, 0.0333, 0.0333, 0.6333, 0.1333, 1),
(0.8667, 0.0667, 0.1, 0.1667, 0.1333, 0.0333, 0.6, 0.0667, 0.7333, 0.1, 1),
(0.7, 0.1333, 0.1333, 0.6, 0.0667, 0.1667, 0.0667, 0.8667, 0.1333, 0.1333, 8),
(0.0333, 0.1667, 0.6667, 0.1667, 0.9, 0.0667, 0.0333, 0.6667, 0.0333, 0.1, 5),
(0.1, 0.7, 0.0333, 0.1, 0.0333, 0.0667, 0.0667, 0.0667, 0.7, 0.9333, 10),
(0.1667, 0.1333, 0.1, 0.0333, 0.1, 0.0667, 0.7333, 0.6333, 0.9333, 0.0667, 9),
(0.6, 0.6667, 0.9, 0.1667, 0.1333, 0.0667, 0.0333, 0.1667, 0.1, 0.0333, 3),
(0.6333, 0.0333, 0.0333, 0.0667, 0.0667, 0.1333, 0.1667, 0.0667, 0.6333, 0.8333, 10),
(0.6333, 0.1333, 0.1667, 0.6667, 0.1667, 0.1, 0.1333, 0.0333, 0.0667, 0.8667, 10),
(0.6333, 0.9, 0.1667, 0.6333, 0.1333, 0.1333, 0.0667, 0.1333, 0.1333, 0.0333, 2),
(0.1, 0.1, 0.1667, 0.6, 0.8667, 0.6667, 0.0667, 0.1333, 0.1667, 0.1667, 5),
(0.5333, 0.6, 0.1, 0.1, 0.0333, 0.1333, 0.1667, 0.0333, 0.1333, 0.9667, 10),
(0.1333, 0.6667, 0.6667, 0.1667, 0.1667, 0.0667, 0.8667, 0.1, 0.1, 0.1333, 7),
(0.0667, 0.1667, 0.1333, 0.9, 0.1667, 0.1333, 0.1, 0.6667, 0.0333, 0.5667, 4),
(0.1333, 0.9333, 0.1, 0.1667, 0.7, 0.1667, 0.1333, 0.1667, 0.1667, 0.6667, 2),
(0.1667, 0.1333, 0.9, 0.6667, 0.1, 0.1, 0.1, 0.6333, 0.0333, 0.1667, 3),
(0.1, 0.7, 0.5333, 0.1, 0.1, 0.0333, 0.9, 0.1333, 0.0667, 0.0667, 7),
(0.9333, 0.6333, 0.1, 0.1667, 0.1, 0.6333, 0.1333, 0.1, 0.1, 0.1333, 1),
(0.7, 0.1333, 0.6667, 0.1667, 0.8667, 0.1333, 0.1333, 0.1, 0.1, 0.1, 5),
(0.1, 0.0333, 0.1333, 0.1333, 0.1667, 0.8667, 0.1667, 0.6667, 0.5333, 0.1333, 6),
(0.1667, 0.0333, 0.0333, 0.0333, 0.6333, 0.0667, 0.0333, 0.8333, 0.7, 0.0667, 8),
(0.1667, 0.6333, 0.1333, 0.6, 0.0333, 0.1, 0.0333, 0.1667, 0.8667, 0.0333, 9),
(0.8667, 0.1, 0.1667, 0.6667, 0.1, 0.1333, 0.1, 0.1333, 0.1, 0.6667, 1),
(0.1333, 0.6333, 0.0333, 0.1667, 0.1667, 0.7, 0.1, 0.0667, 0.1333, 0.8667, 10),
(0.1333, 0.1667, 0.1333, 0.0667, 0.5667, 0.1667, 0.9, 0.6333, 0.1, 0.1, 7),
(0.6667, 0.7333, 0.0667, 0.8333, 0.0667, 0.0333, 0.0333, 0.0667, 0.1, 0.1667, 4),
(0.1333, 0.1333, 0.1333, 0.5667, 0.1667, 0.1333, 0.1667, 0.1, 0.5333, 0.9, 10),
(0.1, 0.1333, 0.5667, 0.9, 0.1333, 0.0333, 0.5, 0.1667, 0.0333, 0.0333, 4),
(0.5333, 0.6667, 0.0333, 0.0667, 0.1, 0.8333, 0.1667, 0.1, 0.0333, 0.1, 6),
(0.0667, 0.1667, 0.0333, 0.1, 0.1667, 0.1667, 0.5333, 0.9333, 0.0333, 0.6, 8),
(0.0667, 0.0333, 0.8, 0.1, 0.1667, 0.5667, 0.1667, 0.0333, 0.6333, 0.1, 3),
(0.5667, 0.1, 0.9, 0.0667, 0.1333, 0.1333, 0.0333, 0.6, 0.1333, 0.1333, 3),
(0.1, 0.1, 0.1, 0.1, 0.1, 0.6333, 0.6, 0.1333, 0.1, 0.8667, 10),
(0.1667, 0.5667, 0.0333, 0.0667, 0.6333, 0.0333, 0.0333, 0.0667, 0.0667, 0.9667, 10),
(0.0333, 0.0333, 0.1333, 0.5333, 0.9, 0.1333, 0.0333, 0.5667, 0.0333, 0.1333, 5),
(0.1667, 0.1, 0.0333, 0.7, 0.0333, 0.9, 0.1333, 0.8, 0.1, 0.0667, 6),
(0.0333, 0.1, 0.1667, 0.6333, 0.5333, 0.1, 0.9, 0.1, 0.1667, 0.1667, 7),
(0.1333, 0.6667, 0.8, 0.1, 0.1333, 0.0667, 0.6, 0.1333, 0.1333, 0.0333, 3),
(0.1333, 0.1, 0.1333, 0.8333, 0.1, 0.5667, 0.1333, 0.6333, 0.1667, 0.1667, 4),
(0.1333, 0.5667, 0.1, 0.7, 0.1, 0.1667, 0.9, 0.0667, 0.1333, 0.1333, 7),
(0.1, 0.1, 0.0667, 0.5667, 0.1333, 0.1333, 0.8, 0.1, 0.1333, 0.6333, 7),
(0.1, 0.8667, 0.1333, 0.1, 0.5667, 0.1667, 0.1667, 0.5667, 0.1333, 0.1667, 2),
(0.1333, 0.1333, 0.6667, 0.9, 0.6, 0.0333, 0.0667, 0.1, 0.1333, 0.0667, 4),
(0.1333, 0.1333, 0.5667, 0.0333, 0.5667, 0.1, 0.1333, 0.1333, 0.9, 0.0333, 9),
(0.1667, 0.0333, 0.0667, 0.1333, 0.6, 0.1667, 0.8333, 0.1, 0.1333, 0.6667, 7),
(0.8667, 0.1333, 0.1667, 0.0333, 0.6333, 0.1, 0.1333, 0.5667, 0.1667, 0.1333, 1),
(0.1667, 0.1333, 0.1, 0.8333, 0.7, 0.1667, 0.1333, 0.1667, 0.1333, 0.6667, 4),
(0.1667, 0.0667, 0.0667, 0.1, 0.0333, 0.6333, 0.1667, 0.1667, 0.6, 0.9333, 10),
(0.6333, 0.1333, 0.1, 0.1, 0.0333, 0.6, 0.1, 0.9, 0.1667, 0.1667, 8),
(0.0333, 0.1667, 0.1333, 0.1, 0.0667, 0.0333, 0.7333, 0.0333, 0.8667, 0.5, 9),
(0.1333, 0.1333, 0.7667, 0.1667, 0.6, 0.1333, 0.1333, 1.0, 0.1333, 0.0333, 8),
(0.1667, 0.1667, 0.5667, 0.0333, 0.8333, 0.1, 0.1333, 0.1333, 0.6, 0.1, 5),
(0.0667, 0.1667, 0.8333, 0.1667, 0.6, 0.1333, 0.6667, 0.1333, 0.1, 0.1667, 3),
(0.0333, 0.1667, 0.1333, 0.1667, 0.1, 0.5667, 0.9, 0.0667, 0.1667, 0.5, 7),
(0.1, 0.1667, 0.1667, 0.1333, 0.6667, 0.0333, 0.0667, 0.1667, 0.9333, 0.6667, 9),
(0.1333, 0.1, 0.6333, 0.1333, 0.1, 0.8667, 0.1333, 0.1667, 0.0667, 0.5667, 6),
(0.1667, 0.0333, 0.0333, 0.1, 0.6667, 0.0667, 0.8333, 0.1667, 0.5667, 0.1, 7),
(0.1, 0.1333, 0.0667, 0.0333, 0.6, 0.1667, 0.8667, 0.0667, 0.0333, 0.6, 7),
(0.0333, 0.1, 0.6667, 0.0333, 0.0333, 0.8667, 0.1333, 0.1333, 0.6333, 0.1333, 6),
(0.1333, 0.6, 0.1333, 0.1333, 0.1333, 0.0333, 0.0333, 0.9333, 0.1333, 0.6, 8),
(0.1667, 0.1667, 0.1333, 0.0333, 0.5667, 0.1667, 0.0667, 0.8667, 0.6333, 0.1333, 8),
(0.1667, 0.1667, 0.0333, 0.9, 0.1, 0.7667, 0.5333, 0.0667, 0.0667, 0.1333, 4),
(0.0333, 0.1667, 0.6667, 0.1333, 0.8, 0.1667, 0.6333, 0.1, 0.0333, 0.1333, 5),
(0.1333, 0.1667, 0.1, 0.1667, 0.1, 0.0667, 0.5, 0.6667, 0.8667, 0.0667, 9),
(0.0667, 0.7333, 0.7333, 0.0667, 0.0667, 0.0333, 0.0667, 0.1667, 0.8667, 0.1667, 9),
(0.1333, 0.6333, 0.0667, 0.0667, 0.6333, 0.8667, 0.0667, 0.1333, 0.0667, 0.0667, 6),
(0.0333, 0.1333, 0.8333, 0.6333, 0.1667, 0.6667, 0.1667, 0.0667, 0.0667, 0.0667, 3),
(0.7, 0.0667, 0.6, 0.0667, 0.0333, 0.0333, 0.0667, 0.1333, 0.8, 0.1333, 9),
(0.0667, 0.1, 0.1667, 0.6333, 0.0333, 0.9333, 0.0667, 0.1, 0.7, 0.0667, 6),
(0.9, 0.1, 0.1333, 0.1333, 0.1333, 0.6, 0.1333, 0.7333, 0.1667, 0.1, 1),
(0.1667, 0.1667, 0.9333, 0.1, 0.6, 0.1, 0.0667, 0.7, 0.1, 0.1667, 3),
(0.0667, 0.0333, 0.0667, 0.1, 1.0, 0.6667, 0.1333, 0.6, 0.1, 0.0667, 5),
(0.6667, 0.0333, 0.0333, 0.1667, 0.1333, 0.8667, 0.0333, 0.1667, 0.6667, 0.1333, 6),
(0.0667, 0.0333, 0.7333, 0.0333, 0.1, 0.6333, 0.0333, 0.0667, 0.8333, 0.1667, 9),
(0.1333, 0.1667, 0.7667, 0.0333, 0.1, 0.6, 0.1333, 0.9, 0.1333, 0.0667, 8),
(0.0667, 0.0667, 0.1, 0.6333, 0.1333, 0.1667, 0.0333, 0.6667, 0.1333, 0.8667, 10),
(0.1333, 0.5667, 0.1667, 0.1, 0.1, 0.1333, 0.1, 0.5667, 0.1667, 0.9333, 10),
(0.1333, 0.0333, 0.1, 0.1333, 0.6667, 0.6333, 0.0667, 0.1667, 0.9333, 0.0333, 9),
(0.1333, 0.0333, 0.0333, 0.1, 0.8667, 0.1333, 0.0333, 0.6, 0.0333, 0.7333, 5),
(0.6, 0.1333, 0.1, 0.1667, 0.1, 0.6333, 0.0333, 0.0667, 0.9333, 0.1, 9),
(0.9333, 0.0333, 0.0667, 0.1, 0.5, 0.0667, 0.0667, 0.5667, 0.0667, 0.1333, 1),
(0.0667, 0.8667, 0.6667, 0.0667, 0.1667, 0.1, 0.0667, 0.5, 0.1667, 0.1667, 2),
(0.1, 0.0667, 0.5333, 0.8667, 0.1, 0.5333, 0.0667, 0.0667, 0.0333, 0.1, 4),
(0.6, 0.1333, 0.1, 0.9, 0.1333, 0.0667, 0.6333, 0.1333, 0.1667, 0.1333, 4),
(0.0333, 0.0667, 0.1333, 0.7, 0.0333, 0.8333, 0.5667, 0.1, 0.1667, 0.1333, 6),
(0.1333, 0.9, 0.6, 0.1667, 0.1, 0.1333, 0.1333, 0.6, 0.0667, 0.1333, 2),
(0.0667, 0.0333, 0.8, 0.0333, 0.6333, 0.1333, 0.6333, 0.0667, 0.1667, 0.1333, 3),
(0.1333, 0.1, 0.1333, 0.8333, 0.1, 0.0333, 0.1333, 0.0667, 0.6333, 0.6333, 4),
(0.1, 0.1667, 0.1333, 0.0667, 0.6333, 0.0333, 0.6333, 0.9, 0.1667, 0.0333, 8),
(0.0667, 0.8, 0.1667, 0.0333, 0.6, 0.1, 0.0667, 0.1333, 0.6667, 0.1, 2),
(0.6, 0.1667, 0.1333, 0.1333, 0.0667, 0.1333, 0.1333, 0.0333, 0.8333, 0.5667, 9),
(0.1333, 0.0667, 0.1, 0.0667, 0.9, 0.6, 0.1667, 0.1333, 0.1667, 0.6333, 5),
(0.0667, 0.5, 0.0667, 0.1667, 0.7667, 0.8333, 0.0667, 0.1667, 0.0667, 0.0667, 6),
(0.1333, 0.0667, 0.0333, 0.6333, 0.0667, 0.1333, 0.6, 0.0667, 0.9, 0.0667, 9),
(0.9333, 0.1667, 0.0333, 0.6333, 0.0667, 0.1667, 0.0667, 0.6667, 0.1333, 0.1667, 1),
(0.1667, 0.5667, 0.1, 0.1667, 0.0333, 0.5667, 0.1333, 0.0333, 0.1333, 0.9, 10),
(0.0333, 0.0333, 0.6, 0.0667, 0.1, 0.0667, 0.9667, 0.1333, 0.6, 0.0333, 7),
(0.0333, 0.0333, 0.6667, 0.0667, 0.9333, 0.1667, 0.0333, 0.7667, 0.1, 0.1333, 5),
(0.0333, 0.6333, 0.1667, 0.0333, 0.1667, 0.9333, 0.1667, 0.0333, 0.1, 0.6333, 6),
(0.0667, 0.0333, 0.6667, 0.6667, 0.0333, 0.0667, 0.1667, 0.1667, 0.1, 0.9, 10),
(0.1667, 0.1333, 0.0333, 1.0, 0.1, 0.6333, 0.5667, 0.0667, 0.1333, 0.1, 4),
(0.0667, 0.7, 0.1, 0.5333, 0.8333, 0.1333, 0.1667, 0.1333, 0.1333, 0.0667, 5),
(0.0333, 0.0333, 0.7333, 0.0667, 0.1667, 0.1, 0.0667, 0.5667, 0.1, 0.8667, 10),
(0.0667, 0.0333, 0.1667, 0.1333, 0.1, 0.0667, 0.5667, 0.1667, 0.5667, 0.9333, 10),
(0.1667, 0.0667, 0.5667, 0.5667, 0.0333, 0.9, 0.1, 0.0667, 0.1, 0.1333, 6),
(0.1, 0.6667, 0.1, 0.1667, 0.0333, 0.0667, 0.1667, 0.0667, 0.7667, 0.9333, 10),
(0.8667, 0.0667, 0.6667, 0.1667, 0.0333, 0.1667, 0.1667, 0.0667, 0.1, 0.5667, 1),
(0.0667, 0.5667, 0.9, 0.1333, 0.1, 0.1, 0.6, 0.1333, 0.1, 0.0667, 3),
(0.1667, 0.6, 0.8333, 0.0333, 0.1333, 0.1667, 0.1667, 0.1333, 0.6, 0.1, 3),
(0.0667, 0.6667, 0.0333, 0.0667, 0.0333, 0.1, 0.6667, 0.1667, 0.1, 0.9, 10),
(0.0333, 0.8667, 0.0333, 0.1, 0.1333, 0.0667, 0.6667, 0.1333, 0.5333, 0.1, 2),
(0.1, 0.7667, 0.6, 0.1667, 0.0333, 0.1333, 0.5, 0.1333, 0.1667, 0.0667, 2),
(0.1667, 0.0667, 0.1, 0.1333, 0.6333, 0.1667, 0.1667, 0.9, 0.1333, 0.6667, 8),
(0.1667, 0.0333, 0.8, 0.0667, 0.1667, 0.1667, 0.1667, 0.9, 0.1333, 0.7, 8),
(0.6333, 0.1667, 0.9333, 0.0333, 0.0333, 0.1667, 0.1667, 0.6, 0.1333, 0.1, 3),
(0.1667, 0.6333, 0.0667, 0.1333, 0.1667, 0.0333, 0.9333, 0.1, 0.6667, 0.0667, 7),
(0.8667, 0.1, 0.0667, 0.1333, 0.5667, 0.1667, 0.5333, 0.1333, 0.1667, 0.0333, 1),
(0.1667, 0.6667, 0.6667, 0.1333, 0.0667, 0.1, 0.1, 0.1667, 0.9667, 0.1667, 9),
(0.0333, 0.0667, 0.1, 0.0333, 0.1667, 0.0333, 0.6333, 0.0333, 0.6333, 0.9333, 10),
(0.1333, 0.9333, 0.7667, 0.4667, 0.1, 0.0667, 0.0667, 0.1667, 0.1, 0.0667, 2),
(0.8667, 0.1667, 0.1667, 0.5667, 0.0333, 0.0333, 0.1333, 0.1, 0.1667, 0.7, 1),
(0.1667, 0.0333, 0.8333, 0.0667, 0.5667, 0.0667, 0.1333, 0.5667, 0.0333, 0.1, 3),
(0.1, 0.0667, 0.9333, 0.7333, 0.6667, 0.1667, 0.0667, 0.1667, 0.1, 0.1333, 3),
(0.1667, 0.1667, 0.6667, 0.1, 0.0667, 0.1667, 0.6333, 0.1333, 0.1667, 0.9, 10),
(0.1667, 0.1333, 0.0333, 0.0667, 0.6, 0.1667, 0.0667, 0.9333, 0.5667, 0.1, 8),
(0.1, 0.6667, 0.6667, 0.9333, 0.1667, 0.0333, 0.0333, 0.1667, 0.1, 0.1, 4),
(0.0667, 0.1, 0.0667, 0.6333, 0.0333, 0.0333, 0.0667, 0.5667, 0.8333, 0.1, 9),
(0.1667, 0.1333, 0.5, 0.0333, 0.0667, 0.8667, 0.1, 0.0333, 0.6, 0.0333, 6),
(0.0667, 0.0667, 0.0333, 0.1667, 0.0667, 0.1667, 0.1333, 0.9, 0.6667, 0.7, 8),
(0.0333, 0.0333, 0.0667, 0.9, 0.6333, 0.5667, 0.1333, 0.0667, 0.1333, 0.1667, 4),
(0.0333, 0.6333, 1.0, 0.1333, 0.1667, 0.1, 0.6667, 0.0333, 0.0333, 0.0333, 3),
(0.1, 0.1, 0.1, 0.1667, 0.6667, 0.1667, 0.0333, 0.0333, 0.9333, 0.5667, 9),
(0.0667, 0.0667, 0.8, 0.1333, 0.0333, 0.7, 0.1, 0.1, 0.6, 0.0333, 3),
(0.1, 0.1333, 0.1333, 0.6, 0.8, 0.0667, 0.1667, 0.7, 0.1667, 0.1, 5),
(0.1333, 0.5667, 0.5, 0.1333, 0.0333, 0.9, 0.1333, 0.0333, 0.1333, 0.0333, 6),
(0.0667, 0.1, 0.0667, 0.6, 0.8667, 0.0667, 0.0667, 0.7, 0.1, 0.0333, 5),
(0.0667, 0.1, 0.6333, 0.1333, 0.1333, 0.0667, 0.6333, 0.9333, 0.1667, 0.0333, 8),
(0.1, 0.0333, 0.6, 0.1, 0.1, 0.1, 0.7667, 0.1, 0.8667, 0.0333, 9),
(0.6, 0.8333, 0.0667, 0.6667, 0.0667, 0.1, 0.1, 0.1, 0.1333, 0.1667, 2),
(0.1667, 0.1, 0.1333, 0.8, 0.0333, 0.1667, 0.1, 0.1667, 0.9667, 0.6667, 9),
(0.1667, 0.1, 0.6667, 0.1333, 0.0667, 0.8667, 0.7, 0.0667, 0.1333, 0.0333, 6),
(0.6, 0.0667, 0.1667, 0.1, 0.1667, 0.1, 0.1, 0.6333, 0.9, 0.0333, 9),
(0.0667, 0.0667, 0.1667, 0.1333, 0.5667, 0.1, 0.6667, 0.1, 0.8, 0.1, 9),
(0.1, 0.0333, 0.7, 0.0333, 0.6667, 0.0667, 0.0333, 0.0333, 0.9333, 0.1333, 9),
(0.9, 0.1333, 0.0667, 0.0333, 0.7, 0.1, 0.0667, 0.0333, 0.1667, 0.7667, 1),
(0.0333, 0.1667, 0.0333, 0.1667, 0.8333, 0.7, 0.0333, 0.0667, 0.6, 0.0333, 5),
(0.1333, 0.7667, 0.1667, 0.0667, 0.1, 0.0667, 0.7333, 0.0333, 0.9, 0.1333, 9),
(0.0667, 0.5333, 0.0333, 0.1667, 0.8333, 0.1333, 0.6333, 0.1333, 0.0667, 0.1667, 5),
(0.1667, 0.8667, 0.0333, 0.0667, 0.5333, 0.6, 0.0333, 0.1667, 0.1667, 0.1667, 2),
(0.1333, 0.1, 0.1333, 0.4667, 0.6667, 0.1667, 0.0667, 0.0333, 0.1667, 0.9, 10),
(0.1667, 0.1333, 0.6667, 0.1667, 0.8, 0.7333, 0.1667, 0.1333, 0.1333, 0.0333, 5),
(0.0333, 0.8667, 0.1333, 0.0667, 0.1667, 0.1, 0.1, 0.5667, 0.0333, 0.5667, 2),
(0.0333, 0.1333, 0.6, 0.1667, 0.1, 0.5667, 0.1, 0.1333, 0.8667, 0.1, 9),
(0.0667, 0.1333, 0.9, 0.5333, 0.0333, 0.1333, 0.1667, 0.5, 0.0333, 0.0333, 3),
(0.0333, 0.0333, 0.1333, 0.5667, 0.1667, 0.1667, 0.9667, 0.1, 0.0667, 0.6, 7),
(0.1, 0.5667, 0.5333, 0.0333, 0.0667, 0.0667, 0.1333, 0.0667, 0.0333, 0.9333, 10),
(0.5667, 0.1, 0.1, 0.0667, 0.0667, 0.7333, 0.9667, 0.0333, 0.1, 0.1333, 7),
(0.5667, 0.1, 0.8333, 0.6, 0.0667, 0.1667, 0.0667, 0.0667, 0.1333, 0.1667, 3),
(0.1333, 0.8667, 0.1, 0.6, 0.1, 0.1333, 0.1, 0.6, 0.1333, 0.1333, 2),
(0.5333, 0.8667, 0.0333, 0.1667, 0.1, 0.1667, 0.1333, 0.0333, 0.6, 0.0333, 2),
(0.1, 0.9333, 0.0667, 0.0333, 0.1333, 0.0667, 0.5667, 0.1667, 0.5667, 0.0333, 2),
(0.1667, 0.8667, 0.6667, 0.1667, 0.5667, 0.1667, 0.0667, 0.1667, 0.1, 0.1667, 2),
(0.0333, 0.1667, 0.0667, 0.1333, 0.1, 0.8667, 0.1667, 0.7, 0.6667, 0.0667, 6),
(0.5667, 0.1, 0.1, 0.6667, 0.1333, 0.1333, 0.1667, 0.0333, 0.0667, 0.9333, 10),
(0.0333, 0.1667, 0.1333, 0.9333, 0.1333, 0.0333, 0.1667, 0.6333, 0.5667, 0.1, 4),
(0.1333, 0.0667, 0.8333, 0.5667, 0.0333, 0.0333, 0.6, 0.0333, 0.1, 0.0333, 3),
(0.0667, 0.1, 0.1333, 0.1667, 0.1667, 0.1667, 0.0667, 0.5333, 0.9667, 0.6667, 9),
(0.1333, 0.9, 0.1, 0.1333, 0.1667, 0.7, 0.1, 0.0667, 0.1667, 0.6667, 2),
(0.1, 0.7, 0.1, 0.9667, 0.1, 0.0333, 0.1667, 0.6333, 0.0667, 0.1333, 4),
(0.0667, 0.1, 0.0333, 0.0667, 0.5333, 0.1333, 0.1333, 0.1667, 0.9, 0.7333, 9),
(0.5667, 0.6667, 0.1667, 0.0333, 0.1, 0.0667, 0.0333, 0.0333, 0.1333, 0.9333, 10),
(0.8667, 0.6, 0.0667, 0.1667, 0.1, 0.6, 0.0333, 0.1667, 0.1333, 0.1333, 1),
(0.0667, 0.1667, 0.6667, 0.1, 0.6, 0.9333, 0.1333, 0.1, 0.1333, 0.1667, 6),
(0.1333, 0.1, 0.7, 0.1333, 0.6333, 0.9, 0.0667, 0.1667, 0.0667, 0.0667, 6),
(0.9667, 0.1333, 0.7, 0.0667, 0.0667, 0.1333, 0.1, 0.1667, 0.0667, 0.6333, 1),
(0.0667, 0.0667, 0.1, 0.5667, 0.9333, 0.1, 0.0667, 0.1667, 0.0333, 0.4667, 5),
(0.1, 0.1, 0.1667, 0.0667, 0.5, 0.0333, 0.0333, 0.0667, 0.6667, 0.9, 10),
(0.8333, 0.0667, 0.1333, 0.1667, 0.6333, 0.0667, 0.0333, 0.0667, 0.0667, 0.5667, 1),
(0.0333, 0.1333, 0.7, 0.1667, 0.1, 0.1333, 0.7, 0.0667, 0.0333, 0.8667, 10),
(0.1333, 0.1333, 0.6333, 0.1, 0.1667, 0.1333, 0.1333, 0.0333, 0.6667, 0.8333, 10),
(0.1333, 0.7, 0.0667, 0.0667, 0.5667, 0.1, 0.9, 0.0667, 0.0667, 0.1333, 7),
(0.1333, 0.0333, 0.6, 0.1333, 0.6333, 0.1667, 0.1333, 0.9333, 0.1333, 0.1333, 8),
(0.6333, 0.0333, 0.1667, 0.0333, 0.1333, 0.1333, 0.1667, 0.0667, 0.8, 0.9, 10),
(0.9, 0.0333, 0.0667, 0.6, 0.0667, 0.7333, 0.1667, 0.1333, 0.1333, 0.1333, 1),
(0.0667, 0.1, 0.6667, 0.0333, 0.1667, 1.0, 0.1333, 0.0667, 0.0333, 0.6667, 6),
(0.1667, 0.0667, 0.0667, 0.1, 0.5, 0.1667, 0.1667, 0.8667, 0.0667, 0.6, 8),
(0.0667, 0.5667, 0.9, 0.0667, 0.1, 0.0333, 0.1667, 0.1, 0.6667, 0.1333, 3),
(0.0333, 0.1333, 0.1333, 0.0667, 0.0667, 0.0667, 0.1333, 0.9667, 0.6667, 0.6667, 8),
(0.1333, 0.1333, 0.7, 0.6333, 0.0667, 0.8333, 0.1333, 0.0333, 0.1333, 0.1667, 6),
(0.8333, 0.1, 0.0667, 0.1, 0.0667, 0.6667, 0.0333, 0.6333, 0.1, 0.0333, 1),
(0.1667, 0.0333, 0.7333, 0.0667, 0.0333, 0.8667, 0.1, 0.5667, 0.1333, 0.1333, 6),
(0.0333, 0.6667, 0.7667, 0.0667, 0.1333, 0.0333, 0.1333, 0.6, 0.1667, 0.0667, 3),
(0.1667, 0.1333, 0.1333, 0.0667, 0.6333, 0.1333, 0.9333, 0.0333, 0.8, 0.1, 7),
(0.1667, 0.1333, 0.0333, 0.9, 0.0333, 0.1, 0.6333, 0.6333, 0.1, 0.1, 4),
(0.7, 0.1667, 0.1667, 0.0667, 0.6, 0.0333, 0.1333, 0.1, 0.1333, 0.9667, 10),
(0.0667, 0.0667, 0.1, 0.6667, 0.9333, 0.1333, 0.5667, 0.0333, 0.1333, 0.1333, 5),
(0.1, 0.0667, 0.1333, 0.8, 0.6333, 0.1333, 0.6667, 0.1333, 0.1667, 0.0333, 4),
(0.0333, 0.1, 0.0333, 0.0667, 0.6667, 0.0667, 0.8333, 0.1667, 0.6333, 0.0667, 7),
(0.6333, 0.1, 0.1333, 0.0333, 0.1, 0.1333, 0.1, 0.9333, 0.6333, 0.1333, 8),
(0.1, 0.0667, 0.0333, 0.6333, 0.1667, 0.1667, 0.0667, 0.0667, 0.9333, 0.6667, 9),
(0.1667, 0.1667, 0.1, 0.7, 0.1333, 0.1667, 0.6, 0.1333, 0.0667, 0.9333, 10),
(0.6667, 0.6, 0.0333, 0.0333, 0.1667, 0.1333, 0.1, 0.1333, 0.7667, 0.1667, 9),
(0.1667, 0.0667, 0.0667, 0.6, 0.0333, 0.0333, 0.6, 0.9, 0.0333, 0.1667, 8),
(0.0667, 0.1, 0.8333, 0.1333, 0.1333, 0.0333, 0.1667, 0.6667, 0.1, 0.6, 3),
(0.7, 0.8667, 0.0333, 0.1333, 0.1, 0.0667, 0.1667, 0.0333, 0.0667, 0.7, 2),
(0.0667, 0.0333, 0.7, 0.0667, 0.1667, 0.6667, 0.1333, 0.1333, 0.0333, 0.9667, 10),
(0.6667, 0.1667, 0.5667, 0.0333, 0.0667, 0.1333, 0.0667, 0.0333, 0.8667, 0.1, 9),
(0.1667, 0.0333, 0.8, 0.0333, 0.1333, 0.1667, 0.5333, 0.0667, 0.7, 0.0333, 3),
(0.1, 0.0667, 0.9, 0.1, 0.0333, 0.6333, 0.6333, 0.1667, 0.1333, 0.0333, 3),
(0.0667, 0.0333, 0.7, 0.5667, 0.1333, 0.1, 0.0667, 0.9, 0.1667, 0.1, 8),
(0.6667, 0.1, 0.9, 0.1667, 0.1333, 0.5667, 0.1, 0.1333, 0.1, 0.0667, 3),
(0.1667, 0.1333, 0.6333, 0.0667, 0.0333, 0.0667, 0.1333, 0.1, 0.5667, 0.9, 10),
(0.1667, 0.7, 0.7333, 0.1, 0.0333, 0.0333, 0.8333, 0.1, 0.1333, 0.1333, 7),
(0.1333, 0.1333, 0.8667, 0.5667, 0.1, 0.1, 0.1, 0.1333, 0.0333, 0.7, 3),
(0.0667, 0.0667, 0.1, 0.0667, 0.6667, 0.0333, 0.0333, 0.9, 0.6, 0.1, 8),
(0.6333, 0.0667, 0.1333, 0.0667, 0.1, 0.0667, 0.5667, 0.8667, 0.1333, 0.1333, 8),
(0.1667, 0.1667, 0.0667, 0.5667, 0.0333, 1.0, 0.1333, 0.7333, 0.1, 0.1667, 6),
(0.0667, 0.0333, 0.0333, 0.9, 0.0667, 0.1667, 0.7333, 0.0333, 0.1333, 0.6, 4),
(0.6, 0.0333, 0.0333, 0.9, 0.1667, 0.7333, 0.0333, 0.0333, 0.1, 0.0333, 4),
(0.9, 0.0667, 0.0333, 0.1333, 0.6333, 0.1667, 0.1333, 0.6667, 0.1333, 0.1333, 1),
(0.1667, 0.6667, 0.0667, 0.1667, 0.1, 0.1, 0.6667, 0.0333, 0.1333, 0.9333, 10),
(0.1333, 0.7, 0.0667, 0.0333, 0.8333, 0.1333, 0.0333, 0.1, 0.0667, 0.6333, 5),
(0.1, 0.1333, 0.0667, 0.0667, 0.0333, 0.7, 0.1333, 0.0333, 0.9333, 0.6333, 9),
(0.8333, 0.5667, 0.0333, 0.0667, 0.1, 0.1333, 0.1667, 0.1667, 0.7333, 0.0333, 1),
(0.1667, 0.0667, 0.0333, 0.1667, 0.1333, 0.1, 0.7, 0.9667, 0.0667, 0.5667, 8),
(0.1, 0.1667, 0.1667, 0.0333, 0.6, 0.6333, 0.9, 0.1333, 0.1667, 0.1667, 7),
(0.1667, 0.1333, 0.6333, 0.0667, 0.1333, 0.1667, 0.6333, 0.8333, 0.0667, 0.1667, 8),
(0.0333, 0.0333, 0.0667, 0.1667, 0.9333, 0.7, 0.0667, 0.7, 0.1333, 0.0333, 5),
(0.8333, 0.1667, 0.5, 0.7667, 0.1333, 0.0333, 0.1, 0.1333, 0.1333, 0.1, 1),
(0.0667, 0.0667, 0.0667, 0.8, 0.6333, 0.0333, 0.1667, 0.1667, 0.6333, 0.1, 4),
(0.1, 0.7, 0.1, 0.9, 0.0667, 0.1667, 0.0333, 0.1333, 0.6, 0.1667, 4),
(0.6, 0.1667, 0.0667, 0.0667, 0.1333, 0.1667, 0.8667, 0.1667, 0.0667, 0.6, 7),
(0.1667, 0.7667, 0.1667, 0.0667, 0.5333, 0.1, 0.8333, 0.1333, 0.1333, 0.0333, 7),
(0.1, 0.1333, 0.1, 0.0333, 0.6, 0.6333, 0.0667, 0.1, 0.1, 0.9333, 10),
(0.1667, 0.0333, 0.1667, 0.6667, 0.0667, 0.6, 0.1, 0.8333, 0.0333, 0.1333, 8),
(0.1333, 0.9333, 0.0333, 0.1, 0.7, 0.1667, 0.0333, 0.4667, 0.1667, 0.1333, 2),
(0.0667, 0.0667, 0.7333, 0.1, 0.1, 0.6667, 0.0667, 0.9333, 0.0667, 0.0667, 8),
(0.9333, 0.0667, 0.1333, 0.6667, 0.0667, 0.1667, 0.1333, 0.1, 0.0667, 0.6667, 1),
(0.6333, 0.6, 0.0667, 0.1667, 0.1, 0.1667, 0.0333, 0.0667, 0.0333, 0.8667, 10),
(0.1667, 0.1667, 0.7333, 0.8667, 0.0333, 0.1333, 0.1, 0.6333, 0.0667, 0.1, 4),
(0.1667, 0.1, 0.1333, 0.1333, 0.6333, 0.6, 0.0667, 0.0333, 0.1, 0.9333, 10),
(0.6333, 0.1, 0.1, 0.0667, 0.0333, 0.8667, 0.0667, 0.7333, 0.1, 0.1, 6),
(0.7333, 0.1333, 0.1333, 0.1333, 0.6667, 0.8667, 0.1667, 0.1333, 0.1667, 0.1333, 6),
(0.1, 0.0667, 0.1667, 0.0333, 0.6, 0.7, 0.9333, 0.0333, 0.1667, 0.1333, 7),
(0.8667, 0.5667, 0.1, 0.0333, 0.1, 0.1, 0.1, 0.1, 0.6667, 0.1667, 1),
(0.1667, 0.1333, 0.0667, 0.5333, 0.0333, 0.1333, 0.0333, 0.9, 0.1333, 0.7, 8),
(0.1667, 0.1333, 0.9333, 0.5667, 0.0333, 0.0667, 0.1333, 0.0667, 0.1667, 0.6, 3),
(0.5333, 0.1, 0.0667, 0.1, 0.0667, 0.0667, 0.9667, 0.1, 0.5, 0.0333, 7),
(0.5667, 0.1667, 0.1333, 0.1, 0.5333, 0.1333, 0.1, 0.0333, 0.8667, 0.1, 9),
(0.6667, 0.1, 0.1667, 0.1667, 0.1667, 0.0333, 0.1333, 0.8667, 0.1667, 0.6667, 8),
(0.1, 0.0333, 0.1, 0.5333, 0.7, 0.1, 0.0333, 0.1667, 0.1333, 0.9333, 10),
(0.1667, 0.0333, 0.0333, 0.9333, 0.1333, 0.0333, 0.1333, 0.1, 0.5333, 0.7333, 4),
(0.1667, 0.8, 0.0333, 0.1333, 0.1, 0.6333, 0.1667, 0.6667, 0.1, 0.0667, 2),
(0.6, 0.1333, 0.1333, 0.6333, 0.8667, 0.1333, 0.1, 0.1, 0.1333, 0.0333, 5),
(0.1333, 0.9333, 0.1333, 0.7667, 0.1667, 0.0333, 0.1333, 0.5667, 0.1333, 0.1, 2),
(0.8667, 0.1, 0.1333, 0.1333, 0.1333, 0.6333, 0.1333, 0.1333, 0.1, 0.6333, 1),
(0.8, 0.1, 0.1333, 0.0333, 0.1667, 0.1, 0.1667, 0.6667, 0.6, 0.0333, 1),
(0.1, 0.1667, 0.6, 0.0333, 0.6667, 0.1667, 0.0333, 0.8667, 0.1, 0.1333, 8),
(0.1667, 0.6333, 0.1333, 0.9333, 0.0667, 0.0333, 0.0333, 0.5333, 0.0333, 0.0333, 4),
(0.0333, 0.1667, 0.8667, 0.8333, 0.0667, 0.1667, 0.6, 0.0333, 0.1333, 0.1667, 3),
(0.1, 0.1333, 0.1333, 0.1667, 0.1333, 0.1333, 0.5333, 0.7667, 0.9, 0.0333, 9),
(0.6, 0.0333, 0.1, 0.1667, 0.0333, 0.1, 0.0667, 0.9333, 0.1, 0.6, 8),
(0.8667, 0.0667, 0.0333, 0.5667, 0.7667, 0.0333, 0.1, 0.1667, 0.1333, 0.0333, 1),
(0.0333, 0.0333, 0.1, 0.1, 0.1667, 0.6333, 0.0667, 0.9, 0.5333, 0.1333, 8),
(0.1333, 0.6, 0.1333, 0.5333, 0.1667, 0.1333, 0.1667, 0.1, 0.1667, 0.8, 10),
(0.1333, 0.5667, 0.1667, 0.1333, 0.9333, 0.1, 0.1, 0.6, 0.0667, 0.1667, 5),
(0.1333, 0.7333, 0.1667, 0.5667, 0.1333, 0.1667, 0.0667, 0.1333, 0.8333, 0.1333, 9),
(0.0667, 0.0333, 0.0333, 0.5333, 0.0667, 0.6333, 0.0333, 0.0333, 0.9667, 0.1, 9),
(0.9, 0.0333, 0.6333, 0.0667, 0.0667, 0.1, 0.1333, 0.7, 0.1667, 0.1, 1),
(0.0667, 0.0667, 0.9667, 0.0333, 0.0667, 0.1, 0.1333, 0.7333, 0.1667, 0.6667, 3),
(0.1333, 0.1, 0.1667, 0.1667, 0.6, 0.0333, 0.8667, 0.6, 0.0333, 0.0333, 7),
(0.1, 0.1, 0.1667, 0.1667, 0.1, 0.1333, 0.6, 0.5667, 0.1667, 0.8667, 10),
(0.7667, 0.1667, 0.1, 0.1, 0.6333, 0.8667, 0.1333, 0.1333, 0.0667, 0.1667, 6),
(0.0333, 0.0667, 0.7, 0.6667, 0.1333, 0.1333, 0.9, 0.1333, 0.1333, 0.1333, 7),
(0.6667, 0.0333, 0.1667, 0.1333, 0.5667, 0.8333, 0.1, 0.0333, 0.0333, 0.1333, 6),
(0.1333, 0.0667, 0.1, 0.1667, 0.7333, 0.0667, 0.9, 0.1, 0.1, 0.7333, 7),
(0.9667, 0.1, 0.1333, 0.7, 0.0667, 0.1667, 0.1667, 0.7333, 0.0667, 0.1333, 1),
(0.1667, 0.1667, 0.1, 0.8667, 0.1, 0.0333, 0.7, 0.1333, 0.0667, 0.6, 4),
(0.5333, 0.1667, 0.6, 0.1, 0.0333, 0.1333, 0.9, 0.1, 0.0333, 0.0333, 7),
(0.0667, 0.7, 0.0667, 0.1333, 0.1, 0.0333, 0.6667, 0.1, 0.9, 0.1333, 9),
(0.0667, 0.1, 0.1667, 0.0333, 0.1333, 0.5333, 0.8333, 0.0333, 0.7, 0.1333, 7),
(0.8, 0.1333, 0.6333, 0.0333, 0.1333, 0.1667, 0.1, 0.1, 0.1667, 0.6333, 1),
(0.6333, 0.0667, 0.1333, 0.5667, 0.1, 0.0333, 0.8667, 0.1667, 0.1667, 0.1, 7),
(0.5333, 0.1333, 0.1333, 0.5333, 0.8667, 0.1333, 0.1, 0.0333, 0.1, 0.0667, 5),
(0.9, 0.6333, 0.6667, 0.1, 0.0333, 0.1, 0.0333, 0.1333, 0.0667, 0.0333, 1),
(0.8667, 0.1, 0.5, 0.1667, 0.1333, 0.0667, 0.0667, 0.0333, 0.1, 0.6333, 1),
(0.7333, 0.0667, 0.0333, 0.1667, 0.6, 0.0333, 0.1333, 0.9, 0.1667, 0.1, 8),
(0.0667, 0.0667, 0.0333, 0.7667, 0.6333, 0.1667, 0.9333, 0.1, 0.0667, 0.0333, 7),
(0.0333, 0.1667, 0.1333, 0.8333, 0.1333, 0.0333, 0.6, 0.7, 0.0667, 0.1667, 4),
(0.6, 0.1333, 0.1333, 0.0333, 0.0667, 0.0333, 0.6, 0.0333, 0.1, 0.9333, 10),
(0.0667, 0.0667, 0.6, 0.0333, 0.1667, 0.1667, 0.9333, 0.1333, 0.1333, 0.5667, 7),
(0.0667, 0.6333, 0.0333, 0.1667, 0.1333, 0.1, 0.1333, 0.1667, 0.7, 0.9, 10),
(0.1667, 0.9333, 0.6667, 0.1333, 0.0333, 0.1667, 0.1, 0.1, 0.0333, 0.6, 2),
(0.0667, 0.6333, 0.6667, 0.1, 0.0333, 0.9, 0.0667, 0.0667, 0.1, 0.1667, 6),
(0.0333, 0.1, 0.6667, 0.0333, 0.5, 0.1333, 0.8667, 0.1333, 0.1, 0.1333, 7),
(0.7, 0.0333, 0.1333, 0.0667, 0.1, 0.1333, 0.8667, 0.0333, 0.1, 0.5, 7),
(0.0333, 0.9667, 0.1667, 0.0667, 0.1333, 0.6, 0.1333, 0.6333, 0.1, 0.1333, 2),
(0.6333, 0.6333, 0.0667, 0.0333, 0.0333, 0.0333, 0.1667, 0.1, 0.9, 0.0667, 9),
(0.1333, 0.0667, 0.6, 0.7, 0.9, 0.1333, 0.1667, 0.1667, 0.0333, 0.1667, 5),
(0.1333, 0.0333, 0.0667, 0.1, 0.1667, 0.6333, 0.1, 0.1, 0.9, 0.7333, 9),
(0.8333, 0.6333, 0.5667, 0.0333, 0.1, 0.1333, 0.1667, 0.0667, 0.1, 0.1333, 1),
(0.6333, 0.6333, 0.0667, 0.9333, 0.0333, 0.0333, 0.1667, 0.1333, 0.1333, 0.1, 4),
(0.1, 0.0333, 0.6333, 0.1667, 0.1333, 0.1, 0.9667, 0.1, 0.1667, 0.6667, 7),
(0.0333, 0.0667, 0.8667, 0.1333, 0.6, 0.0667, 0.1667, 0.1, 0.1667, 0.7, 3),
(0.0667, 0.5667, 0.6667, 0.1333, 0.0667, 0.1667, 0.8333, 0.1333, 0.1, 0.1333, 7),
(0.1, 0.0333, 0.5667, 0.8667, 0.0333, 0.1333, 0.6333, 0.0333, 0.1333, 0.0667, 4),
(0.1667, 0.1667, 0.6, 0.1, 0.1333, 0.9, 0.0667, 0.0667, 0.6667, 0.1667, 6),
(0.1, 0.1333, 0.0667, 0.0333, 0.0667, 0.0667, 0.5333, 0.8667, 0.0667, 0.6333, 8),
(0.1, 0.1333, 0.1333, 0.5667, 0.1, 0.9, 0.0667, 0.7333, 0.1333, 0.1333, 6),
(0.1667, 0.9, 0.7, 0.1, 0.0333, 0.6333, 0.0333, 0.0667, 0.1, 0.0333, 2),
(0.0667, 0.0333, 0.6, 0.1333, 0.1667, 0.9, 0.0333, 0.1667, 0.0667, 0.7, 6),
(0.1333, 0.0333, 0.8333, 0.0667, 0.1, 0.1667, 0.1667, 0.7333, 0.5, 0.0667, 3),
(0.0333, 0.0333, 0.1, 0.0667, 0.6667, 0.6333, 0.1333, 0.8333, 0.1, 0.1667, 8),
(0.0667, 0.1, 0.8333, 0.6667, 0.1, 0.0333, 0.1667, 0.7, 0.0667, 0.1667, 3),
(0.0667, 0.0667, 0.1667, 0.8333, 0.0333, 0.1333, 0.5333, 0.7, 0.1667, 0.1, 4),
(0.6333, 0.1333, 0.1, 0.6, 0.9, 0.1667, 0.1, 0.0333, 0.1667, 0.0667, 5),
(0.5, 0.1667, 0.1667, 0.1, 0.1, 0.0667, 0.6, 0.1667, 0.8333, 0.1667, 9),
(0.1333, 0.6333, 0.0333, 0.1667, 0.1333, 0.0667, 0.1, 0.1, 0.6333, 0.8667, 10),
(0.1, 0.1667, 0.0333, 0.8333, 0.0667, 0.8, 0.0667, 0.0333, 0.1333, 0.5667, 4),
(0.1667, 0.1667, 0.0667, 0.6, 0.8667, 0.1333, 0.0667, 0.5333, 0.1667, 0.0333, 5),
(0.0667, 0.1, 0.0333, 0.7, 0.8333, 0.1333, 0.0667, 0.1, 0.6667, 0.0667, 5),
(0.5667, 0.1333, 0.1667, 0.0333, 0.6667, 0.9, 0.0333, 0.1667, 0.0333, 0.1667, 6),
(0.6, 0.0667, 0.1667, 0.1, 0.1667, 0.0667, 0.9333, 0.0667, 0.6667, 0.1, 7),
(0.1, 0.0333, 0.0333, 0.0667, 0.1333, 0.1667, 0.1333, 0.6, 0.9333, 0.7333, 9),
(0.1667, 0.1667, 0.7667, 0.1333, 0.0667, 0.1333, 0.7667, 0.1667, 0.1, 0.8667, 10),
(0.0667, 0.1667, 0.5333, 0.0667, 0.9333, 0.7333, 0.1667, 0.1333, 0.1333, 0.1333, 5),
(0.6333, 0.7, 0.1667, 0.1, 0.1333, 0.1667, 0.1667, 0.8333, 0.1667, 0.0667, 8),
(0.0333, 0.0667, 0.6, 0.9, 0.0667, 0.0667, 0.1, 0.6333, 0.0667, 0.1333, 4),
(0.1667, 0.0667, 0.0333, 0.1, 0.6, 0.0667, 0.9, 0.1667, 0.1333, 0.6667, 7),
(0.1667, 0.0333, 0.0667, 0.6, 0.5667, 0.8667, 0.1667, 0.0333, 0.1667, 0.1333, 6),
(0.6, 0.1, 0.1667, 0.8667, 0.0333, 0.1, 0.0667, 0.1333, 0.6667, 0.0333, 4),
(0.1, 0.8333, 0.1, 0.6667, 0.6333, 0.1, 0.0333, 0.0333, 0.0667, 0.0667, 2),
(0.0667, 0.6333, 0.0667, 0.1667, 0.8333, 0.1333, 0.1, 0.6, 0.1333, 0.1, 5),
(0.1, 0.1, 0.1667, 0.0667, 0.8333, 0.0333, 0.7, 0.6, 0.1667, 0.0333, 5),
(0.1333, 0.4667, 0.1, 0.0333, 0.0333, 0.0667, 0.6333, 0.1667, 0.1, 0.8667, 10),
(0.0667, 0.1333, 0.0333, 0.8333, 0.1667, 0.0667, 0.0667, 0.1667, 0.6, 0.7, 4),
(0.1333, 0.6, 0.1333, 0.9667, 0.0333, 0.1, 0.0333, 0.1, 0.5667, 0.1333, 4),
(0.9, 0.1667, 0.0667, 0.6667, 0.1, 0.1333, 0.1667, 0.6333, 0.1333, 0.1667, 1),
(0.0667, 0.1667, 0.0667, 0.1667, 0.0333, 0.1667, 0.9333, 0.5, 0.0333, 0.6667, 7),
(0.1333, 0.6, 0.1667, 0.5667, 0.0667, 0.8667, 0.0667, 0.1333, 0.0667, 0.1333, 6),
(0.6, 0.1667, 0.0333, 0.8667, 0.0333, 0.0667, 0.1667, 0.1667, 0.1667, 0.6667, 4),
(0.1333, 0.1333, 0.6, 0.0333, 0.1, 0.5667, 0.1667, 0.8667, 0.1667, 0.0333, 8),
(0.1333, 0.1333, 0.9333, 0.1, 0.1, 0.0667, 0.6, 0.0667, 0.0333, 0.6333, 3),
(0.1, 0.1667, 0.1667, 0.1, 0.6333, 0.6667, 0.1, 0.8, 0.1667, 0.0667, 8),
(0.9, 0.0333, 0.7, 0.0333, 0.1, 0.0667, 0.0667, 0.1, 0.6667, 0.1, 1),
(0.0667, 0.0667, 0.1333, 0.6667, 0.0333, 0.0667, 0.1333, 0.9667, 0.0667, 0.6333, 8),
(0.5667, 0.0667, 0.8667, 0.0333, 0.1667, 0.1333, 0.0667, 0.7667, 0.1333, 0.1667, 3),
(0.0667, 0.0333, 0.1667, 0.0333, 0.0333, 0.0333, 0.6333, 0.8333, 0.1667, 0.6667, 8),
(0.1, 0.6, 0.1667, 0.1667, 0.7667, 0.0667, 0.8667, 0.0333, 0.0333, 0.1333, 7),
(0.1333, 0.1667, 0.1333, 0.1, 0.1667, 0.1667, 0.9333, 0.1, 0.6667, 0.5667, 7),
(0.1667, 0.6667, 0.1333, 0.1667, 0.8333, 0.1333, 0.0333, 0.1333, 0.5667, 0.1667, 5),
(0.6667, 0.6667, 0.1333, 0.1333, 0.9333, 0.1333, 0.1667, 0.0667, 0.0667, 0.0333, 5),
(0.6, 0.0333, 0.8667, 0.0333, 0.6, 0.1667, 0.1667, 0.0333, 0.1, 0.0667, 3),
(0.6667, 0.6333, 0.0333, 0.0667, 0.1, 0.0333, 0.0333, 0.1, 0.1667, 0.9667, 10),
(0.1667, 0.1, 0.1667, 0.1, 0.7, 0.1333, 0.5, 0.1333, 0.8667, 0.1667, 9),
(0.1333, 0.0667, 0.1, 0.0333, 0.0333, 0.6, 0.6667, 0.0667, 0.8333, 0.0333, 9),
(0.1333, 0.9333, 0.1333, 0.1333, 0.1, 0.5333, 0.0667, 0.0333, 0.1, 0.6, 2),
(0.0333, 0.5667, 0.9, 0.0667, 0.0667, 0.1, 0.1, 0.1667, 0.1667, 0.6, 3),
(0.0667, 0.8667, 0.5667, 0.0667, 0.6, 0.1333, 0.1667, 0.1, 0.1, 0.0667, 2),
(0.8667, 0.1333, 0.0333, 0.0333, 0.1667, 0.1667, 0.0667, 0.6333, 0.0667, 0.6667, 1),
(0.1667, 0.5, 0.1333, 0.1667, 0.0333, 0.1333, 0.1333, 0.1, 0.6667, 0.9, 10),
(0.9, 0.6667, 0.1333, 0.6667, 0.0333, 0.0667, 0.1333, 0.1667, 0.1667, 0.0667, 1),
(0.0333, 0.1333, 0.8667, 0.5667, 0.0667, 0.0333, 0.0333, 0.0333, 0.0667, 0.6667, 3),
(0.0333, 0.1667, 0.1667, 0.1333, 0.1667, 0.8333, 0.0333, 0.5667, 0.1667, 0.6, 6),
(0.1, 0.0667, 0.1667, 0.7333, 0.1, 0.1333, 0.8333, 0.5667, 0.1667, 0.0333, 7),
(0.1, 0.6667, 0.0667, 0.0667, 0.0667, 0.0333, 0.7333, 0.9, 0.1667, 0.0333, 8),
(0.1333, 0.0667, 0.0667, 0.8333, 0.1333, 0.1333, 0.0667, 0.6, 0.6, 0.1333, 4),
(0.9333, 0.7, 0.0667, 0.1333, 0.1667, 0.5, 0.1333, 0.1333, 0.1333, 0.0667, 1),
(0.6, 0.0333, 0.1, 0.0667, 0.6, 0.1, 0.1, 0.9, 0.1, 0.1667, 8),
(0.1, 0.1, 0.0333, 0.1333, 0.1333, 0.1333, 0.6667, 0.1, 0.6, 0.8333, 10),
(0.1333, 0.8333, 0.0333, 0.8, 0.0333, 0.0333, 0.6, 0.0667, 0.1, 0.1333, 2),
(0.1, 0.6, 0.1333, 0.1667, 0.0667, 0.0333, 0.0667, 0.6, 0.8667, 0.1, 9),
(0.0667, 0.1667, 0.1, 0.1667, 0.0333, 0.0667, 0.7, 0.1333, 0.5, 0.8667, 10),
(0.1667, 0.1333, 0.6667, 0.1667, 0.1667, 0.0667, 0.9, 0.6667, 0.1667, 0.1, 7),
(0.0667, 0.6667, 0.1667, 0.1667, 0.0667, 0.1333, 0.1, 0.0667, 0.5667, 0.9, 10),
(0.1667, 0.1667, 0.6333, 0.0333, 0.1667, 0.7, 0.1333, 0.8667, 0.0667, 0.1, 8),
(0.1333, 0.9333, 0.1, 0.1, 0.1, 0.1667, 0.1667, 0.1333, 0.5667, 0.7333, 2),
(0.9, 0.1667, 0.0667, 0.6333, 0.7, 0.0333, 0.0667, 0.1667, 0.1667, 0.1667, 1),
(0.1333, 0.1333, 0.6, 0.1667, 0.1667, 0.0667, 0.1, 0.6333, 0.0667, 0.9333, 10),
(0.1667, 0.0333, 0.0333, 0.5333, 0.1333, 0.6, 0.1, 0.1333, 0.0667, 0.9333, 10),
(0.7, 0.0667, 0.1, 0.8333, 0.1, 0.0333, 0.7333, 0.1333, 0.0667, 0.1333, 4),
(0.9667, 0.1, 0.5667, 0.1667, 0.0667, 0.1667, 0.6333, 0.1, 0.1333, 0.0667, 1),
(0.9, 0.1333, 0.0667, 0.1333, 0.0667, 0.1667, 0.5333, 0.0333, 0.1, 0.7333, 1),
(0.1, 0.0333, 0.6333, 0.5667, 0.1, 0.1667, 0.8, 0.1667, 0.0667, 0.1, 7),
(0.1667, 0.0667, 0.1, 0.9333, 0.0333, 0.1333, 0.7, 0.1, 0.7667, 0.1, 4),
(0.0667, 0.1, 0.0667, 0.6, 0.9, 0.0667, 0.1333, 0.0667, 0.1667, 0.5667, 5),
(0.0333, 0.5333, 0.0333, 0.1, 0.1, 0.1667, 0.1667, 0.8, 0.5, 0.1, 8),
(0.9333, 0.6333, 0.1, 0.0667, 0.1, 0.0333, 0.6, 0.0667, 0.0333, 0.0333, 1),
(0.1333, 0.1333, 0.1667, 0.6333, 0.0667, 0.8333, 0.1333, 0.0333, 0.7, 0.1667, 6),
(0.0667, 0.5667, 0.1667, 0.0667, 0.1667, 0.1333, 0.8333, 0.0667, 0.0333, 0.7, 7),
(0.0667, 0.1, 0.1667, 0.1333, 0.0333, 0.7, 0.9333, 0.1, 0.6667, 0.0333, 7),
(0.0667, 0.1333, 0.1667, 0.0667, 0.1333, 0.8667, 0.0333, 0.6333, 0.1667, 0.6667, 6),
(0.6333, 0.1667, 0.9, 0.0333, 0.1, 0.1, 0.1, 0.1667, 0.0667, 0.6, 3),
(0.1, 0.0667, 0.0333, 0.0333, 0.7333, 0.0333, 0.1, 0.7667, 0.1333, 0.8667, 10),
(0.0667, 0.8, 0.6667, 0.0333, 0.1667, 0.0667, 0.1333, 0.0667, 0.7667, 0.1667, 2),
(0.1, 0.5333, 0.1667, 0.0667, 0.8667, 0.1333, 0.1, 0.1, 0.6, 0.1667, 5),
(0.1, 0.8333, 0.1333, 0.6, 0.1333, 0.1667, 0.1667, 0.0667, 0.5667, 0.1, 2),
(0.0667, 0.1667, 0.0667, 0.1667, 0.1667, 0.1667, 0.6, 0.9, 0.1333, 0.5333, 8),
(0.5667, 0.0667, 0.0333, 0.0333, 0.8667, 0.1, 0.1, 0.0667, 0.1, 0.5667, 5),
(0.0667, 0.6667, 0.1667, 0.8, 0.0667, 0.1667, 0.0333, 0.1333, 0.8, 0.0333, 9),
(0.1, 0.1667, 0.6667, 0.5667, 0.1667, 0.0667, 0.1333, 0.9, 0.1333, 0.0667, 8),
(0.6667, 0.1667, 0.0667, 0.1333, 0.1667, 0.8667, 0.7, 0.1, 0.1, 0.0667, 6),
(0.1333, 0.1, 0.0667, 0.0667, 0.6333, 0.9, 0.5667, 0.1667, 0.1333, 0.0667, 6),
(0.1667, 0.1667, 0.6667, 0.1667, 0.1667, 0.1667, 0.8667, 0.7, 0.1333, 0.1333, 7),
(0.0667, 0.0333, 0.1667, 0.9333, 0.1333, 0.1, 0.0667, 0.7333, 0.1, 0.6667, 4),
(0.0667, 0.0333, 0.1, 0.0333, 0.0333, 0.8667, 0.5, 0.6667, 0.0667, 0.1667, 6),
(0.1333, 0.6667, 0.1333, 0.1667, 0.1667, 0.9, 0.5667, 0.1333, 0.0333, 0.1333, 6),
(0.6667, 0.8333, 0.1667, 0.0333, 0.5333, 0.1, 0.1, 0.1333, 0.1667, 0.0333, 2),
(0.0333, 0.0333, 0.7333, 0.1667, 0.0667, 0.1333, 0.6333, 0.1, 0.8333, 0.1667, 9),
(0.7, 0.1333, 0.5667, 0.8667, 0.1, 0.1667, 0.1333, 0.0667, 0.1333, 0.1333, 4),
(0.1, 0.5667, 0.9333, 0.0333, 0.1333, 0.6667, 0.0667, 0.1, 0.0333, 0.1333, 3),
(0.9333, 0.1, 0.1333, 0.0667, 0.6, 0.1667, 0.6, 0.1, 0.1333, 0.0667, 1),
(0.0333, 0.0667, 0.1, 0.7, 0.0333, 0.6667, 0.0667, 0.1667, 0.8667, 0.0333, 9),
(0.1, 0.0333, 0.1667, 0.0667, 0.6, 0.5667, 0.0667, 0.8667, 0.0333, 0.1667, 8),
(0.1667, 0.7, 0.1, 0.1, 0.8667, 0.1333, 0.5667, 0.0333, 0.1, 0.0667, 5),
(0.5667, 0.7333, 0.1333, 0.0333, 0.1, 0.1667, 0.8667, 0.1667, 0.1, 0.1667, 7),
(0.1333, 0.8333, 0.6333, 0.6667, 0.0333, 0.1, 0.1667, 0.1333, 0.0333, 0.1667, 2),
(0.0333, 0.1333, 0.1333, 0.1667, 0.7, 0.0333, 0.1667, 0.9667, 0.7333, 0.1333, 8),
(0.1667, 0.7, 0.8, 0.1, 0.1, 0.0333, 0.1333, 0.1, 0.0333, 0.6, 3),
(0.0333, 0.1333, 0.1333, 0.7, 0.8, 0.7667, 0.0667, 0.1333, 0.1, 0.1, 5),
(0.1, 0.1667, 0.6667, 0.1333, 0.9, 0.0333, 0.4667, 0.1, 0.1, 0.1, 5),
(0.1333, 0.0667, 0.0667, 0.1333, 0.8667, 0.6667, 0.0333, 0.0333, 0.0333, 0.5667, 5),
(0.0333, 0.1, 0.8, 0.1, 0.1667, 0.7, 0.1, 0.6, 0.1, 0.1667, 3),
(0.6, 0.0333, 0.7333, 0.1333, 0.1, 0.1333, 0.1333, 0.9, 0.1333, 0.1, 8),
(0.1333, 0.0333, 0.1333, 0.9333, 0.6667, 0.1667, 0.1, 0.0333, 0.0333, 0.5667, 4),
(0.1, 0.1333, 0.6667, 0.9333, 0.0667, 0.1, 0.1667, 0.6667, 0.0667, 0.1, 4),
(0.0333, 0.7667, 0.1667, 0.1, 0.9667, 0.0667, 0.6333, 0.1667, 0.0667, 0.1, 5),
(0.5667, 0.1667, 0.0667, 0.1667, 0.0333, 0.1333, 0.8667, 0.1, 0.1, 0.7, 7),
(0.1, 0.0333, 0.1333, 0.1333, 0.1333, 0.1667, 0.0667, 0.6, 0.8667, 0.7, 9),
(0.1, 0.0333, 0.5333, 0.1667, 0.9333, 0.0333, 0.5667, 0.0333, 0.0667, 0.0333, 5),
(0.1, 0.0667, 0.1667, 0.6333, 0.0667, 0.7333, 0.1667, 0.8333, 0.0667, 0.1667, 8),
(0.1667, 0.1667, 0.6333, 0.1333, 0.9, 0.5667, 0.1667, 0.0333, 0.1, 0.1667, 5),
(0.1, 0.1667, 0.6333, 0.0333, 0.1, 0.6667, 0.1333, 0.1667, 0.9, 0.1, 9),
(0.8, 0.0333, 0.0333, 0.1, 0.0333, 0.1333, 0.6667, 0.6333, 0.1, 0.1, 1),
(0.1667, 0.1667, 0.1667, 0.9, 0.1333, 0.0667, 0.7333, 0.7667, 0.0667, 0.1333, 4),
(0.0333, 0.0333, 0.1667, 0.6667, 0.1, 0.6667, 0.1333, 0.8667, 0.1333, 0.0667, 8),
(0.8667, 0.1, 0.1333, 0.1, 0.7333, 0.1333, 0.6, 0.0333, 0.1, 0.0667, 1),
(0.7, 0.0333, 0.0333, 0.1333, 0.8333, 0.1333, 0.1, 0.0667, 0.1333, 0.6, 5),
(0.7333, 0.1667, 0.1667, 0.1667, 0.0333, 0.0333, 0.0667, 0.8, 0.1, 0.6, 8),
(0.1667, 0.1333, 0.0333, 0.1667, 0.1, 0.6333, 0.1333, 0.0333, 0.6, 0.8333, 10),
(0.6333, 0.6333, 0.0667, 0.1667, 0.9, 0.1, 0.1667, 0.1333, 0.1333, 0.0333, 5),
(0.0333, 0.0667, 0.7667, 0.0667, 0.1, 0.1667, 0.5667, 0.1333, 0.6, 0.1333, 3),
(0.9, 0.1333, 0.0333, 0.0333, 0.7, 0.6, 0.1667, 0.1667, 0.0333, 0.0333, 1),
(0.1667, 0.9, 0.6667, 0.0667, 0.0333, 0.1667, 0.5333, 0.0667, 0.1667, 0.0333, 2),
(0.1667, 0.0667, 0.0667, 0.6, 0.1333, 0.8667, 0.1667, 0.6333, 0.1667, 0.1, 6),
(0.1, 0.1333, 0.5667, 0.0333, 0.0667, 0.6, 0.0333, 0.0333, 0.9, 0.1, 9),
(0.1, 0.9333, 0.1333, 0.1333, 0.0667, 0.1667, 0.0667, 0.1667, 0.5667, 0.6, 2),
(0.1667, 0.1333, 0.0667, 0.6333, 0.8667, 0.1333, 0.6333, 0.1667, 0.1667, 0.1333, 5),
(0.0333, 0.1333, 0.1333, 0.1667, 0.8333, 0.5667, 0.1, 0.1333, 0.6333, 0.1, 5),
(0.1667, 0.8667, 0.1, 0.6, 0.1, 0.1333, 0.7, 0.1, 0.1333, 0.1333, 2),
(0.6333, 0.1667, 0.0333, 0.6333, 0.1, 0.1667, 0.1, 0.0667, 0.1333, 0.8333, 10),
(0.6333, 0.6667, 0.0667, 0.1667, 0.1333, 1.0, 0.1, 0.1667, 0.0667, 0.1667, 6),
(0.1667, 0.7667, 0.0333, 0.0667, 0.0333, 0.7, 0.1, 0.1, 0.6, 0.1667, 2),
(0.1667, 0.5667, 0.8667, 0.1667, 0.1667, 0.0333, 0.1, 0.1, 0.5667, 0.1667, 3),
(0.1333, 0.1333, 0.1, 0.0667, 0.9, 0.1333, 0.6333, 0.0667, 0.1333, 0.7667, 5),
(0.1667, 0.1333, 0.6333, 0.0667, 0.1, 0.6667, 0.1, 0.8667, 0.1333, 0.1667, 8),
(0.0333, 0.0667, 0.0667, 0.5333, 0.0667, 0.6667, 0.0333, 0.1, 0.8333, 0.1, 9),
(0.8, 0.5667, 0.0667, 0.0667, 0.5667, 0.1333, 0.0667, 0.0667, 0.0333, 0.1667, 1),
(0.8667, 0.1667, 0.1667, 0.0667, 0.0333, 0.1667, 0.0333, 0.5667, 0.6, 0.1333, 1),
(0.0667, 0.1, 0.1, 0.8, 0.1667, 0.6667, 0.7, 0.1333, 0.0333, 0.0333, 4),
(0.1667, 0.6333, 0.7, 0.1667, 0.9333, 0.1333, 0.1, 0.0667, 0.1667, 0.0333, 5),
(0.1333, 0.6667, 0.5667, 0.0667, 0.1667, 0.0333, 0.1, 0.9, 0.1667, 0.1, 8),
(0.1667, 0.7, 0.0333, 0.9, 0.0333, 0.1667, 0.4333, 0.1667, 0.1333, 0.1667, 4),
(0.5667, 0.0667, 0.0333, 0.0333, 0.1667, 0.0333, 0.6667, 0.8667, 0.1667, 0.1, 8),
(0.7, 0.0667, 0.6667, 0.1667, 0.0667, 0.9333, 0.0333, 0.1, 0.1667, 0.1, 6),
(0.0333, 0.5667, 0.6, 0.1, 0.9333, 0.1333, 0.0667, 0.1333, 0.1, 0.1, 5),
(0.0667, 0.6, 0.0333, 0.0333, 0.0667, 0.1, 0.1333, 0.1, 0.9333, 0.5333, 9),
(0.1333, 0.1667, 0.6, 0.0333, 0.6667, 0.0667, 0.8667, 0.0667, 0.1333, 0.1667, 7),
(0.0667, 0.5333, 0.0333, 0.0333, 0.8667, 0.6, 0.1, 0.1667, 0.0667, 0.1333, 5),
(0.1, 0.6333, 0.1333, 0.0667, 0.1333, 0.0333, 0.1667, 0.0667, 0.6333, 0.9, 10),
(0.8667, 0.0667, 0.0667, 0.6667, 0.0667, 0.1333, 0.0333, 0.0333, 0.6, 0.1667, 1),
(0.1667, 0.1, 0.7333, 0.1, 0.1, 0.1667, 0.8, 0.1667, 0.0333, 0.5333, 7),
(0.1667, 0.0333, 0.1333, 0.0333, 0.9, 0.1, 0.6333, 0.1333, 0.1, 0.6, 5),
(0.5, 0.0333, 0.1, 0.1, 0.1333, 0.1333, 0.1, 0.8333, 0.1667, 0.6333, 8),
(0.8667, 0.1333, 0.6333, 0.0333, 0.1667, 0.6667, 0.0667, 0.1667, 0.0667, 0.1, 1),
(0.1333, 0.1, 0.1333, 0.1333, 0.0667, 0.7, 0.1667, 0.1667, 0.5333, 0.8667, 10),
(0.0667, 0.0333, 0.5333, 0.5667, 0.1333, 0.1667, 0.1333, 0.0333, 0.8333, 0.1667, 9),
(0.0667, 0.1333, 0.6, 0.5667, 0.0333, 0.1667, 0.1333, 0.1333, 0.1, 0.8333, 10),
(0.9, 0.1333, 0.1, 0.0667, 0.7333, 0.1667, 0.6667, 0.0333, 0.1667, 0.1, 1),
(0.0667, 0.9, 0.1667, 0.1667, 0.6667, 0.0333, 0.1667, 0.1, 0.1667, 0.7333, 2),
(0.7, 0.1333, 0.1667, 0.0667, 0.1333, 0.1333, 0.1, 0.7667, 0.8333, 0.1667, 9),
(0.0667, 0.1, 0.0333, 0.1333, 0.6333, 0.0667, 0.8667, 0.5667, 0.1333, 0.0667, 7),
(0.7, 0.1667, 0.5667, 0.0333, 0.1667, 0.0333, 0.1, 0.8667, 0.1333, 0.1333, 8),
(0.1667, 0.1, 0.1333, 0.1, 0.4667, 0.1, 0.6667, 0.8, 0.1333, 0.0667, 8),
(0.0333, 0.1333, 0.0667, 0.9333, 0.6, 0.0667, 0.1, 0.6333, 0.1333, 0.1333, 4),
(0.0667, 0.6667, 0.0333, 0.0333, 0.6667, 0.0667, 0.9, 0.0667, 0.0333, 0.1, 7),
(0.1667, 0.7, 0.0333, 0.8, 0.0333, 0.1, 0.1667, 0.0333, 0.0333, 0.5667, 4),
(0.0333, 0.8667, 0.5667, 0.1, 0.1, 0.1667, 0.6, 0.0333, 0.1667, 0.0333, 2),
(0.0333, 0.1, 0.0333, 0.1, 0.1, 0.6333, 0.1333, 0.9333, 0.6333, 0.0667, 8),
(0.1333, 0.5333, 0.7667, 0.1, 0.6, 0.1333, 0.0667, 0.1667, 0.1, 0.1333, 3),
(0.1667, 0.1667, 0.9, 0.1333, 0.1333, 0.1333, 0.5667, 0.0333, 0.6667, 0.0333, 3),
(0.9, 0.1333, 0.0333, 0.0333, 0.0667, 0.0667, 0.0667, 0.7, 0.7333, 0.0667, 1),
(0.6, 0.1, 0.1333, 0.1667, 0.1333, 0.8, 0.1, 0.0667, 0.1, 0.6, 6),
(0.1333, 0.9333, 0.0667, 0.1667, 0.0667, 0.6667, 0.5667, 0.0667, 0.0667, 0.1, 2),
(0.0667, 0.1667, 0.1333, 0.0667, 0.1333, 0.0333, 0.6, 0.0667, 0.9, 0.6, 9),
(0.1667, 0.1333, 0.0667, 0.1667, 0.6333, 0.7, 0.0333, 0.9, 0.1667, 0.1667, 8),
(0.1, 0.6333, 0.1, 0.0667, 0.1667, 0.9, 0.1333, 0.0333, 0.6, 0.1, 6),
(0.7333, 0.1333, 0.0333, 0.0667, 0.1333, 0.8333, 0.1, 0.0333, 0.1, 0.4667, 6),
(0.0333, 0.1333, 0.0667, 0.0333, 0.1667, 0.8667, 0.5333, 0.0333, 0.0667, 0.6, 6),
(0.6333, 0.1667, 0.0333, 0.0667, 0.0667, 0.0333, 0.1333, 0.1333, 0.6667, 0.8667, 10),
(0.1, 0.1333, 0.6333, 0.1333, 0.1667, 0.0333, 0.6333, 0.0333, 0.1333, 0.9667, 10),
(0.0667, 0.0333, 0.1667, 0.9667, 0.0333, 0.1333, 0.5667, 0.6667, 0.1333, 0.0333, 4),
(0.1, 0.0667, 0.0333, 0.1667, 0.9, 0.1, 0.0333, 0.6667, 0.8, 0.1, 5),
(0.1, 0.7, 0.0667, 0.6667, 0.0667, 0.9, 0.1667, 0.0667, 0.0667, 0.1667, 6),
(0.1333, 0.5667, 0.1333, 0.1, 0.0667, 0.1, 0.1667, 0.5333, 0.9, 0.1667, 9),
(0.0333, 0.1333, 0.0333, 0.5333, 0.8, 0.5667, 0.1333, 0.1667, 0.1, 0.0667, 5),
(0.1333, 0.1667, 0.0667, 0.9, 0.1667, 0.5333, 0.1333, 0.1333, 0.0333, 0.6667, 4),
(0.9333, 0.1333, 0.0333, 0.5333, 0.1, 0.8, 0.1333, 0.0333, 0.0667, 0.1667, 1),
(0.0333, 0.1, 0.0667, 0.1667, 0.6, 0.9333, 0.1667, 0.1667, 0.0333, 0.7, 6),
(0.1667, 0.1333, 0.1333, 0.1, 0.0667, 0.0667, 0.6, 0.0333, 0.6, 0.8667, 10),
(0.1667, 0.0667, 0.1333, 0.0667, 0.1667, 0.7667, 0.1667, 0.6667, 0.1333, 0.5333, 6),
(0.0667, 0.1667, 0.7667, 0.0667, 0.1333, 0.0667, 0.1333, 0.1333, 0.5333, 0.8, 3),
(0.9, 0.0667, 0.1667, 0.6, 0.1333, 0.1333, 0.1, 0.6667, 0.1, 0.0667, 1),
(0.1667, 0.5667, 0.0667, 0.0667, 0.1333, 0.0667, 0.9, 0.6667, 0.1667, 0.1333, 7),
(0.0333, 0.0667, 0.5667, 0.0333, 0.1333, 0.5667, 0.0667, 0.1333, 0.1667, 0.8333, 10),
(0.1, 0.0333, 0.0333, 0.6333, 0.0667, 0.1667, 0.1333, 0.9333, 0.1667, 0.5667, 8),
(0.8333, 0.6333, 0.1667, 0.0667, 0.1667, 0.7, 0.1667, 0.1, 0.0667, 0.0333, 1),
(0.9, 0.1667, 0.0333, 0.1667, 0.1333, 0.0333, 0.0333, 0.6333, 0.1333, 0.7333, 1),
(0.0333, 0.1, 0.5667, 0.1, 0.8667, 0.1667, 0.1333, 0.6667, 0.1667, 0.1, 5),
(0.7333, 0.1333, 0.1, 0.0333, 0.1667, 0.0667, 0.1333, 0.8667, 0.1, 0.6667, 8),
(0.1667, 0.1, 0.9, 0.7667, 0.1333, 0.0667, 0.1333, 0.6333, 0.1333, 0.0667, 3),
(0.5667, 0.8333, 0.5667, 0.1667, 0.1667, 0.0333, 0.0667, 0.1667, 0.1667, 0.1333, 2),
(0.8, 0.1333, 0.1333, 0.6333, 0.1, 0.7, 0.0667, 0.0333, 0.0333, 0.1, 1),
(0.5, 0.1333, 0.1333, 0.1333, 0.6, 0.0667, 0.0667, 0.8667, 0.1667, 0.1333, 8),
(0.0333, 0.7, 0.1333, 0.0333, 0.1667, 0.7333, 0.1, 0.1, 1.0, 0.1333, 9),
(0.0667, 0.7, 0.0667, 0.7, 0.1667, 0.1, 0.9667, 0.0333, 0.1333, 0.0667, 7),
(0.0667, 0.9, 0.0667, 0.1667, 0.0667, 0.0667, 0.7333, 0.6, 0.0333, 0.1333, 2),
(0.1, 0.8, 0.1333, 0.0667, 0.6667, 0.1333, 0.7, 0.1333, 0.0333, 0.0333, 2),
(0.1667, 0.6667, 0.0333, 0.1, 0.1, 0.0333, 0.8, 0.6, 0.1667, 0.0333, 7),
(0.1333, 0.1, 0.6667, 0.0333, 0.9333, 0.0667, 0.1667, 0.1333, 0.6, 0.0333, 5),
(0.1667, 0.0667, 0.1, 0.5667, 0.9333, 0.0667, 0.5667, 0.1333, 0.1667, 0.1, 5),
(0.6, 0.0333, 0.1667, 0.1667, 0.9, 0.1333, 0.6333, 0.1667, 0.0333, 0.1667, 5),
(0.7667, 0.1, 0.9, 0.1667, 0.1333, 0.1, 0.0667, 0.5, 0.1, 0.0333, 3),
(0.0333, 0.6333, 0.1, 0.1, 0.0333, 0.1, 0.6333, 0.0667, 0.1333, 0.9333, 10),
(0.1333, 0.9333, 0.5333, 0.0333, 0.6, 0.1, 0.1, 0.0333, 0.1333, 0.1667, 2),
(0.1333, 0.0333, 0.0333, 0.5667, 0.1, 0.9333, 0.1333, 0.6667, 0.1333, 0.1667, 6),
(0.5333, 0.0333, 0.0667, 0.9667, 0.0333, 0.7, 0.1667, 0.0667, 0.1, 0.0333, 4),
(0.5333, 0.0667, 0.8667, 0.6333, 0.1667, 0.0667, 0.1667, 0.0333, 0.1, 0.0667, 3),
(0.0667, 0.5667, 0.1, 0.1, 0.7333, 0.1333, 0.8333, 0.0333, 0.0333, 0.1333, 7),
(0.1333, 0.0667, 0.5, 0.0667, 0.6667, 0.8333, 0.1, 0.1333, 0.1667, 0.1, 6),
(0.6333, 0.0667, 0.0667, 0.1, 0.0333, 0.1667, 0.7, 0.1, 0.0667, 1.0, 10),
(0.1, 0.0667, 0.1333, 0.1667, 0.6667, 0.0333, 0.5667, 0.1, 0.0667, 0.9, 10),
(0.1667, 0.7333, 0.1667, 0.0333, 0.1667, 0.1667, 0.1667, 0.1333, 0.9333, 0.7333, 9),
(0.0333, 0.1333, 0.1, 0.1, 0.7667, 0.6, 0.1333, 0.0333, 0.1, 0.9, 10),
(0.0333, 0.1, 0.1667, 0.0667, 0.1333, 0.5667, 0.1333, 0.0333, 0.7, 0.8667, 10),
(0.1333, 0.1667, 0.6333, 0.0333, 0.0333, 0.8333, 0.1333, 0.0333, 0.6, 0.0667, 6),
(0.0333, 0.0333, 0.1333, 0.9333, 0.5667, 0.1667, 0.0333, 0.6667, 0.0667, 0.1333, 4),
(0.0333, 0.6333, 0.1, 0.6, 0.0667, 0.8333, 0.1667, 0.1667, 0.0667, 0.1667, 6),
(0.9, 0.5333, 0.1667, 0.1333, 0.0667, 0.0667, 0.0667, 0.1333, 0.7333, 0.0333, 1),
(0.5333, 0.6667, 0.0667, 0.0333, 0.1333, 0.1333, 0.8667, 0.0667, 0.1667, 0.1, 7),
(0.8333, 0.0333, 0.7, 0.1667, 0.0333, 0.0667, 0.0667, 0.0667, 0.1667, 0.7333, 1),
(0.0333, 0.8, 0.6333, 0.0333, 0.1333, 0.6, 0.1, 0.0333, 0.0667, 0.0667, 2),
(0.1, 0.9333, 0.1333, 0.1667, 0.1, 0.0667, 0.1667, 0.6667, 0.1667, 0.5333, 2),
(0.6, 0.1, 0.9, 0.1333, 0.0667, 0.1333, 0.1667, 0.1333, 0.6667, 0.1, 3),
(0.0667, 0.1333, 0.0333, 0.1667, 0.0667, 0.1667, 0.6667, 0.0333, 0.7, 0.9333, 10),
(0.0333, 0.1, 0.1333, 0.0333, 0.5333, 0.0667, 0.1, 0.0333, 0.8333, 0.7, 9),
(0.8667, 0.1333, 0.0333, 0.0667, 0.1, 0.6333, 0.0333, 0.1667, 0.1667, 0.5667, 1),
(0.6, 0.1333, 0.1, 0.9, 0.1667, 0.0667, 0.1667, 0.7, 0.1, 0.1667, 4),
(0.1333, 0.1, 0.0333, 0.1333, 0.9, 0.1333, 0.1667, 0.8, 0.5333, 0.0333, 5),
(0.0667, 0.1333, 0.1, 0.1, 0.0333, 0.8667, 0.6333, 0.6333, 0.1, 0.0333, 6),
(0.1333, 0.1, 0.9333, 0.1333, 0.6333, 0.0667, 0.1667, 0.1333, 0.7, 0.1, 3),
(0.9, 0.1667, 0.1, 0.1667, 0.6333, 0.1, 0.1333, 0.0667, 0.1333, 0.7667, 1),
(0.0333, 0.7, 0.9, 0.0333, 0.0667, 0.6667, 0.1667, 0.1667, 0.1, 0.0333, 3),
(0.1667, 0.1, 0.5333, 0.0667, 0.8333, 0.1, 0.1, 0.1333, 0.1, 0.6667, 5),
(0.1, 0.1667, 0.1667, 0.8, 0.5667, 0.1333, 0.0333, 0.0667, 0.5333, 0.1667, 4),
(0.9667, 0.1333, 0.0667, 0.6667, 0.1667, 0.1, 0.1667, 0.1333, 0.6333, 0.1, 1),
(0.5667, 0.6, 0.8333, 0.1, 0.0667, 0.1667, 0.1667, 0.1667, 0.1667, 0.0333, 3),
(0.0333, 0.0667, 0.0333, 0.6, 0.7667, 0.0667, 0.1, 0.1667, 0.0333, 0.8333, 10),
(0.0667, 0.0333, 0.5333, 0.9, 0.0667, 0.7667, 0.0667, 0.0667, 0.0667, 0.1, 4),
(0.0667, 0.1, 0.1, 0.9, 0.0333, 0.6333, 0.0333, 0.0333, 0.1667, 0.6, 4),
(0.1333, 0.6333, 0.0333, 0.1667, 0.9, 0.1667, 0.5333, 0.1, 0.0333, 0.1667, 5),
(0.9333, 0.6667, 0.6, 0.0667, 0.0667, 0.0333, 0.0667, 0.1, 0.0333, 0.0333, 1),
(0.0333, 0.1, 0.7, 0.1, 1.0, 0.1333, 0.1667, 0.0667, 0.5667, 0.0667, 5),
(0.0333, 0.6, 0.0667, 0.1667, 0.1333, 0.1, 0.0333, 0.6667, 0.1667, 0.9333, 10),
(0.1, 0.7, 0.0333, 0.1, 0.0333, 0.1333, 0.0667, 0.6333, 0.0667, 0.8667, 10),
(0.1667, 0.1333, 0.1, 0.6667, 0.0667, 0.9333, 0.5667, 0.0333, 0.0667, 0.0333, 6),
(0.1667, 0.1333, 0.1667, 0.1333, 0.1333, 0.6667, 0.7333, 0.0333, 0.1333, 0.9333, 10),
(0.1, 0.6, 0.0333, 0.1, 0.0667, 0.1667, 0.0667, 0.0667, 0.6667, 0.9667, 10),
(0.8667, 0.1667, 0.0667, 0.1333, 0.6, 0.1, 0.1333, 0.1333, 0.6333, 0.0667, 1),
(0.1667, 0.8667, 0.0333, 0.1333, 0.7333, 0.6667, 0.0667, 0.0667, 0.1, 0.1, 2),
(0.1667, 0.0667, 0.4667, 0.6333, 0.0667, 0.1333, 0.0333, 0.1333, 0.8667, 0.0667, 9),
(0.6, 0.1667, 0.1, 0.1, 0.6667, 0.0333, 0.9333, 0.1667, 0.1333, 0.1333, 7);

DO $$ BEGIN RAISE NOTICE '1000 muestras de entrenamiento cargadas en ml_training_data'; END $$;

-- ############################################################################
--   05_seed_users.sql
--   Usuarios de ejemplo
-- ############################################################################

-- ============================================================
-- REVO DB - Script 05: Admin por defecto + usuario demo
-- ============================================================

-- Admin (password: Admin@REVO2025)
INSERT INTO users (email, password_hash, full_name, student_code, semester, role)
VALUES (
    'admin@revo.edu',
    crypt('Admin@REVO2025', gen_salt('bf', 12)),
    'Administrador REVO',
    NULL,
    NULL,
    'admin'
)
ON CONFLICT (email) DO NOTHING;

-- Estudiante demo (password: Demo@1234)
INSERT INTO users (email, password_hash, full_name, student_code, semester, role)
VALUES (
    'demo@revo.edu',
    crypt('Demo@1234', gen_salt('bf', 12)),
    'Estudiante Demo',
    'SIS-2024-001',
    5,
    'student'
)
ON CONFLICT (email) DO NOTHING;

DO $$ BEGIN
    RAISE NOTICE '✅ Usuarios por defecto creados: admin@revo.edu / demo@revo.edu';
END $$;

-- ############################################################################
--   06_fix_passwords.sql
--   Corrige el hash de las contrasenas de ejemplo
-- ############################################################################

-- Actualizar contraseñas con hashes bcrypt compatibles con passlib (auth-service)
-- Contraseña admin: Admin@REVO2025
UPDATE users 
SET password_hash = '$2b$12$NzLS60SnsFdQcHtJFbMmFeqNMZ.LECw6NO13enzKrqwmsnGmveQgK'
WHERE email = 'admin@revo.edu';

-- Contraseña demo: Demo@1234
UPDATE users 
SET password_hash = '$2b$12$VHDy.eA9vmzqKa7Yu/P8v.r1WppA4yBT/V1Wchtg69XXDgQ4NIsnq'
WHERE email = 'demo@revo.edu';

-- ############################################################################
--   07_seed_courses.sql
--   Catalogo de cursos
-- ############################################################################

-- ==========================================================
-- REVO DB - Script 07: Seed Courses (Monetization MVP)
-- NIVELES ESTRICTOS PARA LINEA DE TIEMPO (ROADMAP)
-- ==========================================================

CREATE TABLE IF NOT EXISTS courses (
    id SERIAL PRIMARY KEY,
    specialization_id INTEGER REFERENCES specializations(id),
    platform VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    url TEXT NOT NULL,
    level VARCHAR(50) DEFAULT 'Principiante',
    price_model VARCHAR(50) DEFAULT 'Pago',
    thumbnail_url TEXT
);

TRUNCATE TABLE courses CASCADE;
ALTER SEQUENCE courses_id_seq RESTART WITH 1;

INSERT INTO courses (specialization_id, platform, title, url, level, price_model, thumbnail_url) VALUES

-- 1. Desarrollo de Software
(1, 'YouTube', 'Fundamentos de la Programación Lógica', 'https://www.youtube.com/watch?v=chPhlsHoEZA', 'Nivel 1: Fundamentos', 'Gratis', ''),
(1, 'Platzi', 'Escuela de Desarrollo Web Core', 'https://platzi.com/web/', 'Nivel 2: Construcción', 'Suscripción', ''),
(1, 'Udemy', 'React: De cero a experto (Hooks y MERN)', 'https://www.udemy.com/course/react-cero-experto/', 'Nivel 3: Experto', 'Pago', ''),

-- 2. Data Science & IA
(2, 'Coursera', 'Fundamentos de la IA en Español por IBM', 'https://www.coursera.org', 'Nivel 1: Fundamentos', 'Gratis', ''),
(2, 'Udemy', 'Machine Learning y Data Science con Python', 'https://www.udemy.com/course/machinelearning-es/', 'Nivel 2: Construcción', 'Pago', ''),
(2, 'Platzi', 'Maestría en Data Science Empresarial', 'https://platzi.com/datos/', 'Nivel 3: Experto', 'Suscripción', ''),

-- 3. Infraestructura & Cloud
(3, 'YouTube', 'Fundamentos de Redes y Sistemas Operativos', 'https://www.youtube.com/', 'Nivel 1: Fundamentos', 'Gratis', ''),
(3, 'Google', 'Google Cloud Computing Foundations', 'https://cloud.google.com/training', 'Nivel 2: Construcción', 'Gratis', ''),
(3, 'Udemy', 'AWS Certified Cloud Practitioner - Español', 'https://www.udemy.com/course/aws-certified-cloud-practitioner-espanol/', 'Nivel 3: Experto', 'Pago', ''),

-- 4. Ciberseguridad
(4, 'YouTube', 'Conceptos Básicos de Ciberseguridad', 'https://www.youtube.com/', 'Nivel 1: Fundamentos', 'Gratis', ''),
(4, 'Platzi', 'Escuela de Ciberseguridad (Defensiva)', 'https://platzi.com/ciberseguridad/', 'Nivel 2: Construcción', 'Suscripción', ''),
(4, 'Udemy', 'Hacking Ético 2024: De Cero a Experto', 'https://www.udemy.com/course/curso-hacker-etico/', 'Nivel 3: Experto', 'Pago', ''),

-- 5. Soporte Técnico & IT Ops
(5, 'YouTube', 'Mantenimiento Preventivo y Correctivo de PC', 'https://www.youtube.com/', 'Nivel 1: Fundamentos', 'Gratis', ''),
(5, 'Coursera', 'Certificado Soporte de TI de Google', 'https://www.coursera.org', 'Nivel 2: Construcción', 'Suscripción', ''),
(5, 'Udemy', 'Comptia A+ en Español (Certificación)', 'https://www.udemy.com/course/comptia-a-enespanol/', 'Nivel 3: Experto', 'Pago', ''),

-- 6. QA & Testing
(6, 'EDteam', 'Ingeniería de Calidad de Software (Teoría)', 'https://ed.team/cursos', 'Nivel 1: Fundamentos', 'Pago', ''),
(6, 'Platzi', 'Curso Integrado de QA Auto-Testing', 'https://platzi.com/cursos/qata/', 'Nivel 2: Construcción', 'Suscripción', ''),
(6, 'Udemy', 'Cypress: Pruebas End-to-End Máster', 'https://www.udemy.com/course/automatizacion-con-cypress/', 'Nivel 3: Experto', 'Pago', ''),

-- 7. Gestión y Producto
(7, 'YouTube', 'Metodologías Ágiles desde Cero', 'https://www.youtube.com/', 'Nivel 1: Fundamentos', 'Gratis', ''),
(7, 'Coursera', 'Google Project Management en Español', 'https://www.coursera.org', 'Nivel 2: Construcción', 'Suscripción', ''),
(7, 'Udemy', 'Scrum Master Certificación Oficial PMI', 'https://www.udemy.com/course/scrum-master-certificacion-oficial/', 'Nivel 3: Experto', 'Pago', ''),

-- 8. Diseño UX/UI
(8, 'YouTube', 'Figma: De Cero a Tu Primer Diseño', 'https://www.youtube.com', 'Nivel 1: Fundamentos', 'Gratis', ''),
(8, 'Platzi', 'Escuela de Diseño de Producto UX', 'https://platzi.com/diseno/', 'Nivel 2: Construcción', 'Suscripción', ''),
(8, 'Udemy', 'Máster en UI Experto y Sistemas de Diseño', 'https://www.udemy.com/course/figma-diseno-ui/', 'Nivel 3: Experto', 'Pago', ''),

-- 9. Sistemas Empresariales
(9, 'Platzi', 'Introducción al Business Intelligence (BI)', 'https://platzi.com/cursos/business-intelligence/', 'Nivel 1: Fundamentos', 'Suscripción', ''),
(9, 'Coursera', 'Certificado IBM Data Science / AI', 'https://www.coursera.org', 'Nivel 2: Construcción', 'Suscripción', ''),
(9, 'Udemy', 'SAP MM y SAP FICO Consulta Máster', 'https://www.udemy.com/course/sap-mm-desde-cero/', 'Nivel 3: Experto', 'Pago', ''),

-- 10. Investigación e Innovación
(10, 'Coursera', 'Fundamentos del Internet of Things (IoT)', 'https://www.coursera.org', 'Nivel 1: Fundamentos', 'Gratis', ''),
(10, 'Platzi', 'Escuela de Arquitectura Blockchain', 'https://platzi.com/crypto/', 'Nivel 2: Construcción', 'Suscripción', ''),
(10, 'Udemy', 'Desarrollo de DApps Globales Solidity', 'https://www.udemy.com/course/ethereum-solidity-dapps/', 'Nivel 3: Experto', 'Pago', '');

DO $$ BEGIN RAISE NOTICE '✅ 30 Cursos de ROADMAP Lineal listos para el UI.'; END $$;

-- ############################################################################
--   08_seed_jobs.sql
--   Catalogo de empleos
-- ############################################################################

-- ==========================================================
-- REVO DB - Script 08: Seed Jobs Realistas (Radar Empleabilidad)
-- Vacantes Simuladas para Latam y Trabajo Remoto (Tier Junior/Mid)
-- ==========================================================

CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    specialization_id INTEGER REFERENCES specializations(id),
    company VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL,
    salary_range VARCHAR(100),
    location VARCHAR(100) DEFAULT 'Remoto - Latam',
    url TEXT DEFAULT '#',
    posted_days_ago INTEGER DEFAULT 1
);

TRUNCATE TABLE jobs CASCADE;
ALTER SEQUENCE jobs_id_seq RESTART WITH 1;

INSERT INTO jobs (specialization_id, company, title, salary_range, location, posted_days_ago) VALUES

-- 1. Desarrollo de Software (React, Node, Python, Java)
(1, 'Mercado Libre', 'Junior React Frontend Developer', '$1,000 - $1,500 USD', 'Híbrido (CDMX / Bogotá / BsAs)', 2),
(1, 'Globant', 'Trainee Backend Python API', '$800 - $1,200 USD', 'Remoto - Latam', 1),
(1, 'StartUp Tech', 'Desarrollador Full Stack MERN', '$1,500 - $2,000 USD', 'Remoto - USA', 4),

-- 2. Data Science & IA
(2, 'Kavak', 'Junior Data Analyst (SQL & Tablaeu)', '$1,100 - $1,600 USD', 'Remoto - Latam', 1),
(2, 'Rappi', 'Machine Learning Engineer L1', '$1,800 - $2,500 USD', 'Híbrido - Bogotá', 3),
(2, 'Agencia IA', 'Ingeniero de Prompts Educativo', '$1,200 - $2,000 USD', 'Remoto - Latam', 0),

-- 3. Infraestructura & Cloud
(3, 'Amazon Web Services', 'Cloud Support Associate', '$1,500 - $2,200 USD', 'Remoto - Latam', 2),
(3, 'Telefónica Tech', 'Junior SysAdmin Linux', '$900 - $1,300 USD', 'Presencial (Depende País)', 5),
(3, 'Fintech Core', 'DevOps Automator (Trainee)', '$1,200 - $1,800 USD', 'Remoto - Latam', 1),

-- 4. Ciberseguridad
(4, 'Banco Santander', 'Analista SOC Nivel 1', '$1,400 - $2,000 USD', 'Híbrido', 2),
(4, 'KPMG', 'Auditor de Ciberseguridad Junior', '$1,300 - $1,800 USD', 'Remoto - Latam', 4),
(4, 'Defense Corp', 'Ethical Hacker & Pentester', '$1,500 - $2,500 USD', 'Remoto - Global', 1),

-- 5. Soporte Técnico & IT Ops
(5, 'IBM', 'Help Desk Technician (IT Support)', '$700 - $1,100 USD', 'Remoto - Latam', 1),
(5, 'Atento', 'Coordinador de Operaciones IT', '$850 - $1,300 USD', 'Presencial', 3),
(5, 'HP Enterprise', 'Analista de Soporte Corporativo', '$900 - $1,400 USD', 'Remoto - Latam', 1),

-- 6. QA & Testing
(6, 'Softtek', 'Junior QA Manual (Web & Mobile)', '$800 - $1,200 USD', 'Remoto - Latam', 2),
(6, 'BairesDev', 'SDET QA Automation (Selenium/Cypress)', '$1,500 - $2,200 USD', 'Remoto - Latam', 1),
(6, 'Accenture', 'Analista de Pruebas de Rendimiento', '$1,100 - $1,600 USD', 'Híbrido', 4),

-- 7. Gestión y Producto
(7, 'Nubank', 'Junior Product Owner (Fintech)', '$1,500 - $2,500 USD', 'Remoto - Latam', 2),
(7, 'Clip', 'Scrum Master (Entry Level)', '$1,200 - $1,800 USD', 'Híbrido - CDMX', 3),
(7, 'Despegar', 'Analista de Producto Técnico', '$1,100 - $1,700 USD', 'Remoto - Latam', 1),

-- 8. Diseño UX/UI
(8, 'Ogilvy', 'Junior UI Designer (Figma)', '$800 - $1,300 USD', 'Híbrido', 2),
(8, 'Bumble', 'UX Researcher (Latam Users)', '$1,500 - $2,200 USD', 'Remoto - Latam', 1),
(8, 'Agencia Digital', 'Diseñador de Producto Web 3.0', '$1,200 - $1,600 USD', 'Remoto - Global', 5),

-- 9. Sistemas Empresariales
(9, 'Oracle', 'Consultor Trainee ERP / ERP NetSuite', '$1,000 - $1,500 USD', 'Híbrido', 4),
(9, 'Neoris', 'Analista Funcional SAP', '$1,200 - $1,800 USD', 'Remoto - Latam', 2),
(9, 'Salesforce', 'Administrador Salesforce (Junior)', '$1,400 - $2,200 USD', 'Remoto - Latam', 1),

-- 10. Investigación e Innovación
(10, 'Binance', 'Trainee Smart Contract Developer', '$2,000 - $3,000 USD', 'Remoto - Global', 2),
(10, 'Siemens', 'Analista de Soluciones IoT', '$1,100 - $1,700 USD', 'Híbrido', 5),
(10, 'Meta', 'Investigador Junior AR/VR (Pasante)', '$1,500 - $2,500 USD', 'Remoto - Global', 1);

DO $$ BEGIN RAISE NOTICE '✅ 30 Ofertas de Trabajo Realistas sembradas para la Bolsa de Empleo.'; END $$;

-- ############################################################################
--   09_psychometric_questions.sql
--   Preguntas de la fase psicometrica
-- ############################################################################

-- ============================================================
-- REVO DB - Script 09: Preguntas Psicométricas Adaptativas
-- Tabla: psychometric_questions
-- Banco de 40 preguntas (4 por cada especialización)
-- ============================================================

CREATE TABLE IF NOT EXISTS psychometric_questions (
    id                  SERIAL PRIMARY KEY,
    specialization_id   INTEGER      NOT NULL REFERENCES specializations(id) ON DELETE CASCADE,
    question_text       TEXT         NOT NULL,
    option_a            TEXT         NOT NULL,
    option_b            TEXT         NOT NULL,
    option_c            TEXT         NOT NULL,
    option_d            TEXT         NOT NULL,
    order_index         SMALLINT     NOT NULL DEFAULT 0,
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_psychometric_spec ON psychometric_questions(specialization_id, is_active);

-- ============================================================
-- SEED: 4 preguntas por cada una de las 10 especializaciones
-- Orden de IDs en specializations (según 02_seed_specializations.sql):
-- 1=Desarrollo de Software, 2=Data Science & IA, 3=Infraestructura & Cloud
-- 4=Ciberseguridad, 5=Soporte Técnico & IT Ops, 6=QA & Testing
-- 7=Gestión y Producto, 8=Diseño UX/UI, 9=Sistemas Empresariales
-- 10=Investigación e Innovación
-- ============================================================

-- Borrar seed previo si existe (idempotente)
TRUNCATE TABLE psychometric_questions RESTART IDENTITY CASCADE;

-- ── 1. Desarrollo de Software ─────────────────────────────────
INSERT INTO psychometric_questions (specialization_id, question_text, option_a, option_b, option_c, option_d, order_index) VALUES
(1, 'Cuando tu código no funciona a la primera, ¿cuál es tu reacción instintiva?',
 'Leo el stack trace línea a línea hasta aislar exactamente el error',
 'Pruebo soluciones rápidas en orden hasta que una funcione',
 'Le explico el problema a un compañero para buscar perspectiva',
 'Refactorizo el bloque completo: prefiero limpiar antes de parchar', 1),

(1, 'Tienes que elegir entre lanzar en 2 días con deuda técnica o en 2 semanas limpio. ¿Qué eliges?',
 'Lanzo en 2 semanas, la arquitectura bien hecha vale la espera',
 'Lanzo en 2 días y creo un ticket de deuda técnica para después',
 'Negocio con el equipo para encontrar una ruta media entre las dos',
 'Solo lanzo si puedo garantizar al menos el 80% de calidad del código', 2),

(1, '¿Cómo describes tu relación con aprender nuevos lenguajes o frameworks?',
 'Me emociona: lo estudio desde la documentación oficial primero',
 'Prefiero aprenderlo construyendo algo real desde el día 1',
 'Aprendo bien en pair programming o un bootcamp grupal',
 'Lo aprendo pero siempre busco dominarlo a fondo antes de usarlo en producción', 3),

(1, 'En un equipo de desarrollo, ¿cuál es tu rol natural?',
 'Arquitecto: diseño la estructura del sistema antes de codificar',
 'Ejecutor: soy el primero en tener una versión funcional en manos del cliente',
 'Integrador: conecto el trabajo de todos y facilito las revisiones de código',
 'Revisor: nada pasa a producción sin que yo lo haya validado', 4);

-- ── 2. Data Science & IA ──────────────────────────────────────
INSERT INTO psychometric_questions (specialization_id, question_text, option_a, option_b, option_c, option_d, order_index) VALUES
(2, 'Te presentan un dataset con 50 columnas y datos sucios. ¿Cuál es tu primer paso?',
 'Construyo un mapa estadístico completo (nulos, distribuciones, correlaciones) antes de tocar nada',
 'Limpio los datos básicos y entreno un modelo rápido para ver si hay potencial',
 'Entrevisto al dueño del negocio para entender qué columnas importan realmente',
 'Documento cada decisión del proceso de limpieza para asegurar reproducibilidad', 1),

(2, 'Tu modelo tiene 94% de accuracy pero el equipo de negocio no confía en él. ¿Qué haces?',
 'Creo visualizaciones de SHAP values para mostrar exactamente qué impulsa cada predicción',
 'Hago una demo en vivo con datos reales para que vean el modelo en acción',
 'Organizo una reunión de revisión donde el equipo puede hacerle preguntas al modelo',
 'Añado más métricas: Precision, Recall y F1 por segmento hasta que los números hablen solos', 2),

(2, '¿Cuál de estas tareas te parece más estimulante dentro de la ciencia de datos?',
 'Diseñar el pipeline de datos y la arquitectura del MLOps',
 'Encontrar el insight que nadie había visto oculto en los datos',
 'Presentar los resultados de forma que todos en la empresa los entiendan',
 'Optimizar el hiperparámetro final que sube el modelo de 94% a 97%', 3),

(2, 'Ante la incertidumbre en los datos, ¿cómo actúas?',
 'Modelo la incertidumbre explícitamente con intervalos de confianza bayesianos',
 'Acepto que la perfecta información no existe y entrego el mejor modelo posible hoy',
 'Consulto a expertos del dominio para aterrizar los supuestos del modelo',
 'No libero el modelo hasta tener al menos 3 validaciones cruzadas estables', 4);

-- ── 3. Infraestructura & Cloud ────────────────────────────────
INSERT INTO psychometric_questions (specialization_id, question_text, option_a, option_b, option_c, option_d, order_index) VALUES
(3, 'Un servidor de producción sube al 95% de CPU. ¿Cuál es tu primera acción?',
 'Reviso los logs, identifico el proceso causante y escalo de forma planificada',
 'Activo auto-scaling inmediatamente y luego investigo la causa raíz',
 'Notifico al equipo de desarrollo porque probablemente el código tiene una fuga',
 'Ejecuto un análisis forense antes de tocar cualquier cosa para evitar empeorar el estado', 1),

(3, '¿Cuál de estas frases describe mejor tu filosofía de infraestructura?',
 'Infrastructure as Code: todo debe ser reproducible desde un repositorio Git',
 'Entrega rápida: si funciona en staging, va a producción hoy',
 'Colaboración: Ops y Dev deben trabajar como un solo equipo',
 'Zero-downtime: ningún despliegue justifica un minuto de indisponibilidad', 2),

(3, '¿Qué tipo de proyecto Cloud te despertaría más curiosidad?',
 'Diseñar una arquitectura multi-región altamente disponible desde cero',
 'Migrar una app monolítica a microservicios en Kubernetes en tiempo récord',
 'Implementar una estrategia de FinOps para reducir el costo de la nube un 40%',
 'Construir el pipeline de CI/CD perfecto con gates de seguridad en cada paso', 3),

(3, 'Ante un cambio urgente en producción fuera de la ventana de mantenimiento, ¿qué haces?',
 'Sigo el runbook y solo ejecuto si tengo el Change Request aprobado',
 'Evalúo el impacto en 5 minutos y ejecuto si el riesgo es menor al del problema actual',
 'Convoco al equipo de guardia antes de tocar nada, no tomo decisiones solo',
 'Preparo un plan de rollback antes de cualquier intervención', 4);

-- ── 4. Ciberseguridad ─────────────────────────────────────────
INSERT INTO psychometric_questions (specialization_id, question_text, option_a, option_b, option_c, option_d, order_index) VALUES
(4, 'Encuentras una vulnerabilidad crítica en el sistema de un cliente. ¿Qué haces primero?',
 'Documento exhaustivamente el vector de ataque antes de reportarlo',
 'Reporto inmediatamente aunque no tenga todos los detalles: el tiempo cuenta',
 'Coordino con el equipo de desarrollo para una divulgación responsable coordinada',
 'Verifico el alcance total del impacto antes de escalar, para no generar pánico innecesario', 1),

(4, '¿Cuál de estos retos de ciberseguridad te atrae más?',
 'Diseñar la arquitectura de seguridad de sistemas críticos bancarios o de salud',
 'Hackear sistemas en entornos de Bug Bounty o Red Team con total libertad',
 'Concientizar y entrenar al equipo humano: el eslabón más débil siempre es la persona',
 'Hacer forense digital y análisis de malware en laboratorio controlado', 2),

(4, '¿Cómo describes tu relación con las reglas y la normativa de seguridad?',
 'Las normas existen por razones: las sigo y las mejoro con nuevos controles',
 'Las normas son un mínimo, yo pienso como el atacante para ir más allá',
 'Las normas deben ser entendidas por todos: mi rol es traducirlas al equipo',
 'El cumplimiento al 100% no es negociable, el riesgo cero es el objetivo', 3),

(4, 'Tu empresa tiene un presupuesto limitado de seguridad. ¿En qué inviertes primero?',
 'En una auditoría de arquitectura: arreglar los cimientos vale más que parches',
 'En un pentest externo: necesito saber cómo me verían desde afuera hoy',
 'En entrenamiento de phishing al equipo: el 85% de los ataques entran por personas',
 'En un SIEM robusto: sin visibilidad no puedo defender nada', 4);

-- ── 5. Soporte Técnico & IT Ops ───────────────────────────────
INSERT INTO psychometric_questions (specialization_id, question_text, option_a, option_b, option_c, option_d, order_index) VALUES
(5, 'Un usuario reporta que "internet no funciona". ¿Cómo abordas el diagnóstico?',
 'Sigo un árbol de diagnóstico sistemático: capa física, DNS, gateway, luego aplicación',
 'Reinicio los más comunes primero (router, adaptador) y escalo si no funciona',
 'Pregunto al usuario cómo ocurrió el problema para entender el contexto antes de actuar',
 'Verifico todos los logs disponibles antes de tocar cualquier equipo físico', 1),

(5, '¿Qué parte del soporte técnico encuentras más significativa?',
 'Documentar procedimientos para que el problema nunca se repita de la misma forma',
 'Resolver el problema del usuario en el menor tiempo posible y dejarlo feliz',
 'Explicarle al usuario qué pasó y cómo evitarlo en el futuro',
 'Encontrar la causa raíz profunda detrás del síntoma superficial reportado', 2),

(5, 'Son las 8am y ya tienes 15 tickets abiertos. ¿Cómo los priorizas?',
 'Los clasifico por impacto de negocio y urgencia antes de atender ninguno',
 'Resuelvo los más rápidos primero para reducir la cola y ganar tiempo',
 'Me coordino con otro técnico para dividir la carga y atender en paralelo',
 'Sigo el SLA al pie de la letra: los tickets por vencer primero tienen prioridad', 3),

(5, 'Un usuario está muy frustrado y eleva el tono. ¿Qué haces?',
 'Le explico con calma el proceso de escalación y los tiempos esperados',
 'Priorizo su caso para darle una respuesta rápida y reducir la tensión',
 'Escucho activamente, valido su frustración y luego propongo la solución',
 'Escalo formalmente al supervisor si el comportamiento no es profesional', 4);

-- ── 6. QA & Testing ───────────────────────────────────────────
INSERT INTO psychometric_questions (specialization_id, question_text, option_a, option_b, option_c, option_d, order_index) VALUES
(6, 'Se lanza una nueva funcionalidad mañana. ¿Cómo estructuras tu plan de testing?',
 'Diseño una matriz de casos de prueba cubriendo happy path, edge cases y regresión',
 'Automatizo las pruebas críticas hoy y ejecuto el resto en exploración mañana',
 'Me reúno con el desarrollador para entender la lógica y enfocar el testing donde más importa',
 'No apruebo el release hasta tener cobertura documentada de los casos de aceptación', 1),

(6, 'Encuentras un bug crítico 30 minutos antes de un release. ¿Qué haces?',
 'Documento el bug con pasos reproductibles y lo reporto al equipo inmediatamente',
 'Evalúo si puede mitigarse con un workaround para no bloquear el release',
 'Convoco una reunión de go/no-go con el PM, el dev y el QA Lead',
 'Bloqueo el release categóricamente: un bug crítico no puede llegar a los usuarios', 2),

(6, '¿Qué tipo de testing te resulta más fascinante?',
 'Testing de contratos y arquitectura de microservicios',
 'Testing exploratorio: encontrar lo que nadie pensó en probar',
 'Testing de usabilidad: comprobar que el producto es intuitivo para el usuario final',
 'Performance testing y pruebas de carga bajo condiciones extremas', 3),

(6, 'El equipo de desarrollo dice que "no hay tiempo para testing". ¿Qué respondes?',
 'Presento datos históricos de bugs en producción que costaron más tiempo que el testing',
 'Propongo testing mínimo viable focalizado en el 20% del código con 80% del riesgo',
 'Negocio para incluir al menos los casos de aceptación del cliente',
 'Escalo a la gerencia: saltar el testing es un riesgo de negocio, no técnico', 4);

-- ── 7. Gestión y Producto ─────────────────────────────────────
INSERT INTO psychometric_questions (specialization_id, question_text, option_a, option_b, option_c, option_d, order_index) VALUES
(7, 'El cliente quiere 10 features nuevas para mañana. ¿Cómo manejas eso?',
 'Analizo el impacto de cada feature en los OKRs del producto y priorizo con datos',
 'Negocio entregas iterativas: 2 features mañana, el resto en sprints posteriores',
 'Facilito un workshop de priorización con el cliente para que él mismo elija los top 3',
 'Creo una matriz de esfuerzo/impacto detallada antes de comprometer cualquier fecha', 1),

(7, '¿Cuál es tu señal más confiable de que un producto va por buen camino?',
 'Las métricas de retención y los KPIs del producto suben consistentemente',
 'El equipo entrega a tiempo y los usuarios usan las features que se construyeron',
 'Los stakeholders y el equipo hablan positivamente del producto en las retrospectivas',
 'El product-market fit es claro: los usuarios pagarían por él aunque dejara de ser gratis', 2),

(7, 'Hay un conflicto entre el equipo de diseño y el de desarrollo. ¿Cómo actúas?',
 'Creo un framework de decisión basado en datos del usuario para resolver el conflicto objetivamente',
 'Tomo una decisión rápida basada en lo que mejor sirve al usuario final ahora mismo',
 'Facilito una sesión de co-creación donde ambos equipos diseñen juntos la solución',
 'Documento los pros y contras de cada postura antes de escalar a la dirección', 3),

(7, '¿Qué describe mejor tu visión del rol de Product Manager?',
 'El CEO del producto: responsable de la visión, la estrategia y los resultados de negocio',
 'El facilitador de entregas: asegura que el equipo pueda moverse rápido sin fricciones',
 'El puente entre el usuario y el equipo técnico: traduce necesidades en soluciones',
 'El guardián de la calidad del producto: nada sale si no cumple el estándar prometido', 4);

-- ── 8. Diseño UX/UI ───────────────────────────────────────────
INSERT INTO psychometric_questions (specialization_id, question_text, option_a, option_b, option_c, option_d, order_index) VALUES
(8, 'Un usuario dice que tu diseño "se ve mal". ¿Cómo respondes?',
 'Le pido que especifique: ¿visual, usabilidad o flujo? Cada uno tiene soluciones distintas',
 'Propongo 3 variantes alternativas rápidas para que el usuario elija la que prefiere',
 'Organizo una sesión de co-diseño con el usuario para rediseñar juntos',
 'Valido el feedback contra los principios de Heurísticas de Nielsen antes de cambiar nada', 1),

(8, '¿Qué parte del proceso de diseño disfrutas más?',
 'La arquitectura de información y los wireframes: la estructura lógica del sistema',
 'El prototipado rápido: tener algo clickeable en manos del usuario lo antes posible',
 'Las entrevistas con usuarios: entender sus frustraciones reales es lo más valioso',
 'El Design System: crear componentes reutilizables perfectamente documentados', 2),

(8, 'El equipo dev dice que tu diseño es "imposible de implementar" tal como está. ¿Qué haces?',
 'Pido una sesión técnica para entender las restricciones y rediseño dentro de ellas',
 'Simplifico el diseño al mínimo que preserve la experiencia de usuario esencial',
 'Propongo un sprint de diseño+dev conjunto para encontrar una solución técnica-visual conjunta',
 'Documento exactamente por qué la experiencia propuesta es necesaria para el negocio', 3),

(8, '¿Qué mides para saber que un diseño fue exitoso?',
 'La reducción del tiempo de tarea y la tasa de finalización de flujos críticos',
 'El NPS y si los usuarios recomendarían el producto a un amigo',
 'El número de tickets de soporte relacionados con confusión de interfaz que disminuyen',
 'La puntuación en tests de usabilidad estructurados con métricas predefinidas de SUS', 4);

-- ── 9. Sistemas Empresariales ─────────────────────────────────
INSERT INTO psychometric_questions (specialization_id, question_text, option_a, option_b, option_c, option_d, order_index) VALUES
(9, 'Una empresa quiere implementar SAP pero el presupuesto se redujo a la mitad. ¿Qué propones?',
 'Hago un análisis de brechas y priorizo los módulos de mayor retorno sobre inversión',
 'Propongo una implementación por fases: el módulo más urgente primero y el resto después',
 'Involucro a los líderes de cada área para que definan sus prioridades críticas',
 'Evalúo alternativas de ERP open source antes de comprometer el presupuesto total', 1),

(9, 'Los usuarios finales rechazan el nuevo sistema ERP. ¿Cómo lo manejas?',
 'Analizo las métricas de adopción para identificar los módulos con mayor resistencia',
 'Inicio quick wins: muestro cómo el sistema ya les ahorra tiempo en el día a día',
 'Formo champions internos: usuarios clave que lideren la adopción entre sus compañeros',
 'Documento los bugs y fricciones de usabilidad reportados y los presento al proveedor', 2),

(9, '¿Qué aspecto de los sistemas empresariales te resulta más valioso?',
 'La integración de datos entre áreas: que finanzas, operaciones y RR.HH. hablen entre sí',
 'La automatización de procesos repetitivos que liberan tiempo al equipo humano',
 'El Business Intelligence: los dashboards que ayudan a la dirección a tomar mejores decisiones',
 'La trazabilidad y el compliance: que cada transacción esté auditada y sea reproducible', 3),

(9, 'Al finalizar una implementación de ERP, ¿cómo mides el éxito?',
 'Con KPIs de eficiencia: reducción en tiempo de procesos y errores de datos',
 'Con la velocidad de adopción: ¿cuántos usuarios activos tiene el sistema a los 30 días?',
 'Con la satisfacción del equipo directivo y de los usuarios finales por separado',
 'Con el cumplimiento total del scope acordado en el contrato de implementación', 4);

-- ── 10. Investigación e Innovación ────────────────────────────
INSERT INTO psychometric_questions (specialization_id, question_text, option_a, option_b, option_c, option_d, order_index) VALUES
(10, 'Lees un paper con resultados que contradicen tu hipótesis inicial. ¿Qué haces?',
 'Reviso la metodología detalladamente para encontrar posibles limitaciones del estudio',
 'Actualizo mi hipótesis inmediatamente: los datos mandan sobre la intuición',
 'Comparto el paper con mis colegas para debatirlo en conjunto antes de concluir',
 'Replico el experimento en mi entorno para verificar si los resultados son reproducibles', 1),

(10, '¿Cuál de estas fases de un proyecto de investigación te entusiasma más?',
 'El diseño metodológico: construir el andamiaje experimental correcto desde el inicio',
 'El prototipado de la idea: ver si algo que nadie hizo antes funciona en la práctica',
 'La difusión: publicar los hallazgos para que otros investigadores los construyan encima',
 'La validación rigurosa: demostrar que los resultados son sólidos y no artefactos estadísticos', 2),

(10, '¿Cómo decides cuándo una idea innovadora vale la pena ser perseguida?',
 'Cuando existe un gap documentado en el estado del arte que mi idea puede cerrar',
 'Cuando puedo tener un prototipo funcional en menos de 2 semanas para testear la hipótesis',
 'Cuando hay al menos un stakeholder con problema real que la idea resolvería',
 'Cuando la idea supera un análisis de factibilidad técnica, legal y de impacto medible', 3),

(10, 'Tu proyecto de innovación pierde financiamiento a mitad de camino. ¿Qué haces?',
 'Reduzco el alcance al núcleo de la hipótesis principal y busco nuevos fondos específicos',
 'Busco un partner de industria que se beneficie de los resultados y cofinancie el resto',
 'Abro el proyecto como investigación colaborativa abierta para atraer otros investigadores',
 'Publico los avances hasta la fecha como paper preliminar para no perder el trabajo hecho', 4);

-- ############################################################################
--   10_rls.sql
--   Seguridad por filas y roles revo_app / revo_service
-- ############################################################################

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
-- El nombre del dueno NO se escribe a mano. En el compose es revo_user, pero
-- en un Postgres gestionado (Supabase, Neon, RDS) es otro, normalmente
-- `postgres`. Con el nombre fijo, esta migracion fallaba con
-- 'role "revo_user" does not exist' y arrastraba a las dos siguientes.
DO $privilegios$
BEGIN
    EXECUTE format(
        'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
        'GRANT USAGE, SELECT ON SEQUENCES TO revo_app, revo_service',
        current_user
    );
END
$privilegios$;

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

-- ############################################################################
--   12_consentimiento.sql
--   Consentimiento informado versionado (Ley 29733)
-- ############################################################################

-- ============================================================
-- REVO DB - Script 12: consentimiento informado y documentos legales
-- ============================================================
-- REVO recoge datos de orientacion vocacional de estudiantes y el plan de
-- negocio contempla dos usos adicionales al servicio en si:
--   a) compartir informacion agregada con universidades y academias
--   b) usar las respuestas para entrenar el modelo
--
-- Bajo la Ley 29733 (Proteccion de Datos Personales, Peru) y su reglamento,
-- esos dos usos son FINALIDADES DISTINTAS del servicio. El consentimiento
-- para ellas tiene que ser libre, previo, expreso, informado e inequivoco, y
-- no puede condicionarse a poder usar la plataforma. De ahi el diseno:
--
--   terms + privacy  -> obligatorios, sin ellos no hay cuenta
--   data_commercial  -> opcional, casilla aparte, desmarcada por defecto
--   ai_training      -> opcional, casilla aparte, desmarcada por defecto
--
-- Cada aceptacion guarda QUE version del texto se acepto, CUANDO y DESDE
-- DONDE. Un consentimiento sin version es inservible como prueba: si el
-- texto cambia, no hay forma de saber a que acepto realmente el alumno.
--
-- AVISO: el contenido de los documentos es un borrador tecnico. Antes de
-- salir a produccion con la parte comercial debe revisarlo un abogado.
-- ============================================================

-- ------------------------------------------------------------
-- 1. Documentos legales versionados
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS legal_documents (
    id             SERIAL PRIMARY KEY,
    doc_type       VARCHAR(30)  NOT NULL
                                CHECK (doc_type IN ('terms','privacy','data_commercial','ai_training')),
    version        VARCHAR(20)  NOT NULL,
    title          VARCHAR(200) NOT NULL,
    summary        TEXT         NOT NULL,   -- el resumen corto de la casilla
    body_md        TEXT         NOT NULL,   -- el texto completo del "Leer mas"
    is_required    BOOLEAN      NOT NULL DEFAULT FALSE,
    effective_from TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    is_current     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (doc_type, version)
);

-- Solo puede haber una version vigente por tipo de documento. Un indice
-- parcial unico lo garantiza en la base de datos, no en la aplicacion:
-- dos versiones vigentes a la vez significan que no se sabe que acepto el
-- alumno, y eso invalida el consentimiento entero.
CREATE UNIQUE INDEX IF NOT EXISTS idx_legal_vigente
    ON legal_documents (doc_type) WHERE is_current;

-- ------------------------------------------------------------
-- 2. Consentimientos otorgados
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_consents (
    id          SERIAL       PRIMARY KEY,
    user_id     INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    doc_type    VARCHAR(30)  NOT NULL
                             CHECK (doc_type IN ('terms','privacy','data_commercial','ai_training')),
    doc_version VARCHAR(20)  NOT NULL,
    granted     BOOLEAN      NOT NULL,
    granted_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    revoked_at  TIMESTAMPTZ,

    -- Evidencia de la aceptacion. La IP es un dato personal en si misma:
    -- se guarda porque la ley pide poder acreditar el consentimiento, y se
    -- borra con la cuenta por el ON DELETE CASCADE de arriba.
    ip_address  INET,
    user_agent  VARCHAR(400),

    UNIQUE (user_id, doc_type, doc_version)
);

CREATE INDEX IF NOT EXISTS idx_consents_user ON user_consents(user_id);

-- Consulta tipica: "de los alumnos que autorizaron uso comercial, cuantos
-- siguen vigentes". Sin este indice parcial es una pasada completa por tabla.
CREATE INDEX IF NOT EXISTS idx_consents_vigentes
    ON user_consents(doc_type, user_id) WHERE granted AND revoked_at IS NULL;

-- ------------------------------------------------------------
-- 3. Vista del estado actual de consentimiento
-- ------------------------------------------------------------
-- Evita que cada servicio reimplemente "cual es el consentimiento vigente":
-- la ultima decision por tipo de documento, sin revocar.
--
-- security_invoker=true es imprescindible: sin el, la vista consulta con los
-- permisos de SU DUENO y se convierte en un tunel que rodea el RLS de la
-- tabla de abajo. Con el activado, cada consulta a la vista aplica las
-- politicas del rol que pregunta.
CREATE OR REPLACE VIEW user_consent_state WITH (security_invoker = true) AS
SELECT DISTINCT ON (uc.user_id, uc.doc_type)
    uc.user_id,
    uc.doc_type,
    uc.doc_version,
    uc.granted AND uc.revoked_at IS NULL AS vigente,
    uc.granted_at,
    uc.revoked_at
FROM user_consents uc
ORDER BY uc.user_id, uc.doc_type, uc.granted_at DESC;

-- ------------------------------------------------------------
-- 4. RLS
-- ------------------------------------------------------------
-- Los documentos legales son publicos: hay que poder leerlos ANTES de tener
-- cuenta, porque se aceptan durante el registro.
ALTER TABLE legal_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE legal_documents FORCE ROW LEVEL SECURITY;

GRANT SELECT ON legal_documents TO revo_app, revo_service;
GRANT INSERT, UPDATE ON legal_documents TO revo_app;

DROP POLICY IF EXISTS legales_lectura ON legal_documents;
CREATE POLICY legales_lectura ON legal_documents FOR SELECT USING (true);

DROP POLICY IF EXISTS legales_escritura ON legal_documents;
CREATE POLICY legales_escritura ON legal_documents FOR ALL
    USING (revo_es_admin()) WITH CHECK (revo_es_admin());

-- Los consentimientos son datos personales del alumno.
ALTER TABLE user_consents ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_consents FORCE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE ON user_consents TO revo_app;
-- El servicio necesita saber quien autorizo el entrenamiento antes de
-- meter su vector en el dataset.
GRANT SELECT ON user_consents TO revo_service;

GRANT SELECT ON user_consent_state TO revo_app, revo_service;

-- Las secuencias de estas dos tablas nacen despues del GRANT masivo de la
-- migracion 10, asi que se conceden aqui de forma explicita. (La migracion 10
-- deja ademas un ALTER DEFAULT PRIVILEGES para que esto no vuelva a hacer
-- falta en migraciones futuras, pero no retroactivamente sobre estas.)
GRANT USAGE, SELECT ON SEQUENCE legal_documents_id_seq TO revo_app;
GRANT USAGE, SELECT ON SEQUENCE user_consents_id_seq TO revo_app;

DROP POLICY IF EXISTS consentimientos_propios ON user_consents;
CREATE POLICY consentimientos_propios ON user_consents FOR ALL
    USING (revo_es_alumno(user_id) OR revo_es_admin() OR revo_es_servicio())
    WITH CHECK (revo_es_alumno(user_id) OR revo_user_id() IS NULL);
-- El WITH CHECK admite user_id sin contexto porque el consentimiento se
-- graba en el mismo INSERT del registro, cuando el alumno todavia no tiene
-- sesion. La fila queda atada por clave foranea al usuario recien creado.

-- ------------------------------------------------------------
-- 5. Contenido inicial de los documentos
-- ------------------------------------------------------------
-- El INSERT va DESPUES de activar RLS con FORCE, asi que la politica de
-- escritura (solo admin) tambien aplica a quien corre la migracion.
--
-- En un Postgres local eso no se nota porque el dueno suele ser superusuario
-- y los superusuarios se saltan RLS. En un Postgres gestionado (Supabase,
-- Neon, RDS) el dueno NO es superusuario y la migracion fallaba con
-- 'new row violates row-level security policy for table "legal_documents"'.
--
-- El contexto de admin hace falta ademas por el ON CONFLICT del final:
-- PostgreSQL necesita poder VER la fila en conflicto para resolverlo, asi que
-- un INSERT ... ON CONFLICT sobre una tabla con RLS falla si la politica de
-- SELECT no deja ver nada, aunque el WITH CHECK del INSERT si pase.
SELECT set_config('revo.role', 'admin', false);

INSERT INTO legal_documents (doc_type, version, title, summary, body_md, is_required)
VALUES
(
    'terms', '1.0',
    'Terminos y Condiciones de uso de REVO',
    'Acepto los Terminos y Condiciones y la Politica de Privacidad de REVO.',
$doc$
# Terminos y Condiciones de uso de REVO

**Version 1.0**

## 1. Que es REVO

REVO es una herramienta de orientacion academica dirigida a estudiantes de
Ingenieria de Sistemas. A partir de un cuestionario por fases, estima tu
afinidad con diez especializaciones de la carrera y te sugiere una ruta.

## 2. Que NO es REVO

El resultado es **una sugerencia orientativa, no un diagnostico**. No
sustituye la tutoria academica, la asesoria profesional ni tu propio
criterio. REVO no garantiza resultados academicos ni laborales derivados de
seguir la ruta sugerida, y no se responsabiliza de las decisiones de
matricula o de carrera que tomes a partir de ella.

## 3. Tu cuenta

Para usar REVO necesitas una cuenta con un correo valido. Eres responsable
de la veracidad de los datos que registras y de mantener tu contrasena en
secreto. Si detectas un uso no autorizado de tu cuenta, avisanos.

## 4. Uso aceptable

No esta permitido:

- Automatizar el llenado del cuestionario o falsear respuestas de forma masiva.
- Intentar acceder a datos de otros usuarios.
- Interferir con el funcionamiento del servicio o sus limites de uso.
- Extraer el contenido de la plataforma para reproducirlo o comercializarlo.

## 5. Tus datos

El tratamiento de tus datos personales se rige por la Politica de
Privacidad, que forma parte de estos Terminos. Los usos comerciales y de
entrenamiento del modelo son **opcionales** y se autorizan por separado:
puedes usar REVO con normalidad sin aceptarlos.

## 6. Disponibilidad

REVO se ofrece "tal cual". Podemos modificar, suspender o descontinuar
funciones. Avisaremos con antelacion razonable de los cambios relevantes.

## 7. Cambios en estos Terminos

Si cambiamos estos Terminos, publicaremos una version nueva y te pediremos
que la aceptes de nuevo. La version que aceptaste queda registrada.

## 8. Contacto

Para cualquier consulta sobre estos Terminos, escribe al correo de contacto
publicado en la plataforma.
$doc$,
    TRUE
),
(
    'privacy', '1.0',
    'Politica de Privacidad de REVO',
    'He leido como se tratan mis datos personales.',
$doc$
# Politica de Privacidad de REVO

**Version 1.0**

Esta politica explica que datos recogemos, para que, y que puedes hacer al
respecto. Se rige por la **Ley 29733, Ley de Proteccion de Datos Personales**
del Peru y su reglamento (D.S. 003-2013-JUS).

## 1. Que datos recogemos

**Datos de cuenta.** Nombre completo, correo electronico, codigo de
estudiante y ciclo. Los das tu al registrarte.

**Datos del cuestionario.** Tus respuestas a las preguntas de afinidad y de
perfil profesional, y el tiempo que tardas en responderlas.

**Resultados.** La especializacion recomendada, tu nivel de afinidad con
cada una y tu valoracion sobre si el resultado te representa.

**Datos tecnicos.** Direccion IP, tipo de navegador y registro de accesos.
Se usan para seguridad y para evitar abusos del servicio.

## 2. Para que los usamos

**Necesario para el servicio** (base legal: ejecucion del servicio que
solicitas):

- Calcular y mostrarte tu resultado.
- Guardar tu historial para que puedas consultarlo.
- Mantener tu sesion y proteger la plataforma frente a abusos.

**Opcional, solo si lo autorizas expresamente** (base legal: tu
consentimiento, revocable en cualquier momento):

- **Uso comercial con instituciones educativas.** Compartir informacion
  sobre tendencias de afinidad con universidades y academias, para que
  disenen su oferta formativa.
- **Entrenamiento del modelo.** Usar tus respuestas y tu resultado para
  mejorar la precision del modelo de recomendacion.

**No condicionamos el uso de REVO a que aceptes los usos opcionales.**
Puedes rechazarlos y la plataforma funciona igual.

## 3. Como se comparte la informacion comercial

Si autorizas el uso comercial, la informacion que se comparte con terceros
es **agregada y seudonimizada**: estadisticas por ciclo, por especializacion
y por tendencia. No se entrega tu nombre, tu correo ni tu codigo de
estudiante, y no se entregan respuestas individuales atribuibles a una
persona identificada.

Los terceros que reciban esa informacion quedan obligados por contrato a no
reidentificar a ninguna persona.

## 4. Cuanto tiempo los guardamos

- Datos de cuenta: mientras la cuenta este activa.
- Cuestionarios y resultados: mientras la cuenta este activa, para tu historial.
- Registros tecnicos de seguridad: hasta 12 meses.
- Registros de consentimiento: mientras dure la relacion y el plazo legal de
  prescripcion posterior, porque son la prueba de que autorizaste cada uso.

Al eliminar tu cuenta se borran tus datos personales identificables. Lo que
ya se haya incorporado de forma agregada y seudonimizada a estadisticas o al
entrenamiento del modelo no es reversible, porque en ese estado ya no esta
asociado a ti.

## 5. Tus derechos

La Ley 29733 te reconoce los derechos de **acceso, rectificacion,
cancelacion y oposicion** (derechos ARCO), ademas del derecho a revocar tu
consentimiento.

Puedes ejercerlos desde tu perfil o escribiendo al correo de contacto. Las
casillas opcionales se pueden desmarcar en cualquier momento, y a partir de
ese momento dejamos de usar tus datos para esa finalidad.

Si consideras que no atendimos tu solicitud, puedes acudir a la **Autoridad
Nacional de Proteccion de Datos Personales** del Ministerio de Justicia.

## 6. Seguridad

Las contrasenas se guardan cifradas con bcrypt y nunca en claro. El acceso a
la base de datos esta restringido por politicas de seguridad a nivel de fila:
cada consulta solo alcanza las filas del alumno que la origina. Las
comunicaciones viajan cifradas con TLS.

## 7. Menores de edad

REVO esta dirigida a estudiantes universitarios. Si eres menor de 14 anos
necesitas la autorizacion de tu padre, madre o tutor conforme al reglamento
de la Ley 29733.

## 8. Cambios

Si cambiamos esta politica publicaremos una version nueva y te pediremos que
la revises. Los usos opcionales que ya rechazaste seguiran rechazados.
$doc$,
    TRUE
),
(
    'data_commercial', '1.0',
    'Uso comercial de informacion agregada',
    'Autorizo que REVO comparta informacion agregada y seudonimizada de mis resultados con universidades y academias. Es opcional y puedo retirarlo cuando quiera.',
$doc$
# Uso comercial de informacion agregada

**Version 1.0 — OPCIONAL**

## Que estas autorizando

Que REVO incluya tus resultados, **de forma agregada y seudonimizada**, en
informes y conjuntos de datos que se comparten o comercializan con
universidades, institutos y academias.

## Que se comparte exactamente

- Tu nivel de afinidad con cada una de las diez especializaciones.
- Tu ciclo academico y la especializacion resultante.
- Tendencias calculadas sobre grupos de estudiantes.

## Que NO se comparte

- Tu nombre.
- Tu correo electronico.
- Tu codigo de estudiante.
- Cualquier dato que permita identificarte de forma directa.

## Para que lo usan esas instituciones

Para disenar su oferta de cursos y programas segun la demanda real de
especializacion que muestran los estudiantes.

## Si no lo autorizas

REVO funciona exactamente igual. Tu resultado, tu historial y todas las
funciones siguen disponibles. Esta casilla no condiciona nada.

## Como retirarlo

Desde tu perfil, en cualquier momento. Al retirarlo dejamos de incluir tus
datos en nuevos informes. Los informes ya entregados no se pueden retirar
porque la informacion en ellos ya no esta asociada a ti.
$doc$,
    FALSE
),
(
    'ai_training', '1.0',
    'Uso de mis respuestas para entrenar el modelo',
    'Autorizo que mis respuestas se usen para entrenar y mejorar el modelo de recomendacion de REVO. Es opcional y puedo retirarlo cuando quiera.',
$doc$
# Uso de mis respuestas para entrenar el modelo

**Version 1.0 — OPCIONAL**

## Que estas autorizando

Que tus respuestas al cuestionario y el resultado que obtuviste se
incorporen al conjunto de datos con el que se entrena el modelo de
recomendacion de REVO.

## Por que sirve

El modelo mejora cuando aprende de respuestas de estudiantes reales en lugar
de solo datos simulados. Cuantos mas casos reales, mas fiable es la
recomendacion para quien venga despues.

## Que se incorpora

Tu vector de afinidad (diez valores numericos) y la especializacion
resultante. **Sin ningun dato identificativo asociado**: al dataset de
entrenamiento no llega tu nombre, ni tu correo, ni tu codigo.

## Si no lo autorizas

REVO funciona exactamente igual y tu resultado es el mismo. Simplemente tus
datos no entran al entrenamiento.

## Como retirarlo

Desde tu perfil, en cualquier momento. Dejamos de usar tus datos en los
entrenamientos siguientes. Un modelo ya entrenado no se puede "desentrenar":
los pesos actuales no se pueden revertir a mano, pero tus datos salen del
conjunto y no participan en ningun entrenamiento posterior.
$doc$,
    FALSE
)
ON CONFLICT (doc_type, version) DO NOTHING;

-- Se suelta la identidad de administrador en cuanto deja de hacer falta.
SELECT set_config('revo.role', '', false);

DO $verificacion$
DECLARE
    faltan INTEGER;
BEGIN
    SELECT count(*) INTO faltan
    FROM (VALUES ('terms'),('privacy'),('data_commercial'),('ai_training')) AS t(tipo)
    WHERE NOT EXISTS (
        SELECT 1 FROM legal_documents d WHERE d.doc_type = t.tipo AND d.is_current
    );

    IF faltan > 0 THEN
        RAISE EXCEPTION 'Faltan % documentos legales vigentes', faltan;
    END IF;

    RAISE NOTICE 'Consentimiento informado listo: 4 documentos vigentes';
END
$verificacion$;

-- ############################################################################
--   13_registro.sql
--   Registro y verificacion de correo
-- ############################################################################

-- ============================================================
-- REVO DB - Script 13: alta de alumnos bajo RLS
-- ============================================================
-- Problema que resuelve, encontrado por las pruebas de integracion:
--
--   El registro ocurre SIN identidad (el alumno todavia no existe), asi que
--   la sesion no tiene contexto RLS. Un INSERT plano pasa, porque la
--   politica users_insert solo exige role = 'student'. Pero SQLAlchemy no
--   hace un INSERT plano: hace INSERT ... RETURNING id para recuperar la
--   clave. Y PostgreSQL aplica tambien la politica de SELECT a las filas que
--   devuelve un RETURNING. Sin contexto, users_select es falsa, y el alta
--   revienta con "new row violates row-level security policy".
--
--   Quitar el RETURNING no es opcion (el ORM lo necesita) y relajar
--   users_select tampoco (es lo que impide que un alumno lea a otro).
--
-- Solucion: una unica primitiva privilegiada para el alta, igual que
-- revo_credenciales_por_email lo es para el login. Todo lo demas del
-- registro (el consentimiento) sigue pasando por RLS normal.
--
-- Ventaja adicional: el rol queda fijado a 'student' DENTRO de la funcion.
-- Ya no depende de que la aplicacion se acuerde de no mandar 'admin': es
-- estructuralmente imposible crear un administrador desde el registro.
-- ============================================================

CREATE OR REPLACE FUNCTION revo_crear_alumno(
    p_email         TEXT,
    p_password_hash TEXT,
    p_full_name     TEXT,
    p_student_code  TEXT DEFAULT NULL,
    -- INTEGER y no SMALLINT: psycopg2 manda los enteros de Python como
    -- integer, y PostgreSQL no reduce el tipo al resolver que funcion
    -- llamar. Con SMALLINT la llamada falla con "function does not exist",
    -- que es un mensaje que no lleva a ninguna parte. El rango real lo
    -- sigue imponiendo el CHECK de la columna.
    p_semester      INTEGER DEFAULT NULL
)
RETURNS TABLE (nuevo_id INTEGER, motivo TEXT)
LANGUAGE plpgsql SECURITY DEFINER AS
$fn$
DECLARE
    v_email TEXT := lower(trim(p_email));
    v_id    INTEGER;
BEGIN
    IF v_email IS NULL OR v_email = '' THEN
        RETURN QUERY SELECT NULL::INTEGER, 'email_invalido'::TEXT;
        RETURN;
    END IF;

    IF EXISTS (SELECT 1 FROM users u WHERE lower(u.email) = v_email) THEN
        RETURN QUERY SELECT NULL::INTEGER, 'email_duplicado'::TEXT;
        RETURN;
    END IF;

    IF p_student_code IS NOT NULL AND EXISTS (
        SELECT 1 FROM users u WHERE u.student_code = p_student_code
    ) THEN
        RETURN QUERY SELECT NULL::INTEGER, 'codigo_duplicado'::TEXT;
        RETURN;
    END IF;

    -- El rol va escrito aqui, no llega como parametro. Es la razon principal
    -- de que esta funcion exista.
    INSERT INTO users (email, password_hash, full_name, student_code, semester, role)
    VALUES (v_email, p_password_hash, p_full_name, p_student_code,
            p_semester::SMALLINT, 'student')
    RETURNING id INTO v_id;

    RETURN QUERY SELECT v_id, NULL::TEXT;
END
$fn$;

-- SECURITY DEFINER corre con los permisos del dueno. Sin fijar search_path,
-- un esquema controlado por el atacante que este antes en el path puede
-- suplantar a la tabla users que la funcion nombra.
ALTER FUNCTION revo_crear_alumno(TEXT, TEXT, TEXT, TEXT, INTEGER)
    SET search_path = public, pg_temp;

REVOKE ALL ON FUNCTION revo_crear_alumno(TEXT, TEXT, TEXT, TEXT, INTEGER) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION revo_crear_alumno(TEXT, TEXT, TEXT, TEXT, INTEGER) TO revo_app;

DO $verificacion$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'revo_crear_alumno'
    ) THEN
        RAISE EXCEPTION 'La funcion de alta no se creo';
    END IF;
    RAISE NOTICE 'Alta de alumnos disponible bajo RLS';
END
$verificacion$;

-- ############################################################################
--   14_cuentas.sql
--   Gestion de cuentas y secretos caducados
-- ############################################################################

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

-- ############################################################################
--   15_roles_por_servicio.sql
--   Un rol de base de datos por microservicio
-- ############################################################################

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

-- ############################################################################
--   17_mover_catalogos.sql
--   Cursos y empleos pasan a ml-service
-- ############################################################################

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

-- ############################################################################
--   18_compatibilidad_gestionado.sql
--   IMPRESCINDIBLE en Supabase: sin esto nadie inicia sesion
-- ############################################################################

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

-- ############################################################################
--
--   PASO FINAL - CONTRASENAS DE LOS CUATRO ROLES
--
--   >>> EDITA LAS CUATRO LINEAS MARCADAS ANTES DE EJECUTAR <<<
--
--   Cada microservicio se conecta con SU PROPIO rol. Es lo que impide que el
--   cuestionario pueda leer la tabla de usuarios aunque una consulta se
--   equivoque: la frontera la pone la base de datos, no el codigo.
--
-- ############################################################################

DO $revo_final$
DECLARE
    -- ↓↓↓ CAMBIA ESTAS CUATRO ↓↓↓
    clave_auth    text := 'CAMBIAME-auth';
    clave_survey  text := 'CAMBIAME-survey';
    clave_ml      text := 'CAMBIAME-ml';
    clave_service text := 'CAMBIAME-service';
    -- ↑↑↑ CAMBIA ESTAS CUATRO ↑↑↑

    claves text[];
BEGIN
    claves := ARRAY[clave_auth, clave_survey, clave_ml, clave_service];

    -- Falla en vez de dejar la base abierta con contrasenas publicadas en
    -- un fichero que esta en GitHub.
    IF EXISTS (SELECT 1 FROM unnest(claves) c WHERE c LIKE 'CAMBIAME-%') THEN
        RAISE EXCEPTION
            'Falta cambiar las contrasenas del bloque PASO FINAL. Estan en el fichero, o sea que son publicas.';
    END IF;

    -- Cuatro iguales dejarian los roles separados solo de nombre.
    IF (SELECT count(DISTINCT c) FROM unnest(claves) c) < 4 THEN
        RAISE EXCEPTION
            'Las cuatro contrasenas tienen que ser distintas: con una repetida, quien consiga una credencial las tiene todas.';
    END IF;

    IF (SELECT min(length(c)) FROM unnest(claves) c) < 20 THEN
        RAISE EXCEPTION 'Alguna contrasena tiene menos de 20 caracteres.';
    END IF;

    -- Se pasan como parametro, no concatenadas: una comilla simple dentro de
    -- la contrasena romperia la sentencia si se pegara a mano.
    EXECUTE format('ALTER ROLE revo_auth    WITH PASSWORD %L', clave_auth);
    EXECUTE format('ALTER ROLE revo_survey  WITH PASSWORD %L', clave_survey);
    EXECUTE format('ALTER ROLE revo_ml      WITH PASSWORD %L', clave_ml);
    EXECUTE format('ALTER ROLE revo_service WITH PASSWORD %L', clave_service);

    -- revo_app quedo sin permisos en la migracion 15. Un rol sin uso que
    -- todavia puede conectarse es una puerta que nadie vigila.
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'revo_app') THEN
        EXECUTE 'ALTER ROLE revo_app NOLOGIN';
    END IF;

    RAISE NOTICE 'Contrasenas asignadas a revo_auth, revo_survey, revo_ml y revo_service.';
END
$revo_final$;


-- ############################################################################
--   COMPROBACIONES
-- ############################################################################

-- 1) Los cuatro roles existen y ninguno se salta la seguridad por filas.
--    rolsuper y rolbypassrls tienen que salir en false los cuatro.
SELECT rolname AS rol,
       rolsuper AS es_superusuario,
       rolbypassrls AS se_salta_rls,
       rolcanlogin AS puede_conectarse
FROM pg_roles
WHERE rolname LIKE 'revo\_%'
ORDER BY rolname;

-- 2) Las tablas con datos de alumnos tienen RLS activo.
SELECT tablename AS tabla,
       rowsecurity AS rls_activo
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY rowsecurity, tablename;
