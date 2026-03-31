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
