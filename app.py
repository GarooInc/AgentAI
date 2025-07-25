import os
import json
import logging
import traceback
import uvicorn
import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv

from agents_module import reservations_agent, graph_code_agent
from agents_wrapper import Runner
from helper import execute_graph_agent_code
from chat_module import chat_betterQuestions, chat_better_answers
from cache_manager import get_cached_knowledge


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

# Thread pool para operaciones CPU-intensivas
executor = ThreadPoolExecutor(max_workers=4)

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

        # Ejecutar mejora de pregunta y agente SQL en paralelo cuando sea posible
        better_question_task = asyncio.create_task(chat_betterQuestions(request.question))
        better_question = await better_question_task
        
        print(f"[DEBUG] - Pregunta mejorada: {better_question}")

        # Ejecutar agente SQL
        resp = await Runner.run(reservations_agent, better_question)
        raw: Dict[str, Any] = resp.final_output
        table_data = raw.get("returned_json", [])
        print(f"[DEBUG] - Datos de la tabla: {table_data}")

        # Crear tasks para procesamiento paralelo
        tasks = []
        
        # Task para generar gráfico si es necesario
        if flag_graph and table_data:
            graph_task = asyncio.create_task(generate_graph_async(table_data, request.question))
            tasks.append(("graph", graph_task))
        
        # Task para generar respuesta mejorada (siempre)
        answer_task = asyncio.create_task(chat_better_answers(raw))
        tasks.append(("answer", answer_task))
        
        # Esperar a que terminen todas las tasks
        results = {}
        for task_name, task in tasks:
            try:
                results[task_name] = await task
            except Exception as e:
                print(f"[ERROR] - Error en task {task_name}: {e}")
                if task_name == "graph":
                    results[task_name] = None
                else:
                    raise
        
        # Agregar URL de gráfico si se generó exitosamente
        if "graph" in results and results["graph"]:
            raw["graph_url"] = results["graph"]
        
        # Obtener respuesta final
        better_answers = results["answer"]
        
        # Limpiar respuesta si es necesario
        if "### Gráfica\n![Gráfica no disponible en este momento]" in better_answers:
            better_answers = better_answers.replace("### Gráfica\n![Gráfica no disponible en este momento]", "")

        print(f"[DEBUG] - Respuesta mejorada: \n\n{better_answers}\n\n")
        return {"markdown": better_answers}
        
    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "traceback": tb}
        )

async def generate_graph_async(table_data: list, user_question: str) -> Optional[str]:
    """Genera gráfico de forma asíncrona"""
    try:
        graph_payload = {
            "table_data": table_data,
            "user_question": user_question
        }
        
        # Ejecutar agente de gráficos
        resp_graph = await Runner.run(graph_code_agent, json.dumps(graph_payload))
        resp_graph_code = resp_graph.final_output["code"]
        
        # Ejecutar generación de imagen en thread pool
        loop = asyncio.get_event_loop()
        url_img = await loop.run_in_executor(
            executor, 
            execute_graph_agent_code, 
            resp_graph_code, 
            table_data
        )
        
        return url_img
        
    except Exception as e:
        print(f"[ERROR] - Error al generar gráfica: {e}")
        return None

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": "2025-01-23"}

@app.get("/metrics")
async def get_metrics():
    """Basic metrics endpoint"""
    from cache_manager import knowledge_cache
    return {
        "cache_size": len(knowledge_cache._cache),
        "cached_files": list(knowledge_cache._cache.keys())
    }

if __name__ == "__main__":
    # Ejecutar con: python app.py o uvicorn app:app --reload --host 0.0.0.0 --port 8000
    # Levanta la app desde este módulo (app.py)
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

# http://127.0.0.1:8000/docs