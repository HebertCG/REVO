-- ============================================================
-- REVO DB - Script 09: Preguntas Psicométricas Adaptativas
-- Tabla: psychometric_questions
-- Banco de 40 preguntas (4 por cada especialización)
-- ============================================================

CREATE TABLE IF NOT EXISTS psychometric_questions (
    id                  SERIAL PRIMARY KEY,
    specialization_id   INTEGER      NOT NULL REFERENCES specializations(id) ON DELETE CASCADE,
    question_text       TEXT         NOT NULL,
    option_a            TEXT         NOT NULL,
    option_b            TEXT         NOT NULL,
    option_c            TEXT         NOT NULL,
    option_d            TEXT         NOT NULL,
    order_index         SMALLINT     NOT NULL DEFAULT 0,
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_psychometric_spec ON psychometric_questions(specialization_id, is_active);

-- ============================================================
-- SEED: 4 preguntas por cada una de las 10 especializaciones
-- Orden de IDs en specializations (según 02_seed_specializations.sql):
-- 1=Desarrollo de Software, 2=Data Science & IA, 3=Infraestructura & Cloud
-- 4=Ciberseguridad, 5=Soporte Técnico & IT Ops, 6=QA & Testing
-- 7=Gestión y Producto, 8=Diseño UX/UI, 9=Sistemas Empresariales
-- 10=Investigación e Innovación
-- ============================================================

-- Borrar seed previo si existe (idempotente)
TRUNCATE TABLE psychometric_questions RESTART IDENTITY CASCADE;

-- ── 1. Desarrollo de Software ─────────────────────────────────
INSERT INTO psychometric_questions (specialization_id, question_text, option_a, option_b, option_c, option_d, order_index) VALUES
(1, 'Cuando tu código no funciona a la primera, ¿cuál es tu reacción instintiva?',
 'Leo el stack trace línea a línea hasta aislar exactamente el error',
 'Pruebo soluciones rápidas en orden hasta que una funcione',
 'Le explico el problema a un compañero para buscar perspectiva',
 'Refactorizo el bloque completo: prefiero limpiar antes de parchar', 1),

(1, 'Tienes que elegir entre lanzar en 2 días con deuda técnica o en 2 semanas limpio. ¿Qué eliges?',
 'Lanzo en 2 semanas, la arquitectura bien hecha vale la espera',
 'Lanzo en 2 días y creo un ticket de deuda técnica para después',
 'Negocio con el equipo para encontrar una ruta media entre las dos',
 'Solo lanzo si puedo garantizar al menos el 80% de calidad del código', 2),

(1, '¿Cómo describes tu relación con aprender nuevos lenguajes o frameworks?',
 'Me emociona: lo estudio desde la documentación oficial primero',
 'Prefiero aprenderlo construyendo algo real desde el día 1',
 'Aprendo bien en pair programming o un bootcamp grupal',
 'Lo aprendo pero siempre busco dominarlo a fondo antes de usarlo en producción', 3),

(1, 'En un equipo de desarrollo, ¿cuál es tu rol natural?',
 'Arquitecto: diseño la estructura del sistema antes de codificar',
 'Ejecutor: soy el primero en tener una versión funcional en manos del cliente',
 'Integrador: conecto el trabajo de todos y facilito las revisiones de código',
 'Revisor: nada pasa a producción sin que yo lo haya validado', 4);

-- ── 2. Data Science & IA ──────────────────────────────────────
INSERT INTO psychometric_questions (specialization_id, question_text, option_a, option_b, option_c, option_d, order_index) VALUES
(2, 'Te presentan un dataset con 50 columnas y datos sucios. ¿Cuál es tu primer paso?',
 'Construyo un mapa estadístico completo (nulos, distribuciones, correlaciones) antes de tocar nada',
 'Limpio los datos básicos y entreno un modelo rápido para ver si hay potencial',
 'Entrevisto al dueño del negocio para entender qué columnas importan realmente',
 'Documento cada decisión del proceso de limpieza para asegurar reproducibilidad', 1),

(2, 'Tu modelo tiene 94% de accuracy pero el equipo de negocio no confía en él. ¿Qué haces?',
 'Creo visualizaciones de SHAP values para mostrar exactamente qué impulsa cada predicción',
 'Hago una demo en vivo con datos reales para que vean el modelo en acción',
 'Organizo una reunión de revisión donde el equipo puede hacerle preguntas al modelo',
 'Añado más métricas: Precision, Recall y F1 por segmento hasta que los números hablen solos', 2),

(2, '¿Cuál de estas tareas te parece más estimulante dentro de la ciencia de datos?',
 'Diseñar el pipeline de datos y la arquitectura del MLOps',
 'Encontrar el insight que nadie había visto oculto en los datos',
 'Presentar los resultados de forma que todos en la empresa los entiendan',
 'Optimizar el hiperparámetro final que sube el modelo de 94% a 97%', 3),

(2, 'Ante la incertidumbre en los datos, ¿cómo actúas?',
 'Modelo la incertidumbre explícitamente con intervalos de confianza bayesianos',
 'Acepto que la perfecta información no existe y entrego el mejor modelo posible hoy',
 'Consulto a expertos del dominio para aterrizar los supuestos del modelo',
 'No libero el modelo hasta tener al menos 3 validaciones cruzadas estables', 4);

-- ── 3. Infraestructura & Cloud ────────────────────────────────
INSERT INTO psychometric_questions (specialization_id, question_text, option_a, option_b, option_c, option_d, order_index) VALUES
(3, 'Un servidor de producción sube al 95% de CPU. ¿Cuál es tu primera acción?',
 'Reviso los logs, identifico el proceso causante y escalo de forma planificada',
 'Activo auto-scaling inmediatamente y luego investigo la causa raíz',
 'Notifico al equipo de desarrollo porque probablemente el código tiene una fuga',
 'Ejecuto un análisis forense antes de tocar cualquier cosa para evitar empeorar el estado', 1),

(3, '¿Cuál de estas frases describe mejor tu filosofía de infraestructura?',
 'Infrastructure as Code: todo debe ser reproducible desde un repositorio Git',
 'Entrega rápida: si funciona en staging, va a producción hoy',
 'Colaboración: Ops y Dev deben trabajar como un solo equipo',
 'Zero-downtime: ningún despliegue justifica un minuto de indisponibilidad', 2),

(3, '¿Qué tipo de proyecto Cloud te despertaría más curiosidad?',
 'Diseñar una arquitectura multi-región altamente disponible desde cero',
 'Migrar una app monolítica a microservicios en Kubernetes en tiempo récord',
 'Implementar una estrategia de FinOps para reducir el costo de la nube un 40%',
 'Construir el pipeline de CI/CD perfecto con gates de seguridad en cada paso', 3),

(3, 'Ante un cambio urgente en producción fuera de la ventana de mantenimiento, ¿qué haces?',
 'Sigo el runbook y solo ejecuto si tengo el Change Request aprobado',
 'Evalúo el impacto en 5 minutos y ejecuto si el riesgo es menor al del problema actual',
 'Convoco al equipo de guardia antes de tocar nada, no tomo decisiones solo',
 'Preparo un plan de rollback antes de cualquier intervención', 4);

-- ── 4. Ciberseguridad ─────────────────────────────────────────
INSERT INTO psychometric_questions (specialization_id, question_text, option_a, option_b, option_c, option_d, order_index) VALUES
(4, 'Encuentras una vulnerabilidad crítica en el sistema de un cliente. ¿Qué haces primero?',
 'Documento exhaustivamente el vector de ataque antes de reportarlo',
 'Reporto inmediatamente aunque no tenga todos los detalles: el tiempo cuenta',
 'Coordino con el equipo de desarrollo para una divulgación responsable coordinada',
 'Verifico el alcance total del impacto antes de escalar, para no generar pánico innecesario', 1),

(4, '¿Cuál de estos retos de ciberseguridad te atrae más?',
 'Diseñar la arquitectura de seguridad de sistemas críticos bancarios o de salud',
 'Hackear sistemas en entornos de Bug Bounty o Red Team con total libertad',
 'Concientizar y entrenar al equipo humano: el eslabón más débil siempre es la persona',
 'Hacer forense digital y análisis de malware en laboratorio controlado', 2),

(4, '¿Cómo describes tu relación con las reglas y la normativa de seguridad?',
 'Las normas existen por razones: las sigo y las mejoro con nuevos controles',
 'Las normas son un mínimo, yo pienso como el atacante para ir más allá',
 'Las normas deben ser entendidas por todos: mi rol es traducirlas al equipo',
 'El cumplimiento al 100% no es negociable, el riesgo cero es el objetivo', 3),

(4, 'Tu empresa tiene un presupuesto limitado de seguridad. ¿En qué inviertes primero?',
 'En una auditoría de arquitectura: arreglar los cimientos vale más que parches',
 'En un pentest externo: necesito saber cómo me verían desde afuera hoy',
 'En entrenamiento de phishing al equipo: el 85% de los ataques entran por personas',
 'En un SIEM robusto: sin visibilidad no puedo defender nada', 4);

-- ── 5. Soporte Técnico & IT Ops ───────────────────────────────
INSERT INTO psychometric_questions (specialization_id, question_text, option_a, option_b, option_c, option_d, order_index) VALUES
(5, 'Un usuario reporta que "internet no funciona". ¿Cómo abordas el diagnóstico?',
 'Sigo un árbol de diagnóstico sistemático: capa física, DNS, gateway, luego aplicación',
 'Reinicio los más comunes primero (router, adaptador) y escalo si no funciona',
 'Pregunto al usuario cómo ocurrió el problema para entender el contexto antes de actuar',
 'Verifico todos los logs disponibles antes de tocar cualquier equipo físico', 1),

(5, '¿Qué parte del soporte técnico encuentras más significativa?',
 'Documentar procedimientos para que el problema nunca se repita de la misma forma',
 'Resolver el problema del usuario en el menor tiempo posible y dejarlo feliz',
 'Explicarle al usuario qué pasó y cómo evitarlo en el futuro',
 'Encontrar la causa raíz profunda detrás del síntoma superficial reportado', 2),

(5, 'Son las 8am y ya tienes 15 tickets abiertos. ¿Cómo los priorizas?',
 'Los clasifico por impacto de negocio y urgencia antes de atender ninguno',
 'Resuelvo los más rápidos primero para reducir la cola y ganar tiempo',
 'Me coordino con otro técnico para dividir la carga y atender en paralelo',
 'Sigo el SLA al pie de la letra: los tickets por vencer primero tienen prioridad', 3),

(5, 'Un usuario está muy frustrado y eleva el tono. ¿Qué haces?',
 'Le explico con calma el proceso de escalación y los tiempos esperados',
 'Priorizo su caso para darle una respuesta rápida y reducir la tensión',
 'Escucho activamente, valido su frustración y luego propongo la solución',
 'Escalo formalmente al supervisor si el comportamiento no es profesional', 4);

-- ── 6. QA & Testing ───────────────────────────────────────────
INSERT INTO psychometric_questions (specialization_id, question_text, option_a, option_b, option_c, option_d, order_index) VALUES
(6, 'Se lanza una nueva funcionalidad mañana. ¿Cómo estructuras tu plan de testing?',
 'Diseño una matriz de casos de prueba cubriendo happy path, edge cases y regresión',
 'Automatizo las pruebas críticas hoy y ejecuto el resto en exploración mañana',
 'Me reúno con el desarrollador para entender la lógica y enfocar el testing donde más importa',
 'No apruebo el release hasta tener cobertura documentada de los casos de aceptación', 1),

(6, 'Encuentras un bug crítico 30 minutos antes de un release. ¿Qué haces?',
 'Documento el bug con pasos reproductibles y lo reporto al equipo inmediatamente',
 'Evalúo si puede mitigarse con un workaround para no bloquear el release',
 'Convoco una reunión de go/no-go con el PM, el dev y el QA Lead',
 'Bloqueo el release categóricamente: un bug crítico no puede llegar a los usuarios', 2),

(6, '¿Qué tipo de testing te resulta más fascinante?',
 'Testing de contratos y arquitectura de microservicios',
 'Testing exploratorio: encontrar lo que nadie pensó en probar',
 'Testing de usabilidad: comprobar que el producto es intuitivo para el usuario final',
 'Performance testing y pruebas de carga bajo condiciones extremas', 3),

(6, 'El equipo de desarrollo dice que "no hay tiempo para testing". ¿Qué respondes?',
 'Presento datos históricos de bugs en producción que costaron más tiempo que el testing',
 'Propongo testing mínimo viable focalizado en el 20% del código con 80% del riesgo',
 'Negocio para incluir al menos los casos de aceptación del cliente',
 'Escalo a la gerencia: saltar el testing es un riesgo de negocio, no técnico', 4);

-- ── 7. Gestión y Producto ─────────────────────────────────────
INSERT INTO psychometric_questions (specialization_id, question_text, option_a, option_b, option_c, option_d, order_index) VALUES
(7, 'El cliente quiere 10 features nuevas para mañana. ¿Cómo manejas eso?',
 'Analizo el impacto de cada feature en los OKRs del producto y priorizo con datos',
 'Negocio entregas iterativas: 2 features mañana, el resto en sprints posteriores',
 'Facilito un workshop de priorización con el cliente para que él mismo elija los top 3',
 'Creo una matriz de esfuerzo/impacto detallada antes de comprometer cualquier fecha', 1),

(7, '¿Cuál es tu señal más confiable de que un producto va por buen camino?',
 'Las métricas de retención y los KPIs del producto suben consistentemente',
 'El equipo entrega a tiempo y los usuarios usan las features que se construyeron',
 'Los stakeholders y el equipo hablan positivamente del producto en las retrospectivas',
 'El product-market fit es claro: los usuarios pagarían por él aunque dejara de ser gratis', 2),

(7, 'Hay un conflicto entre el equipo de diseño y el de desarrollo. ¿Cómo actúas?',
 'Creo un framework de decisión basado en datos del usuario para resolver el conflicto objetivamente',
 'Tomo una decisión rápida basada en lo que mejor sirve al usuario final ahora mismo',
 'Facilito una sesión de co-creación donde ambos equipos diseñen juntos la solución',
 'Documento los pros y contras de cada postura antes de escalar a la dirección', 3),

(7, '¿Qué describe mejor tu visión del rol de Product Manager?',
 'El CEO del producto: responsable de la visión, la estrategia y los resultados de negocio',
 'El facilitador de entregas: asegura que el equipo pueda moverse rápido sin fricciones',
 'El puente entre el usuario y el equipo técnico: traduce necesidades en soluciones',
 'El guardián de la calidad del producto: nada sale si no cumple el estándar prometido', 4);

-- ── 8. Diseño UX/UI ───────────────────────────────────────────
INSERT INTO psychometric_questions (specialization_id, question_text, option_a, option_b, option_c, option_d, order_index) VALUES
(8, 'Un usuario dice que tu diseño "se ve mal". ¿Cómo respondes?',
 'Le pido que especifique: ¿visual, usabilidad o flujo? Cada uno tiene soluciones distintas',
 'Propongo 3 variantes alternativas rápidas para que el usuario elija la que prefiere',
 'Organizo una sesión de co-diseño con el usuario para rediseñar juntos',
 'Valido el feedback contra los principios de Heurísticas de Nielsen antes de cambiar nada', 1),

(8, '¿Qué parte del proceso de diseño disfrutas más?',
 'La arquitectura de información y los wireframes: la estructura lógica del sistema',
 'El prototipado rápido: tener algo clickeable en manos del usuario lo antes posible',
 'Las entrevistas con usuarios: entender sus frustraciones reales es lo más valioso',
 'El Design System: crear componentes reutilizables perfectamente documentados', 2),

(8, 'El equipo dev dice que tu diseño es "imposible de implementar" tal como está. ¿Qué haces?',
 'Pido una sesión técnica para entender las restricciones y rediseño dentro de ellas',
 'Simplifico el diseño al mínimo que preserve la experiencia de usuario esencial',
 'Propongo un sprint de diseño+dev conjunto para encontrar una solución técnica-visual conjunta',
 'Documento exactamente por qué la experiencia propuesta es necesaria para el negocio', 3),

(8, '¿Qué mides para saber que un diseño fue exitoso?',
 'La reducción del tiempo de tarea y la tasa de finalización de flujos críticos',
 'El NPS y si los usuarios recomendarían el producto a un amigo',
 'El número de tickets de soporte relacionados con confusión de interfaz que disminuyen',
 'La puntuación en tests de usabilidad estructurados con métricas predefinidas de SUS', 4);

-- ── 9. Sistemas Empresariales ─────────────────────────────────
INSERT INTO psychometric_questions (specialization_id, question_text, option_a, option_b, option_c, option_d, order_index) VALUES
(9, 'Una empresa quiere implementar SAP pero el presupuesto se redujo a la mitad. ¿Qué propones?',
 'Hago un análisis de brechas y priorizo los módulos de mayor retorno sobre inversión',
 'Propongo una implementación por fases: el módulo más urgente primero y el resto después',
 'Involucro a los líderes de cada área para que definan sus prioridades críticas',
 'Evalúo alternativas de ERP open source antes de comprometer el presupuesto total', 1),

(9, 'Los usuarios finales rechazan el nuevo sistema ERP. ¿Cómo lo manejas?',
 'Analizo las métricas de adopción para identificar los módulos con mayor resistencia',
 'Inicio quick wins: muestro cómo el sistema ya les ahorra tiempo en el día a día',
 'Formo champions internos: usuarios clave que lideren la adopción entre sus compañeros',
 'Documento los bugs y fricciones de usabilidad reportados y los presento al proveedor', 2),

(9, '¿Qué aspecto de los sistemas empresariales te resulta más valioso?',
 'La integración de datos entre áreas: que finanzas, operaciones y RR.HH. hablen entre sí',
 'La automatización de procesos repetitivos que liberan tiempo al equipo humano',
 'El Business Intelligence: los dashboards que ayudan a la dirección a tomar mejores decisiones',
 'La trazabilidad y el compliance: que cada transacción esté auditada y sea reproducible', 3),

(9, 'Al finalizar una implementación de ERP, ¿cómo mides el éxito?',
 'Con KPIs de eficiencia: reducción en tiempo de procesos y errores de datos',
 'Con la velocidad de adopción: ¿cuántos usuarios activos tiene el sistema a los 30 días?',
 'Con la satisfacción del equipo directivo y de los usuarios finales por separado',
 'Con el cumplimiento total del scope acordado en el contrato de implementación', 4);

-- ── 10. Investigación e Innovación ────────────────────────────
INSERT INTO psychometric_questions (specialization_id, question_text, option_a, option_b, option_c, option_d, order_index) VALUES
(10, 'Lees un paper con resultados que contradicen tu hipótesis inicial. ¿Qué haces?',
 'Reviso la metodología detalladamente para encontrar posibles limitaciones del estudio',
 'Actualizo mi hipótesis inmediatamente: los datos mandan sobre la intuición',
 'Comparto el paper con mis colegas para debatirlo en conjunto antes de concluir',
 'Replico el experimento en mi entorno para verificar si los resultados son reproducibles', 1),

(10, '¿Cuál de estas fases de un proyecto de investigación te entusiasma más?',
 'El diseño metodológico: construir el andamiaje experimental correcto desde el inicio',
 'El prototipado de la idea: ver si algo que nadie hizo antes funciona en la práctica',
 'La difusión: publicar los hallazgos para que otros investigadores los construyan encima',
 'La validación rigurosa: demostrar que los resultados son sólidos y no artefactos estadísticos', 2),

(10, '¿Cómo decides cuándo una idea innovadora vale la pena ser perseguida?',
 'Cuando existe un gap documentado en el estado del arte que mi idea puede cerrar',
 'Cuando puedo tener un prototipo funcional en menos de 2 semanas para testear la hipótesis',
 'Cuando hay al menos un stakeholder con problema real que la idea resolvería',
 'Cuando la idea supera un análisis de factibilidad técnica, legal y de impacto medible', 3),

(10, 'Tu proyecto de innovación pierde financiamiento a mitad de camino. ¿Qué haces?',
 'Reduzco el alcance al núcleo de la hipótesis principal y busco nuevos fondos específicos',
 'Busco un partner de industria que se beneficie de los resultados y cofinancie el resto',
 'Abro el proyecto como investigación colaborativa abierta para atraer otros investigadores',
 'Publico los avances hasta la fecha como paper preliminar para no perder el trabajo hecho', 4);
