import asyncio
import json
from typing import Optional

from agents import Agent, ItemHelpers, Runner, TResponseInputItem, function_tool, trace
from .auxiliary_functions import log


from .module_agents import (
    evaluator_agent, 
    evaluator_output,
    analyst_output, 
    reservations_data_analyst_agent,
    marketing_strategist_agent,
    judge_ruling,
    judge_agent

)

async def agent_workflow(user_question: str, max_retries: int = 2 ) -> dict:

    start_time = asyncio.get_event_loop().time()

    convo: list[TResponseInputItem] = [{"role": "user", "content":user_question}]
    eval_resp = await Runner.run(evaluator_agent, convo)
    convo = eval_resp.to_input_list()


    log(f"Agente seleccionado: {eval_resp.final_output.appropriate_agent} \n")
    log(f"Pregunta original: {eval_resp.final_output.original_question} \n")
    log(f"Meta del usuario: {eval_resp.final_output.user_goal} \n")
    log(f"Pregunta mejorada: {eval_resp.final_output.better_question} \n")
    log(f"Información adicional: {eval_resp.final_output.additional_info} \n")
    log(f"Plan de investigación: {eval_resp.final_output.research_plan} \n")

    # appropiate agent selection
    if eval_resp.final_output.appropriate_agent == "Reservations Analyst":
        agent = reservations_data_analyst_agent
    elif eval_resp.final_output.appropriate_agent == "Marketing Strategist":
        agent = marketing_strategist_agent

    
    # first analysis run
    an_resp = await Runner.run(agent, convo)
    convo = an_resp.to_input_list()

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
            break # accepted. 
        else:
            # add feedback from judge to convo. 
            feedback = f"{ruling.reason}. Please adjust your analysis accordingly. Previous analysis were not enough. "
            convo.append({"role":"user", "content":feedback})
            an_resp = await Runner.run(agent, convo)
            convo = an_resp.to_input_list()

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



    

    


    