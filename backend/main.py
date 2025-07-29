import asyncio
import json
from typing import Optional

from agents import Agent, ItemHelpers, Runner, TResponseInputItem, function_tool, trace
from .auxiliary_functions import log, execute_graph_agent_code


from .module_agents import (
    orchestrator_agent,
    data_analyst,
    marketing_analyst,
)

async def agent_workflow(user_question: str, convo: list[TResponseInputItem] = [],  max_retries: int = 2 ) -> dict:


    start_time = asyncio.get_event_loop().time()

    final_response = {}

    log("Starting agent workflow...")

    print("ESPECIAL: ")# ammount of items in convo
    print(len(convo))
    
    # add user question to conversation
    convo.append({"role": "user", "content": user_question})

    try:
        log("Running Orchestrator ...")
        orchestrator_response = await Runner.run(orchestrator_agent, convo)
        log("Orchestrator response received.")

        print("\n\nOrchestrator response: ")
        log(f"Orchestrator assigned agent: {orchestrator_response.final_output.assigned_agents}")
        log(f"Orchestrator user_question: {orchestrator_response.final_output.user_question}")
        log(f"Orchestrator user_goal: {orchestrator_response.final_output.user_goal}")
        log(f"Orchestrator commentary: {orchestrator_response.final_output.commentary}")
        log(f"Orchestrator requires_graph: {orchestrator_response.final_output.requires_graph}")
        log(f"Orchestrator clarifying_question: {orchestrator_response.final_output.clarifying_question}")

        if orchestrator_response.final_output.clarifying_question:
            log("Orchestrator requires clarification.")
            final_response["clarifying_question"] = orchestrator_response.final_output.clarifying_question


    except Exception as e:
        log(f"Error in orchestrator: {e}")
        return {"error": str(e)}



    end_time = asyncio.get_event_loop().time()
    overall_time = end_time - start_time

    final_response["overall_time"] = overall_time

    return final_response

    







    

    


    