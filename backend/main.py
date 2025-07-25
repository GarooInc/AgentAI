import asyncio
import json

from agents import Agent, ItemHelpers, Runner, TResponseInputItem, function_tool, trace
from .auxiliary_functions import log


from .module_agents import (
    evaluator_agent, 
    evaluator_output,
    analyst_output, 
    reservations_data_analyst_agent,
    marketing_strategist_agent,
)

async def agent_workflow(user_question: str):

    start_time = asyncio.get_event_loop().time()

    convo: list[TResponseInputItem] = [{"role": "user", "content": user_question}]

    # Paso 1: Evaluador
    evaluator_result = await Runner.run(evaluator_agent, convo)
    print(f"Evaluador: {evaluator_result.final_output}")

    # Actualizar historial
    convo = evaluator_result.to_input_list()

    analisys_result : analyst_output

    # Si necesita delegar a otro agente:
    if evaluator_result.final_output.appropriate_agent == "Reservations Analyst":
        analisys_result = await Runner.run(reservations_data_analyst_agent, convo)
        # print(f"Reservations Analyst: {reservations_result.final_output}")

        log(f"Reservations Analyst: \n{analisys_result.final_output.report}")

        convo = analisys_result.to_input_list()


    elif evaluator_result.final_output.appropriate_agent == "Marketing Strategist":
        analisys_result = await Runner.run(marketing_strategist_agent, convo)
        # print(f"Marketing Strategist: {marketing_result.final_output}")

        log(f"Marketing Strategist: \n{analisys_result.final_output.report}")
        convo = analisys_result.to_input_list()

    else:
        raise ValueError(f"Agente no reconocido: {evaluator_result.final_output.appropriate_agent}")
    




    endTime = asyncio.get_event_loop().time()
    elapsed_time = endTime - start_time

    final_response = {
        "reservations_result": analisys_result.final_output.dict(),  # Todo lo que tiene reservations_result
        "execution_time": elapsed_time  # Tiempo de ejecución
    }

    return final_response