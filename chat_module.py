import asyncio
import json
from openai import OpenAI

from helper import load_context

from dotenv import load_dotenv
import os

# Carga variables de entorno desde .env
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Falta definir OPENAI_API_KEY en las variables de entorno")

client = OpenAI(api_key=OPENAI_API_KEY)

resv_columns = load_context("knowledge/reservations_columns.md")
wholesalers_list = load_context("knowledge/wholesalers.txt")
itzana_knowledge = load_context("knowledge/itzana_context.md")

async def chat_betterQuestions(userQuery: str) -> str:
    """
    Genera una versión mejorada de la pregunta original para que sea
    más clara y específica al ejecutarse contra la base de datos.
    """
    contexto = (
        "Eres un asistente experto en análisis de datos para el resort Itz'ana. "
        "Tu tarea es transformar la pregunta del usuario en una instrucción técnica, concisa y precisa, describiendo EXACTAMENTE la consulta a realizar, usando los nombres exactos de las columnas de la tabla 'reservations'. "
        "Corrige cualquier error ortográfico en los nombres de mayoristas (wholesalers) usando la lista de mayoristas conocidos. "
        "Si el usuario menciona un mayorista de forma incorrecta o con errores, corrígelo y usa el nombre correcto. "
        "No generes el query SQL. "
        "No seas conversacional, solo describe con precisión qué columnas se deben usar para agrupar, filtrar, sumar, contar, etc. No contestes preguntas. "
        "IMPORTANTE: Si parte de la pregunta del usuario solicita recomendaciones o preguntas abiertas que no se pueden responder con datos, debes devolver esa parte ademas de lo referente a la consulta sql. "
        "No repitas la pregunta original. "
        "Ejemplo: 'Obtener el total de EFFECTIVE_RATE_AMOUNT agrupado por ROOM_CATEGORY_LABEL, filtrando por COMPANY_NAME igual a \"EXPEDIA, INC.\".' "
        f"Columnas de la tabla: {resv_columns} "
        f"Lista de mayoristas: {wholesalers_list} "
        "Si la pregunta menciona una grafica y no menciona el tipo de grafica, asume que es una barra."
        "Si la pregunta menciona una grafica y menciona el tipo de grafica, usa ese tipo. pero intenta mejorar la descripcion de la grafica."
    )


    try:
        # Ejecutamos la llamada síncrona en un hilo para no bloquear el event loop
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": contexto},
                {"role": "user",   "content": userQuery}
            ],
            max_tokens=2000,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error al generar preguntas: {e}")
        # Si algo falla, devolvemos la pregunta original
        return userQuery


async def chat_better_answers(agent_response: dict) -> str:
    """
    Genera una respuesta conversacional y profesional en formato Markdown
    a partir de la respuesta estructurada del agente.
    """
    # chat_module.py (o donde definas tu prompt)

    prompt = (
        """
        <instrucciones>
        <rol>
            Eres un compañero experto en análisis de datos para el resort Itz'ana en Placencia, Belice,
            con un estilo conversacional, como si estuviéramos charlando sobre los números.
        </rol>
        <contexto>
            <descripcion>Contexto del negocio</descripcion>
            <contenido>{itzana_knowledge}</contenido>
            <nota>Intenta siempre relacionar los datos con el contexto del negocio. Al responder es deseable que complementes con información del contexto de negocio, pero no es obligatorio.</nota>
        </contexto>
        <formato>
            <seccion nombre="Título">
            <instruccion>Debe ser breve, claro y representativo del análisis.</instruccion>
            <nota>El título no es 'título', sino que debes generar un título descriptivo de la respuesta.</nota>
            </seccion>
            <seccion nombre="Análisis">
            <instruccion>Comenta tendencias, anomalías, contexto, oportunidades y riesgos.</instruccion>
            <nota>Adapta el lenguaje al estilo conversacional; evita formatos rígidos.</nota>
            </seccion>
            <seccion nombre="Datos">
            <instrucciones>
                <item>Si los datos de <code>returned_json</code> son relevantes, incluye la tabla completa.</item>
                <item>Asegúrate de formatear números con comas para miles y punto para decimales.</item>
                <item>Moneda: USD si aplica (revenue siempre en dólares).</item>
                <item>Si no son útiles, omite esta sección.</item>
                <item>Si hay una celda en la tabla que está vacía, no incluyas esa fila en la tabla.</item>
            </instrucciones>
            </seccion>
            <seccion nombre="Gráfica">
            <instrucciones>
                <item>Si recibes <code>graph_url</code>, incrusta la imagen justo después de la tabla.</item>
                <item>Si no hay URL, omite esta sección completamente (ni siquiera la menciones).</item>
            </instrucciones>
            </seccion>
            <seccion nombre="Recomendaciones">
            <instrucciones>
                <item>Usa la información del contexto de negocio y los datos analizados.</item>
                <item>Bullet points con acciones realistas para el día a día del resort.</item>
                <item>Solo inclúyelas si los datos permiten sugerir algo útil.</item>
                <item>Extiéndete en esta sección, pero no repitas lo que ya has dicho en el análisis.</item>
            </instrucciones>
            </seccion>
            <seccion nombre="Notas Finales">
            <instrucciones>
                <item>Recuerda que solo usaste la información proporcionada.</item>
                <item>Mantén siempre un tono cercano y conversacional.</item>
                <item>No inventes nada: usa únicamente la información disponible.</item>
            </instrucciones>
            </seccion>
        </formato>
        </instrucciones>
        """.format(itzana_knowledge=itzana_knowledge)
    )


    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(agent_response, indent=2) if isinstance(agent_response, dict) else agent_response}
            ],
            max_tokens=2000,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error al generar respuesta conversacional: {e}")
        return f"No se pudo generar la respuesta conversacional. {agent_response} "
    

async def chat_evaluate_questions(user_question:str) -> str:
    """
    Evalua la pregunta del usuario para determinar si es adecuada para el analisis de datos, o debe ser consultada en la web. 
    """

    prompt = (
        "Tu tarea es evaluar la pregunta del usuario y determinar si es adecuada para el agente del analisis de datos y su worflow, "
        "o si puede ser contestada con una busqueda en la web. "

    )