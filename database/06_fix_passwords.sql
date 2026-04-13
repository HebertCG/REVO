-- Actualizar contraseñas con hashes bcrypt compatibles con passlib (auth-service)
-- Contraseña admin: Admin@REVO2025
UPDATE users 
SET password_hash = '$2b$12$NzLS60SnsFdQcHtJFbMmFeqNMZ.LECw6NO13enzKrqwmsnGmveQgK'
WHERE email = 'admin@revo.edu';

-- Contraseña demo: Demo@1234
UPDATE users 
SET password_hash = '$2b$12$VHDy.eA9vmzqKa7Yu/P8v.r1WppA4yBT/V1Wchtg69XXDgQ4NIsnq'
WHERE email = 'demo@revo.edu';
