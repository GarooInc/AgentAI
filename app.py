from fastapi import FastAPI
import uvicorn
from backend.main import agent_workflow


app = FastAPI(\
    title="Itzana Agents API",
    description="API para ejecutar los agentes de análisis (currently 1)",
    version="1.0.0",
)


@app.post("/ask")
async def ask_question(question: str):
    # Aquí iría la lógica para procesar la pregunta
    try:
        response = await agent_workflow(question)  # Await the async function
    except Exception as e:
        return {"error": str(e)}
    return response  # Directly return the dictionary response


if __name__ == "__main__":
    # Ejecutar con: python app.py o uvicorn app:app --reload --host 0.0.0.0 --port 8000
    # Levanta la app desde este módulo (app.py)
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

# http://127.0.0.1:8000/docs