from database import SessionLocal
from model.trainer import train_model

def retrain():
    db = SessionLocal()
    try:
        res = train_model(db, trained_by_id=2)
        print("Retrain Success:", res)
    finally:
        db.close()

if __name__ == '__main__':
    retrain()
