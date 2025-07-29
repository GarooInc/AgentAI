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
    final_response = {"overall_time": 0, "clarifying_question": "", "data": {}, "markdown": ""}
    # if not convo: convo = []

    log(f"Starting agent workflow... Conversation length: {len(convo)}")
    convo.append({"role": "user", "content": user_question})

    try:
        log("Running Orchestrator ...")
        orchestrator_response = await Runner.run(orchestrator_agent, convo)
        log("Orchestrator response received.")
        print(f"\tAGENTES: {orchestrator_response.final_output.assigned_agents}\n\tUSER GOAL: {orchestrator_response.final_output.user_goal}\n\tREQUIRES GRAPH: {orchestrator_response.final_output.requires_graph}\n\tCLARIFYING QUESTION: {orchestrator_response.final_output.clarifying_question}")

        # Orchestrator response handling
        if orchestrator_response.final_output.clarifying_question: 
            log("Orchestrator requires clarification.")
            final_response["clarifying_question"] = orchestrator_response.final_output.clarifying_question
            final_response["overall_time"] = asyncio.get_event_loop().time() - start_time
            return final_response
        
        else: # No hay clarifying question, proceed with assigned agents
            
            # define order of agents to run
            agent_list = orchestrator_response.final_output.assigned_agents
            while agent_list:
                agent_name = agent_list.pop(0)
                log(f"Running agent:")
                
                if agent_name == "data_analyst":
                    response = await Runner.run(data_analyst, convo, max_turns=10)
                elif agent_name == "marketing_analyst":
                    #response = await Runner.run(marketing_analyst, convo, max_turns=10)
                    continue
                else:
                    continue
                
                # Process the response
                if response.final_output:
                    final_response["data"] = response.final_output.data
                    final_response["markdown"] += response.final_output.findings + "\n"
                    print(f"\n\nAgent {agent_name} response processed.")
                    print(final_response["markdown"])
                else:
                    log(f"No final output from agent {agent_name}")


    except Exception as e:
        log(f"Error in orchestrator: {e}")
        return {"error": str(e)}

    final_response["overall_time"] = asyncio.get_event_loop().time() - start_time

    return final_response