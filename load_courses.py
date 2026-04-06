from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://postgres:Hebertjose89@localhost:5432/revo_db"
engine = create_engine(DATABASE_URL)

files = [
    r"C:\Users\corne\OneDrive\Escritorio\HC\REVO\database\07_seed_courses.sql",
    r"C:\Users\corne\OneDrive\Escritorio\HC\REVO\database\08_seed_jobs.sql"
]

with engine.begin() as conn:
    print("Inyectando B2B y Roadmap a PostgreSQL...")
    for f in files:
        with open(f, 'r', encoding='utf-8') as file:
            conn.execute(text(file.read()))
            print(f"Éxito: {f}")
print("Bases de Datos de Empleos y Cursos re-sincronizadas!")
