-- ============================================================
-- REVO DB - Script 12: consentimiento informado y documentos legales
-- ============================================================
-- REVO recoge datos de orientacion vocacional de estudiantes y el plan de
-- negocio contempla dos usos adicionales al servicio en si:
--   a) compartir informacion agregada con universidades y academias
--   b) usar las respuestas para entrenar el modelo
--
-- Bajo la Ley 29733 (Proteccion de Datos Personales, Peru) y su reglamento,
-- esos dos usos son FINALIDADES DISTINTAS del servicio. El consentimiento
-- para ellas tiene que ser libre, previo, expreso, informado e inequivoco, y
-- no puede condicionarse a poder usar la plataforma. De ahi el diseno:
--
--   terms + privacy  -> obligatorios, sin ellos no hay cuenta
--   data_commercial  -> opcional, casilla aparte, desmarcada por defecto
--   ai_training      -> opcional, casilla aparte, desmarcada por defecto
--
-- Cada aceptacion guarda QUE version del texto se acepto, CUANDO y DESDE
-- DONDE. Un consentimiento sin version es inservible como prueba: si el
-- texto cambia, no hay forma de saber a que acepto realmente el alumno.
--
-- AVISO: el contenido de los documentos es un borrador tecnico. Antes de
-- salir a produccion con la parte comercial debe revisarlo un abogado.
-- ============================================================

-- ------------------------------------------------------------
-- 1. Documentos legales versionados
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS legal_documents (
    id             SERIAL PRIMARY KEY,
    doc_type       VARCHAR(30)  NOT NULL
                                CHECK (doc_type IN ('terms','privacy','data_commercial','ai_training')),
    version        VARCHAR(20)  NOT NULL,
    title          VARCHAR(200) NOT NULL,
    summary        TEXT         NOT NULL,   -- el resumen corto de la casilla
    body_md        TEXT         NOT NULL,   -- el texto completo del "Leer mas"
    is_required    BOOLEAN      NOT NULL DEFAULT FALSE,
    effective_from TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    is_current     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (doc_type, version)
);

-- Solo puede haber una version vigente por tipo de documento. Un indice
-- parcial unico lo garantiza en la base de datos, no en la aplicacion:
-- dos versiones vigentes a la vez significan que no se sabe que acepto el
-- alumno, y eso invalida el consentimiento entero.
CREATE UNIQUE INDEX IF NOT EXISTS idx_legal_vigente
    ON legal_documents (doc_type) WHERE is_current;

-- ------------------------------------------------------------
-- 2. Consentimientos otorgados
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_consents (
    id          SERIAL       PRIMARY KEY,
    user_id     INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    doc_type    VARCHAR(30)  NOT NULL
                             CHECK (doc_type IN ('terms','privacy','data_commercial','ai_training')),
    doc_version VARCHAR(20)  NOT NULL,
    granted     BOOLEAN      NOT NULL,
    granted_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    revoked_at  TIMESTAMPTZ,

    -- Evidencia de la aceptacion. La IP es un dato personal en si misma:
    -- se guarda porque la ley pide poder acreditar el consentimiento, y se
    -- borra con la cuenta por el ON DELETE CASCADE de arriba.
    ip_address  INET,
    user_agent  VARCHAR(400),

    UNIQUE (user_id, doc_type, doc_version)
);

CREATE INDEX IF NOT EXISTS idx_consents_user ON user_consents(user_id);

-- Consulta tipica: "de los alumnos que autorizaron uso comercial, cuantos
-- siguen vigentes". Sin este indice parcial es una pasada completa por tabla.
CREATE INDEX IF NOT EXISTS idx_consents_vigentes
    ON user_consents(doc_type, user_id) WHERE granted AND revoked_at IS NULL;

-- ------------------------------------------------------------
-- 3. Vista del estado actual de consentimiento
-- ------------------------------------------------------------
-- Evita que cada servicio reimplemente "cual es el consentimiento vigente":
-- la ultima decision por tipo de documento, sin revocar.
--
-- security_invoker=true es imprescindible: sin el, la vista consulta con los
-- permisos de SU DUENO y se convierte en un tunel que rodea el RLS de la
-- tabla de abajo. Con el activado, cada consulta a la vista aplica las
-- politicas del rol que pregunta.
CREATE OR REPLACE VIEW user_consent_state WITH (security_invoker = true) AS
SELECT DISTINCT ON (uc.user_id, uc.doc_type)
    uc.user_id,
    uc.doc_type,
    uc.doc_version,
    uc.granted AND uc.revoked_at IS NULL AS vigente,
    uc.granted_at,
    uc.revoked_at
FROM user_consents uc
ORDER BY uc.user_id, uc.doc_type, uc.granted_at DESC;

-- ------------------------------------------------------------
-- 4. RLS
-- ------------------------------------------------------------
-- Los documentos legales son publicos: hay que poder leerlos ANTES de tener
-- cuenta, porque se aceptan durante el registro.
ALTER TABLE legal_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE legal_documents FORCE ROW LEVEL SECURITY;

GRANT SELECT ON legal_documents TO revo_app, revo_service;
GRANT INSERT, UPDATE ON legal_documents TO revo_app;

DROP POLICY IF EXISTS legales_lectura ON legal_documents;
CREATE POLICY legales_lectura ON legal_documents FOR SELECT USING (true);

DROP POLICY IF EXISTS legales_escritura ON legal_documents;
CREATE POLICY legales_escritura ON legal_documents FOR ALL
    USING (revo_es_admin()) WITH CHECK (revo_es_admin());

-- Los consentimientos son datos personales del alumno.
ALTER TABLE user_consents ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_consents FORCE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE ON user_consents TO revo_app;
-- El servicio necesita saber quien autorizo el entrenamiento antes de
-- meter su vector en el dataset.
GRANT SELECT ON user_consents TO revo_service;

GRANT SELECT ON user_consent_state TO revo_app, revo_service;

-- Las secuencias de estas dos tablas nacen despues del GRANT masivo de la
-- migracion 10, asi que se conceden aqui de forma explicita. (La migracion 10
-- deja ademas un ALTER DEFAULT PRIVILEGES para que esto no vuelva a hacer
-- falta en migraciones futuras, pero no retroactivamente sobre estas.)
GRANT USAGE, SELECT ON SEQUENCE legal_documents_id_seq TO revo_app;
GRANT USAGE, SELECT ON SEQUENCE user_consents_id_seq TO revo_app;

DROP POLICY IF EXISTS consentimientos_propios ON user_consents;
CREATE POLICY consentimientos_propios ON user_consents FOR ALL
    USING (revo_es_alumno(user_id) OR revo_es_admin() OR revo_es_servicio())
    WITH CHECK (revo_es_alumno(user_id) OR revo_user_id() IS NULL);
-- El WITH CHECK admite user_id sin contexto porque el consentimiento se
-- graba en el mismo INSERT del registro, cuando el alumno todavia no tiene
-- sesion. La fila queda atada por clave foranea al usuario recien creado.

-- ------------------------------------------------------------
-- 5. Contenido inicial de los documentos
-- ------------------------------------------------------------
INSERT INTO legal_documents (doc_type, version, title, summary, body_md, is_required)
VALUES
(
    'terms', '1.0',
    'Terminos y Condiciones de uso de REVO',
    'Acepto los Terminos y Condiciones y la Politica de Privacidad de REVO.',
$doc$
# Terminos y Condiciones de uso de REVO

**Version 1.0**

## 1. Que es REVO

REVO es una herramienta de orientacion academica dirigida a estudiantes de
Ingenieria de Sistemas. A partir de un cuestionario por fases, estima tu
afinidad con diez especializaciones de la carrera y te sugiere una ruta.

## 2. Que NO es REVO

El resultado es **una sugerencia orientativa, no un diagnostico**. No
sustituye la tutoria academica, la asesoria profesional ni tu propio
criterio. REVO no garantiza resultados academicos ni laborales derivados de
seguir la ruta sugerida, y no se responsabiliza de las decisiones de
matricula o de carrera que tomes a partir de ella.

## 3. Tu cuenta

Para usar REVO necesitas una cuenta con un correo valido. Eres responsable
de la veracidad de los datos que registras y de mantener tu contrasena en
secreto. Si detectas un uso no autorizado de tu cuenta, avisanos.

## 4. Uso aceptable

No esta permitido:

- Automatizar el llenado del cuestionario o falsear respuestas de forma masiva.
- Intentar acceder a datos de otros usuarios.
- Interferir con el funcionamiento del servicio o sus limites de uso.
- Extraer el contenido de la plataforma para reproducirlo o comercializarlo.

## 5. Tus datos

El tratamiento de tus datos personales se rige por la Politica de
Privacidad, que forma parte de estos Terminos. Los usos comerciales y de
entrenamiento del modelo son **opcionales** y se autorizan por separado:
puedes usar REVO con normalidad sin aceptarlos.

## 6. Disponibilidad

REVO se ofrece "tal cual". Podemos modificar, suspender o descontinuar
funciones. Avisaremos con antelacion razonable de los cambios relevantes.

## 7. Cambios en estos Terminos

Si cambiamos estos Terminos, publicaremos una version nueva y te pediremos
que la aceptes de nuevo. La version que aceptaste queda registrada.

## 8. Contacto

Para cualquier consulta sobre estos Terminos, escribe al correo de contacto
publicado en la plataforma.
$doc$,
    TRUE
),
(
    'privacy', '1.0',
    'Politica de Privacidad de REVO',
    'He leido como se tratan mis datos personales.',
$doc$
# Politica de Privacidad de REVO

**Version 1.0**

Esta politica explica que datos recogemos, para que, y que puedes hacer al
respecto. Se rige por la **Ley 29733, Ley de Proteccion de Datos Personales**
del Peru y su reglamento (D.S. 003-2013-JUS).

## 1. Que datos recogemos

**Datos de cuenta.** Nombre completo, correo electronico, codigo de
estudiante y ciclo. Los das tu al registrarte.

**Datos del cuestionario.** Tus respuestas a las preguntas de afinidad y de
perfil profesional, y el tiempo que tardas en responderlas.

**Resultados.** La especializacion recomendada, tu nivel de afinidad con
cada una y tu valoracion sobre si el resultado te representa.

**Datos tecnicos.** Direccion IP, tipo de navegador y registro de accesos.
Se usan para seguridad y para evitar abusos del servicio.

## 2. Para que los usamos

**Necesario para el servicio** (base legal: ejecucion del servicio que
solicitas):

- Calcular y mostrarte tu resultado.
- Guardar tu historial para que puedas consultarlo.
- Mantener tu sesion y proteger la plataforma frente a abusos.

**Opcional, solo si lo autorizas expresamente** (base legal: tu
consentimiento, revocable en cualquier momento):

- **Uso comercial con instituciones educativas.** Compartir informacion
  sobre tendencias de afinidad con universidades y academias, para que
  disenen su oferta formativa.
- **Entrenamiento del modelo.** Usar tus respuestas y tu resultado para
  mejorar la precision del modelo de recomendacion.

**No condicionamos el uso de REVO a que aceptes los usos opcionales.**
Puedes rechazarlos y la plataforma funciona igual.

## 3. Como se comparte la informacion comercial

Si autorizas el uso comercial, la informacion que se comparte con terceros
es **agregada y seudonimizada**: estadisticas por ciclo, por especializacion
y por tendencia. No se entrega tu nombre, tu correo ni tu codigo de
estudiante, y no se entregan respuestas individuales atribuibles a una
persona identificada.

Los terceros que reciban esa informacion quedan obligados por contrato a no
reidentificar a ninguna persona.

## 4. Cuanto tiempo los guardamos

- Datos de cuenta: mientras la cuenta este activa.
- Cuestionarios y resultados: mientras la cuenta este activa, para tu historial.
- Registros tecnicos de seguridad: hasta 12 meses.
- Registros de consentimiento: mientras dure la relacion y el plazo legal de
  prescripcion posterior, porque son la prueba de que autorizaste cada uso.

Al eliminar tu cuenta se borran tus datos personales identificables. Lo que
ya se haya incorporado de forma agregada y seudonimizada a estadisticas o al
entrenamiento del modelo no es reversible, porque en ese estado ya no esta
asociado a ti.

## 5. Tus derechos

La Ley 29733 te reconoce los derechos de **acceso, rectificacion,
cancelacion y oposicion** (derechos ARCO), ademas del derecho a revocar tu
consentimiento.

Puedes ejercerlos desde tu perfil o escribiendo al correo de contacto. Las
casillas opcionales se pueden desmarcar en cualquier momento, y a partir de
ese momento dejamos de usar tus datos para esa finalidad.

Si consideras que no atendimos tu solicitud, puedes acudir a la **Autoridad
Nacional de Proteccion de Datos Personales** del Ministerio de Justicia.

## 6. Seguridad

Las contrasenas se guardan cifradas con bcrypt y nunca en claro. El acceso a
la base de datos esta restringido por politicas de seguridad a nivel de fila:
cada consulta solo alcanza las filas del alumno que la origina. Las
comunicaciones viajan cifradas con TLS.

## 7. Menores de edad

REVO esta dirigida a estudiantes universitarios. Si eres menor de 14 anos
necesitas la autorizacion de tu padre, madre o tutor conforme al reglamento
de la Ley 29733.

## 8. Cambios

Si cambiamos esta politica publicaremos una version nueva y te pediremos que
la revises. Los usos opcionales que ya rechazaste seguiran rechazados.
$doc$,
    TRUE
),
(
    'data_commercial', '1.0',
    'Uso comercial de informacion agregada',
    'Autorizo que REVO comparta informacion agregada y seudonimizada de mis resultados con universidades y academias. Es opcional y puedo retirarlo cuando quiera.',
$doc$
# Uso comercial de informacion agregada

**Version 1.0 — OPCIONAL**

## Que estas autorizando

Que REVO incluya tus resultados, **de forma agregada y seudonimizada**, en
informes y conjuntos de datos que se comparten o comercializan con
universidades, institutos y academias.

## Que se comparte exactamente

- Tu nivel de afinidad con cada una de las diez especializaciones.
- Tu ciclo academico y la especializacion resultante.
- Tendencias calculadas sobre grupos de estudiantes.

## Que NO se comparte

- Tu nombre.
- Tu correo electronico.
- Tu codigo de estudiante.
- Cualquier dato que permita identificarte de forma directa.

## Para que lo usan esas instituciones

Para disenar su oferta de cursos y programas segun la demanda real de
especializacion que muestran los estudiantes.

## Si no lo autorizas

REVO funciona exactamente igual. Tu resultado, tu historial y todas las
funciones siguen disponibles. Esta casilla no condiciona nada.

## Como retirarlo

Desde tu perfil, en cualquier momento. Al retirarlo dejamos de incluir tus
datos en nuevos informes. Los informes ya entregados no se pueden retirar
porque la informacion en ellos ya no esta asociada a ti.
$doc$,
    FALSE
),
(
    'ai_training', '1.0',
    'Uso de mis respuestas para entrenar el modelo',
    'Autorizo que mis respuestas se usen para entrenar y mejorar el modelo de recomendacion de REVO. Es opcional y puedo retirarlo cuando quiera.',
$doc$
# Uso de mis respuestas para entrenar el modelo

**Version 1.0 — OPCIONAL**

## Que estas autorizando

Que tus respuestas al cuestionario y el resultado que obtuviste se
incorporen al conjunto de datos con el que se entrena el modelo de
recomendacion de REVO.

## Por que sirve

El modelo mejora cuando aprende de respuestas de estudiantes reales en lugar
de solo datos simulados. Cuantos mas casos reales, mas fiable es la
recomendacion para quien venga despues.

## Que se incorpora

Tu vector de afinidad (diez valores numericos) y la especializacion
resultante. **Sin ningun dato identificativo asociado**: al dataset de
entrenamiento no llega tu nombre, ni tu correo, ni tu codigo.

## Si no lo autorizas

REVO funciona exactamente igual y tu resultado es el mismo. Simplemente tus
datos no entran al entrenamiento.

## Como retirarlo

Desde tu perfil, en cualquier momento. Dejamos de usar tus datos en los
entrenamientos siguientes. Un modelo ya entrenado no se puede "desentrenar":
los pesos actuales no se pueden revertir a mano, pero tus datos salen del
conjunto y no participan en ningun entrenamiento posterior.
$doc$,
    FALSE
)
ON CONFLICT (doc_type, version) DO NOTHING;

DO $verificacion$
DECLARE
    faltan INTEGER;
BEGIN
    SELECT count(*) INTO faltan
    FROM (VALUES ('terms'),('privacy'),('data_commercial'),('ai_training')) AS t(tipo)
    WHERE NOT EXISTS (
        SELECT 1 FROM legal_documents d WHERE d.doc_type = t.tipo AND d.is_current
    );

    IF faltan > 0 THEN
        RAISE EXCEPTION 'Faltan % documentos legales vigentes', faltan;
    END IF;

    RAISE NOTICE 'Consentimiento informado listo: 4 documentos vigentes';
END
$verificacion$;
