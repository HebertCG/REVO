import { useState, Fragment } from 'react'
import personaCelularImg from '../assets/persona-celular.png'
import personaDiferenciaImg from '../assets/persona-diferencia.png'
import './PanelInformativo.css'

const RAMAS = [
  'Desarrollo de Software', 'Data Science e IA', 'Infraestructura y Cloud',
  'Ciberseguridad', 'Soporte Tecnico e IT Ops', 'QA y Testing',
  'Gestion y Producto', 'Diseno UX/UI', 'Sistemas Empresariales',
  'Investigacion e Innovacion',
].map((n, i) => ({ n, id: String(i + 1).padStart(2, '0') }))

// Puntos que ilustran cuantas preguntas cubre cada fase sobre el banco de 100.
const puntos = (c) => Array.from({ length: c }, (_, i) => ({ i }))

/**
 * Panel informativo de la landing: como funciona el sistema, que ofrece
 * y que lo diferencia. Portado desde Claude Design.
 *
 * Los estilos van en linea, igual que en el diseno original, para no
 * colisionar con las clases de Landing.css. Solo viven en el CSS los
 * keyframes y los estados :hover, que no pueden expresarse en linea.
 */
export default function PanelInformativo({
  panelDocente = true,
  notaConfianza = true,
  ilustraciones = true,
}) {
  const [fase, setFase] = useState(1)

  const esFase1 = fase === 1
  const esFase2 = fase === 2
  const esFase3 = fase === 3
  const verFase1 = () => setFase(1)
  const verFase2 = () => setFase(2)
  const verFase3 = () => setFase(3)

  const dotsFase1 = puntos(10)
  const dotsFase2 = puntos(15)
  const dotsFase3 = puntos(4)
  const dotsResto = puntos(71)
  const ramas = RAMAS

  return (
    <div className="revo-panel">
      <div style={{fontFamily: "'Plus Jakarta Sans',system-ui,-apple-system,sans-serif", color: "#0d1220", background: "#fff", WebkitFontSmoothing: "antialiased"}}>
        <section style={{position: "relative", overflow: "hidden", padding: "clamp(40px,6vw,84px) clamp(18px,5vw,64px) clamp(48px,6vw,88px)", background: "radial-gradient(1100px 620px at 78% -8%, #e4ecff 0%, rgba(228,236,255,0) 62%), linear-gradient(180deg,#fbfcff 0%,#ffffff 100%)"}}>
          <div style={{position: "absolute", inset: "0", backgroundImage: "radial-gradient(rgba(47,95,232,.16) 1px, transparent 1px)", backgroundSize: "26px 26px", opacity: ".5", pointerEvents: "none"}}></div>
          <div style={{position: "relative", maxWidth: "1180px", margin: "0 auto", display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(320px,1fr))", gap: "clamp(32px,4vw,56px)", alignItems: "center"}}>
            <div style={{animation: "revoRise .6s ease both"}}>
              <div style={{display: "flex", justifyContent: "center"}}>
                <div style={{display: "inline-flex", alignItems: "center", gap: "9px", padding: "6px 12px 6px 7px", borderRadius: "999px", background: "#fff", border: "1px solid rgba(13,18,32,.09)", boxShadow: "0 1px 2px rgba(13,18,32,.05)", fontSize: "12.5px", fontWeight: "600", color: "#3b465c"}}>
                  <span style={{display: "inline-block", padding: "3px 8px", borderRadius: "999px", background: "#2f5fe8", color: "#fff", fontFamily: "'JetBrains Mono',monospace", fontSize: "10px", letterSpacing: ".06em"}}>
                    REVO
                  </span>
                  Para estudiantes de Ingeniería de Sistemas
                </div>
              </div>
              <h1 style={{margin: "20px 0 0", fontSize: "clamp(34px,5.2vw,58px)", lineHeight: "1.04", letterSpacing: "-.03em", fontWeight: "800", textWrap: "balance"}}>
                Ya elegiste la carrera.
                <br />
                Ahora elige
                <span style={{color: "#2f5fe8", background: "linear-gradient(transparent 72%,#c9d9ff 72%,#c9d9ff 93%,transparent 93%)", WebkitBoxDecorationBreak: "clone", boxDecorationBreak: "clone"}}>
                  hacia dónde
                </span>
                te especializas.
              </h1>
              <p style={{margin: "20px 0 0", maxWidth: "520px", fontSize: "clamp(15.5px,1.5vw,18px)", lineHeight: "1.6", color: "#5a6478", textWrap: "pretty"}}>
                Un cuestionario que se adapta a tus respuestas y te devuelve una recomendación entre 10 ramas de Ingeniería de Sistemas — con el porcentaje de confianza de cada una, no con una respuesta única y absoluta.
              </p>
              <div style={{display: "flex", flexWrap: "wrap", gap: "12px", marginTop: "28px"}}>
                <a className="rv-h1" href="#revo-como" style={{display: "inline-flex", alignItems: "center", gap: "10px", padding: "15px 22px", borderRadius: "12px", background: "#2f5fe8", color: "#fff", fontSize: "15px", fontWeight: "700", boxShadow: "0 8px 20px rgba(47,95,232,.28)"}}>
                  Empezar el test
                  <span style={{display: "inline-flex", alignItems: "center", justifyContent: "center", width: "22px", height: "22px", borderRadius: "999px", background: "rgba(255,255,255,.2)", fontSize: "13px"}}>
                    →
                  </span>
                </a>
                <a className="rv-h2" href="#revo-ofrece" style={{display: "inline-flex", alignItems: "center", gap: "10px", padding: "15px 22px", borderRadius: "12px", background: "#fff", border: "1px solid rgba(13,18,32,.12)", color: "#0d1220", fontSize: "15px", fontWeight: "600"}}>
                  Ver qué recibes al terminar
                </a>
              </div>
              <div style={{display: "flex", flexWrap: "wrap", gap: "10px 22px", marginTop: "26px", fontSize: "13px", color: "#5a6478", fontWeight: "500"}}>
                <span style={{display: "flex", alignItems: "center", gap: "7px"}}>
                  <span style={{width: "7px", height: "7px", borderRadius: "999px", background: "#2f5fe8"}}></span>
                  29 preguntas, no 100
                </span>
                <span style={{display: "flex", alignItems: "center", gap: "7px"}}>
                  <span style={{width: "7px", height: "7px", borderRadius: "999px", background: "#2f5fe8"}}></span>
                  ~8 minutos
                </span>
                <span style={{display: "flex", alignItems: "center", gap: "7px"}}>
                  <span style={{width: "7px", height: "7px", borderRadius: "999px", background: "#2f5fe8"}}></span>
                  Sin cuenta para probar
                </span>
              </div>
            </div>
            <div style={{position: "relative", animation: "revoRise .7s .1s ease both"}}>
              <div style={{display: "flex", justifyContent: "flex-end", marginBottom: "14px"}}>
                <div style={{display: "flex", alignItems: "center", gap: "10px", padding: "10px 14px", borderRadius: "12px", background: "#0d1220", color: "#fff", boxShadow: "0 12px 26px rgba(13,18,32,.22)", animation: "revoFloat 5s ease-in-out infinite"}}>
                  <span style={{fontFamily: "'JetBrains Mono',monospace", fontSize: "18px", fontWeight: "600", color: "#8fb0ff"}}>
                    29
                  </span>
                  <span style={{fontSize: "11.5px", lineHeight: "1.25", fontWeight: "600"}}>
                    preguntas
                    <br />
                    <span style={{color: "#9aa4b8", fontWeight: "500"}}>
                      de un banco de 100
                    </span>
                  </span>
                </div>
              </div>
              <div style={{borderRadius: "20px", background: "#fff", border: "1px solid rgba(13,18,32,.09)", boxShadow: "0 28px 60px rgba(23,43,99,.16),0 2px 6px rgba(13,18,32,.05)", overflow: "hidden"}}>
                <div style={{display: "flex", alignItems: "center", gap: "10px", padding: "13px 16px", borderBottom: "1px solid rgba(13,18,32,.07)", background: "#fafbff"}}>
                  <span style={{width: "9px", height: "9px", borderRadius: "999px", background: "#e2e6ef"}}></span>
                  <span style={{width: "9px", height: "9px", borderRadius: "999px", background: "#e2e6ef"}}></span>
                  <span style={{width: "9px", height: "9px", borderRadius: "999px", background: "#e2e6ef"}}></span>
                  <span style={{marginLeft: "6px", fontFamily: "'JetBrains Mono',monospace", fontSize: "11px", color: "#8a93a6"}}>
                    revo / mi resultado
                  </span>
                </div>
                <div style={{padding: "clamp(18px,2.4vw,26px)"}}>
                  <div style={{fontSize: "11px", fontWeight: "700", letterSpacing: ".1em", textTransform: "uppercase", color: "#8a93a6"}}>
                    Especialización recomendada
                  </div>
                  <div style={{display: "flex", flexWrap: "wrap", alignItems: "center", gap: "12px", marginTop: "9px"}}>
                    <div style={{fontSize: "clamp(22px,2.6vw,28px)", fontWeight: "800", letterSpacing: "-.02em"}}>
                      Data Science e IA
                    </div>
                    <span style={{padding: "5px 10px", borderRadius: "8px", background: "#eaf0ff", color: "#2f5fe8", fontFamily: "'JetBrains Mono',monospace", fontSize: "12px", fontWeight: "600"}}>
                      82% confianza
                    </span>
                  </div>
                  <div style={{display: "flex", flexDirection: "column", gap: "14px", marginTop: "22px"}}>
                    <div>
                      <div style={{display: "flex", justifyContent: "space-between", fontSize: "13px", fontWeight: "600", marginBottom: "7px"}}>
                        <span>
                          Data Science e IA
                        </span>
                        <span style={{fontFamily: "'JetBrains Mono',monospace", color: "#2f5fe8"}}>
                          82%
                        </span>
                      </div>
                      <div style={{height: "9px", borderRadius: "999px", background: "#eef1f7", overflow: "hidden"}}>
                        <div style={{height: "100%", borderRadius: "999px", background: "linear-gradient(90deg,#2f5fe8,#5b86ff)", animation: "revoBar82 1.1s .3s cubic-bezier(.2,.8,.2,1) both"}}></div>
                      </div>
                    </div>
                    <div>
                      <div style={{display: "flex", justifyContent: "space-between", fontSize: "13px", fontWeight: "600", marginBottom: "7px"}}>
                        <span>
                          Desarrollo de Software
                        </span>
                        <span style={{fontFamily: "'JetBrains Mono',monospace", color: "#5a6478"}}>
                          61%
                        </span>
                      </div>
                      <div style={{height: "9px", borderRadius: "999px", background: "#eef1f7", overflow: "hidden"}}>
                        <div style={{height: "100%", borderRadius: "999px", background: "#9db8ff", animation: "revoBar61 1.1s .45s cubic-bezier(.2,.8,.2,1) both"}}></div>
                      </div>
                    </div>
                    <div>
                      <div style={{display: "flex", justifyContent: "space-between", fontSize: "13px", fontWeight: "600", marginBottom: "7px"}}>
                        <span>
                          Investigación e Innovación
                        </span>
                        <span style={{fontFamily: "'JetBrains Mono',monospace", color: "#5a6478"}}>
                          44%
                        </span>
                      </div>
                      <div style={{height: "9px", borderRadius: "999px", background: "#eef1f7", overflow: "hidden"}}>
                        <div style={{height: "100%", borderRadius: "999px", background: "#c8d6fb", animation: "revoBar44 1.1s .6s cubic-bezier(.2,.8,.2,1) both"}}></div>
                      </div>
                    </div>
                  </div>
                  <div style={{display: "flex", flexWrap: "wrap", gap: "10px", marginTop: "22px", paddingTop: "18px", borderTop: "1px solid rgba(13,18,32,.08)"}}>
                    <span style={{padding: "7px 11px", borderRadius: "9px", background: "#0d1220", color: "#fff", fontSize: "12px", fontWeight: "600"}}>
                      Estilo: Analítico
                    </span>
                    <span style={{padding: "7px 11px", borderRadius: "9px", background: "#fdf3e2", color: "#8a5b12", fontSize: "12px", fontWeight: "600"}}>
                      Fase 3 · 4 escenarios
                    </span>
                    <span style={{padding: "7px 11px", borderRadius: "9px", background: "#f2f4f9", color: "#5a6478", fontSize: "12px", fontWeight: "600"}}>
                      Basado en ocupaciones O*NET
                    </span>
                  </div>
                </div>
                {notaConfianza && (
                  <>
                  <div style={{display: "flex", gap: "11px", padding: "14px 18px", background: "#fdf9f0", borderTop: "1px solid #f2e6cf"}}>
                    <span style={{flex: "none", width: "20px", height: "20px", borderRadius: "999px", background: "#f2a93b", color: "#fff", fontSize: "12px", fontWeight: "800", display: "flex", alignItems: "center", justifyContent: "center"}}>
                      !
                    </span>
                    <p style={{margin: "0", fontSize: "12.5px", lineHeight: "1.5", color: "#7a5a1e"}}>
                      Tu perfil está entre dos ramas cercanas. REVO te lo dice en vez de fingir certeza: revisa el plan de acción de ambas antes de decidir.
                    </p>
                  </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </section>
        <section id="revo-como" style={{padding: "clamp(48px,6.5vw,96px) clamp(18px,5vw,64px)", background: "#fff", scrollMarginTop: "20px"}}>
          <div style={{maxWidth: "1180px", margin: "0 auto"}}>
            <div style={{display: "flex", alignItems: "center", gap: "14px", marginBottom: "clamp(28px,4vw,52px)"}}>
              <span style={{flex: "1", height: "1px", background: "linear-gradient(to right,rgba(13,18,32,0),rgba(13,18,32,.14))"}}></span>
              <span style={{display: "flex", alignItems: "center", gap: "5px"}}>
                <span style={{width: "5px", height: "5px", borderRadius: "999px", background: "#c8d6fb"}}></span>
                <span style={{width: "7px", height: "7px", borderRadius: "999px", background: "#2f5fe8"}}></span>
                <span style={{width: "5px", height: "5px", borderRadius: "999px", background: "#c8d6fb"}}></span>
              </span>
              <span style={{flex: "1", height: "1px", background: "linear-gradient(to left,rgba(13,18,32,0),rgba(13,18,32,.14))"}}></span>
            </div>
            <div style={{display: "flex", flexWrap: "wrap", alignItems: "flex-end", justifyContent: "space-between", gap: "20px"}}>
              <div style={{maxWidth: "640px"}}>
                <h2 style={{margin: "0", fontSize: "clamp(26px,3.6vw,40px)", lineHeight: "1.1", letterSpacing: "-.025em", fontWeight: "800", textWrap: "balance"}}>
                  Tres fases. Cada una pregunta según lo que respondiste antes.
                </h2>
              </div>
              <p style={{margin: "0", maxWidth: "360px", fontSize: "15px", lineHeight: "1.6", color: "#5a6478"}}>
                Nadie contesta las 100 preguntas del banco. El test detecta dónde tienes señal y profundiza solo ahí.
              </p>
            </div>
            <div style={{display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(250px,1fr))", gap: "16px", marginTop: "36px"}}>
              <div className="rv-h3" style={{position: "relative", padding: "24px", borderRadius: "16px", border: "1px solid rgba(13,18,32,.09)", background: "#fff", cursor: "pointer", transition: "transform .18s ease,box-shadow .18s ease"}} onClick={verFase1}>
                {esFase1 && (
                  <>
                  <div style={{position: "absolute", inset: "-1px", borderRadius: "16px", border: "2px solid #2f5fe8", pointerEvents: "none"}}></div>
                  </>
                )}
                <div style={{display: "flex", alignItems: "center", justifyContent: "space-between"}}>
                  <span style={{display: "inline-flex", alignItems: "center", justifyContent: "center", width: "34px", height: "34px", borderRadius: "10px", background: "#2f5fe8", color: "#fff", fontFamily: "'JetBrains Mono',monospace", fontSize: "14px", fontWeight: "600"}}>
                    01
                  </span>
                  <span style={{fontFamily: "'JetBrains Mono',monospace", fontSize: "12px", color: "#2f5fe8", fontWeight: "600"}}>
                    10 preguntas
                  </span>
                </div>
                <h3 style={{margin: "16px 0 0", fontSize: "18px", fontWeight: "700", letterSpacing: "-.01em"}}>
                  Barrido inicial
                </h3>
                <p style={{margin: "8px 0 0", fontSize: "14px", lineHeight: "1.55", color: "#5a6478"}}>
                  Una pregunta por cada una de las 10 especializaciones. Sale con tus tres áreas de mayor afinidad.
                </p>
                <div style={{display: "flex", gap: "4px", marginTop: "16px"}}>
                  <span style={{flex: "1", height: "5px", borderRadius: "999px", background: "#2f5fe8"}}></span>
                  <span style={{flex: "1", height: "5px", borderRadius: "999px", background: "#e6eaf3"}}></span>
                  <span style={{flex: "1", height: "5px", borderRadius: "999px", background: "#e6eaf3"}}></span>
                </div>
              </div>
              <div className="rv-h3" style={{position: "relative", padding: "24px", borderRadius: "16px", border: "1px solid rgba(13,18,32,.09)", background: "#fff", cursor: "pointer", transition: "transform .18s ease,box-shadow .18s ease"}} onClick={verFase2}>
                {esFase2 && (
                  <>
                  <div style={{position: "absolute", inset: "-1px", borderRadius: "16px", border: "2px solid #2f5fe8", pointerEvents: "none"}}></div>
                  </>
                )}
                <div style={{display: "flex", alignItems: "center", justifyContent: "space-between"}}>
                  <span style={{display: "inline-flex", alignItems: "center", justifyContent: "center", width: "34px", height: "34px", borderRadius: "10px", background: "#0d1220", color: "#fff", fontFamily: "'JetBrains Mono',monospace", fontSize: "14px", fontWeight: "600"}}>
                    02
                  </span>
                  <span style={{fontFamily: "'JetBrains Mono',monospace", fontSize: "12px", color: "#0d1220", fontWeight: "600"}}>
                    15 preguntas
                  </span>
                </div>
                <h3 style={{margin: "16px 0 0", fontSize: "18px", fontWeight: "700", letterSpacing: "-.01em"}}>
                  Profundización
                </h3>
                <p style={{margin: "8px 0 0", fontSize: "14px", lineHeight: "1.55", color: "#5a6478"}}>
                  Cinco preguntas por cada área detectada. Solo se pregunta donde hubo señal, no sobre las diez ramas.
                </p>
                <div style={{display: "flex", gap: "4px", marginTop: "16px"}}>
                  <span style={{flex: "1", height: "5px", borderRadius: "999px", background: "#2f5fe8"}}></span>
                  <span style={{flex: "1", height: "5px", borderRadius: "999px", background: "#2f5fe8"}}></span>
                  <span style={{flex: "1", height: "5px", borderRadius: "999px", background: "#e6eaf3"}}></span>
                </div>
              </div>
              <div className="rv-h3" style={{position: "relative", padding: "24px", borderRadius: "16px", border: "1px solid rgba(13,18,32,.09)", background: "#fff", cursor: "pointer", transition: "transform .18s ease,box-shadow .18s ease"}} onClick={verFase3}>
                {esFase3 && (
                  <>
                  <div style={{position: "absolute", inset: "-1px", borderRadius: "16px", border: "2px solid #2f5fe8", pointerEvents: "none"}}></div>
                  </>
                )}
                <div style={{display: "flex", alignItems: "center", justifyContent: "space-between"}}>
                  <span style={{display: "inline-flex", alignItems: "center", justifyContent: "center", width: "34px", height: "34px", borderRadius: "10px", background: "#f2a93b", color: "#fff", fontFamily: "'JetBrains Mono',monospace", fontSize: "14px", fontWeight: "600"}}>
                    03
                  </span>
                  <span style={{fontFamily: "'JetBrains Mono',monospace", fontSize: "12px", color: "#8a5b12", fontWeight: "600"}}>
                    4 escenarios
                  </span>
                </div>
                <h3 style={{margin: "16px 0 0", fontSize: "18px", fontWeight: "700", letterSpacing: "-.01em"}}>
                  Estilo de trabajo
                </h3>
                <p style={{margin: "8px 0 0", fontSize: "14px", lineHeight: "1.55", color: "#5a6478"}}>
                  Situaciones reales de equipo que te clasifican como Analítico, Ejecutor, Colaborador o Perfeccionista.
                </p>
                <div style={{display: "flex", gap: "4px", marginTop: "16px"}}>
                  <span style={{flex: "1", height: "5px", borderRadius: "999px", background: "#2f5fe8"}}></span>
                  <span style={{flex: "1", height: "5px", borderRadius: "999px", background: "#2f5fe8"}}></span>
                  <span style={{flex: "1", height: "5px", borderRadius: "999px", background: "#f2a93b"}}></span>
                </div>
              </div>
            </div>
            <div style={{display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(300px,1fr))", gap: "clamp(20px,3vw,40px)", alignItems: "center", marginTop: "20px", padding: "clamp(22px,3vw,34px)", borderRadius: "20px", background: "#f5f7fd", border: "1px solid rgba(13,18,32,.06)"}}>
              <div>
                <div style={{display: "grid", gridTemplateColumns: "repeat(20,1fr)", gap: "6px", maxWidth: "420px"}}>
                  {dotsFase1.map((d, i) => (
                    <Fragment key={i}>
                      <span style={{aspectRatio: "1", borderRadius: "3px", background: "#2f5fe8"}}></span>
                    </Fragment>
                  ))}
                  {dotsFase2.map((d, i) => (
                    <Fragment key={i}>
                      <span style={{aspectRatio: "1", borderRadius: "3px", background: "#7ea1ff"}}></span>
                    </Fragment>
                  ))}
                  {dotsFase3.map((d, i) => (
                    <Fragment key={i}>
                      <span style={{aspectRatio: "1", borderRadius: "3px", background: "#f2a93b"}}></span>
                    </Fragment>
                  ))}
                  {dotsResto.map((d, i) => (
                    <Fragment key={i}>
                      <span style={{aspectRatio: "1", borderRadius: "3px", background: "#dfe4ee"}}></span>
                    </Fragment>
                  ))}
                </div>
                <div style={{display: "flex", flexWrap: "wrap", gap: "14px", marginTop: "16px", fontSize: "12px", color: "#5a6478", fontWeight: "600"}}>
                  <span style={{display: "flex", alignItems: "center", gap: "6px"}}>
                    <span style={{width: "9px", height: "9px", borderRadius: "2px", background: "#2f5fe8"}}></span>
                    Fase 1
                  </span>
                  <span style={{display: "flex", alignItems: "center", gap: "6px"}}>
                    <span style={{width: "9px", height: "9px", borderRadius: "2px", background: "#7ea1ff"}}></span>
                    Fase 2
                  </span>
                  <span style={{display: "flex", alignItems: "center", gap: "6px"}}>
                    <span style={{width: "9px", height: "9px", borderRadius: "2px", background: "#f2a93b"}}></span>
                    Fase 3
                  </span>
                  <span style={{display: "flex", alignItems: "center", gap: "6px"}}>
                    <span style={{width: "9px", height: "9px", borderRadius: "2px", background: "#dfe4ee"}}></span>
                    Nunca las ves
                  </span>
                </div>
              </div>
              <div>
                {esFase1 && (
                  <>
                  <div>
                    <p style={{margin: "0", fontSize: "clamp(16px,1.7vw,19px)", lineHeight: "1.55", fontWeight: "600", letterSpacing: "-.01em", textWrap: "pretty"}}>
                      “Te dan un problema sin instrucciones claras. ¿Lo desarmas en datos, lo prototipas, o lo hablas con el equipo primero?”
                    </p>
                    <p style={{margin: "14px 0 0", fontSize: "14px", lineHeight: "1.6", color: "#5a6478"}}>
                      Diez preguntas de calibración, una por rama. Al final la app se queda con tus tres áreas más fuertes y descarta las otras siete.
                    </p>
                  </div>
                  </>
                )}
                {esFase2 && (
                  <>
                  <div>
                    <p style={{margin: "0", fontSize: "clamp(16px,1.7vw,19px)", lineHeight: "1.55", fontWeight: "600", letterSpacing: "-.01em", textWrap: "pretty"}}>
                      “Un modelo predice bien en pruebas y mal en producción. ¿Qué revisas primero?”
                    </p>
                    <p style={{margin: "14px 0 0", fontSize: "14px", lineHeight: "1.6", color: "#5a6478"}}>
                      Cinco preguntas por cada área detectada. Aquí se separa el interés real de la curiosidad pasajera: son tareas concretas de esa rama, no gustos generales.
                    </p>
                  </div>
                  </>
                )}
                {esFase3 && (
                  <>
                  <div>
                    <p style={{margin: "0", fontSize: "clamp(16px,1.7vw,19px)", lineHeight: "1.55", fontWeight: "600", letterSpacing: "-.01em", textWrap: "pretty"}}>
                      “Faltan dos días para la entrega y el módulo de otro compañero no compila. ¿Qué haces?”
                    </p>
                    <p style={{margin: "14px 0 0", fontSize: "14px", lineHeight: "1.6", color: "#5a6478"}}>
                      Cuatro escenarios de equipo. Definen tu estilo de trabajo — Analítico, Ejecutor, Colaborador o Perfeccionista — y ajustan la recomendación final.
                    </p>
                    <div style={{display: "flex", flexWrap: "wrap", gap: "8px", marginTop: "16px"}}>
                      <span style={{padding: "6px 11px", borderRadius: "8px", background: "#fff", border: "1px solid rgba(13,18,32,.1)", fontSize: "12.5px", fontWeight: "600"}}>
                        Analítico
                      </span>
                      <span style={{padding: "6px 11px", borderRadius: "8px", background: "#fff", border: "1px solid rgba(13,18,32,.1)", fontSize: "12.5px", fontWeight: "600"}}>
                        Ejecutor
                      </span>
                      <span style={{padding: "6px 11px", borderRadius: "8px", background: "#fff", border: "1px solid rgba(13,18,32,.1)", fontSize: "12.5px", fontWeight: "600"}}>
                        Colaborador
                      </span>
                      <span style={{padding: "6px 11px", borderRadius: "8px", background: "#fff", border: "1px solid rgba(13,18,32,.1)", fontSize: "12.5px", fontWeight: "600"}}>
                        Perfeccionista
                      </span>
                    </div>
                  </div>
                  </>
                )}
                <p style={{margin: "18px 0 0", fontSize: "12.5px", color: "#8a93a6"}}>
                  Toca cada fase para ver un ejemplo de pregunta.
                </p>
              </div>
            </div>
            <div style={{marginTop: "34px", paddingTop: "24px", borderTop: "1px solid rgba(13,18,32,.1)"}}>
              <div style={{display: "flex", flexWrap: "wrap", alignItems: "baseline", justifyContent: "space-between", gap: "10px"}}>
                <h3 style={{margin: "0", fontSize: "17px", fontWeight: "700", letterSpacing: "-.01em"}}>
                  Las 10 ramas sobre las que decide
                </h3>
                <span style={{fontFamily: "'JetBrains Mono',monospace", fontSize: "11.5px", color: "#8a93a6"}}>
                  mapeadas a ocupaciones O*NET
                </span>
              </div>
              <div style={{display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(210px,1fr))", gap: "1px", marginTop: "18px", background: "rgba(13,18,32,.09)", border: "1px solid rgba(13,18,32,.09)", borderRadius: "14px", overflow: "hidden"}}>
                {ramas.map((r, i) => (
                  <Fragment key={i}>
                    <div className="rv-h4" style={{display: "flex", alignItems: "baseline", gap: "11px", padding: "15px 16px", background: "#fff", cursor: "default", transition: "background .16s ease,color .16s ease"}}>
                      <span style={{fontFamily: "'JetBrains Mono',monospace", fontSize: "11.5px", fontWeight: "600", color: "#2f5fe8"}}>
                        {r.id}
                      </span>
                      <span style={{fontSize: "13.5px", fontWeight: "600", lineHeight: "1.35"}}>
                        {r.n}
                      </span>
                    </div>
                  </Fragment>
                ))}
              </div>
            </div>
          </div>
        </section>
        <section id="revo-ofrece" style={{padding: "clamp(34px,4.4vw,64px) clamp(18px,5vw,64px)", background: "#f5f7fd", borderTop: "1px solid rgba(13,18,32,.06)", borderBottom: "1px solid rgba(13,18,32,.06)", scrollMarginTop: "20px"}}>
          <div style={{maxWidth: "1180px", margin: "0 auto"}}>
            <div style={{display: "flex", alignItems: "center", gap: "14px", marginBottom: "clamp(24px,3.4vw,44px)"}}>
              <span style={{flex: "1", height: "1px", background: "linear-gradient(to right,rgba(13,18,32,0),rgba(13,18,32,.14))"}}></span>
              <span style={{display: "flex", alignItems: "center", gap: "5px"}}>
                <span style={{width: "5px", height: "5px", borderRadius: "999px", background: "#c8d6fb"}}></span>
                <span style={{width: "7px", height: "7px", borderRadius: "999px", background: "#2f5fe8"}}></span>
                <span style={{width: "5px", height: "5px", borderRadius: "999px", background: "#c8d6fb"}}></span>
              </span>
              <span style={{flex: "1", height: "1px", background: "linear-gradient(to left,rgba(13,18,32,0),rgba(13,18,32,.14))"}}></span>
            </div>
            <div style={{display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(290px,1fr))", gap: "clamp(20px,4vw,56px)", alignItems: "center"}}>
              <div style={{position: "relative", display: "flex", justifyContent: "center", alignItems: "center"}}>
                <div style={{position: "absolute", width: "min(420px,100%)", aspectRatio: "1.25", borderRadius: "28px", background: "radial-gradient(closest-side,#e2eaff 0%,#eef2ff 66%,rgba(238,242,255,0) 100%)"}}></div>
                <img src={personaCelularImg} alt="Ilustración: estudiante resolviendo el test" style={{position: "relative", width: "min(460px,100%)", aspectRatio: "3/2", height: "auto", mixBlendMode: "multiply", maskImage: "radial-gradient(115% 105% at 50% 48%, #000 52%, rgba(0,0,0,.5) 72%, transparent 88%)", WebkitMaskImage: "radial-gradient(115% 105% at 50% 48%, #000 52%, rgba(0,0,0,.5) 72%, transparent 88%)", display: "block", objectFit: "contain"}} />
                <div style={{position: "absolute", width: "min(460px,100%)", aspectRatio: "3/2", pointerEvents: "none", background: "linear-gradient(to right,#f5f7fd 0%,rgba(245,247,253,0) 16%),linear-gradient(to left,#f5f7fd 0%,rgba(245,247,253,0) 16%),linear-gradient(to bottom,#f5f7fd 0%,rgba(245,247,253,0) 14%),linear-gradient(to top,#f5f7fd 0%,rgba(245,247,253,0) 14%)"}}></div>
              </div>
              <div>
                <h2 style={{margin: "0", fontSize: "clamp(26px,3.6vw,40px)", lineHeight: "1.1", letterSpacing: "-.025em", fontWeight: "800", textWrap: "balance"}}>
                  El resultado no es una etiqueta. Es qué hacer el lunes.
                </h2>
                <p style={{margin: "16px 0 0", maxWidth: "520px", fontSize: "15.5px", lineHeight: "1.6", color: "#5a6478", textWrap: "pretty"}}>
                  Terminas el test en el celular, entre clases, y sales con seis cosas concretas: tu comparativa, tu plan, cursos, empleos, tu historial y —si eres docente— la foto completa del curso.
                </p>
                <div style={{display: "flex", flexWrap: "wrap", gap: "8px 20px", marginTop: "20px", fontSize: "13px", fontWeight: "600", color: "#5a6478"}}>
                  <span style={{display: "flex", alignItems: "center", gap: "7px"}}>
                    <span style={{width: "7px", height: "7px", borderRadius: "999px", background: "#2f5fe8"}}></span>
                    Funciona en el celular
                  </span>
                  <span style={{display: "flex", alignItems: "center", gap: "7px"}}>
                    <span style={{width: "7px", height: "7px", borderRadius: "999px", background: "#2f5fe8"}}></span>
                    Repetible cada semestre
                  </span>
                </div>
              </div>
            </div>
            <div className="rv-grid-3" style={{display: "grid", gap: "16px", marginTop: "28px"}}>
              <div className="rv-h3" style={{padding: "22px", borderRadius: "16px", background: "#fff", border: "1px solid rgba(13,18,32,.08)", transition: "transform .18s ease,box-shadow .18s ease"}}>
                <div style={{display: "flex", alignItems: "flex-end", gap: "4px", height: "38px"}}>
                  <span style={{width: "9px", height: "16px", borderRadius: "3px", background: "#c8d6fb"}}></span>
                  <span style={{width: "9px", height: "30px", borderRadius: "3px", background: "#2f5fe8"}}></span>
                  <span style={{width: "9px", height: "22px", borderRadius: "3px", background: "#9db8ff"}}></span>
                </div>
                <h3 style={{margin: "16px 0 0", fontSize: "16.5px", fontWeight: "700"}}>
                  Comparativa visual
                </h3>
                <p style={{margin: "7px 0 0", fontSize: "14px", lineHeight: "1.55", color: "#5a6478"}}>
                  Gráficos que enfrentan tus tres opciones más probables, con el porcentaje de confianza de cada una.
                </p>
              </div>
              <div className="rv-h3" style={{padding: "22px", borderRadius: "16px", background: "#fff", border: "1px solid rgba(13,18,32,.08)", transition: "transform .18s ease,box-shadow .18s ease"}}>
                <div style={{display: "flex", alignItems: "center", gap: "6px", height: "38px"}}>
                  <span style={{width: "11px", height: "11px", borderRadius: "999px", background: "#2f5fe8"}}></span>
                  <span style={{flex: "none", width: "14px", height: "2px", background: "#dfe4ee"}}></span>
                  <span style={{width: "11px", height: "11px", borderRadius: "999px", background: "#9db8ff"}}></span>
                  <span style={{flex: "none", width: "14px", height: "2px", background: "#dfe4ee"}}></span>
                  <span style={{width: "11px", height: "11px", borderRadius: "999px", background: "#dfe4ee"}}></span>
                </div>
                <h3 style={{margin: "16px 0 0", fontSize: "16.5px", fontWeight: "700"}}>
                  Plan de acción
                </h3>
                <p style={{margin: "7px 0 0", fontSize: "14px", lineHeight: "1.55", color: "#5a6478"}}>
                  Pasos concretos para esta semana, este mes, en tres meses y al graduarte. Nada de “sigue aprendiendo”.
                </p>
              </div>
              <div className="rv-h3" style={{padding: "22px", borderRadius: "16px", background: "#fff", border: "1px solid rgba(13,18,32,.08)", transition: "transform .18s ease,box-shadow .18s ease"}}>
                <div style={{display: "flex", flexDirection: "column", gap: "5px", height: "38px", justifyContent: "center"}}>
                  <span style={{width: "44px", height: "7px", borderRadius: "999px", background: "#2f5fe8"}}></span>
                  <span style={{width: "64px", height: "7px", borderRadius: "999px", background: "#dfe4ee"}}></span>
                  <span style={{width: "52px", height: "7px", borderRadius: "999px", background: "#dfe4ee"}}></span>
                </div>
                <h3 style={{margin: "16px 0 0", fontSize: "16.5px", fontWeight: "700"}}>
                  Cursos según tu perfil
                </h3>
                <p style={{margin: "7px 0 0", fontSize: "14px", lineHeight: "1.55", color: "#5a6478"}}>
                  Rutas de estudio filtradas por la rama recomendada y por tu estilo de trabajo, ordenadas por dificultad.
                </p>
              </div>
              <div className="rv-h3" style={{padding: "22px", borderRadius: "16px", background: "#fff", border: "1px solid rgba(13,18,32,.08)", transition: "transform .18s ease,box-shadow .18s ease"}}>
                <div style={{display: "grid", gridTemplateColumns: "repeat(2,14px)", gap: "5px", height: "38px", alignContent: "center"}}>
                  <span style={{height: "14px", borderRadius: "4px", background: "#2f5fe8"}}></span>
                  <span style={{height: "14px", borderRadius: "4px", background: "#c8d6fb"}}></span>
                  <span style={{height: "14px", borderRadius: "4px", background: "#c8d6fb"}}></span>
                  <span style={{height: "14px", borderRadius: "4px", background: "#9db8ff"}}></span>
                </div>
                <h3 style={{margin: "16px 0 0", fontSize: "16.5px", fontWeight: "700"}}>
                  Bolsa de empleos
                </h3>
                <p style={{margin: "7px 0 0", fontSize: "14px", lineHeight: "1.55", color: "#5a6478"}}>
                  Vacantes y prácticas relacionadas con tu rama, para ver a qué se parece el trabajo real antes de comprometerte.
                </p>
              </div>
              <div className="rv-h3" style={{padding: "22px", borderRadius: "16px", background: "#fff", border: "1px solid rgba(13,18,32,.08)", transition: "transform .18s ease,box-shadow .18s ease"}}>
                <div style={{display: "flex", alignItems: "flex-end", gap: "5px", height: "38px"}}>
                  <span style={{width: "8px", height: "10px", borderRadius: "2px", background: "#dfe4ee"}}></span>
                  <span style={{width: "8px", height: "17px", borderRadius: "2px", background: "#c8d6fb"}}></span>
                  <span style={{width: "8px", height: "24px", borderRadius: "2px", background: "#9db8ff"}}></span>
                  <span style={{width: "8px", height: "34px", borderRadius: "2px", background: "#2f5fe8"}}></span>
                </div>
                <h3 style={{margin: "16px 0 0", fontSize: "16.5px", fontWeight: "700"}}>
                  Historial personal
                </h3>
                <p style={{margin: "7px 0 0", fontSize: "14px", lineHeight: "1.55", color: "#5a6478"}}>
                  Repite el test cada semestre y compara: tu perfil cambia con lo que estudias, y aquí lo ves.
                </p>
              </div>
              {panelDocente && (
                <>
                <div className="rv-h5" style={{padding: "22px", borderRadius: "16px", background: "#0d1220", border: "1px solid #0d1220", color: "#fff", transition: "transform .18s ease,box-shadow .18s ease"}}>
                  <div style={{height: "38px", display: "flex", alignItems: "center"}}>
                    <span style={{width: "38px", height: "38px", borderRadius: "999px", background: "conic-gradient(#5b86ff 0 38%,#f2a93b 0 62%,#8fb0ff 0 80%,#33405e 0 100%)"}}></span>
                  </div>
                  <h3 style={{margin: "16px 0 0", fontSize: "16.5px", fontWeight: "700"}}>
                    Panel para docentes
                  </h3>
                  <p style={{margin: "7px 0 0", fontSize: "14px", lineHeight: "1.55", color: "#9aa4b8"}}>
                    Distribución de perfiles del alumnado por curso y por semestre, para orientar electivas y proyectos.
                  </p>
                </div>
                </>
              )}
            </div>
            <div style={{marginTop: "16px", padding: "clamp(22px,3vw,34px)", borderRadius: "20px", background: "#fff", border: "1px solid rgba(13,18,32,.08)"}}>
              <div style={{display: "flex", flexWrap: "wrap", alignItems: "baseline", justifyContent: "space-between", gap: "12px"}}>
                <h3 style={{margin: "0", fontSize: "19px", fontWeight: "700", letterSpacing: "-.01em"}}>
                  Tu plan de acción, si sale Data Science e IA
                </h3>
                <span style={{fontFamily: "'JetBrains Mono',monospace", fontSize: "12px", color: "#8a93a6"}}>
                  ejemplo real de salida
                </span>
              </div>
              <div style={{display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(215px,1fr))", gap: "14px", marginTop: "22px"}}>
                <div style={{paddingTop: "18px", borderTop: "3px solid #2f5fe8"}}>
                  <div style={{fontFamily: "'JetBrains Mono',monospace", fontSize: "11px", letterSpacing: ".1em", color: "#2f5fe8", fontWeight: "600"}}>
                    ESTA SEMANA
                  </div>
                  <p style={{margin: "9px 0 0", fontSize: "14px", lineHeight: "1.55", color: "#3b465c"}}>
                    Instala el entorno y reproduce un notebook de regresión con datos de tu universidad.
                  </p>
                </div>
                <div style={{paddingTop: "18px", borderTop: "3px solid #7ea1ff"}}>
                  <div style={{fontFamily: "'JetBrains Mono',monospace", fontSize: "11px", letterSpacing: ".1em", color: "#2f5fe8", fontWeight: "600"}}>
                    ESTE MES
                  </div>
                  <p style={{margin: "9px 0 0", fontSize: "14px", lineHeight: "1.55", color: "#3b465c"}}>
                    Termina el curso base de estadística aplicada y sube tu primer proyecto a GitHub.
                  </p>
                </div>
                <div style={{paddingTop: "18px", borderTop: "3px solid #c8d6fb"}}>
                  <div style={{fontFamily: "'JetBrains Mono',monospace", fontSize: "11px", letterSpacing: ".1em", color: "#2f5fe8", fontWeight: "600"}}>
                    EN 3 MESES
                  </div>
                  <p style={{margin: "9px 0 0", fontSize: "14px", lineHeight: "1.55", color: "#3b465c"}}>
                    Postula a una práctica de datos y elige la electiva de aprendizaje automático.
                  </p>
                </div>
                <div style={{paddingTop: "18px", borderTop: "3px solid #f2a93b"}}>
                  <div style={{fontFamily: "'JetBrains Mono',monospace", fontSize: "11px", letterSpacing: ".1em", color: "#8a5b12", fontWeight: "600"}}>
                    AL GRADUARTE
                  </div>
                  <p style={{margin: "9px 0 0", fontSize: "14px", lineHeight: "1.55", color: "#3b465c"}}>
                    Portafolio con tres proyectos y tesis alineada a un problema de datos con datos reales.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>
        <section style={{padding: "clamp(48px,6.5vw,96px) clamp(18px,5vw,64px)", background: "#0d1220", color: "#fff"}}>
          <div style={{maxWidth: "1180px", margin: "0 auto"}}>
            <div style={{display: "flex", alignItems: "center", gap: "14px", marginBottom: "clamp(24px,3.4vw,44px)"}}>
              <span style={{flex: "1", height: "1px", background: "linear-gradient(to right,rgba(255,255,255,0),rgba(255,255,255,.18))"}}></span>
              <span style={{display: "flex", alignItems: "center", gap: "5px"}}>
                <span style={{width: "5px", height: "5px", borderRadius: "999px", background: "rgba(143,176,255,.5)"}}></span>
                <span style={{width: "7px", height: "7px", borderRadius: "999px", background: "#8fb0ff"}}></span>
                <span style={{width: "5px", height: "5px", borderRadius: "999px", background: "rgba(143,176,255,.5)"}}></span>
              </span>
              <span style={{flex: "1", height: "1px", background: "linear-gradient(to left,rgba(255,255,255,0),rgba(255,255,255,.18))"}}></span>
            </div>
            <div style={{display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(300px,1fr))", gap: "clamp(24px,3.5vw,48px)", alignItems: "stretch"}}>
              <div style={{display: "flex", flexDirection: "column", gap: "16px"}}>
                <div>
                  <h2 style={{margin: "0", fontSize: "clamp(26px,3.4vw,38px)", lineHeight: "1.1", letterSpacing: "-.025em", fontWeight: "800", textWrap: "balance"}}>
                    Los tests vocacionales responden “qué carrera estudio”. Esa pregunta ya la contestaste.
                  </h2>
                </div>
                <div style={{padding: "24px", borderRadius: "18px", background: "rgba(255,255,255,.05)", border: "1px solid rgba(255,255,255,.1)"}}>
                  <div style={{fontSize: "12px", fontWeight: "700", letterSpacing: ".08em", textTransform: "uppercase", color: "#8a93a6"}}>
                    Test vocacional común
                  </div>
                  <p style={{margin: "12px 0 0", fontSize: "clamp(17px,1.8vw,21px)", lineHeight: "1.35", fontWeight: "700", color: "#9aa4b8"}}>
                    “¿Qué carrera debería estudiar?”
                  </p>
                  <p style={{margin: "12px 0 0", fontSize: "14px", lineHeight: "1.6", color: "#8a93a6"}}>
                    Te sirve una vez, antes de entrar. Después ya no te dice nada.
                  </p>
                </div>
                <div style={{padding: "24px", borderRadius: "18px", background: "linear-gradient(160deg,#2f5fe8,#1e46bd)", border: "1px solid rgba(255,255,255,.14)", boxShadow: "0 18px 40px rgba(47,95,232,.28)"}}>
                  <div style={{fontSize: "12px", fontWeight: "700", letterSpacing: ".08em", textTransform: "uppercase", color: "#c9d9ff"}}>
                    REVO
                  </div>
                  <p style={{margin: "12px 0 0", fontSize: "clamp(17px,1.8vw,21px)", lineHeight: "1.35", fontWeight: "700"}}>
                    “Ya estoy aquí. ¿Hacia dónde me especializo?”
                  </p>
                  <p style={{margin: "12px 0 0", fontSize: "14px", lineHeight: "1.6", color: "#dbe5ff"}}>
                    Trabaja dentro de Ingeniería de Sistemas, sobre las 10 ramas donde de verdad vas a terminar.
                  </p>
                </div>
              </div>
              <div style={{position: "relative", display: "flex", alignItems: "center", justifyContent: "center", minHeight: "clamp(340px,40vw,520px)"}}>
                <div style={{position: "absolute", width: "min(440px,96%)", aspectRatio: "1", borderRadius: "999px", background: "radial-gradient(closest-side,rgba(47,95,232,.34) 0%,rgba(47,95,232,.12) 55%,rgba(47,95,232,0) 100%)", filter: "blur(6px)"}}></div>
                <img src={personaDiferenciaImg} alt="PNG sin fondo: estudiante 3D dudando entre dos caminos" style={{position: "relative", width: "min(400px,94%)", aspectRatio: "1", height: "auto", filter: "saturate(.92)", maskImage: "radial-gradient(circle at 50% 46%, #000 38%, rgba(0,0,0,.55) 58%, transparent 74%)", WebkitMaskImage: "radial-gradient(circle at 50% 46%, #000 38%, rgba(0,0,0,.55) 58%, transparent 74%)", display: "block", objectFit: "contain"}} />
                <div style={{position: "absolute", width: "min(400px,94%)", aspectRatio: "1", borderRadius: "999px", pointerEvents: "none", background: "radial-gradient(circle at 50% 46%, rgba(13,18,32,0) 34%, rgba(13,18,32,.55) 62%, #0d1220 78%)"}}></div>
                <div style={{position: "absolute", left: "0", right: "0", bottom: "2%", display: "flex", justifyContent: "center"}}>
                  <a className="rv-h1" href="#revo-como" style={{display: "inline-flex", alignItems: "center", gap: "10px", padding: "15px 24px", borderRadius: "12px", background: "#2f5fe8", color: "#fff", fontSize: "15px", fontWeight: "700", boxShadow: "0 12px 28px rgba(47,95,232,.4)"}}>
                    Realizar el test
                    <span style={{display: "inline-flex", alignItems: "center", justifyContent: "center", width: "22px", height: "22px", borderRadius: "999px", background: "rgba(255,255,255,.2)", fontSize: "13px"}}>
                      →
                    </span>
                  </a>
                </div>
              </div>
            </div>
            <div style={{display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(250px,1fr))", gap: "16px", marginTop: "16px"}}>
              <div style={{padding: "24px", borderRadius: "16px", border: "1px solid rgba(255,255,255,.1)"}}>
                <div style={{fontFamily: "'JetBrains Mono',monospace", fontSize: "26px", fontWeight: "600", color: "#8fb0ff"}}>
                  29/100
                </div>
                <h3 style={{margin: "12px 0 0", fontSize: "16.5px", fontWeight: "700"}}>
                  Se adapta, no interroga
                </h3>
                <p style={{margin: "7px 0 0", fontSize: "14px", lineHeight: "1.55", color: "#9aa4b8"}}>
                  Las preguntas dependen de tus respuestas anteriores. Dos estudiantes no ven el mismo test.
                </p>
              </div>
              <div style={{padding: "24px", borderRadius: "16px", border: "1px solid rgba(255,255,255,.1)"}}>
                <div style={{fontFamily: "'JetBrains Mono',monospace", fontSize: "26px", fontWeight: "600", color: "#8fb0ff"}}>
                  O*NET
                </div>
                <h3 style={{margin: "12px 0 0", fontSize: "16.5px", fontWeight: "700"}}>
                  Ocupaciones reales
                </h3>
                <p style={{margin: "7px 0 0", fontSize: "14px", lineHeight: "1.55", color: "#9aa4b8"}}>
                  Las 10 ramas están mapeadas al catálogo ocupacional del Departamento de Trabajo de EE. UU., no inventadas por nosotros.
                </p>
              </div>
              <div style={{padding: "24px", borderRadius: "16px", border: "1px solid rgba(255,255,255,.1)"}}>
                <div style={{fontFamily: "'JetBrains Mono',monospace", fontSize: "26px", fontWeight: "600", color: "#f2a93b"}}>
                  82%
                </div>
                <h3 style={{margin: "12px 0 0", fontSize: "16.5px", fontWeight: "700"}}>
                  Dice cuánta certeza tiene
                </h3>
                <p style={{margin: "7px 0 0", fontSize: "14px", lineHeight: "1.55", color: "#9aa4b8"}}>
                  Cada recomendación viene con su nivel de confianza, y si tu perfil es ambiguo el sistema lo admite.
                </p>
              </div>
            </div>
          </div>
        </section>
        <section style={{padding: "clamp(48px,6vw,88px) clamp(18px,5vw,64px)", background: "linear-gradient(180deg,#ffffff,#eef3ff)"}}>
          <div style={{maxWidth: "900px", margin: "0 auto", textAlign: "center"}}>
            {ilustraciones && (
              <>
              <div style={{display: "flex", justifyContent: "center", alignItems: "center", marginBottom: "22px"}}>
                <span style={{position: "relative", width: "48px", height: "48px", borderRadius: "999px", background: "#dbe5ff", border: "3px solid #fff", overflow: "hidden", boxShadow: "0 2px 6px rgba(13,18,32,.1)"}}>
                  <span style={{position: "absolute", left: "50%", top: "9px", transform: "translateX(-50%)", width: "16px", height: "16px", borderRadius: "999px", background: "#2f5fe8"}}></span>
                  <span style={{position: "absolute", left: "50%", bottom: "-10px", transform: "translateX(-50%)", width: "34px", height: "24px", borderRadius: "999px 999px 0 0", background: "#2f5fe8"}}></span>
                </span>
                <span style={{position: "relative", width: "48px", height: "48px", borderRadius: "999px", background: "#fdf3e2", border: "3px solid #fff", marginLeft: "-13px", overflow: "hidden", boxShadow: "0 2px 6px rgba(13,18,32,.1)"}}>
                  <span style={{position: "absolute", left: "50%", top: "9px", transform: "translateX(-50%)", width: "16px", height: "16px", borderRadius: "999px", background: "#f2a93b"}}></span>
                  <span style={{position: "absolute", left: "50%", bottom: "-10px", transform: "translateX(-50%)", width: "34px", height: "24px", borderRadius: "999px 999px 0 0", background: "#f2a93b"}}></span>
                </span>
                <span style={{position: "relative", width: "48px", height: "48px", borderRadius: "999px", background: "#e2e6ef", border: "3px solid #fff", marginLeft: "-13px", overflow: "hidden", boxShadow: "0 2px 6px rgba(13,18,32,.1)"}}>
                  <span style={{position: "absolute", left: "50%", top: "9px", transform: "translateX(-50%)", width: "16px", height: "16px", borderRadius: "999px", background: "#0d1220"}}></span>
                  <span style={{position: "absolute", left: "50%", bottom: "-10px", transform: "translateX(-50%)", width: "34px", height: "24px", borderRadius: "999px 999px 0 0", background: "#0d1220"}}></span>
                </span>
                <span style={{marginLeft: "10px", fontSize: "13px", fontWeight: "600", color: "#5a6478"}}>
                  +340 estudiantes ya lo hicieron
                </span>
              </div>
              </>
            )}
            <h2 style={{margin: "0", fontSize: "clamp(26px,3.6vw,40px)", lineHeight: "1.1", letterSpacing: "-.025em", fontWeight: "800", textWrap: "balance"}}>
              Ocho minutos ahora, o dos años averiguándolo a golpes.
            </h2>
            <p style={{margin: "16px auto 0", maxWidth: "520px", fontSize: "16px", lineHeight: "1.6", color: "#5a6478"}}>
              Haz el test, mira tu comparativa y quédate con el plan. Puedes repetirlo cada semestre.
            </p>
            <div style={{display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "12px", marginTop: "26px"}}>
              <a className="rv-h6" href="#revo-como" style={{display: "inline-flex", alignItems: "center", gap: "10px", padding: "16px 26px", borderRadius: "12px", background: "#2f5fe8", color: "#fff", fontSize: "15.5px", fontWeight: "700", boxShadow: "0 10px 24px rgba(47,95,232,.3)"}}>
                Empezar el test
                <span style={{fontSize: "14px"}}>
                  →
                </span>
              </a>
              <a className="rv-h2" href="#revo-ofrece" style={{display: "inline-flex", alignItems: "center", padding: "16px 26px", borderRadius: "12px", background: "#fff", border: "1px solid rgba(13,18,32,.12)", color: "#0d1220", fontSize: "15.5px", fontWeight: "600"}}>
                Soy docente
              </a>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
