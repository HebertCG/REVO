from database import engine, Base, MLTrainingData
from sqlalchemy import text

print("Borrando tabla ml_training_data para actualizar esquema...")
MLTrainingData.__table__.drop(engine, checkfirst=True)
MLTrainingData.__table__.create(engine)
print("Tabla actualizada.")

print("Insertando nuevo motor de 400 estudiantes adaptativos...")
with engine.begin() as conn:
    with open(r"C:\Users\corne\OneDrive\Escritorio\HC\REVO\database\04_seed_training_data.sql", 'r', encoding='utf-8') as file:
        sql = file.read()
        conn.execute(text(sql))
        print("Completado.")
