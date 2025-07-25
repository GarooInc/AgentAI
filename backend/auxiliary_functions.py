import json
import os
import io
import random
import string
import requests

from datetime import datetime

import pandas as pd
import matplotlib.pyplot as plt
import sqlite3


## GLOBALES
_db_connection = None



def load_json(filename: str) -> dict:
    """
    Carga un archivo JSON y devuelve su contenido como un diccionario.
    """
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)
    
def get_db() -> str:
    try:
        # Corrige la ruta al archivo de configuración
        config_path = os.path.abspath('backend/config/db_conn.json')
        
        # Carga el archivo JSON
        db_conn_json = load_json(config_path)
        
        # Extrae el filepath de la base de datos o usa el valor por defecto
        db_filepath = db_conn_json.get('db_filepath', 'data/resv.db')
        
        # Convierte la ruta de la base de datos a absoluta
        return os.path.abspath(db_filepath)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        # Manejo de errores en caso de que el archivo no exista o sea inválido
        raise RuntimeError(f"Error al cargar la configuración de la base de datos: {e}")
    
# Variable global para la conexión a la base de datos
_db_connection = None

def get_db_connection() -> sqlite3.Connection:
    """
    Devuelve una conexión global a la base de datos. Si no existe, la crea.
    """
    global _db_connection

    if _db_connection is None:
        db_path = get_db()  # Obtiene la ruta de la base de datos
        _db_connection = sqlite3.connect(db_path)
        log(f"Conexión a la base de datos establecida: {db_path}")

    return _db_connection

def close_db_connection():
    """
    Cierra la conexión global a la base de datos si está abierta.
    """
    global _db_connection

    if _db_connection is not None:
        _db_connection.close()
        log("Conexión a la base de datos cerrada.")
        _db_connection = None



def upload_to_file_server(file_path: str = None, buf: io.BytesIO = None) -> str:
    """
    Sube un archivo (desde ruta local o buffer) al servidor y devuelve la URL pública.
    """

    # Genera nombre único
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rand_suffix = "".join(random.choices(string.ascii_letters + string.digits, k=3))
    filename = f"{timestamp}-{rand_suffix}.png"

    # Decide fuente de datos
    if buf is not None:
        file_data = (filename, buf, "image/png")
    elif file_path is not None:
        with open(file_path, "rb") as f:
            file_data = (filename, f, "image/png")
    else:
        raise ValueError("Debes proporcionar file_path o buf")

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    resp = requests.post(
        "https://agents.garooinc.com/upload/itzana-agents",
        files={"file": file_data},
        headers=headers
    )
    resp.raise_for_status()
    result = resp.json()

    # la respuesta es asi:
    # {
    #  "message": "Archivo subido correctamente como '1617b5d2-92b0-4594-9d78-657408721b75.png'",
    #  "url": "https://agents.garooinc.com/files/itzana-agents/1617b5d2-92b0-4594-9d78-657408721b75.png"

    if "url" not in result:
        raise ValueError("Respuesta inesperada del servidor: no se encontró la URL")
    return result["url"]  # Devuelve la URL pública del archivo subido

    

def execute_graph_agent_code(code: str, table_data: list, output_file:str = "out.png") -> str:
    """
    Executes python code generated from the graph_code_agent and uploads the resulting image to the file server.
    """
    img_buf = io.BytesIO()

    code = code.replace("plt.show()", "")

    exec_globals = {
        "table_data": table_data,
        "pd": pd,
        "plt": plt,
        "img_buf": img_buf
    }

    print(f"\n[DEBUG] - Ejecutando código del agente de gráficos:\n{code}\n")
    try:
        exec(code, exec_globals)
    except Exception as e:
        raise RuntimeError(f"Error al ejecutar el código del agente de gráficos: {e}")
    
    if img_buf.getbuffer().nbytes == 0:
        raise ValueError("El código del agente de gráficos no generó una imagen válida.")
    
    public_url = upload_to_file_server(buf=img_buf)
    # print(f"[DEBUG] - Imagen subida correctamente: {public_url}")
    return public_url

def log(message: str):
    """
    Prints debug information to the console with a timestamp.
    """
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[DEBUG] [{timestamp}] - {message}")