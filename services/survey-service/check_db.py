from database import SessionLocal, Question
db = SessionLocal()
print("Total questions:", db.query(Question).count())
for spec_id in range(1, 11):
    count = db.query(Question).filter(Question.specialization_id == spec_id).count()
    print(f"Spec {spec_id}: {count} questions")
