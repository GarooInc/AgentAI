from typing import List
from fastapi import Body, FastAPI
import uvicorn
from backend.main import agent_workflow
from pydantic import BaseModel


app = FastAPI(\
    title="Itzana Agents API",
    description="API para ejecutar los agentes de análisis (currently 1)",
    version="1.0.0",
)


class HistoryItem(BaseModel):
    content: str
    role: str

class InputData(BaseModel):
    question: str
    history: List[HistoryItem] = []

@app.post("/ask")
async def ask_question(input_data: InputData = Body(...)):
    try:
        question = input_data.question
        history = input_data.history
        response = await agent_workflow(question)  # Await the async function
    except Exception as e:
        return {"error": str(e)}
    return response  # Directly return the dictionary response


if __name__ == "__main__":
    # Ejecutar con: python app.py o uvicorn app:app --reload --host 0.0.0.0 --port 8000
    # Levanta la app desde este módulo (app.py)
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

# http://127.0.0.1:8000/docs