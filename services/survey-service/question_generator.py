import random

SQL_FILE = r"C:\Users\corne\OneDrive\Escritorio\HC\REVO\database\03_seed_questions.sql"

# Definimos 10 ramas, cada una con un tema
BRANCHES = [
    (1, "Desarrollo de Software", ["programar", "diseñar interfaces", "escribir código limpio", "crear aplicaciones web", "desarrollar apps móviles", "estructurar algoritmos", "depurar código", "usar frameworks modernos", "construir APIs", "trabajar con bases de datos relacionales"]),
    (2, "Data Science & IA", ["analizar datos", "entrenar modelos", "usar machine learning", "encontrar patrones en datos", "aplicar estadística", "usar Python/R", "visualizar métricas numéricas", "limpiar bases de datos grandes", "programar redes neuronales", "procesar lenguaje natural"]),
    (3, "Infraestructura & Cloud", ["configurar servidores", "orquestar contenedores", "usar AWS/Azure", "mantener redes globales", "automatizar despliegues", "monitorear tiempos de actividad", "configurar routers físicos", "usar Linux a fondo", "balancear cargas de tráfico", "gestionar permisos de red"]),
    (4, "Ciberseguridad", ["encontrar vulnerabilidades", "actuar como hacker ético", "analizar malware", "proteger datos sensibles", "auditar sistemas", "investigar ataques cibernéticos", "encriptar información", "usar Kali Linux", "hacer pruebas de penetración", "planificar respuestas a incidentes"]),
    (5, "Soporte Técnico & IT Ops", ["ayudar a usuarios", "reparar computadoras", "diagnosticar errores de Windows", "configurar impresoras corporativas", "atender tickets de servicio", "mantener inventario de IT", "resolver problemas de red locales", "documentar fallas comunes", "actuar con paciencia", "instalar software de ofimática"]),
    (6, "QA & Testing", ["encontrar bugs", "automatizar pruebas", "ser meticuloso", "escribir casos de prueba", "medir el rendimiento de la app", "garantizar la calidad total", "romper aplicaciones intencionalmente", "usar Selenium/Cypress", "verificar accesibilidad", "revisar flujos críticos"]),
    (7, "Gestión y Producto", ["liderar equipos técnicos", "usar Scrum o Kanban", "definir requerimientos", "hablar con clientes", "planificar sprints", "evitar bloqueos del equipo", "entender el modelo de negocio", "hacer diagramas de Gantt", "priorizar tareas", "medir KPIs del producto"]),
    (8, "Diseño UX/UI", ["crear wireframes", "entender al usuario final", "diseñar experiencias fluidas", "usar Figma", "combinar colores armónicamente", "diseñar flujos de navegación", "entrevistar usuarios", "crear prototipos interactivos", "aplicar psicología del diseño", "mejorar la accesibilidad visual"]),
    (9, "Sistemas Empresariales", ["parametrizar SAP/Oracle", "entender flujos financieros", "optimizar recursos humanos", "integrar CRMs", "gestionar inventarios digitales", "automatizar contabilidad", "auditar procesos de negocio", "implementar Salesforce", "modelar flujos de suministro", "traducir leyes a software"]),
    (10, "Investigación e Innovación", ["programar en bajo nivel", "explorar Blockchain", "conectar Arduino y sensores", "leer papers académicos", "trabajar en Realidad Virtual", "optimizar compiladores", "crear algoritmos matemáticos puros", "investigar computación cuántica", "soldar microcontroladores", "escribir código en C/Rust"])
]

# Definimos 4 categorías
CATEGORIES = ["academic", "skills", "interests", "personality"]

def main():
    questions = []
    order = 1
    for b_id, b_name, topics in BRANCHES:
        for i, topic in enumerate(topics):
            # Alternar frases
            if i % 4 == 0:
                text = f"Me considero extremadamente hábil para {topic} en mi día a día."
                cat = "skills"
            elif i % 4 == 1:
                text = f"Siento un profundo interés por aprender a {topic} en el nivel más avanzado."
                cat = "interests"
            elif i % 4 == 2:
                text = f"Mi personalidad metódica encaja perfectamente con la tarea de {topic}."
                cat = "personality"
            else:
                text = f"A nivel académico, destaco ampliamente al tener que {topic}."
                cat = "academic"
            
            # Formato final para Insert
            questions.append(f"('{text}', '{cat}', {b_id}, 'Desacuerdo', 'Totalmente', {order})")
            order += 1
            
    # Mezclamos
    random.shuffle(questions)
            
    with open(SQL_FILE, 'w', encoding='utf-8') as f:
        f.write("-- ============================================================\n")
        f.write("-- Script 03: Seed de Preguntas ADAPTATIVAS (100 preguntas)\n")
        f.write("-- ============================================================\n\n")
        f.write("TRUNCATE TABLE questions CASCADE;\n")
        f.write("ALTER SEQUENCE questions_id_seq RESTART WITH 1;\n\n")
        f.write("INSERT INTO questions (text, category, specialization_id, min_label, max_label, order_index)\nVALUES\n")
        f.write(",\n".join(questions) + ";\n\n")
        f.write("DO $$ BEGIN RAISE NOTICE '✅ 100 preguntas adaptativas sembradas en revo_db'; END $$;\n")

if __name__ == '__main__':
    main()
