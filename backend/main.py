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
    if not convo: convo = []

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

            ## add orchestrator response to conversation
            #convo += orchestrator_response.to_input_list() remove the first element of the response, which is the user question.
            convo += orchestrator_response.to_input_list()[1:]            

            analysts_responses = []

            # define order of agents to run
            agent_list = orchestrator_response.final_output.assigned_agents
            while agent_list:
                agent_name = agent_list.pop(0)
                log(f"Running agent:")
                
                if agent_name == "data_analyst":
                    response = await Runner.run(data_analyst, convo, max_turns=5)
                    convo.append({"role": "assistant", "content": f"data: {response.final_output.data} findings: {response.final_output.findings} clarifying_question: {response.final_output.clarifying_question}"})
                elif agent_name == "marketing_analyst":
                    response = await Runner.run(marketing_analyst, convo, max_turns=3)
                    convo.append({"role": "assistant", "content": f"data: {response.final_output.data} findings: {response.final_output.findings} clarifying_question: {response.final_output.clarifying_question}"})
                else:
                    continue

                log(f"Agent {agent_name} response: {response.final_output}")

                # Guardar la respuesta en analysts_responses
                analysts_responses.append({
                    "agent_name": agent_name,
                    "data": response.final_output.data if response.final_output and response.final_output.data is not None else {},
                    "findings": response.final_output.findings if response.final_output and response.final_output.findings is not None else [],
                    "clarifying_question": response.final_output.clarifying_question if response.final_output and response.final_output.clarifying_question is not None else ""
                })

            # aqui ya estan todas las respuestas de los analistas
            


            print_convo(convo)

    except Exception as e:
        log(f"Error in orchestrator: {e}")
        return {"error": str(e)}

    final_response["overall_time"] = asyncio.get_event_loop().time() - start_time

    return final_response



## Helper funcictions, should be deleted later.

def print_convo(convo: list[TResponseInputItem]) -> None:
    print("\nConversation history:")
    for i, item in enumerate(convo):
        print(f"{i+1}. Role: {item.get('role', 'N/A')}, Content: {item.get('content', 'N/A')}")
