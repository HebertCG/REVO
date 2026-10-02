"""
Reentrenamiento manual desde la linea de comandos.

    docker compose exec ml-service python retrain.py

Uso previsto: forzar un reentrenamiento sin pasar por el panel de
administracion (por ejemplo tras cargar datos nuevos a mano). El
reentrenamiento automatico NO vive aqui: lo dispara `check_and_retrain` en
routers/predict.py cuando se acumulan UMBRAL_REENTRENAMIENTO predicciones
nuevas desde el ultimo entrenamiento.

Este script estaba roto: importaba `SessionLocal` de `database`, que no
existe. El motor y la fabrica de sesiones los construye ServicioREVO, y las
tareas de fondo necesitan `sesion_de_servicio()`, que abre la sesion con el
contexto RLS del rol de servicio. Sin el, el SELECT sobre ml_training_data
devuelve cero filas y el entrenamiento falla con "No hay datos de
entrenamiento" aunque la tabla este llena.
"""
import sys

from main import servicio
from model.trainer import train_model


def reentrenar() -> int:
    db = servicio.sesion_de_servicio()
    try:
        resultado = train_model(db)
    finally:
        db.close()

    print(f"Modelo      : {resultado['algorithm']} {resultado['model_version']}")
    print(f"Accuracy    : {resultado['accuracy']:.4f}")
    print(f"F1          : {resultado['f1']:.4f}")
    print(f"Muestras    : {resultado['training_samples']} entrenamiento / "
          f"{resultado['test_samples']} prueba")
    print(f"Iteraciones : {resultado['n_iterations']}"
          f"{'' if resultado['converged'] else '  <-- NO CONVERGIO, subir max_iter'}")

    # El lift es la unica cifra que dice si el modelo aporta algo: cuanto
    # acierta POR ENCIMA de la regla trivial argmax(afinidades). Si sale
    # negativo, una linea de codigo sin aprendizaje automatico lo hace mejor.
    lift = resultado["lift_over_baseline"]
    print(f"Baseline    : {resultado['baseline_accuracy']:.4f} (regla argmax)")
    print(f"Lift        : {lift:+.4f}")

    calibracion = resultado.get("calibracion") or {}
    if calibracion.get("calibrado"):
        print(f"Calibracion : T={calibracion['temperatura']}  "
              f"ECE {calibracion['ece_antes']} -> {calibracion['ece_despues']}")
    else:
        print("Calibracion : SIN CALIBRAR (faltan muestras)")

    conformal = resultado.get("conformal") or {}
    if conformal.get("suficientes_muestras"):
        evaluacion = conformal.get("evaluacion", {})
        print(f"Conformal   : cobertura real {evaluacion.get('cobertura_real')} "
              f"(objetivo {conformal['cobertura_objetivo']}), "
              f"conjunto medio {evaluacion.get('tamano_medio')}")

    # Entrenar ya no implica desplegar. Si el candidato no paso la puerta,
    # decirlo es lo mas importante de toda esta salida: sin ello, quien
    # reentrena se queda creyendo que su modelo esta sirviendo.
    print()
    if resultado["promovido"]:
        print(f"DESPLEGADO  : {resultado['motivo']}")
    else:
        print(f"NO DESPLEGADO: {resultado['motivo']}")
        print("               Sigue sirviendo el modelo anterior.")

    for aviso in resultado.get("avisos", []):
        print(f"\nAVISO: {aviso}")

    if lift <= 0 or not resultado["promovido"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(reentrenar())
