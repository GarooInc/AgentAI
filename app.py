from fastapi import Body, FastAPI
import uvicorn
from backend.main import agent_workflow

app = FastAPI(
    title="Itzana Agents API",
    description="Itzana Agents API for handling user questions",
    version="3.0.0",
)

@app.post("/ask")
async def ask_question(input_data: dict = Body(...)):

    # 


    try:
        question = input_data.get("question", "")
        history = input_data.get("history", [])

        # Reemplaza todos los roles "agent" por "assistant" # hotfix, should be fixed in agent's backend and frontend. 
        for item in history:
            if isinstance(item, dict) and item.get("role") == "agent":
                item["role"] = "assistant"

        response = await agent_workflow(question, history)
    except Exception as e:
        return {"error": str(e)}
    return response


if __name__ == "__main__":
    # Ejecutar con: python app.py o uvicorn app:app --reload --host 0.0.0.0 --port 8000
    # Levanta la app desde este módulo (app.py)
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

# http://127.0.0.1:8000/docs