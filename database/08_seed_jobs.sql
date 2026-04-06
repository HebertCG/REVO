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
