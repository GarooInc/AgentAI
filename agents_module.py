import sqlite3
from typing import Any, List, Dict, TypedDict
from agents import Agent, function_tool, AgentOutputSchema

from helper import get_db, get_itzana_knowledge, get_wholesalers_list, get_reservations_columns
from typing_extensions import TypedDict


# ----------------------------------
#         Analysis Agent 
# ----------------------------------

reservations_columns = get_reservations_columns()
wholesalers_list = get_wholesalers_list()
itzana_knowledge = get_itzana_knowledge()

class AnalysisOutput(TypedDict):
    """
    Esquema de salida estricto:
    - title: titulo de la respuesta. 
    - returned_json: lista de objetos con los resultados de la consulta
    - findings: resumen de los hallazgos principales
    - methodology: descripción del proceso y filtros aplicados
    """
    title: str
    returned_json: List[Dict[str, Any]]
    findings: str
    methodology: str


@function_tool
def execute_query_to_sqlite(query: str) -> Any:
    """Ejecuta la consulta SQL en Itzana.db y retorna resultados."""
    conn = None

    print(f"\n[DEBUG] - Consulta SQL generada por el agente:\n{query}")  # <-- Agrega este print

    try:
        conn = sqlite3.connect(get_db())
        cursor = conn.cursor()
        cursor.execute(query)
        if query.strip().lower().startswith("select"):
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            result = [dict(zip(columns, row)) for row in rows]
        else:
            conn.commit()
            result = [{"mensaje": f"Consulta ejecutada. Filas afectadas: {cursor.rowcount}"}]
        return result
    except Exception as e:
        return [{"error": f"Error al ejecutar la consulta: {str(e)}"}]
    finally:
        if conn:
            conn.close()

# Instrucciones para el agente de reservaciones
reservations_instructions = f"""
Eres un analista de datos con acceso a una base SQLite llamada `resv.db`. La tabla principal es `reservations`.
El esquema de la tabla `reservations` es el siguiente: {reservations_columns}.

Tu tarea es, a partir de la pregunta del usuario, **generar una consulta SQL (SQLite)** sobre la tabla `reservations` que permita responder a la pregunta. Debes razonar qué datos solicitar.
nota: toma en cuenta que el formato de fechas es YYYY-MM-DD y que los montos son en USD. Por esto, usa strftime('%Y-%m', ...) para agrupar por mes y año.
Las columnas de fecha son `ARRIVAL` Y `DEPARTURE`.

Una vez generada la consulta, úsala llamando a la herramienta `execute_query_to_sqlite` para obtener los datos en formato JSON. **Luego, debes entregar tu respuesta en un JSON con los siguientes campos**:

- `title`: un título descriptivo de la respuesta.
- `returned_json`: el resultado devuelto por la consulta (en JSON).
- `findings`: explicacion de los datos encontrados.
- `methodology`: descripción de cómo se generó la consulta y qué filtros se aplicaron.

Devuelve **solo** un objeto JSON válido con este esquema:

{{
  "title": "Título descriptivo de la respuesta",
  "returned_json": [...],
  "findings": "...",
  "methodology": "..."
}}

NOTAS:
- Si la pregunta menciona wholesalers, debes usar el campo COMPANY_NAME.
- No uses nunca los nombres de las columnas como respuestas, debes adaptar este nombre a un lenguaje conversacional. 
- Responde en el lenguaje de la pregunta. 
- las unidades monetarias son en USD.
- toda la informacion de la tabla `reservations` es del resort Itzana. Por lo que no vale la pena incluirlo al hacer consultas. 
- en otras palabras, no uses WHERE RESORT = 'Itz''ana'. 

"""


reservations_agent = Agent(
    name="ReservationsAgent",
    instructions=reservations_instructions,
    model="gpt-4o",
    tools=[execute_query_to_sqlite],
    output_type=AgentOutputSchema(AnalysisOutput, strict_json_schema=False)

)

# ----------------------------------
#       Graph Generator Agent
# ----------------------------------

class GraphCodeOutput(TypedDict):
    code: str  # Python code for plotting


graph_code_agent_instructions = """
    You will receive:
    - `table_data`: a Python list of dictionaries (already loaded), each representing a row in a table.
    - `img_buf`: an open BytesIO buffer available for you to save the figure into.
    - `user_question`: the user's request for a specific plot.

    Write Python code using ONLY `table_data` and `img_buf` as already available variables.
    Do NOT load or declare `table_data` or `img_buf`.
    Do NOT call plt.show() anywhere.
    Do NOT use 'import' statements for them.
    Just use pandas and matplotlib to generate the requested plot and save it into the provided `img_buf` with `plt.savefig(img_buf, format='png')` and `img_buf.seek(0)`.
    Do NOT return anything but the code.
"""


graph_code_agent = Agent(
    name="GraphCodeAgent",
    instructions=graph_code_agent_instructions,
    model="gpt-4o",
    output_type=AgentOutputSchema(GraphCodeOutput, strict_json_schema=False)
)




