import asyncio
import json
from typing import Optional

from agents import Agent, ItemHelpers, Runner, TResponseInputItem, function_tool, trace
from .auxiliary_functions import log, execute_graph_agent_code


from .module_agents import (
    evaluator_agent, 
    evaluator_output,
    analyst_output, 
    reservations_data_analyst_agent,
    marketing_strategist_agent,
    judge_ruling,
    judge_agent,
    graph_code_agent

)

async def agent_workflow(user_question: str, max_retries: int = 2 ) -> dict:

    convo: list[TResponseInputItem] = []

    start_time = asyncio.get_event_loop().time()

    convo = [{"role": "user", "content":user_question}]
    eval_resp = await Runner.run(evaluator_agent, convo)
    convo = eval_resp.to_input_list()


    log(f"Agente seleccionado: {eval_resp.final_output.appropriate_agent} \n")
    log(f"Pregunta original: {eval_resp.final_output.original_question} \n")

    # appropiate agent selection
    if eval_resp.final_output.appropriate_agent == "Reservations Analyst":
        agent = reservations_data_analyst_agent
    elif eval_resp.final_output.appropriate_agent == "Marketing Strategist":
        agent = marketing_strategist_agent

    
    # first analysis run
    log(f"[{asyncio.get_event_loop().time()}] Running analysis with {agent.name} agent...")
    an_resp = await Runner.run(agent, convo)
    convo = an_resp.to_input_list()
    log(f"[{asyncio.get_event_loop().time()}] Análisis completado con {agent.name} agent.")

    # judge ruling and posterior runs. 
    for _ in range(max_retries):
        jinput = [
            {
                "role": "user",
                "content": json.dumps({
                    "original_question": eval_resp.final_output.original_question,
                    "user_goal": eval_resp.final_output.user_goal,
                    "data": an_resp.final_output.data,
                    "report": an_resp.final_output.report
                })
            }
        ]

        jresp = await Runner.run(judge_agent, jinput)
        ruling: judge_ruling = jresp.final_output

        if ruling.veredict == 1 :
            log(f"Judge ruling: {ruling.reason} - Analysis accepted.")
            break # accepted. 
        else:
            # add feedback from judge to convo. 
            log(f"Judge ruling: {ruling.reason} - Analysis rejected. Retrying...")
            feedback = f"{ruling.reason}. Please adjust your analysis accordingly. Previous analysis were not enough. "
            convo.append({"role":"user", "content":feedback})
            an_resp = await Runner.run(agent, convo)
            convo = an_resp.to_input_list()


    if eval_resp.final_output.needs_graph:
        log("Generating graphs...")
        

        try:
            graph_payload = {
                "table_data": an_resp.final_output.data,
                "user_question": eval_resp.final_output.original_question
            }

            graph_res = await Runner.run(graph_code_agent, json.dumps(graph_payload))
            graph_code = graph_res.final_output.code
            log(f"Graph code generated: {graph_code}")

            public_url = execute_graph_agent_code(graph_code, an_resp.final_output.data)
            log(f"Graph URL: {public_url}")

            log("Adding graph URL to the report...")
            an_resp.final_output.report += f"\n\n![Ver gráfico generado]({public_url})"

        except Exception as e:
            log(f"Error generating graph: {e}")

    # get final time
    end_time = asyncio.get_event_loop().time()

    log(f"REPORT: \n{an_resp.final_output.report}\n")


    final_response = {
        "time_stamp": end_time - start_time,
        "original_question": eval_resp.final_output.original_question,
        "user_goal": eval_resp.final_output.user_goal,
        "data": an_resp.final_output.data,
        "report": an_resp.final_output.report
    }

    return final_response



    

    


    