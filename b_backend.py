import re
import mysql.connector
import pandas as pd
import streamlit as st
import google.generativeai as genai

# Configurar API de Gemini desde secrets.toml
genai.configure(api_key=st.secrets["general"]["api_key"])
model = genai.GenerativeModel("gemini-1.5-flash")
chat = model.start_chat()

# Configuración base de datos desde secrets.toml
db_config = {
    'host': st.secrets["mysql"]["host"],
    'database': st.secrets["mysql"]["database"],
    'user': st.secrets["mysql"]["user"],
    'password': st.secrets["mysql"]["password"],
    'port': st.secrets["mysql"]["port"]
}

# Guarda el último SQL generado por la IA
ultima_sql = ""

# Función para generar SQL desde lenguaje natural
def obtener_sql_de_gemini(pregunta):
    estructura_vista = """
    Realiza todas las consultas exclusivamente sobre la vista llamada OML_Business_Intelligence.
    Sus columnas son:
    - NOMBRE_EMPRESA: nombre de la empresa que hace la solicitud.
    - NOMBRE_SOLICITUD: estado de la solicitud (Cerrada, Asignada, Pendiente Asignar, En sitio).
    - FECHA_SOLICITUD: fecha de la solicitud para ejecutar la orden.
    - PRECIO_PARAM: valor económico parametrizado.

    IMPORTANTE:
    Cuando filtres por estado (por ejemplo: NOMBRE_SOLICITUD = 'Cerrada'), usa esta forma exacta:
    CONVERT(NOMBRE_SOLICITUD USING utf8mb4) COLLATE utf8mb4_general_ci = 'Cerrada'
    
    Solo usa esa vista. No inventes otras tablas como 'Facturas' ni 'Solicitudes'.
    """

    prompt = f"{estructura_vista}\nConvierte esta pregunta en una consulta SQL válida para MySQL:\n{pregunta}"
    response = chat.send_message(prompt)
    match = re.search(r"(SELECT\s.+?;)", response.text, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else None

# Función para ejecutar el SQL generado
def ejecutar_sql(query):
    if not query:
        return pd.DataFrame()
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute(query)
    data = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    df = pd.DataFrame(data, columns=columns)
    cursor.close()
    conn.close()
    return df

# Función para analizar los resultados con IA
def analizar_resultados(df):
    if df.empty:
        return "No se encontraron resultados."

    texto_tabla = df.to_string(index=False)
    prompt = f"""
    A continuación tienes los resultados de una consulta a una base de datos:

    {texto_tabla}

    1. Muestra los datos en forma de tabla clara.
    2. Da un análisis experto de los resultados.
    3. Ofrece una recomendación útil para el negocio.
    """
    response = chat.send_message(prompt)
    return response.text

# Función principal llamada desde app.py
def consulta(pregunta):
    global ultima_sql
    sql = obtener_sql_de_gemini(pregunta)
    ultima_sql = sql  # guardamos el último SQL generado

    if sql:
        df = ejecutar_sql(sql)
        analisis = analizar_resultados(df)
        return df, analisis
    else:
        return pd.DataFrame(), "No se pudo generar una consulta SQL válida."
