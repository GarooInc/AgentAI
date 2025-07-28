# module_agents.py

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import asyncio
from typing_extensions import Literal
from agents import Agent, AgentOutputSchema, ItemHelpers, Runner, TResponseInputItem, function_tool, trace, WebSearchTool
from pydantic import BaseModel
from .auxiliary_functions import log, get_db_connection, close_db_connection, execute_graph_agent_code
import os

from dotenv import load_dotenv
load_dotenv()

conn = get_db_connection()

# -----------------------------------------------------------------------------------------------------------------------------------------
#                                                                   Evaluator Agent
# -----------------------------------------------------------------------------------------------------------------------------------------

class evaluator_output(BaseModel):
    """
    Output model for the evaluator agent.
    """
    original_question: str
    appropriate_agent: Literal["Reservations Analyst", "Marketing Strategist"]
    user_goal: str
    better_question: Optional[str] = None # a corrected version of the original question so that the agent can answer it better. Should also correct spelling (specially about wholesalers.)
    additional_info: Optional[str] = None
    research_plan: Optional[str] = None
    expected_report_outline: str
    needs_graph: bool = False

@function_tool
def retrieve_reservationsdb_columns() -> Dict[str, str]:
    """
    Retrieves all the information from the reservations_columns.md file.

    Returns:
        A dictionary where keys are column names and values are their descriptions.
    """

    log("Retrieving reservations columns from reservations_columns.md")

    # Define the path to the reservations_columns.md file
    file_path = os.path.join(os.path.dirname(__file__), 'knowledge', 'reservations_columns.md')

    # Initialize a dictionary to store the columns and their descriptions
    columns_info = {}

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                # Parse lines that follow the format: - "COLUMN_NAME": Description
                if line.startswith('- "'):
                    column_name, description = line[2:].split(':', 1)
                    columns_info[column_name.strip().strip('"')] = description.strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"The file {file_path} does not exist.")
    except Exception as e:
        raise RuntimeError(f"An error occurred while reading the file: {e}")

    log(f"Retrieved {len(columns_info)} columns from reservations_columns.md")

    return columns_info

@function_tool
def retrieve_resort_general_information() -> str:
    """
    Retrieves general information about the resort from the itzana_context.md file.

    Returns:
        A string containing the general information about the resort.
    """

    log("Retrieving resort general information from itzana_context.md")

    # Define the path to the itzana_context.md file
    file_path = os.path.join(os.path.dirname(__file__), 'knowledge', 'itzana_context.md')

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            context_info = file.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"The file {file_path} does not exist.")
    except Exception as e:
        raise RuntimeError(f"An error occurred while reading the file: {e}")

    log("Retrieved resort general information successfully")

    return context_info

@function_tool
def retrieve_wholesalers_list() -> List[str]:
    """
    Retrieves a list of wholesalers from the wholesalers.txt file.

    Returns:
        A list of wholesalers.
    """

    log("Retrieving wholesalers list from wholesalers.txt")

    # Define the path to the wholesalers.txt file
    file_path = os.path.join(os.path.dirname(__file__), 'knowledge', 'wholesalers.txt')

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            wholesalers = [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        raise FileNotFoundError(f"The file {file_path} does not exist.")
    except Exception as e:
        raise RuntimeError(f"An error occurred while reading the file: {e}")
    
    log(f"Retrieved {len(wholesalers)} wholesalers from wholesalers.txt")

    return wholesalers

evaluator_agent = Agent(
    name="Evaluator Agent",
    instructions=(
        "This agent evaluates the user's question and determines the most appropriate agent to answer it. "
        "It provides an improved version of the question if necessary, correcting spelling errors (especially related to wholesalers), "
        "and offers additional information to assist the selected agent. "
        "You should call `retrieve_reservationsdb_columns` if the question to check if the question is about reservations db, "
        "`retrieve_resort_general_information` if the question is about the resort, and `retrieve_wholesalers_list` if the question is about wholesalers. "
        "If the question is can be answered solely by reservations db (which is a log of all the reservations made in the resort), you should return 'Reservations Analyst' as the appropriate agent."
        "If the question does not specify a timeframe, assume is 2025. This is EXTREMELY important, as the agents will assume that the question is about the latest year."
        "The output includes the following fields: \n"
        "- original_question: The user's original question.\n"
        "- appropriate_agent: Either 'Reservations Analyst' or 'Marketing Strategist', depending on the question.\n"
        "- users_goal: The user's intended goal or purpose.\n"
        "- better_question: A corrected and improved version of the original question, if applicable.\n"
        "- additional_info: Supplementary information useful for answering the question.\n"
        "- research_plan: A suggested plan for conducting research, if needed.\n"
        "- expected_report_outline: The expected structure of the report to be generated.\n"
        "- needs_graph: A boolean indicating whether a graph is required in the response given the question. Only if the user specifically requests a graph or something related to a graph, like other keywords like 'plot', 'chart', etc. If the question does not explicitly request a graph, this should be False."
        "IF you mention anything from the db columns, you should always assing it to the `Reservations Analyst`"
    ),
    tools=[
        retrieve_wholesalers_list,
        retrieve_resort_general_information,
        retrieve_reservationsdb_columns
    ], 
    output_type=evaluator_output,
)


class analyst_output(BaseModel):
    """
    Output model for the Analyst-type agents.
    """
    original_question: str
    user_goal: str
    responding_agent: Literal["Reservations Analyst", "Marketing Strategist"]
    better_question: str
    data: List[Dict[str, Any]] = None  
    report: str = None # long markdown report with the analysis of the data, including insights and conclusions.


# -----------------------------------------------------------------------------------------------------------------------------------------
#                                                     Reservations Data Analyst Agent
# -----------------------------------------------------------------------------------------------------------------------------------------

@function_tool
def execute_sql_query(query: str, max_rows: int = 300, sample_size: int = 300) -> List[Dict[str, Any]]:
    """
    Executes a SQL query on the reservations database and returns the results.
    If the result set exceeds max_rows, applies random sampling to reduce it to sample_size rows.

    Args:
        query (str): The SQL query to execute.
        max_rows (int): The maximum number of rows allowed before applying sampling.
        sample_size (int): The number of rows to return after sampling.

    Returns:
        List[Dict[str, Any]]: The results of the query as a list of dictionaries.
    """
    log(f"Executing SQL query: {query}")
    
    try:
        # Use the global connection `conn`
        cursor = conn.cursor()
        cursor.execute(query)
        columns = [column[0] for column in cursor.description]  # Get column names
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]  # Convert rows to dictionaries
        
        log(f"Query executed successfully. Retrieved {len(results)} rows.")
        
        # Apply random sampling if the number of rows exceeds max_rows
        if len(results) > max_rows:
            log(f"[WARNING] - Query returned {len(results)} rows. Applying random sampling to reduce to {sample_size} rows.")
            sampled_query = f"{query.strip()} ORDER BY RANDOM() LIMIT {sample_size}"
            cursor.execute(sampled_query)
            sampled_results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            log(f"Random sampling applied. Returning {len(sampled_results)} rows.")
            return sampled_results
        
        return results
    except Exception as e:
        log(f"Error executing query: {e}")
        raise RuntimeError(f"Failed to execute query: {e}")
    

reservations_data_analyst_agent = Agent(
    name="Reservations Data Analyst Agent",
    instructions=(
        "This agent is responsible for analyzing the reservations database to answer questions related to reservations. "
        "It receives the output from the Evaluator Agent, which includes the improved question, the user's goal, and a research plan. "
        "Follow this disciplined THINK→PLAN→QUERY cycle to retrieve minimal, conclusive datasets:\n\n"
        "1. **Understand the schema** – call `retrieve_reservationsdb_columns` to inspect column names and descriptions.\n\n"
        "2. **Review inputs** – re‑read `better_question`, `user_goal`, and `research_plan`. Identify exactly which metrics, filters, groupings, and timeframes are required.\n\n"
        "3. **Plan your SQL** – sketch out:\n"
        "   • Which specific columns or expressions to SELECT (no `SELECT *`).\n"
        "   • Which aggregations (`SUM`, `AVG`, `COUNT`, etc.) or analytic functions are needed.\n"
        "   • Precise `WHERE` filters, `GROUP BY` clauses, and any subqueries or CTEs to pre‑filter data.\n\n"
        "4. **Write the query** – translate your plan into a single, optimized SQL statement that pushes all logic into the database (aggregations, joins, subqueries).\n\n"
        "5. **Execute** – use `execute_sql_query(...)` to run your SQL and fetch results.\n\n"
        "6. **Generate a detailed report** – create a long markdown report summarizing the findings, including:\n"
        "   - Key insights and conclusions derived from the data.\n"
        "   - Any trends, patterns, or anomalies observed.\n"
        "   - Recommendations based on the analysis.\n"
        "   - Include graphs or visualizations if explicitly requested.\n\n"
        "7. **Output the results** – return a JSON object containing:\n"
        "   - **original_question**: The user's original question.\n"
        "   - **user_goal**: The user's intended goal or purpose.\n"
        "   - **responding_agent**: Always 'Reservations Analyst'.\n"
        "   - **better_question**: The improved version from the Evaluator Agent.\n"
        "   - **data**: The list of dictionaries returned by `execute_sql_query`.\n"
        "   - **report**: The markdown report with data table, insights, conclusions, and recommendations. Link in any resort context via `retrieve_resort_general_information`, avoiding raw DB jargon.\n\n"
        "Always favor tight, aggregate‑first SQL (GROUP BY, filters, CTEs) over post‑processing large raw datasets to minimize token usage and maximize clarity."
        "DO NOT USE RESORT COLUMN. THEY ARE ALL FOR ITZANA RESORT."
        "Do not mention anything about a graph. It will be handled separately by the Graph Code Agent if needed."
    ),
    tools=[execute_sql_query, retrieve_resort_general_information, WebSearchTool()],
    output_type=AgentOutputSchema(analyst_output, strict_json_schema=False),
)

# -----------------------------------------------------------------------------------------------------------------------------------------
#                                                     Marketing Strategist Agent
# -----------------------------------------------------------------------------------------------------------------------------------------

marketing_strategist_agent = Agent(
    name="Marketing Strategist Agent",
    instructions=(
        "This agent is responsible for analyzing the marketing strategies and performance of the resort. "
        "It receives the output from the Evaluator Agent, which includes the improved question, the user's goal, and a research plan. "
        "The agent should follow these steps to fulfill its task:\n\n"
        "1. **Understand the resort's context**: Use the `retrieve_resort_general_information` tool to gather general information about the resort. "
        "This will help you understand the resort's unique selling points, target audience, and current positioning.\n\n"
        "2. **Review the input**: Use the improved question (`better_question`), the user's goal (`user_goal`), and the research plan (`research_plan`) provided by the Evaluator Agent to guide your analysis. "
        "Ensure that your analysis aligns with the user's goal and addresses the improved question effectively.\n\n"
        "3. **Conduct market research**: Use the `WebSearchTool` to gather external data about market trends, competitor strategies, and customer preferences. "
        "Incorporate this information into your analysis to provide a comprehensive perspective.\n\n"
        "4. **Analyze the data**: Combine the resort's context, the user's goal, and the external research to identify opportunities, challenges, and areas for improvement in the resort's marketing strategies. "
        "Focus on actionable insights that can directly inform marketing decisions.\n\n"
        "5. **Generate a marketing strategy**: Based on your analysis, create a detailed marketing strategy tailored to the resort's needs. "
        "The strategy should include:\n"
        "- Key objectives and goals.\n"
        "- Target audience segmentation.\n"
        "- Recommended marketing channels and tactics.\n"
        "- Messaging and positioning strategies.\n"
        "- Metrics for measuring success.\n\n"
        "6. **Generate a detailed report**: Create a long markdown report summarizing your findings and recommendations. The report should include:\n"
        "- Key insights and conclusions derived from the analysis.\n"
        "- A detailed marketing strategy with actionable recommendations.\n"
        "- Any trends, patterns, or external factors influencing the strategy.\n"
        "- If the user explicitly requests a graph or visualization, include it in the report if possible.\n\n"
        "7. **Output the results**: Provide the following fields in the output:\n"
        "- **original_question**: The user's original question.\n"
        "- **user_goal**: The user's intended goal or purpose.\n"
        "- **responding_agent**: Always 'Marketing Strategist'.\n"
        "- **better_question**: The improved version of the original question provided by the Evaluator Agent.\n"
        "- **data**: Any relevant data or insights gathered during the analysis as a list of dictionaries.\n"
        "- **report**: Written in the user's language. A long markdown report with the analysis, strategy, and recommendations.\n\n"
        "The agent should ensure that all steps are completed thoroughly and that the output aligns with the user's goal and research plan."
        "Do not mention anything about a graph. It will be handled separately by the Graph Code Agent if needed."
    ),
    output_type=AgentOutputSchema(analyst_output, strict_json_schema=False),
    tools=[retrieve_resort_general_information, WebSearchTool()]
)

# -----------------------------------------------------------------------------------------------------------------------------------------
#                                                     Judge Agent
# -----------------------------------------------------------------------------------------------------------------------------------------

class judge_ruling(BaseModel):
    """
    Output model for the Judge Agent.
    """
    veredict: float # 0 - not useful, 0.5 - partially useful, 1 - useful
    reason: str
    usefull_data: Optional[List[Dict[str, Any]]] = None  # If the data is useful, this should contain the data that is useful for the user.
    usefull_report: str = None  # If the report is useful, this should contain the report that is useful for the user.
    suggestions: Optional[str] = None  # If the veredict is not 1, this should contain suggestions on how the analyst could improve the next iteration.


judge_agent = Agent(
    name= "Judge Agent",
    instructions=(
        "You are a specialized judge. You will receive the original question, the user's goal, the data_table and the report from an analyst. "
        "Your task is to evaluate the usefulness of the provided data and report. "
        "There are three possible verdicts:\n" \
        "- 1: The data and report directly and correctly answer the question. "
        "- 0.5: The data and report partially answer the question, missing some information or only covering part of the requirement. "
        "- 0: The data and report do not answer the question at all, being incorrect or irrelevant.\n\n"
        "You should return a verdict (0, 0.5 or 1), a clear explanation of your reasoning, and if the data is useful, "
        "you should return the data that is useful for the user. If the report is useful, you should return the report that is useful for the user.\n\n"
        "If the verdict is not 1, you should suggest how the analyst could improve the next iteration."
        "If graph is needed, it should be a URL to the image generated by the Graph Code Agent, which will be handled separately."
    ),
    output_type=AgentOutputSchema(judge_ruling, strict_json_schema=False),
)


# -----------------------------------------------------------------------------------------------------------------------------------------
#                                                     Graph Code Agent
# -----------------------------------------------------------------------------------------------------------------------------------------
class GraphCodeOutput(BaseModel):
    code: str  # Python code for plotting

graph_code_agent_instructions = """
    You will receive:
    - `table_data`: a Python list of dictionaries (already loaded), each representing a row in a table.
    - `img_buf`: an open BytesIO buffer available for you to save the figure into.
    - `user_question`: the user's request for a specific plot.

    Write Python code using ONLY `table_data` and `img_buf` as already available variables.
    Do NOT load or declare `table_data` or `img_buf`.
    Do NOT call plt.show() anywhere.
    Do NOT use 'import' statements for them.
    Just use pandas and matplotlib to generate the requested plot and save it into the provided `img_buf` with `plt.savefig(img_buf, format='png')` and `img_buf.seek(0)`.
    Do NOT return anything but the code.
"""

graph_code_agent = Agent(
    name="GraphCodeAgent",
    instructions=graph_code_agent_instructions,
    model="gpt-4o",
    output_type=AgentOutputSchema(GraphCodeOutput, strict_json_schema=False)
)
