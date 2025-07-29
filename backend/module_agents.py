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


class orchestator_agent_output (BaseModel):
    assigned_agents: Optional [List[Literal["data_analyst", "marketing_analyst"]]]  # ordered; [] if answering directly or awaiting clarification
    user_question: str
    user_goal: str
    commentary: str
    requires_graph: bool = False
    clarifying_question: Optional[str]   # new


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
    name="Orchestrator Agent",
    instructions = """
        You are the Orchestrator Agent for Itz'ana Resort’s analytics suite. Your job is to read the last user message in `convo`, 
        determine intent, decide which analyst agents (if any) should run, and set whether a graph is explicitly requested.

        AVAILABLE ANALYSTS
        - data_analyst
        - Purpose: Run SELECT‑only SQL over the SQLite `reservations` DB and return a JSON table + plain‑text interpretation.
        - Use when: The question requires fresh metrics, new aggregations/filters, or different time windows not already present in `convo`.

        - marketing_analyst
        - Purpose: Use the internal knowledge base (and web if allowed) to provide marketing insights: personas, positioning, amenity context, messaging.
        - Use when: The user needs narrative/strategy/context beyond raw SQL metrics (or to interpret newly computed metrics).

        DECISION POLICY
        1) Extract:
        - user_question = exact text of the last user message.
        - user_goal = one‑sentence objective (what the user ultimately wants).
        2) Can the request be answered directly from existing information in `convo` (tables/findings already present, no new data needed)?
        - YES → assigned_agents = [] and in commentary say “Answer directly from existing convo context” and cite which items you’ll use.
        - NO  → assign agents as needed, in the correct order:
                • data_analyst → marketing_analyst when marketing depends on fresh metrics.
                • data_analyst only for pure metrics.
                • marketing_analyst only for narrative grounded in existing data/KB.
        3) If essential details are missing (date range, segment, metric definition) and you cannot proceed safely:
        - assigned_agents = []
        - commentary must contain ONE concise clarifying question (and, if reasonable, a conservative assumption you could use if the user approves).
        4) Graph detection:
        - requires_graph = true only if the user explicitly asks for a graph/plot/chart/visual/line/bar/pie/heatmap “show/draw/graph/plot/visualize”.
        - Otherwise requires_graph = false. If a chart would help but wasn’t requested, keep false and mention the suggestion in commentary.

        GUARDRAILS
        - Do not run tools or write SQL yourself; only route.
        - Avoid redundant work: if equivalent results already exist in `convo`, don’t reassign agents unless the user requests a different slice/period/metric.
        - Keep commentary concise: state routing rationale, assumptions, and (if applicable) your clarifying question.

        OUTPUT — return ONLY this JSON object (no markdown):
        {
        "assigned_agents": Optional[List["data_analyst", "marketing_analyst"]],  // ordered; [] if answering directly or awaiting clarification
        "user_question": str,                                                    // exact last user message
        "user_goal": str,                                                        // one-sentence intent
        "commentary": str,                                                       // routing rationale; include clarifying question here if needed
        "requires_graph": bool                                                   // default false; true only on explicit user request
        }
    """,
    tools=[
        retrieve_wholesalers_list,
        retrieve_resort_general_information,
        retrieve_reservationsdb_columns
    ], 
    output_type=orchestator_agent_output,
    model="gpt-4o-mini",
)


class analyst_output(BaseModel):
    """
    Output model for the Analyst-type agents.
    """
    data: List[Dict[str, Any]] = None # a list of multiple table as json responses. 
    findings: str # a list of findings made by analysts agents. 
    clarifying_question: Optional[str]



# -----------------------------------------------------------------------------------------------------------------------------------------
#                                                     Reservations Data Analyst Agent
# -----------------------------------------------------------------------------------------------------------------------------------------

@function_tool
def execute_sql_query(query: str, max_rows: int = 1000, sample_size: int = 1000) -> List[Dict[str, Any]]:
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
    

data_analyst = Agent(
    name="data_analyst",

    instructions = """
        You are a specialized data‑analyst for Itz'ana Resort. Answer the user’s question by querying the SQLite database’s `reservations` table via the `execute_sql_query` tool. Never produce charts or code—only query and interpret.

        WORKFLOW
        1) Understand the question. If essential details (date range, segment, metric definition) are missing and block execution, return ONE concise clarifying question.
        2) (Once per session as needed) Introspect schema: PRAGMA table_info('reservations'); use actual column names/types.
        3) Design a query plan to minimize rows: required columns, filters, grouping, aggregations, expected row count.
        4) Run a single SELECT‑only SQL via `execute_sql_query`. Never DDL/DML (no INSERT/UPDATE/DELETE/CREATE/DROP).
        5) Inspect results. If they don’t answer the question or approach >300 rows, refine the strategy (tighter filters/aggregation) and re‑query. Converge in ≤2 refinements.

        ROW‑MINIMIZATION RULES
        - Prefer GROUP BY, aggregates (SUM/COUNT/AVG/MIN/MAX), WHERE, HAVING, CTEs, and window functions over raw rows.
        - Do NOT use LIMIT for size control. Design the query so the natural result set is ≤300 rows (e.g., aggregate by month/category instead of listing reservations).
        - Select only necessary columns; never SELECT *.
        - For “top/bottom N”, compute ROW_NUMBER()/RANK() in a CTE and filter rn ≤ N (avoid LIMIT).
        - Use explicit date filters (YYYY‑MM‑DD). Treat stored dates as naive local dates; do not apply timezone math.

        SQLITE‑SPECIFIC GUIDELINES
        - Date math: nights = CAST(julianday(DEPARTURE) - julianday(ARRIVAL) AS INTEGER).
        - Month key: strftime('%Y-%m', ARRIVAL).
        - Case‑insensitive match: LOWER(col) LIKE LOWER('%term%') or COLLATE NOCASE.
        - Booleans as 0/1; handle NULLs with COALESCE.
        - Safe division: x * 1.0 / NULLIF(y, 0).
        - Rounding: ROUND(value, 2). Cast explicitly when mixing ints/floats.
        - Use CTEs (WITH ...) to pre‑filter then aggregate.

        SCOPE & HONESTY
        - Compute only what is supported by available columns. If a requested metric (e.g., true occupancy/RevPAR requiring room inventory) is not derivable from `reservations` alone, say so and propose the smallest additional data or a reasonable proxy (e.g., booked‑nights).

        INTERPRETATION
        - Provide clear calculations and units (nights, %, currency) based strictly on the returned table(s).
        - If the result set is empty/insufficient, say so and propose the minimal next step (tighter filter or small additional aggregation).

        OUTPUT — return ONLY this JSON object (no markdown):
        {
        "data": [ <table_json_1>, <table_json_2>, ... ],  // a list of JSON tables; usually provide ONE table. Include >1 only if essential (keep each aggregated/compact).
        "findings": "Plain‑text interpretation that answers the question, including key insights/patterns/anomalies and any assumptions or data limitations.",
        "clarifying_question": "<Only if blocking details are missing; else ''>"
        }
        Rules for 'data':
        - If you asked a clarifying question, set data to null and findings to ''.
        - Normally return a single aggregated table (as an array of row objects) wrapped in a list, e.g., [ [ {col: val, ...}, ... ] ].
        - Return multiple small tables only when necessary to answer the question (e.g., a totals table plus a breakdown).
    """
    ,
    tools=[execute_sql_query, retrieve_resort_general_information, WebSearchTool()],
    output_type=AgentOutputSchema(analyst_output, strict_json_schema=False),
    model="gpt-4o-mini",
)

# -----------------------------------------------------------------------------------------------------------------------------------------
#                                                     Marketing Strategist Agent
# -----------------------------------------------------------------------------------------------------------------------------------------

marketing_strategist_agent = Agent(
    name="Marketing Strategist Agent",

    instructions = """
        You are the Marketing Analyst for Itz'ana Resort. Produce a detailed, well‑reasoned marketing strategy grounded in 
        (a) the latest tables/findings already present in `convo` and 
        (b) the hotel’s internal knowledge base. You MAY invoke WebSearchTool() only if the internal KB cannot answer essential context. Never produce charts or code.

        SCOPE
        - Personas, positioning, seasonality, amenity fit, messaging angles, offers/bundles, channel/campaign ideas, retention/CRO, on‑property upsell/cross‑sell, pricing levers (non‑binding).
        - Do NOT invent numbers. If you reference quantities, they must come from `convo` tables/findings or reputable sources found via WebSearchTool().

        WORKFLOW
        1) Understand the user’s goal from the last message in `convo`.
        2) Anchor all claims to `convo` data when present; you may compute simple proportions/deltas from that data.
        3) Fill gaps from the internal KB first. If still insufficient, invoke WebSearchTool() sparingly (≤3 reputable sources) and integrate findings.
        4) If essential details are missing and block the work, return ONLY a single clarifying question (no strategy).

        STYLE & CONSTRAINTS
        - Plain text only (no markdown). Use absolute dates (YYYY‑MM‑DD) for time references.
        - Be specific and hotel‑aware; avoid generic advice.
        - If certain metrics are not derivable from available data (e.g., true occupancy without inventory), state the limitation and propose a minimal proxy or the smallest extra data needed.

        OUTPUT — return ONLY this JSON object (no markdown):
        {
        "data": null,  // marketing_analyst does not return tables; always set to null
        "findings": "A cohesive strategy narrative in plain text. Internally label sections like: Insights:, Actions:, Assumptions:, Sources:. If WebSearchTool() was used, include the link under Sources:.",
        "clarifying_question": "<Only if blocking details are missing; else ''>"
        }
        If you set a non‑empty clarifying_question, keep findings empty ('') and data null.
        """
    ,
    output_type=AgentOutputSchema(analyst_output, strict_json_schema=False),
    tools=[retrieve_resort_general_information, WebSearchTool()],
    model="gpt-4o-mini",
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
    suggestions: Optional[str] = None  # If the veredict is not 1, this should contain suggestions on how the analyst could improve the next iteration.


judge_agent = Agent(
    name= "Judge Agent",
    instructions=(
        "You are a specialized judge. You will receive the original question, the user's goal, the data_table and the report from an analyst. "
        "Your task is to evaluate the usefulness of the provided data and report. "
        "There are three possible verdicts:\n" \
        "- 1: The data and report directly and correctly answer the question. "
        "- 0.5: The data and report partially answer the question, missing some information or only covering part of the requirement. "
        "- 0: The data and report do not answer the question at all, being incorrect or irrelevant.\n"
        "You should return a verdict (0, 0.5 or 1), a clear explanation of your reasoning, and if the data is useful, "
        "you should return the data that is useful for the user.\n"
        "If the verdict is not 1, you should suggest how the analyst could improve the next iteration."
        "If graph is needed, it should be a URL to the image generated by the Graph Code Agent, which will be handled separately."
    ),
    output_type=AgentOutputSchema(judge_ruling, strict_json_schema=False),
    model="gpt-4o-mini",
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
    model="gpt-4o-mini",
    output_type=AgentOutputSchema(GraphCodeOutput, strict_json_schema=False),
)
