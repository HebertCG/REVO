"""
fix_passwords.py — Actualiza hashes de contraseñas en revo_db
Compatible con bcrypt 4.0.1 + passlib 1.7.4
"""
import sys
sys.path.insert(0, '.')

from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://postgres:Hebertjose89@localhost:5432/revo_db"
engine = create_engine(DATABASE_URL)

# Hashes generados con bcrypt 4.0.1
ADMIN_HASH = "$2b$12$kUJEWCIyqgLZ9biN95LXROy8DAMkbju85zGLqedQikWXLgeKomLkK"
DEMO_HASH  = "$2b$12$VHDy.eA9vmzqKa7Yu/P8v.r1WppA4yBT/V1Wchtg69XXDgQ4NIsnq"

with engine.connect() as conn:
    conn.execute(text(
        "UPDATE users SET password_hash = :h WHERE email = 'admin@revo.edu'"
    ), {"h": ADMIN_HASH})
    conn.execute(text(
        "UPDATE users SET password_hash = :h WHERE email = 'demo@revo.edu'"
    ), {"h": DEMO_HASH})
    conn.commit()

    rows = conn.execute(text("SELECT id, email, role, LEFT(password_hash,20) FROM users")).fetchall()
    for r in rows:
        print(f"  ID={r[0]}  email={r[1]}  role={r[2]}  hash={r[3]}...")

print("\nContrasenas actualizadas OK.")
print("  admin@revo.edu -> Admin@1234")
print("  demo@revo.edu  -> Demo@1234")
