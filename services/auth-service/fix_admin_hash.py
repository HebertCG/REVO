import sys
sys.path.insert(0, ".")
from security import hash_password, verify_password

# Generar hash nuevo (válido para passlib)
new_hash = hash_password("Admin@REVO2025")
print("NEW_HASH:", new_hash)
print("Self-verify:", verify_password("Admin@REVO2025", new_hash))

# Conectar a la BD y actualizar
import psycopg2
conn = psycopg2.connect(
    host="localhost", port=5432, dbname="revo_db",
    user="postgres", password="Hebertjose89"
)
cur = conn.cursor()
cur.execute("UPDATE users SET password_hash=%s WHERE email='admin@revo.edu' RETURNING id, email, role", (new_hash,))
row = cur.fetchone()
conn.commit()
cur.close()
conn.close()
print("DB Updated:", row)
