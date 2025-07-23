import os
import json
import logging
import traceback
import uvicorn

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv

from agents_module import reservations_agent, graph_code_agent
from agents import Runner
from helper import execute_graph_agent_code
from chat_module import chat_betterQuestions, chat_better_answers


# Carga las variables de entorno desde .env
load_dotenv()

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

class QueryRequest(BaseModel):
    question: str


app = FastAPI(
    title="Itzana Agents API",
    description="API para ejecutar los agentes de análisis (currently 1)",
    version="1.0.0",
)

class outputAsk2(BaseModel):
    markdown : str


GRAPH_KEYWORDS = [
    "grafica", "gráfico", "gráfica",
    "grafico", "visualiza", "visualización",
    "diagrama", "imagen", "representa",
    "graph", "chart", "plot", "visualize", "diagram", "picture", "figure"
]

@app.post("/ask", response_model=outputAsk2)
async def query_agent(request: QueryRequest):
    try:

        print(f"[DEBUG] - Pregunta original: {request.question}")

        flag_graph = any(keyword in request.question.lower() for keyword in GRAPH_KEYWORDS)

        better_question = await chat_betterQuestions(request.question)
        
        print(f"[DEBUG] - Pregunta mejorada: {better_question}")

        # 1) Llamas al agente SQL
        resp = await Runner.run(reservations_agent, better_question)
        raw: Dict[str, Any] = resp.final_output  # dict con your analysis
        table_data = raw.get("returned_json", [])
        print(f"[DEBUG] - Datos de la tabla: {table_data}")

        # second agent: Graph Generator Agent
        if flag_graph and raw.get("returned_json", []):  # Solo si hay datos en returned_json

            try:
                graph_payload = {
                    "table_data": table_data,
                    "user_question": request.question
                }

                # llamada al agente de codigo para graficos
                resp_graph = await Runner.run(graph_code_agent, json.dumps(graph_payload))
                resp_graph_code = resp_graph.final_output["code"]
                # print(f"[DEBUG] - Código del agente de gráficos:\n{resp_graph_code}")

                # Ejecutar el código del agente de gráficos
                url_img = execute_graph_agent_code(resp_graph_code, table_data)

                # add la URL de la imagen al raw
                raw["graph_url"] = url_img

            except Exception as e:
                print(f"[ERROR] - Error al generar la gráfica: {e}")

        betterAnswers = await chat_better_answers(raw)

        # si betteranswers contiene "### Gráfica\n![Gráfica no disponible en este momento]"
        if "### Gráfica\n![Gráfica no disponible en este momento]" in betterAnswers:
            betterAnswers = betterAnswers.replace("### Gráfica\n![Gráfica no disponible en este momento]", "")

        print(f"[DEBUG] - Respuesta mejorada: \n\n{betterAnswers}\n\n")

        return {"markdown" : betterAnswers}
        

    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "traceback": tb}
        )

if __name__ == "__main__":
    # Ejecutar con: python app.py o uvicorn app:app --reload --host 0.0.0.0 --port 8000
    # Levanta la app desde este módulo (app.py)
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

# http://127.0.0.1:8000/docs