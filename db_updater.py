from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://postgres:Hebertjose89@localhost:5432/revo_db"
engine = create_engine(DATABASE_URL)

files = [
    r"C:\Users\corne\OneDrive\Escritorio\HC\REVO\database\02_seed_specializations.sql",
    r"C:\Users\corne\OneDrive\Escritorio\HC\REVO\database\03_seed_questions.sql",
    r"C:\Users\corne\OneDrive\Escritorio\HC\REVO\database\04_seed_training_data.sql"
]

with engine.begin() as conn:
    for f in files:
        with open(f, 'r', encoding='utf-8') as file:
            sql_script = file.read()
            print(f"Executing {f}...")
            try:
                conn.execute(text(sql_script))
                print(f"Success: {f}")
            except Exception as e:
                print(f"Error executing {f}: \n{e}")

print("Database update finished!")
