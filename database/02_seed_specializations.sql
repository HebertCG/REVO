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
