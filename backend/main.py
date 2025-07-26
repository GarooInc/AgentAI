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
    judge_ruling,
    judge_agent

)

async def agent_workflow(user_question: str, max_retries: int = 2 ) -> dict:

    start_time = asyncio.get_event_loop().time()

    convo: list[TResponseInputItem] = [{"role": "user", "content":user_question}]
    eval_resp = await Runner.run(evaluator_agent, convo)
    convo = eval_resp.to_input_list()

    # Paso 2: Determinar qué agentes ejecutar
    if eval_resp.final_output.appropriate_agent == "Reservations Analyst":
        agents_to_run = [("Reservations Analyst", reservations_data_analyst_agent)]
    elif eval_resp.final_output.appropriate_agent == "Marketing Strategist":
        agents_to_run = [("Marketing Strategist", marketing_strategist_agent)]
    else:  # both
        agents_to_run = [
            ("Reservations Analyst", reservations_data_analyst_agent),
            ("Marketing Strategist", marketing_strategist_agent),
        ]


    # Creamos una tarea por cada agente y copiamos el historial
    tasks = []
    convos = {}
    for name, agent in agents_to_run:
        c = convo.copy()
        convos[name] = c
        tasks.append(Runner.run(agent, c))

    # Ejecutamos TODOS al mismo tiempo
    results = await asyncio.gather(*tasks)

    combined_data = []
    combined_report_parts = []

    for (name, _), res in zip(agents_to_run, results):
        fo = res.final_output  # instancia de analyst_output
        convos[name] = res.to_input_list()  # para posibles reruns
        if fo.data:
            combined_data.extend(fo.data)
        if fo.report:
            # opcionalmente, marca cada sección:
            combined_report_parts.append(f"### Resultado de {name}\n\n{fo.report}")

    # Construir un único analyst_output
    from types import SimpleNamespace
    combined_fo = SimpleNamespace(
        data=combined_data,
        report="\n\n".join(combined_report_parts),
        # añade aquí cualquier otro campo que uses en judge_input:
        original_question=results[0].final_output.original_question,
        user_goal=results[0].final_output.user_goal
    )

    for _ in range(max_retries):
        # Prepara la entrada JSON para el juez
        jinput = [{
            "role":"user",
            "content": json.dumps({
                "original_question": combined_fo.original_question,
                "user_goal":        combined_fo.user_goal,
                "data":             combined_fo.data,
                "report":           combined_fo.report
            })
        }]
        jresp = await Runner.run(judge_agent, jinput)
        ruling = jresp.final_output

        if ruling.veredict == "useful":
            break

        # Feedback del juez: ¿quién rerun?
        for agent_name in ruling.agents_to_rerun or []:
            convos[agent_name].append(
                {"role":"user","content":f"El juez dice: {ruling.reason}. Ajusta tu análisis."}
            )
            # Re‑run sólo ese agente
            idx = [n for n, _ in agents_to_run].index(agent_name)
            _, agent = agents_to_run[idx]
            res = await Runner.run(agent, convos[agent_name])
            convos[agent_name] = res.to_input_list()
            # Actualiza combined_fo con este nuevo fragmento
            fo = res.final_output
            if fo.data:
                combined_fo.data.extend(fo.data)
            if fo.report:
                combined_fo.report += "\n\n" + f"### Actualizado de {agent_name}\n\n{fo.report}"


    final_response = {
        "time_stamp": asyncio.get_event_loop().time() - start_time,
        "original_question": eval_resp.final_output.original_question,
        "user_goal": eval_resp.final_output.user_goal,
        "data": combined_fo.data,
        "report": combined_fo.report
    }

    return final_response
    


    

    


    