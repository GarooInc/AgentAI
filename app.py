import asyncio
from typing import Any, Dict, List
from fastapi import Body, FastAPI
from pydantic import BaseModel
import uvicorn
from backend.main import agent_workflow

app = FastAPI(
    title="Itzana Agents API",
    description="Itzana Agents API for handling user questions",
    version="3.0.0",
)

class AskRequest(BaseModel):
    question: str
    history: List[Dict[str, Any]]

@app.post("/ask")
async def ask_question(input_data: AskRequest = Body(...)) -> Dict[str, Any]:
    try:
        question = input_data.question
        history = input_data.history

        # Reemplaza todos los roles "agent" por "assistant" # hotfix, should be fixed in agent's backend and frontend. 
        for item in history:
            if isinstance(item, dict) and item.get("role") == "agent":
                item["role"] = "assistant"

        response = await asyncio.wait_for(agent_workflow(question, history), timeout=60*4)
    except Exception as e:
        return {"error": str(e)}
    return response


if __name__ == "__main__":
    # Ejecutar con: python app.py o uvicorn app:app --reload --host 0.0.0.0 --port 8000
    # Levanta la app desde este módulo (app.py)
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

# http://127.0.0.1:8000/docs