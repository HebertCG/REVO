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
