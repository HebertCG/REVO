"""
Script para regenerar el hash correcto del admin usando el mismo código Python 
que usa el auth-service. Debe ejecutarse desde el contexto del auth-service.
"""
import sys
sys.path.insert(0, r"C:\Users\corne\OneDrive\Escritorio\HC\REVO\services\auth-service")

# Importar el venv del auth-service
import subprocess, os

result = subprocess.run(
    [r"C:\Users\corne\OneDrive\Escritorio\HC\REVO\services\auth-service\venv\Scripts\python.exe",
     "-c",
     """
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__truncate_error=False)
h = pwd_context.hash("Admin@REVO2025"[:72])
print(h)
v = pwd_context.verify("Admin@REVO2025"[:72], h)
print("Verify same hash:", v)
"""],
    capture_output=True, text=True
)
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr[:300] if result.stderr else "")
