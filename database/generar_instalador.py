# -*- coding: utf-8 -*-
"""Une las 17 migraciones en un solo fichero para el editor SQL de Supabase.

El orden es explicito y no alfabetico: `01b_schema_sync` va DESPUES de
`01_init`, porque sincroniza columnas sobre tablas que aquel crea. Ordenar
por nombre lo pondria antes y fallaria.
"""
import io, os

BASE = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(BASE, 'INSTALAR_SUPABASE.sql')

ORDEN = [
    ('01_init.sql',                   'Tablas base, extensiones e indices'),
    ('01b_schema_sync.sql',           'Columnas anadidas despues de la version inicial'),
    ('02_seed_specializations.sql',   'Las diez especializaciones'),
    ('03_seed_questions.sql',         'Banco de preguntas del cuestionario'),
    ('04_seed_training_data.sql',     'Datos de arranque para entrenar el modelo'),
    ('05_seed_users.sql',             'Usuarios de ejemplo'),
    ('06_fix_passwords.sql',          'Corrige el hash de las contrasenas de ejemplo'),
    ('07_seed_courses.sql',           'Catalogo de cursos'),
    ('08_seed_jobs.sql',              'Catalogo de empleos'),
    ('09_psychometric_questions.sql', 'Preguntas de la fase psicometrica'),
    ('10_rls.sql',                    'Seguridad por filas y roles revo_app / revo_service'),
    ('12_consentimiento.sql',         'Consentimiento informado versionado (Ley 29733)'),
    ('13_registro.sql',               'Registro y verificacion de correo'),
    ('14_cuentas.sql',                'Gestion de cuentas y secretos caducados'),
    ('15_roles_por_servicio.sql',     'Un rol de base de datos por microservicio'),
    ('17_mover_catalogos.sql',        'Cursos y empleos pasan a ml-service'),
    ('18_compatibilidad_gestionado.sql', 'IMPRESCINDIBLE en Supabase: sin esto nadie inicia sesion'),
]

CABECERA = '''-- ============================================================================
--  REVO - INSTALACION COMPLETA
--  Pegar entero en el editor SQL de Supabase y pulsar Run.
-- ============================================================================
--
--  QUE HACE
--    Crea el esquema completo, las politicas de seguridad por filas, los
--    cuatro roles de base de datos y los datos de arranque. Reune las 17
--    migraciones de database/ en el orden correcto.
--
--  ANTES DE EJECUTAR
--    Baja hasta el final del fichero, al bloque PASO FINAL, y sustituye las
--    cuatro contrasenas de ejemplo por otras de verdad. El script se niega a
--    terminar si no lo haces.
--
--    Para generarlas:
--        python -c "import secrets; print(secrets.token_urlsafe(36))"
--
--    Tienen que ser CUATRO DISTINTAS. Si repites la misma, cualquiera que
--    consiga una credencial las tiene todas y la separacion entre servicios
--    deja de significar nada.
--
--  SE PUEDE VOLVER A EJECUTAR
--    Todo el fichero es idempotente: crea lo que falta y respeta lo que ya
--    existe. Si algo falla a mitad, corrige y vuelve a ejecutarlo entero.
--
--  DESPUES
--    Al final se imprimen dos comprobaciones. Los cuatro roles tienen que
--    salir con rolsuper = false y rolbypassrls = false. Si alguno sale true,
--    ese servicio puede leerlo todo y RLS no protege nada.
-- ============================================================================


'''

PIE = '''

-- ############################################################################
--
--   PASO FINAL - CONTRASENAS DE LOS CUATRO ROLES
--
--   >>> EDITA LAS CUATRO LINEAS MARCADAS ANTES DE EJECUTAR <<<
--
--   Cada microservicio se conecta con SU PROPIO rol. Es lo que impide que el
--   cuestionario pueda leer la tabla de usuarios aunque una consulta se
--   equivoque: la frontera la pone la base de datos, no el codigo.
--
-- ############################################################################

DO $revo_final$
DECLARE
    -- ↓↓↓ CAMBIA ESTAS CUATRO ↓↓↓
    clave_auth    text := 'CAMBIAME-auth';
    clave_survey  text := 'CAMBIAME-survey';
    clave_ml      text := 'CAMBIAME-ml';
    clave_service text := 'CAMBIAME-service';
    -- ↑↑↑ CAMBIA ESTAS CUATRO ↑↑↑

    claves text[];
BEGIN
    claves := ARRAY[clave_auth, clave_survey, clave_ml, clave_service];

    -- Falla en vez de dejar la base abierta con contrasenas publicadas en
    -- un fichero que esta en GitHub.
    IF EXISTS (SELECT 1 FROM unnest(claves) c WHERE c LIKE 'CAMBIAME-%') THEN
        RAISE EXCEPTION
            'Falta cambiar las contrasenas del bloque PASO FINAL. Estan en el fichero, o sea que son publicas.';
    END IF;

    -- Cuatro iguales dejarian los roles separados solo de nombre.
    IF (SELECT count(DISTINCT c) FROM unnest(claves) c) < 4 THEN
        RAISE EXCEPTION
            'Las cuatro contrasenas tienen que ser distintas: con una repetida, quien consiga una credencial las tiene todas.';
    END IF;

    IF (SELECT min(length(c)) FROM unnest(claves) c) < 20 THEN
        RAISE EXCEPTION 'Alguna contrasena tiene menos de 20 caracteres.';
    END IF;

    -- Se pasan como parametro, no concatenadas: una comilla simple dentro de
    -- la contrasena romperia la sentencia si se pegara a mano.
    EXECUTE format('ALTER ROLE revo_auth    WITH PASSWORD %L', clave_auth);
    EXECUTE format('ALTER ROLE revo_survey  WITH PASSWORD %L', clave_survey);
    EXECUTE format('ALTER ROLE revo_ml      WITH PASSWORD %L', clave_ml);
    EXECUTE format('ALTER ROLE revo_service WITH PASSWORD %L', clave_service);

    -- revo_app quedo sin permisos en la migracion 15. Un rol sin uso que
    -- todavia puede conectarse es una puerta que nadie vigila.
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'revo_app') THEN
        EXECUTE 'ALTER ROLE revo_app NOLOGIN';
    END IF;

    RAISE NOTICE 'Contrasenas asignadas a revo_auth, revo_survey, revo_ml y revo_service.';
END
$revo_final$;


-- ############################################################################
--   COMPROBACIONES
-- ############################################################################

-- 1) Los cuatro roles existen y ninguno se salta la seguridad por filas.
--    rolsuper y rolbypassrls tienen que salir en false los cuatro.
SELECT rolname AS rol,
       rolsuper AS es_superusuario,
       rolbypassrls AS se_salta_rls,
       rolcanlogin AS puede_conectarse
FROM pg_roles
WHERE rolname LIKE 'revo\\_%'
ORDER BY rolname;

-- 2) Las tablas con datos de alumnos tienen RLS activo.
SELECT tablename AS tabla,
       rowsecurity AS rls_activo
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY rowsecurity, tablename;
'''

partes = [CABECERA]
for fichero, resumen in ORDEN:
    ruta = os.path.join(BASE, fichero)
    if not os.path.exists(ruta):
        raise SystemExit('FALTA: ' + fichero)
    contenido = io.open(ruta, encoding='utf-8').read().rstrip()
    partes.append(
        '\n\n-- ############################################################################\n'
        f'--   {fichero}\n'
        f'--   {resumen}\n'
        '-- ############################################################################\n\n'
    )
    partes.append(contenido)

partes.append(PIE)
texto = ''.join(partes)
io.open(SALIDA, 'w', encoding='utf-8', newline='\n').write(texto)

print(f'Generado: {SALIDA}')
print(f'  migraciones unidas: {len(ORDEN)}')
print(f'  lineas: {texto.count(chr(10)):,}')
print(f'  tamano: {len(texto.encode("utf-8"))/1024:.0f} KB')
