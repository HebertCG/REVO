from database import engine
from sqlalchemy import text

print("Agregando columnas nuevas al motor adaptativo...")

with engine.begin() as conn:
    try:
        conn.execute(text("ALTER TABLE questions ADD COLUMN specialization_id INTEGER NOT NULL DEFAULT 1;"))
    except Exception as e:
        print("specialization_id ya existe o error:", e)

    try:
        conn.execute(text("ALTER TABLE questionnaire_sessions ADD COLUMN phase SMALLINT DEFAULT 1;"))
    except Exception as e:
        print("phase ya existe o error:", e)

    try:
        conn.execute(text("ALTER TABLE questionnaire_sessions DROP CONSTRAINT IF EXISTS questionnaire_sessions_user_id_fkey CASCADE;"))
    except Exception as e:
        print("Error eliminando fkey de users:", e)
        
    try:
        conn.execute(text("ALTER TABLE questionnaire_sessions ADD COLUMN phase_data JSON;"))
    except Exception as e:
        print("phase_data ya existe o error:", e)

    print("Columnas agregadas. Insertando 100 preguntas...")
    with open(r"C:\Users\corne\OneDrive\Escritorio\HC\REVO\database\03_seed_questions.sql", 'r', encoding='utf-8') as file:
        sql = file.read()
        conn.execute(text(sql))
        print("Completado. 100 preguntas insertadas.")
