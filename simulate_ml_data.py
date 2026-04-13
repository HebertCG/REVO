import random

NUM_SAMPLES = 1000
with open('database/04_seed_training_data.sql', 'w', encoding='utf-8') as f:
    f.write('-- ============================================================\n')
    f.write('-- REVO DB - Script 04: Training Data Generator (10 Afinidades)\n')
    f.write('-- ============================================================\n\n')
    f.write('TRUNCATE TABLE ml_training_data CASCADE;\n')
    f.write('ALTER SEQUENCE ml_training_data_id_seq RESTART WITH 1;\n\n')
    f.write('INSERT INTO ml_training_data (\n')
    f.write('    aff_1, aff_2, aff_3, aff_4, aff_5, aff_6, aff_7, aff_8, aff_9, aff_10, specialization_id\n')
    f.write(') VALUES\n')

    rows = []
    for _ in range(NUM_SAMPLES):
        # 1. Decide the true target specialization
        target_spec = random.randint(1, 10)
        
        # 2. Pick 2 other specs to be the "Top 3" evaluated in Phase 2
        others = list(range(1, 11))
        others.remove(target_spec)
        top3_specs = [target_spec] + random.sample(others, 2)
        random.shuffle(top3_specs)

        # 3. Simulate Phase 1 answers (1 to 5) for all 10 specs
        phase1 = {i: random.randint(1, 5) for i in range(1, 11)}
        # Ensure top 3 actually score generally high in phase 1 so they qualify!
        for spec in top3_specs:
            phase1[spec] = random.randint(3, 5)
        
        # 4. Simulate Phase 2 answers (5 questions, 1-5 each) for top 3 specs
        phase2 = {i: 0 for i in range(1, 11)}
        for spec in top3_specs:
            if spec == target_spec:
                # Target gets very high scores (mostly 4 and 5)
                phase2[spec] = sum([random.randint(4, 5) for _ in range(5)])
            else:
                # Top specs but not target gets medium-high (mostly 2, 3, 4)
                phase2[spec] = sum([random.randint(2, 4) for _ in range(5)])

        # 5. Calculate final affinities
        aff = {}
        for i in range(1, 11):
            total_score = phase1[i] + phase2[i]
            # Max possible is 30
            aff[i] = round(total_score / 30.0, 4)
            
        vector_str = ', '.join([str(aff[i]) for i in range(1, 11)])
        rows.append(f'({vector_str}, {target_spec})')

    f.write(',\n'.join(rows))
    f.write(';\n\n')
    f.write('DO \$\$ BEGIN RAISE NOTICE ''✅ 1000 estudiantes REVO realistas generados para el ML.''; END \$\$;\n')
