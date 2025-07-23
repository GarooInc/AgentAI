from typing import Any, List, Dict, TypedDict
from agents_wrapper import Agent, function_tool, AgentOutputSchema
from typing_extensions import TypedDict

from database import db_manager
from cache_manager import get_cached_knowledge

# ----------------------------------
#         Analysis Agent 
# ----------------------------------

# Usar cache para datos de conocimiento
knowledge_data = get_cached_knowledge()
reservations_columns = knowledge_data['reservations_columns']
wholesalers_list = knowledge_data['wholesalers_list']
itzana_knowledge = knowledge_data['itzana_knowledge']

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
    """Ejecuta la consulta SQL usando el database manager optimizado."""
    return db_manager.execute_query(query)

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




