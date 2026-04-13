import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { surveyApi, mlApi } from '../services/api'
import './Questionnaire.css'

const CATEGORY_META = {
  academic:    { label: 'Académico',    icon: '📚', color: '#6C63FF' },
  skills:      { label: 'Habilidades',  icon: '🛠️', color: '#00D4FF' },
  interests:   { label: 'Intereses',    icon: '❤️',  color: '#FF6B9D' },
  personality: { label: 'Personalidad', icon: '🧠', color: '#10B981' },
}

// Banco de preguntas psicométricas adaptativas por especialización
// 4 preguntas distintas para cada una de las 10 especializaciones
const PHASE3_BANK = {
  'Desarrollo de Software': [
    {
      id: 'p3_sw_1',
      question: 'Cuando tu código no funciona a la primera, ¿cuál es tu reacción instintiva?',
      options: [
        { key: 'A', text: 'Leo el stack trace línea a línea hasta aislar exactamente el error' },
        { key: 'B', text: 'Pruebo soluciones rápidas en orden hasta que una funcione' },
        { key: 'C', text: 'Le explico el problema a un compañero para buscar perspectiva' },
        { key: 'D', text: 'Refactorizo el bloque completo: prefiero limpiar antes de parchar' },
      ]
    },
    {
      id: 'p3_sw_2',
      question: 'Tienes que elegir entre lanzar en 2 días con deuda técnica o en 2 semanas limpio. ¿Qué eliges?',
      options: [
        { key: 'A', text: 'Lanzo en 2 semanas, la arquitectura bien hecha vale la espera' },
        { key: 'B', text: 'Lanzo en 2 días y creo un ticket de deuda técnica para después' },
        { key: 'C', text: 'Negocio con el equipo para encontrar una ruta media entre las dos' },
        { key: 'D', text: 'Solo lanzo si puedo garantizar al menos el 80% de calidad del código' },
      ]
    },
    {
      id: 'p3_sw_3',
      question: '¿Cómo describes tu relación con aprender nuevos lenguajes o frameworks?',
      options: [
        { key: 'A', text: 'Me emociona: lo estudio desde la documentación oficial primero' },
        { key: 'B', text: 'Prefiero aprenderlo construyendo algo real desde el día 1' },
        { key: 'C', text: 'Aprendo bien en pair programming o un bootcamp grupal' },
        { key: 'D', text: 'Lo aprendo pero siempre busco dominarlo a fondo antes de usarlo en producción' },
      ]
    },
    {
      id: 'p3_sw_4',
      question: 'En un equipo de desarrollo, ¿cuál es tu rol natural?',
      options: [
        { key: 'A', text: 'Arquitecto: diseño la estructura del sistema antes de codificar' },
        { key: 'B', text: 'Ejecutor: soy el primero en tener una versión funcional en manos del cliente' },
        { key: 'C', text: 'Integrador: conecto el trabajo de todos y facilito las revisiones de código' },
        { key: 'D', text: 'Revisor: nada pasa a producción sin que yo lo haya validado' },
      ]
    },
  ],
  'Data Science & IA': [
    {
      id: 'p3_ds_1',
      question: 'Te presentan un dataset con 50 columnas y datos sucios. ¿Cuál es tu primer paso?',
      options: [
        { key: 'A', text: 'Construyo un mapa estadístico completo (nulos, distribuciones, correlaciones) antes de tocar nada' },
        { key: 'B', text: 'Limpio los datos básicos y entreno un modelo rápido para ver si hay potencial' },
        { key: 'C', text: 'Entrevisto al dueño del negocio para entender qué columnas importan realmente' },
        { key: 'D', text: 'Documento cada decisión del proceso de limpieza para asegurar reproducibilidad' },
      ]
    },
    {
      id: 'p3_ds_2',
      question: 'Tu modelo tiene 94% de accuracy pero el equipo de negocio no confía en él. ¿Qué haces?',
      options: [
        { key: 'A', text: 'Creo visualizaciones de SHAP values para mostrar exactamente qué impulsa cada predicción' },
        { key: 'B', text: 'Hago una demo en vivo con datos reales para que vean el modelo en acción' },
        { key: 'C', text: 'Organizo una reunión de revisión donde el equipo puede hacerle preguntas al modelo' },
        { key: 'D', text: 'Añado más métricas: Precision, Recall y F1 por segmento hasta que los números hablen solos' },
      ]
    },
    {
      id: 'p3_ds_3',
      question: '¿Cuál de estas tareas te parece más estimulante dentro de la ciencia de datos?',
      options: [
        { key: 'A', text: 'Diseñar el pipeline de datos y la arquitectura del MLOps' },
        { key: 'B', text: 'Encontrar el insight que nadie había visto oculto en los datos' },
        { key: 'C', text: 'Presentar los resultados de forma que todos en la empresa los entiendan' },
        { key: 'D', text: 'Optimizar el hiperparámetro final que sube el modelo de 94% a 97%' },
      ]
    },
    {
      id: 'p3_ds_4',
      question: 'Ante la incertidumbre en los datos, ¿cómo actúas?',
      options: [
        { key: 'A', text: 'Modelo la incertidumbre explícitamente con intervalos de confianza bayesianos' },
        { key: 'B', text: 'Acepto que la perfecta información no existe y entrego el mejor modelo posible hoy' },
        { key: 'C', text: 'Consulto a expertos del dominio para aterrizar los supuestos del modelo' },
        { key: 'D', text: 'No libero el modelo hasta tener al menos 3 validaciones cruzadas estables' },
      ]
    },
  ],
  'Infraestructura & Cloud': [
    {
      id: 'p3_infra_1',
      question: 'Un servidor de producción sube al 95% de CPU. ¿Cuál es tu primera acción?',
      options: [
        { key: 'A', text: 'Reviso los logs, identifico el proceso causante y escalo de forma planificada' },
        { key: 'B', text: 'Activo auto-scaling inmediatamente y luego investigo la causa raíz' },
        { key: 'C', text: 'Notifico al equipo de desarrollo porque probablemente el código tiene una fuga' },
        { key: 'D', text: 'Ejecuto un análisis forense antes de tocar cualquier cosa para evitar empeorar el estado' },
      ]
    },
    {
      id: 'p3_infra_2',
      question: '¿Cuál de estas frases describe mejor tu filosofía de infraestructura?',
      options: [
        { key: 'A', text: '"Infrastructure as Code: todo debe ser reproducible desde un repositorio Git"' },
        { key: 'B', text: '"Entrega rápida: si funciona en staging, va a producción hoy"' },
        { key: 'C', text: '"Colaboración: Ops y Dev deben trabajar como un solo equipo"' },
        { key: 'D', text: '"Zero-downtime: ningún despliegue justifica un minuto de indisponibilidad"' },
      ]
    },
    {
      id: 'p3_infra_3',
      question: '¿Qué tipo de proyecto Cloud te despertaría más curiosidad?',
      options: [
        { key: 'A', text: 'Diseñar una arquitectura multi-región altamente disponible desde cero' },
        { key: 'B', text: 'Migrar una app monolítica a microservicios en Kubernetes en tiempo récord' },
        { key: 'C', text: 'Implementar una estrategia de FinOps para reducir el costo de la nube un 40%' },
        { key: 'D', text: 'Construir el pipeline de CI/CD perfecto con gates de seguridad en cada paso' },
      ]
    },
    {
      id: 'p3_infra_4',
      question: 'Ante un cambio urgente en producción fuera de la ventana de mantenimiento, ¿qué haces?',
      options: [
        { key: 'A', text: 'Sigo el runbook y solo ejecuto si tengo el Change Request aprobado' },
        { key: 'B', text: 'Evalúo el impacto en 5 minutos y ejecuto si el riesgo es menor al del problema actual' },
        { key: 'C', text: 'Convoco al equipo de guardia antes de tocar nada, no tomo decisiones solo' },
        { key: 'D', text: 'Preparo un plan de rollback antes de cualquier intervención' },
      ]
    },
  ],
  'Ciberseguridad': [
    {
      id: 'p3_sec_1',
      question: 'Encuentras una vulnerabilidad crítica en el sistema de un cliente. ¿Qué haces primero?',
      options: [
        { key: 'A', text: 'Documento exhaustivamente el vector de ataque antes de reportarlo' },
        { key: 'B', text: 'Reporto inmediatamente aunque no tenga todos los detalles: el tiempo cuenta' },
        { key: 'C', text: 'Coordino con el equipo de desarrollo para una divulgación responsable coordinada' },
        { key: 'D', text: 'Verifico el alcance total del impacto antes de escalar, para no generar pánico innecesario' },
      ]
    },
    {
      id: 'p3_sec_2',
      question: '¿Cuál de estos retos de ciberseguridad te atrae más?',
      options: [
        { key: 'A', text: 'Diseñar la arquitectura de seguridad de sistemas críticos bancarios o de salud' },
        { key: 'B', text: 'Hackear sistemas en entornos de Bug Bounty o Red Team con total libertad' },
        { key: 'C', text: 'Concientizar y entrenar al equipo humano: el eslabón más débil siempre es la persona' },
        { key: 'D', text: 'Hacer forense digital y análisis de malware en laboratorio controlado' },
      ]
    },
    {
      id: 'p3_sec_3',
      question: '¿Cómo describes tu relación con las reglas y la normativa de seguridad?',
      options: [
        { key: 'A', text: 'Las normas existen por razones: las sigo y las mejoro con nuevos controles' },
        { key: 'B', text: 'Las normas son un mínimo, yo pienso como el atacante para ir más allá' },
        { key: 'C', text: 'Las normas deben ser entendidas por todos: mi rol es traducirlas al equipo' },
        { key: 'D', text: 'El cumplimiento al 100% no es negociable, el riesgo cero es el objetivo' },
      ]
    },
    {
      id: 'p3_sec_4',
      question: 'Tu empresa tiene un presupuesto limitado de seguridad. ¿En qué inviertes primero?',
      options: [
        { key: 'A', text: 'En una auditoría de arquitectura: arreglar los cimientos vale más que parches' },
        { key: 'B', text: 'En un pentest externo: necesito saber cómo me verían desde afuera hoy' },
        { key: 'C', text: 'En entrenamiento de phishing al equipo: el 85% de los ataques entran por personas' },
        { key: 'D', text: 'En un SIEM robusto: sin visibilidad no puedo defender nada' },
      ]
    },
  ],
  'Soporte Técnico & IT Ops': [
    {
      id: 'p3_sup_1',
      question: 'Un usuario reporta que "internet no funciona". ¿Cómo abordas el diagnóstico?',
      options: [
        { key: 'A', text: 'Sigo un árbol de diagnóstico sistemático: capa física, DNS, gateway, luego aplicación' },
        { key: 'B', text: 'Reinicio los más comunes primero (router, adaptador) y escalo si no funciona' },
        { key: 'C', text: 'Pregunto al usuario cómo ocurrió el problema para entender el contexto antes de actuar' },
        { key: 'D', text: 'Verifico todos los logs disponibles antes de tocar cualquier equipo físico' },
      ]
    },
    {
      id: 'p3_sup_2',
      question: '¿Qué parte del soporte técnico encuentras más significativa?',
      options: [
        { key: 'A', text: 'Documentar procedimientos para que el problema nunca se repita de la misma forma' },
        { key: 'B', text: 'Resolver el problema del usuario en el menor tiempo posible y dejarlo feliz' },
        { key: 'C', text: 'Explicarle al usuario qué pasó y cómo evitarlo en el futuro' },
        { key: 'D', text: 'Encontrar la causa raíz profunda detrás del síntoma superficial reportado' },
      ]
    },
    {
      id: 'p3_sup_3',
      question: 'Son las 8am y ya tienes 15 tickets abiertos. ¿Cómo los priorizo?',
      options: [
        { key: 'A', text: 'Los clasifico por impacto de negocio y urgencia antes de atender ninguno' },
        { key: 'B', text: 'Resuelvo los más rápidos primero para reducir la cola y ganar tiempo' },
        { key: 'C', text: 'Me coordino con otro técnico para dividir la carga y atender en paralelo' },
        { key: 'D', text: 'Sigo el SLA al pie de la letra: los tickets por vencer primero tienen prioridad' },
      ]
    },
    {
      id: 'p3_sup_4',
      question: 'Un usuario está muy frustrado y eleva el tono. ¿Qué haces?',
      options: [
        { key: 'A', text: 'Le explico con calma el proceso de escalación y los tiempos esperados' },
        { key: 'B', text: 'Priorizo su caso para darle una respuesta rápida y reducir la tensión' },
        { key: 'C', text: 'Escucho activamente, valido su frustración y luego propongo la solución' },
        { key: 'D', text: 'Escalo formalmente al supervisor si el comportamiento no es profesional' },
      ]
    },
  ],
  'QA & Testing': [
    {
      id: 'p3_qa_1',
      question: 'Se lanza una nueva funcionalidad mañana. ¿Cómo estructuras tu plan de testing?',
      options: [
        { key: 'A', text: 'Diseño una matriz de casos de prueba cubriendo happy path, edge cases y regresión' },
        { key: 'B', text: 'Automatizo las pruebas críticas hoy y ejecuto el resto en exploración mañana' },
        { key: 'C', text: 'Me reúno con el desarrollador para entender la lógica y enfocar el testing donde más importa' },
        { key: 'D', text: 'No apruebo el release hasta tener cobertura documentada de los casos de aceptación' },
      ]
    },
    {
      id: 'p3_qa_2',
      question: 'Encuentras un bug crítico 30 minutos antes de un release. ¿Qué haces?',
      options: [
        { key: 'A', text: 'Documento el bug con pasos reproductibles y lo reporto al equipo inmediatamente' },
        { key: 'B', text: 'Evalúo si puede mitigarse con un workaround para no bloquear el release' },
        { key: 'C', text: 'Convoco una reunión de go/no-go con el PM, el dev y el QA Lead' },
        { key: 'D', text: 'Bloqueo el release categóricamente: un bug crítico no puede llegar a los usuarios' },
      ]
    },
    {
      id: 'p3_qa_3',
      question: '¿Qué tipo de testing te resulta más fascinante?',
      options: [
        { key: 'A', text: 'Testing de contratos y arquitectura de microservicios' },
        { key: 'B', text: 'Testing exploratorio: encontrar lo que nadie pensó en probar' },
        { key: 'C', text: 'Testing de usabilidad: comprobar que el producto es intuitivo para el usuario final' },
        { key: 'D', text: 'Performance testing y pruebas de carga bajo condiciones extremas' },
      ]
    },
    {
      id: 'p3_qa_4',
      question: 'El equipo de desarrollo dice que "no hay tiempo para testing". ¿Qué respondes?',
      options: [
        { key: 'A', text: 'Presento datos históricos de bugs en producción que costaron más tiempo que el testing' },
        { key: 'B', text: 'Propongo testing mínimo viable focalizado en el 20% del código con 80% del riesgo' },
        { key: 'C', text: 'Negocio para incluir al menos los casos de aceptación del cliente' },
        { key: 'D', text: 'Escalo a la gerencia: saltar el testing es un riesgo de negocio, no técnico' },
      ]
    },
  ],
  'Gestión y Producto': [
    {
      id: 'p3_pm_1',
      question: 'El cliente quiere 10 features nuevas para mañana. ¿Cómo manejas eso?',
      options: [
        { key: 'A', text: 'Analizo el impacto de cada feature en los OKRs del producto y priorizo con datos' },
        { key: 'B', text: 'Negocio entregas iterativas: 2 features mañana, el resto en sprints posteriores' },
        { key: 'C', text: 'Facilito un workshop de priorización con el cliente para que él mismo elija los top 3' },
        { key: 'D', text: 'Creo una matriz de esfuerzo/impacto detallada antes de comprometer cualquier fecha' },
      ]
    },
    {
      id: 'p3_pm_2',
      question: '¿Cuál es tu señal más confiable de que un producto va por buen camino?',
      options: [
        { key: 'A', text: 'Las métricas de retención y los KPIs del producto suben consistentemente' },
        { key: 'B', text: 'El equipo entrega a tiempo y los usuarios usan las features que se construyeron' },
        { key: 'C', text: 'Los stakeholders y el equipo hablan positivamente del producto en las retrospectivas' },
        { key: 'D', text: 'El product-market fit es claro: los usuarios pagarían por él aunque dejara de ser gratis' },
      ]
    },
    {
      id: 'p3_pm_3',
      question: 'Hay un conflicto entre el equipo de diseño y el de desarrollo. ¿Cómo actúas?',
      options: [
        { key: 'A', text: 'Creo un framework de decisión basado en datos del usuario para resolver el conflicto objetivamente' },
        { key: 'B', text: 'Tomo una decisión rápida basada en lo que mejor sirve al usuario final ahora mismo' },
        { key: 'C', text: 'Facilito una sesión de co-creación donde ambos equipos diseñen juntos la solución' },
        { key: 'D', text: 'Documento los pros y contras de cada postura antes de escalar a la dirección' },
      ]
    },
    {
      id: 'p3_pm_4',
      question: '¿Qué describe mejor tu visión del rol de Product Manager?',
      options: [
        { key: 'A', text: 'El CEO del producto: responsable de la visión, la estrategia y los resultados de negocio' },
        { key: 'B', text: 'El facilitador de entregas: asegura que el equipo pueda moverse rápido sin fricciones' },
        { key: 'C', text: 'El puente entre el usuario y el equipo técnico: traduce necesidades en soluciones' },
        { key: 'D', text: 'El guardián de la calidad del producto: nada sale si no cumple el estándar prometido' },
      ]
    },
  ],
  'Diseño UX/UI': [
    {
      id: 'p3_ux_1',
      question: 'Un usuario dice que tu diseño "se ve mal". ¿Cómo respondes?',
      options: [
        { key: 'A', text: 'Le pido que especifique: ¿visual, usabilidad o flujo? Cada uno tiene soluciones distintas' },
        { key: 'B', text: 'Propongo 3 variantes alternativas rápidas para que el usuario elija la que prefiere' },
        { key: 'C', text: 'Organizo una sesión de co-diseño con el usuario para rediseñar juntos' },
        { key: 'D', text: 'Valido el feedback contra los principios de Heurísticas de Nielsen antes de cambiar nada' },
      ]
    },
    {
      id: 'p3_ux_2',
      question: '¿Qué parte del proceso de diseño disfrutas más?',
      options: [
        { key: 'A', text: 'La arquitectura de información y los wireframes: la estructura lógica del sistema' },
        { key: 'B', text: 'El prototipado rápido: tener algo clickeable en manos del usuario lo antes posible' },
        { key: 'C', text: 'Las entrevistas con usuarios: entender sus frustraciones reales es lo más valioso' },
        { key: 'D', text: 'El Design System: crear componentes reutilizables perfectamente documentados' },
      ]
    },
    {
      id: 'p3_ux_3',
      question: 'El equipo dev dice que tu diseño es "imposible de implementar" tal como está. ¿Qué haces?',
      options: [
        { key: 'A', text: 'Pido una sesión técnica para entender las restricciones y rediseño dentro de ellas' },
        { key: 'B', text: 'Simplifico el diseño al mínimo que preserve la experiencia de usuario esencial' },
        { key: 'C', text: 'Propongo un sprint de diseño+dev conjunto para encontrar una solución técnica-visual conjunta' },
        { key: 'D', text: 'Documento exactamente por qué la experiencia propuesta es necesaria para el negocio' },
      ]
    },
    {
      id: 'p3_ux_4',
      question: '¿Qué mides para saber que un diseño fue exitoso?',
      options: [
        { key: 'A', text: 'La reducción del tiempo de tarea y la tasa de finalización de flujos críticos' },
        { key: 'B', text: 'El NPS y si los usuarios recomendarían el producto a un amigo' },
        { key: 'C', text: 'El número de tickets de soporte relacionados con confusión de interfaz que disminuyen' },
        { key: 'D', text: 'La puntuación en tests de usabilidad estructurados con métricas predefinidas de SUS' },
      ]
    },
  ],
  'Sistemas Empresariales': [
    {
      id: 'p3_erp_1',
      question: 'Una empresa quiere implementar SAP pero el presupuesto se redujo a la mitad. ¿Qué propones?',
      options: [
        { key: 'A', text: 'Hago un análisis de brechas y priorizo los módulos de mayor retorno sobre inversión' },
        { key: 'B', text: 'Propongo una implementación por fases: el módulo más urgente primero y el resto después' },
        { key: 'C', text: 'Involucro a los líderes de cada área para que definan sus prioridades críticas' },
        { key: 'D', text: 'Evalúo alternativas de ERP open source antes de comprometer el presupuesto total' },
      ]
    },
    {
      id: 'p3_erp_2',
      question: 'Los usuarios finales rechazan el nuevo sistema ERP. ¿Cómo lo manejas?',
      options: [
        { key: 'A', text: 'Analizo las métricas de adopción para identificar los módulos con mayor resistencia' },
        { key: 'B', text: 'Inicio quick wins: muestro cómo el sistema ya les ahorra tiempo en el día a día' },
        { key: 'C', text: 'Formo champions internos: usuarios clave que lideren la adopción entre sus compañeros' },
        { key: 'D', text: 'Documento los bugs y fricciones de usabilidad reportados y los presento al proveedor' },
      ]
    },
    {
      id: 'p3_erp_3',
      question: '¿Qué aspecto de los sistemas empresariales te resulta más valioso?',
      options: [
        { key: 'A', text: 'La integración de datos entre áreas: que finanzas, operaciones y RR.HH. hablen entre sí' },
        { key: 'B', text: 'La automatización de procesos repetitivos que liberan tiempo al equipo humano' },
        { key: 'C', text: 'El Business Intelligence: los dashboards que ayudan a la dirección a tomar mejores decisiones' },
        { key: 'D', text: 'La trazabilidad y el compliance: que cada transacción esté auditada y sea reproducible' },
      ]
    },
    {
      id: 'p3_erp_4',
      question: 'Al finalizar una implementación de ERP, ¿cómo mides el éxito?',
      options: [
        { key: 'A', text: 'Con KPIs de eficiencia: reducción en tiempo de procesos y errores de datos' },
        { key: 'B', text: 'Con la velocidad de adopción: ¿cuántos usuarios activos tiene el sistema a los 30 días?' },
        { key: 'C', text: 'Con la satisfacción del equipo directivo y de los usuarios finales por separado' },
        { key: 'D', text: 'Con el cumplimiento total del scope acordado en el contrato de implementación' },
      ]
    },
  ],
  'Investigación e Innovación': [
    {
      id: 'p3_inv_1',
      question: 'Lees un paper con resultados que contradicen tu hipótesis inicial. ¿Qué haces?',
      options: [
        { key: 'A', text: 'Reviso la metodología detalladamente para encontrar posibles limitaciones del estudio' },
        { key: 'B', text: 'Actualizo mi hipótesis inmediatamente: los datos mandan sobre la intuición' },
        { key: 'C', text: 'Comparto el paper con mis colegas para debatirlo en conjunto antes de concluir' },
        { key: 'D', text: 'Replico el experimento en mi entorno para verificar si los resultados son reproducibles' },
      ]
    },
    {
      id: 'p3_inv_2',
      question: '¿Cuál de estas fases de un proyecto de investigación te entusiasma más?',
      options: [
        { key: 'A', text: 'El diseño metodológico: construir el andamiaje experimental correcto desde el inicio' },
        { key: 'B', text: 'El prototipado de la idea: ver si algo que nadie hizo antes funciona en la práctica' },
        { key: 'C', text: 'La difusión: publicar los hallazgos para que otros investigadores los construyan encima' },
        { key: 'D', text: 'La validación rigurosa: demostrar que los resultados son sólidos y no artefactos estadísticos' },
      ]
    },
    {
      id: 'p3_inv_3',
      question: '¿Cómo decides cuándo una idea innovadora vale la pena ser perseguida?',
      options: [
        { key: 'A', text: 'Cuando existe un gap documentado en el estado del arte que mi idea puede cerrar' },
        { key: 'B', text: 'Cuando puedo tener un prototipo funcional en menos de 2 semanas para testear la hipótesis' },
        { key: 'C', text: 'Cuando hay al menos un stakeholder con problema real que la idea resolvería' },
        { key: 'D', text: 'Cuando la idea supera un análisis de factibilidad técnica, legal y de impacto medible' },
      ]
    },
    {
      id: 'p3_inv_4',
      question: 'Tu proyecto de innovación pierde financiamiento a mitad de camino. ¿Qué haces?',
      options: [
        { key: 'A', text: 'Reduzco el alcance al núcleo de la hipótesis principal y busco nuevos fondos específicos' },
        { key: 'B', text: 'Busco un partner de industria que se beneficie de los resultados y cofinancie el resto' },
        { key: 'C', text: 'Abro el proyecto como investigación colaborativa abierta para atraer otros investigadores' },
        { key: 'D', text: 'Publico los avances hasta la fecha como paper preliminar para no perder el trabajo hecho' },
      ]
    },
  ],
}

// Fallback: si la especialización no está en el banco, usa preguntas genéricas
const PHASE3_FALLBACK = [
  {
    id: 'p3_fb_1',
    question: 'Acabas de terminar un módulo de trabajo. ¿Cuál es tu reacción natural?',
    options: [
      { key: 'A', text: 'Lo reviso buscando posibles errores antes de entregarlo' },
      { key: 'B', text: 'Lo entrego y si hay correcciones, las ajusto sobre la marcha' },
      { key: 'C', text: 'Lo comparto con mi equipo para recibir retroalimentación primero' },
      { key: 'D', text: 'Lo optimizo para que sea más limpio y eficiente antes de entregarlo' },
    ]
  },
  {
    id: 'p3_fb_2',
    question: 'Un proceso falla inesperadamente. ¿Qué haces primero?',
    options: [
      { key: 'A', text: 'Construyo un diagnóstico completo antes de intervenir' },
      { key: 'B', text: 'Implemento una solución temporal y luego investigo la causa raíz' },
      { key: 'C', text: 'Escalo al líder del equipo de inmediato' },
      { key: 'D', text: 'No actúo hasta tener certeza sobre la causa exacta' },
    ]
  },
  {
    id: 'p3_fb_3',
    question: '¿Cómo prefieres aprender algo nuevo en tu área?',
    options: [
      { key: 'A', text: 'Con documentación oficial, paso a paso y de forma estructurada' },
      { key: 'B', text: 'Construyendo un proyecto real desde el primer día' },
      { key: 'C', text: 'En equipo, con mentores o grupos de estudio colaborativos' },
      { key: 'D', text: 'Con materiales curados y tomando notas detalladas para repasar' },
    ]
  },
  {
    id: 'p3_fb_4',
    question: 'Descríbete en un equipo de trabajo:',
    options: [
      { key: 'A', text: 'El estratega: diseño la estructura general antes de ejecutar' },
      { key: 'B', text: 'El ejecutor: soy el primero en tener resultados en mano' },
      { key: 'C', text: 'El conector: facilito la comunicación y coordinación del equipo' },
      { key: 'D', text: 'El revisor: nada sale sin que yo lo haya validado previamente' },
    ]
  },
]

// Obtiene las preguntas de Fase 3 correctas según la especialización ganadora del ML
function getPhase3Questions(specName) {
  // Busca directamente o por contiene (por si hay variaciones menores)
  if (PHASE3_BANK[specName]) return PHASE3_BANK[specName]
  const key = Object.keys(PHASE3_BANK).find(k => specName?.includes(k) || k.includes(specName))
  return key ? PHASE3_BANK[key] : PHASE3_FALLBACK
}

function calcArchetype(answers) {
  const counts = { A: 0, B: 0, C: 0, D: 0 }
  Object.values(answers).forEach(v => { if (counts[v] !== undefined) counts[v]++ })
  return Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0]
}


export default function Questionnaire() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const [questions, setQuestions] = useState([])
  const [sessionId, setSessionId] = useState(null)
  const [answers, setAnswers] = useState({})     // { questionId: value }
  const [current, setCurrent] = useState(0)       // index pregunta actual
  const [phase, setPhase] = useState(1)           // 1, 2 o 3
  const [phase3Answers, setPhase3Answers] = useState({}) // respuestas psicométricas
  const [phase3Current, setPhase3Current] = useState(0)  // índice dentro de Fase 3
  const [phase3Questions, setPhase3Questions] = useState(PHASE3_FALLBACK) // preguntas adaptadas
  
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [transitioning, setTransitioning] = useState(false)
  const [error, setError] = useState('')
  const cardRef = useRef(null)

  useEffect(() => {
    if (!user) return
    let sid = null
    surveyApi.createSession()
      .then(sRes => {
        sid = sRes.data.id
        setSessionId(sid)
        return surveyApi.getSessionQuestions(sid)
      })
      .then(qRes => {
        setQuestions(qRes.data)
      })
      .catch(e => {
        console.error("Error cargando cuestionario", e)
        setError('Error cargando el cuestionario')
      })
      .finally(() => setLoading(false))
  }, [user])

  const loadPhase2 = async (sid) => {
    setTransitioning(true)
    try {
      const qRes = await surveyApi.getSessionQuestions(sid)
      setQuestions(qRes.data)
      setCurrent(0)
      setPhase(2)
    } catch(e) {
      setError('Error al cargar preguntas avanzadas.')
    } finally {
      setTransitioning(false)
    }
  }

  const triggerPhase3 = (specName) => {
    const qs = getPhase3Questions(specName)
    setPhase3Questions(qs)
    setPhase(3)
    setPhase3Current(0)
    setPhase3Answers({})
  }

  const q = questions[current]
  const progress = questions.length ? Math.round((current / questions.length) * 100) : 0
  const isAnswered = q && answers[q.id] !== undefined
  const isLast = current === questions.length - 1

  const setAnswer = (val) => setAnswers(a => ({ ...a, [q.id]: val }))

  const next = async () => {
    if (!isAnswered) return
    // Guardar respuesta actual en bd
    surveyApi.saveAnswers(sessionId, {
      answers: [{ question_id: q.id, value: answers[q.id] }]
    }).catch(console.error)

    if (isLast) { 
      setSubmitting(true)

      // Helper: sleep
      const sleep = (ms) => new Promise(r => setTimeout(r, ms))

      // Función de submit con reintentos automáticos (por cold start del ML en Render Free)
      const submitWithRetry = async (maxRetries = 3) => {
        for (let attempt = 1; attempt <= maxRetries; attempt++) {
          try {
            const allPhaseAnswers = questions.map(q2 => ({ question_id: q2.id, value: answers[q2.id] || 3 }))
            await surveyApi.saveAnswers(sessionId, { answers: allPhaseAnswers })
            
            const { data: transitionData } = await surveyApi.submitPhase(sessionId)
            
            if (transitionData.next_phase === 2) {
              setSubmitting(false)
              loadPhase2(sessionId)
              return

            } else if (transitionData.prediction_id) {
              setSubmitting(false)
              sessionStorage.setItem('revo_pending_result', transitionData.prediction_id)
              const specName = transitionData.primary_specialization || ''
              sessionStorage.setItem('revo_winning_spec', specName)
              triggerPhase3(specName)
              return

            } else if (transitionData.error && attempt < maxRetries) {
              // ML en cold start — esperar y reintentar
              const waitSecs = attempt * 8
              setError(`⏳ El servidor de IA está despertando... reintentando en ${waitSecs}s (intento ${attempt}/${maxRetries})`)
              await sleep(waitSecs * 1000)
              setError('')
              // Continúa al siguiente intento

            } else if (transitionData.error && attempt === maxRetries) {
              // Último intento: si tenemos affinities pasamos igual a la Fase 3 sin predicción guardada
              setError('')
              setSubmitting(false)
              sessionStorage.removeItem('revo_pending_result')
              const specName = transitionData.predicted_spec || transitionData.primary_specialization || ''
              sessionStorage.setItem('revo_winning_spec', specName)
              triggerPhase3(specName)
              return

            } else {
              setError('Respuesta inesperada del servidor. Intenta de nuevo.')
              setSubmitting(false)
              return
            }
          } catch (e) {
            if (attempt < maxRetries) {
              const waitSecs = attempt * 8
              setError(`⏳ Conexión lenta, reintentando en ${waitSecs}s... (intento ${attempt}/${maxRetries})`)
              await sleep(waitSecs * 1000)
              setError('')
            } else {
              setError('No se pudo conectar con el servidor. Verifica tu conexión e intenta de nuevo.')
              setSubmitting(false)
            }
          }
        }
      }

      await submitWithRetry()

    } else {
      // Siguiente pregunta animada
      if (cardRef.current) { cardRef.current.style.opacity = '0'; cardRef.current.style.transform = 'translateX(30px)' }
      setTimeout(() => {
        setCurrent(c => c + 1)
        if (cardRef.current) { cardRef.current.style.opacity = '1'; cardRef.current.style.transform = 'translateX(0)' }
      }, 200)
    }
  }

  const prev = () => {
    if (current > 0) setCurrent(c => c - 1)
  }

  if (loading) return (
    <div className="page" style={{ display:'flex', alignItems:'center', justifyContent:'center' }}>
      <div className="text-center">
        <div className="loading-tree">🌳</div>
        <p className="text-muted">Iniciando Fase 1: Calibración General...</p>
      </div>
    </div>
  )

  if (submitting) return (
    <div className="page" style={{ display:'flex', alignItems:'center', justifyContent:'center' }}>
      <div className="text-center analyzing">
        <div className="analyzing-icon">🧠</div>
        <h2 className="gradient-text" style={{ fontFamily:'Space Grotesk', fontSize:'1.8rem', fontWeight:800 }}>
          {phase === 1 ? 'Calculando Inteligencia Adaptativa...' : 'Ejecutando Árbol de ML...'}
        </h2>
        <p className="text-muted">
          {phase === 1 ? 'Encontrando tus mejores 3 ramas y generando preguntas avanzadas.' : 'El algoritmo está decidiendo tu futuro ideal.'}
        </p>
        <div className="analyzing-dots"><span/><span/><span/></div>
      </div>
    </div>
  )
  
  if (transitioning) return (
    <div className="page" style={{ display:'flex', alignItems:'center', justifyContent:'center' }}>
      <div className="text-center analyzing">
        <div className="analyzing-icon">🔥</div>
        <h2 className="gradient-text" style={{ fontFamily:'Space Grotesk', fontSize:'1.8rem', fontWeight:800 }}>
          ¡Fase 2 Desbloqueada!
        </h2>
        <p className="text-muted">Hemos descubierto para qué eres bueno. Ahora, a profundizar.</p>
        <div className="analyzing-dots"><span/><span/><span/></div>
      </div>
    </div>
  )

  // ── FASE 3: Cuestionario Psicométrico ──────────────────────────────────────
  if (phase === 3) {
    const p3q = phase3Questions[phase3Current]
    const p3Progress = Math.round(((phase3Current) / phase3Questions.length) * 100)
    const p3Selected = phase3Answers[p3q?.id]
    const isLastP3 = phase3Current === phase3Questions.length - 1
    const winningSpec = sessionStorage.getItem('revo_winning_spec') || ''


    const handleP3Select = (key) => {
      setPhase3Answers(prev => ({ ...prev, [p3q.id]: key }))
    }

    const handleP3Next = () => {
      if (!p3Selected) return
      if (isLastP3) {
        // Calcular arquetipo y navegar a resultados
        const finalAnswers = { ...phase3Answers, [p3q.id]: p3Selected }
        const archetype = calcArchetype(finalAnswers)
        sessionStorage.setItem('revo_archetype', JSON.stringify(archetype))
        const pendingId = sessionStorage.getItem('revo_pending_result')
        navigate(`/results/${pendingId}`)
      } else {
        setPhase3Current(c => c + 1)
      }
    }

    return (
      <div className="page quiz-page">
        <div className="container quiz-container">
          <div className="quiz-header animate-fade">
            <div className="quiz-progress-info">
              <span className="text-sm text-muted">🧠 Fase 3/3 — Perfil Profesional · Pregunta {phase3Current + 1} de {phase3Questions.length}</span>
              <span className="text-sm font-semibold" style={{ color: '#10B981' }}>{p3Progress}%</span>
            </div>
            <div className="progress-track" style={{ height: 8 }}>
              <div className="progress-fill" style={{ width: `${p3Progress}%`, background: '#10B981' }} />
            </div>
            <div style={{ marginTop: 12, padding: '8px 14px', background: 'rgba(16,185,129,0.08)', borderRadius: 8, border: '1px solid rgba(16,185,129,0.2)' }}>
              <span className="text-sm" style={{ color: '#10B981' }}>
                🎉 El ML te recomienda <strong>{winningSpec || 'tu especialización'}</strong>. Ahora descubramos tu perfil profesional exacto.
              </span>
            </div>
          </div>

          {p3q && (
            <div className="glass question-card animate-scale" style={{ transition: 'opacity 0.2s, transform 0.2s' }}>
              <div className="q-category-badge" style={{ background: 'rgba(16,185,129,0.15)', color: '#10B981' }}>
                🧠 Perfil Psicométrico
              </div>
              <h2 className="q-text">{p3q.question}</h2>

              {/* Opciones tipo card en lugar de escala numérica */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12, margin: '24px 0' }}>
                {p3q.options.map(opt => (
                  <button
                    key={opt.key}
                    onClick={() => handleP3Select(opt.key)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 14, textAlign: 'left',
                      padding: '14px 18px', borderRadius: 12, cursor: 'pointer',
                      border: p3Selected === opt.key ? '2px solid #10B981' : '1px solid rgba(255,255,255,0.08)',
                      background: p3Selected === opt.key ? 'rgba(16,185,129,0.12)' : 'rgba(255,255,255,0.03)',
                      color: p3Selected === opt.key ? '#F1F5F9' : '#94A3B8',
                      transition: 'all 0.2s ease', fontFamily: 'inherit', fontSize: '0.95rem',
                    }}
                  >
                    <span style={{
                      width: 32, height: 32, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontWeight: 800, fontSize: '0.85rem', flexShrink: 0,
                      background: p3Selected === opt.key ? '#10B981' : 'rgba(255,255,255,0.08)',
                      color: p3Selected === opt.key ? '#fff' : '#64748B',
                    }}>
                      {opt.key}
                    </span>
                    {opt.text}
                  </button>
                ))}
              </div>

              <div className="quiz-nav">
                <button onClick={() => phase3Current > 0 && setPhase3Current(c => c - 1)} disabled={phase3Current === 0} className="btn btn-secondary">
                  ← Anterior
                </button>
                <button onClick={handleP3Next} disabled={!p3Selected} className="btn btn-primary"
                  style={{ background: '#10B981', borderColor: '#10B981' }}>
                  {isLastP3 ? '🎯 Ver mi Resultado Completo →' : 'Siguiente →'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

  // ── FASES 1 y 2: Cuestionario normal ───────────────────────────────────────
  return (
    <div className="page quiz-page">
      <div className="container quiz-container">
        {/* Progress header */}
        <div className="quiz-header animate-fade">
          <div className="quiz-progress-info">
            <span className="text-sm text-muted"> Fase {phase}/3 — Pregunta {current + 1} de {questions.length}</span>
            <span className="text-sm font-semibold" style={{ color: '#6C63FF' }}>{progress}%</span>
          </div>
          <div className="progress-track" style={{ height: 8 }}>
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
          {/* Categoría indicator */}
          {q && (
            <div className="quiz-categories">
              {Object.entries(CATEGORY_META).map(([key, meta]) => (
                <div key={key} className={`cat-chip ${q.category === key ? 'active' : ''}`}
                  style={{ '--cc': meta.color }}>
                  {meta.icon} {meta.label}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Question card */}
        {q && (
          <div className="glass question-card animate-scale" ref={cardRef}
            style={{ transition: 'opacity 0.2s, transform 0.2s' }}>
            <div className="q-category-badge" style={{ background: CATEGORY_META[q.category]?.color + '22', color: CATEGORY_META[q.category]?.color }}>
              {CATEGORY_META[q.category]?.icon} {CATEGORY_META[q.category]?.label}
            </div>
            <h2 className="q-text">{q.text}</h2>
            {error && <div className="auth-error text-sm">{error}</div>}

            {/* Scale 1-5 */}
            <div className="scale-container">
              <span className="scale-label">{q.min_label}</span>
              <div className="scale-buttons">
                {[1,2,3,4,5].map(v => (
                  <button key={v} onClick={() => setAnswer(v)}
                    className={`scale-btn ${answers[q.id] === v ? 'selected' : ''}`}
                    style={ answers[q.id] === v ? { background: CATEGORY_META[q.category]?.color, borderColor: CATEGORY_META[q.category]?.color } : {} }>
                    {v}
                  </button>
                ))}
              </div>
              <span className="scale-label">{q.max_label}</span>
            </div>

            {/* Scale descriptors */}
            <div className="scale-desc">
              {[
                { v:1, l:'Muy bajo' }, { v:2, l:'Bajo'}, { v:3, l:'Regular'},
                { v:4, l:'Bueno'}, { v:5, l:'Excelente'}
              ].map(d => (
                <span key={d.v} className={`scale-desc-item ${answers[q.id] === d.v ? 'sel' : ''}`}>{d.l}</span>
              ))}
            </div>

            {/* Navigation */}
            <div className="quiz-nav">
              <button onClick={prev} disabled={current === 0} className="btn btn-secondary">
                ← Anterior
              </button>
              <button onClick={next} disabled={!isAnswered} className="btn btn-primary">
                {isLast ? (phase === 1 ? '🔥 Ir a Fase 2 →' : '🧠 Ir a Perfil Profesional →') : 'Siguiente →'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
