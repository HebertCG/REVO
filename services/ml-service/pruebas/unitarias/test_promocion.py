"""
Pruebas de la puerta de promocion.

El reentrenamiento es AUTOMATICO: salta solo cada 50 predicciones nuevas. Sin
puerta, un dataset que se degrada degrada el modelo en produccion sin que
nadie intervenga ni se entere.

La decision de diseno mas discutible del modulo se prueba explicitamente en
`test_sin_lift_avisa_pero_deja_pasar`: la regla "un modelo que no supera su
linea base no se despliega" NO bloquea por defecto, porque con el dataset
actual el lift es ~0 siempre y bloquear dejaria al servicio sin ningun
modelo. Avisa siempre y bloquea cuando se le pide.
"""
from model import promocion


def metricas(f1=0.8, lift=0.05, **extra):
    return {"f1": f1, "accuracy": f1, "lift_over_baseline": lift, **extra}


class TestPrimerModelo:
    def test_sin_modelo_activo_se_promueve(self):
        # No tener modelo es peor que tener uno mediocre: sin el, ningun
        # alumno recibe resultado.
        veredicto = promocion.decidir(metricas(), None)

        assert veredicto.promover is True
        assert "primer_modelo" in veredicto.motivo

    def test_el_primer_modelo_se_promueve_aunque_no_tenga_lift(self):
        veredicto = promocion.decidir(metricas(lift=-0.01), None)

        assert veredicto.promover is True
        assert veredicto.avisos  # pero deja constancia


class TestNoEmpeorar:
    def test_un_candidato_claramente_peor_se_rechaza(self):
        veredicto = promocion.decidir(metricas(f1=0.60), metricas(f1=0.85))

        assert veredicto.promover is False
        assert "regresion" in veredicto.motivo

    def test_un_candidato_mejor_se_promueve(self):
        veredicto = promocion.decidir(metricas(f1=0.90), metricas(f1=0.85))

        assert veredicto.promover is True

    def test_una_caida_dentro_de_la_tolerancia_se_acepta(self):
        # Sin margen, la fluctuacion normal entre particiones del mismo
        # dataset bloquearia reentrenamientos legitimos.
        veredicto = promocion.decidir(
            metricas(f1=0.84), metricas(f1=0.85), tolerancia_f1=0.02)

        assert veredicto.promover is True

    def test_el_motivo_dice_los_numeros_comparados(self):
        # Un rechazo sin cifras no se puede discutir ni auditar.
        veredicto = promocion.decidir(metricas(f1=0.50), metricas(f1=0.85))

        assert "0.5" in veredicto.motivo and "0.85" in veredicto.motivo


class TestLiftSobreLaReglaTrivial:
    def test_sin_lift_avisa_pero_deja_pasar(self):
        # El comportamiento por defecto, y el motivo esta documentado en el
        # modulo: bloquear con el dataset actual dejaria el servicio sin
        # modelo, porque el lift es ~0 SIEMPRE por construccion del generador.
        veredicto = promocion.decidir(metricas(lift=0.0), metricas(f1=0.7))

        assert veredicto.promover is True
        assert any("trivial" in aviso for aviso in veredicto.avisos)

    def test_sin_lift_bloquea_cuando_se_exige(self):
        # La regla se vuelve bloqueante cuando el dataset deja de ser
        # circular. Que sea un interruptor y no una constante es el punto.
        veredicto = promocion.decidir(
            metricas(lift=0.0), metricas(f1=0.7), exigir_lift_positivo=True)

        assert veredicto.promover is False
        assert "sin_lift" in veredicto.motivo

    def test_con_lift_positivo_no_avisa_de_la_regla_trivial(self):
        veredicto = promocion.decidir(metricas(lift=0.12), metricas(f1=0.7))

        assert not any("trivial" in aviso for aviso in veredicto.avisos)

    def test_el_aviso_dice_que_no_se_reporte_como_acierto(self):
        # Es la frase que evita que el accuracy se cite en la memoria como
        # evidencia de que el modelo funciona.
        veredicto = promocion.decidir(metricas(lift=0.0), None)

        assert any("No reportar" in aviso or "no reportar" in aviso.lower()
                   for aviso in veredicto.avisos)


class TestCalibracion:
    def test_avisa_si_la_calibracion_no_cumple_el_objetivo(self):
        veredicto = promocion.decidir(
            metricas(calibracion={"cumple_objetivo": False, "ece_despues": 0.18}),
            metricas(f1=0.7),
        )

        assert any("ECE" in aviso for aviso in veredicto.avisos)

    def test_una_calibracion_correcta_no_genera_aviso(self):
        veredicto = promocion.decidir(
            metricas(calibracion={"cumple_objetivo": True, "ece_despues": 0.02}),
            metricas(f1=0.7),
        )

        assert not any("ECE" in aviso for aviso in veredicto.avisos)


class TestFormato:
    def test_el_veredicto_se_serializa_para_la_respuesta_http(self):
        resultado = promocion.decidir(metricas(), None).como_dict()

        assert set(resultado) == {"promovido", "motivo", "avisos"}
        assert isinstance(resultado["avisos"], list)
