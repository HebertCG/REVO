-- Actualizar contraseñas con hashes bcrypt 4.0.1 compatibles
-- Admin@1234
UPDATE users 
SET password_hash = '$2b$12$kUJEWCIyqgLZ9biN95LXROy8DAMkbju85zGLqedQikWXLgeKomLkK'
WHERE email = 'admin@revo.edu';

-- Demo@1234
UPDATE users 
SET password_hash = '$2b$12$VHDy.eA9vmzqKa7Yu/P8v.r1WppA4yBT/V1Wchtg69XXDgQ4NIsnq'
WHERE email = 'demo@revo.edu';
