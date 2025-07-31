import asyncio
import json
from typing import Optional
import traceback


from agents import Agent, ItemHelpers, Runner, TResponseInputItem, function_tool, trace
from openai import BaseModel
from .auxiliary_functions import log, execute_graph_agent_code


from .module_agents import (
    orchestrator_agent,
    data_analyst,
    marketing_analyst,
    response_agent,
    better_questions_agent
)

async def agent_workflow(user_question: str, convo: list[TResponseInputItem] = [],  max_retries: int = 10 ) -> dict:

    log("Convo: ")
    for message in convo:
        print(f"  {message['role']}: {message['content']}")

    final_response = {"overall_time": 0, "data": {}, "markdown": ""}
    stime = asyncio.get_event_loop().time()
    convo = convo or []
    convo.append({"role": "user", "content": user_question})

    try:
        log("Starting agent's workflow.")

        # 1) run orchestrator agent. 
        log("Running Orchestrator ...")
        o_resp = await Runner.run(orchestrator_agent, convo, max_turns=10)
        o_out = o_resp.final_output
        log(f"Orchestrator response: {o_out.assigned_agents}, {o_out.requires_graph}, {o_out.clarifying_question}")

        convo.append({
            "role": "assistant",
            "content": (
                f"Orchestrator response: ["
                f"Assigned Agents: {o_out.assigned_agents}, "
                f"User Question: {o_out.user_question}, "
                f"User Goal: {o_out.user_goal}, "
                f"Commentary: {o_out.commentary}, "
                f"Requires Graph: {o_out.requires_graph}, "
                f"Clarifying Question: {o_out.clarifying_question}]"
            )
        })


        # 2) run analyst agents. 
        if not o_out.clarifying_question and not o_out.clarifying_question == "": # orc no devuelve pregunta, continua el ciclo. 

            log("Orchestrator does not require clarification, proceeding with assigned agents.")
            for analyst in o_out.assigned_agents:
                log(f"Running agent: {analyst}")
                if analyst == "data_analyst":
                    try:
                        log("Running better questions agent...")
                        bresponse = await Runner.run(better_questions_agent, convo, max_turns=10)
                        bq = bresponse.final_output.refined_question
                        log(f"Better Questions Agent response: {bq}")
                        bc = bresponse.final_output.context
                        log(f"Better Questions Agent context: {bc}")

                        convo.append({
                            "role": "assistant",
                            "content": (
                                f"Better Questions Agent response: ["
                                f"Refined Question: {bq}, "
                                f"Context: {bc}]"
                            )
                        })

                        response = await Runner.run(data_analyst, convo, max_turns=10)
                        final_response["data"] = response.final_output.data # revisar. 
                    except Exception as e:
                        log(f"Error occurred while running data_analyst: {e}")
                elif analyst == "marketing_analyst":
                    try:
                        response = await Runner.run(marketing_analyst, convo, max_turns=10)
                        final_response["data"] = response.final_output.data # revisar.
                    except Exception as e:
                        log(f"Error occurred while running marketing_analyst: {e}")
                else:
                    raise ValueError(f"Unknown agent: {analyst}")
                
                log(f"Agent {analyst} finished. ")

                rout = response.final_output
                convo.append({
                    "role": "assistant",
                    "content": (
                        f"Data Analyst response: ["
                        f"Data: {rout.data}, "
                        f"Findings: {rout.findings}, "
                        f"Clarifying Question: {rout.clarifying_question}]" # esto no me convence, hay que revisarlo. 
                    )
                })
                

        # 3) run graph agent if required.
            if o_out.requires_graph:
                pass

        # 4) run response agent.
            log("Running Response Agent...")
            response = await Runner.run(response_agent, convo)
            out = response.final_output.markdown

        # 5) prepare final response.
            final_response["overall_time"] = asyncio.get_event_loop().time() - stime 
            final_response["markdown"] = out
            log(f"Response Agent finished.")
            print(out.replace('\n', r'\n'))

        else: # orc si devuelve pregunta, devuelve la esa pregunta y termina el ciclo.
            log("Orchestrator requires clarification.")
            final_response["markdown"] = o_out.clarifying_question
            final_response["overall_time"] = asyncio.get_event_loop().time() - stime
            return final_response
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        log(f"Error in orchestrator: {e}\nTraceback:\n{error_details}")
        return {"error": str(e), "details": error_details}

    return final_response



## Helper funcictions, should be deleted later.

def print_convo(convo: list[TResponseInputItem]) -> None:
    print("\nConversation history:")
    for i, item in enumerate(convo):
        print(f"{i+1}. Role: {item.get('role', 'N/A')}, Content: {item.get('content', 'N/A')}")
