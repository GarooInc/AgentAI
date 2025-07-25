import asyncio
import json

from agents import Agent, ItemHelpers, Runner, TResponseInputItem, function_tool, trace


from .module_agents import (
    evaluator_agent, 
    evaluator_output
)




import json

async def agent_workflow(user_question: str):
    evaluator_response: evaluator_output = await Runner.run(evaluator_agent, user_question)
    response = evaluator_response.final_output

    response.appropriate_agent = response.appropriate_agent.strip()
    if response.appropriate_agent == "Reservations Analyst":
        pass
    elif response.appropriate_agent == "Marketing Strategist":
        pass

    else:
        raise ValueError(f"Agente inapropiado: {response.appropriate_agent}")
    

    # Si eval_short_answer es un string, intenta convertirlo a JSON
    if isinstance(response, str):
        try:
            # Si el string ya es un JSON válido
            return json.loads(response)
        except json.JSONDecodeError:
            # Si no es un JSON válido, procesa el string para convertirlo
            return {"final_output": response}

    # Si eval_short_answer es un objeto con .dict(), lo usamos
    if hasattr(response, "dict"):
        return response.dict()

    # Si no es ni string ni un objeto con .dict(), devuelve un error
    return {"error": "Unexpected output format from evaluator agent"}