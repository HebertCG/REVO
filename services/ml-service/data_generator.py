import random

SQL_FILE = r"C:\Users\corne\OneDrive\Escritorio\HC\REVO\database\04_seed_training_data.sql"

def generate_student_affinities(target_branch):
    # Genera 10 floats de afinidad. El objetivo será el más alto.
    affinities = []
    for i in range(1, 11):
        if i == target_branch:
            # Afinidad primaria alta (70% a 100%)
            val = round(random.uniform(0.70, 1.00), 4)
        else:
            # Afinidades secundarias bajas (10% a 50%)
            val = round(random.uniform(0.10, 0.50), 4)
            # Ocasionalmente alguna rama cruzada puede ser un poco alta
            if random.random() < 0.15:
                val = round(random.uniform(0.50, 0.70), 4)
        affinities.append(val)
    return affinities, target_branch

def main():
    rows = []
    # Generar 40 estudiantes sintéticos por rama = 400 total
    for b in range(1, 11):
        for _ in range(40):
            affs, branch = generate_student_affinities(b)
            # Format: (aff_1..aff_10, specialization_id)
            val = f"({', '.join(map(str, affs))}, {branch})"
            rows.append(val)
    
    random.shuffle(rows)
    
    with open(SQL_FILE, 'w', encoding='utf-8') as f:
        f.write("-- ============================================================\n")
        f.write("-- REVO DB - Script 04: Training Data Generator (10 Afinidades)\n")
        f.write("-- ============================================================\n\n")
        f.write("TRUNCATE TABLE ml_training_data CASCADE;\n")
        f.write("ALTER SEQUENCE ml_training_data_id_seq RESTART WITH 1;\n\n")
        f.write("INSERT INTO ml_training_data (\n")
        cols = [f"aff_{i}" for i in range(1, 11)] + ["specialization_id"]
        f.write(f"    {', '.join(cols)}\n) VALUES\n")
        
        f.write(",\n".join(rows) + ";\n\n")
        f.write("DO $$ BEGIN RAISE NOTICE '✅ 400 estudiantes de entrenamiento sembrados para las 10 afinidades.'; END $$;\n")
        
    print(f"Generated 400 synthetic profiles into {SQL_FILE}")

if __name__ == '__main__':
    main()
