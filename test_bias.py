import random
from collections import Counter
import sys

# Import ML Predictor
sys.path.append('services/ml-service')
from model.predictor import predict

print('--- INICIANDO TEST DE SESGO DE ML (1000 simulaciones) ---')
ml_results = []
for _ in range(1000):
    # FASE 1: 10 preguntas aleatorias (1 a 5)
    phase1 = {i: random.randint(1, 5) for i in range(1, 11)}
    
    # Obtener los top 3 (simulando la lógica del servidor)
    # Mezclamos antes para romper empates exactos como en el backend
    keys = list(phase1.keys())
    random.shuffle(keys)
    top3 = sorted(keys, key=lambda k: phase1[k], reverse=True)[:3]
    
    # FASE 2: 15 preguntas (5 para cada uno de los top3)
    phase2 = {i: 0 for i in range(1, 11)}
    for target_spec in top3:
        phase2[target_spec] = sum(random.randint(1, 5) for _ in range(5))
        
    # Calculando 'feature vector'
    answers = {}
    for i in range(1, 11):
        score = phase1[i] + phase2[i]
        answers[f'aff_{i}'] = score / 30.0
        
    # Predecir
    res = predict(answers)
    ml_results.append(res['primary']['specialization_id'])

counter_ml = Counter(ml_results)
total_ml = sum(counter_ml.values())
for spec_id in range(1, 11):
    count = counter_ml.get(spec_id, 0)
    print(f'Especialidad {spec_id:2d}: {count} veces ({(count/total_ml)*100:.1f}%)')


print('\n--- INICIANDO TEST DE SESGO DE ARQUETIPO PSICOMÉTRICO (1000 simulaciones) ---')
# Lógica idéntica al frontend calcArchetype
def calcArchetype(answers):
    counts = {'A': 0, 'B': 0, 'C': 0, 'D': 0}
    for v in answers.values():
        if v in counts:
            counts[v] += 1
    max_count = max(counts.values())
    winners = [k for k, v in counts.items() if v == max_count]
    return random.choice(winners)

arch_results = []
options = ['A', 'B', 'C', 'D']
for _ in range(1000):
    ans = {
        'q1': random.choice(options),
        'q2': random.choice(options),
        'q3': random.choice(options),
        'q4': random.choice(options)
    }
    arch_results.append(calcArchetype(ans))

counter_arch = Counter(arch_results)
total_arch = sum(counter_arch.values())
for k in options:
    count = counter_arch.get(k, 0)
    print(f'Arquetipo {k}: {count} veces ({(count/total_arch)*100:.1f}%)')
