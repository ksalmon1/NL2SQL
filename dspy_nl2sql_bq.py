from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv
from typing import List, Optional, Dict
import os
import dspy
import mlflow
import pydantic

from db_schema_example import example_json_schema

db_schema = example_json_schema()

# Load environment variables
load_dotenv()
anthropic_api_key = os.getenv('anthropic_api_key')
gcloud_toolbox = os.getenv('gcloud_toolbox')
gcloud_bq_project = os.getenv('gcloud_bq_project')

# MLflow configuration
mlflow.set_tracking_uri("http://localhost:5000")
mlflow.set_experiment("DSPy")
mlflow.dspy.autolog()

# Create server parameters for stdio connection
server_params = StdioServerParameters( 
    command=gcloud_toolbox,
    args=["--prebuilt","bigquery","--stdio"],
    env={"BIGQUERY_PROJECT": gcloud_bq_project}
)

# LM Configuration
lm = dspy.LM('claude-sonnet-4-5-20250929', 
             api_key=anthropic_api_key,
             temperature=0.0)
dspy.configure(lm=lm)

RULES = [
    "Use CTEs for complex queries",
    "Use table aliases to shorten table names",
    "Use column aliases for computed columns",
    "Only use SQL features supported by the target dialect (given in schema)",
    "Always use explicit JOINs instead of WHERE-based joins",
    "Always use fully qualified column names (table.column)",
    "Ensure the SQL is syntactically correct",
    "Ensure the SQL is semantically correct (e.g. GROUP BY columns)",
    "Ensure the SQL addresses all subtasks in the decomposition",
    "Ensure the SQL is safe against SQL injection (e.g. no direct string interpolation)",
    "Ensure the SQL returns correct results for the question",
    "Ensure the SQL is efficient and scalable (e.g. avoid SELECT *)",
    "Ensure the SQL uses appropriate indexing (e.g. WHERE clauses on indexed columns)",
    "Ensure the SQL uses appropriate aggregation functions (e.g. COUNT, SUM, AVG)",
    "Ensure the SQL uses appropriate filtering (e.g. WHERE, HAVING)",
    "Ensure the SQL uses appropriate sorting (e.g. ORDER BY)",
    "Ensure the SQL uses appropriate grouping (e.g. GROUP BY)",
    "Ensure the SQL uses appropriate joins (e.g. INNER JOIN, LEFT JOIN)",
    "When you use a WHERE caluse, use `WHERE 1 = 1` as the first condition to make appending conditions easier. Subsequent conditions should use AND/OR on a new row.",
]

#==============================#
#  ----  1. Data Models   ---- #
#==============================#
class joinSpec(pydantic.BaseModel):
    left: str
    right: str
    on: str
    type: str | None = pydantic.Field(default=None, description="join type if relevant")

class dbSchema(pydantic.BaseModel):
    tables: Dict[str, List[str]]
    primary_keys: Dict[str, str]
    columns: Dict[str, str] = pydantic.Field(
        description="The column names and their respective data types (e.g., INT, VARCHAR, DATE)"
    )
    joins: List[joinSpec] = []

class subProblem(pydantic.BaseModel):
    clause: str = pydantic.Field(
        description="SQL clause name like WHERE, GROUP BY, HAVING, ORDER BY"
    )
    goal: str = pydantic.Field(description="What this clause should accomplish")

class decomposition(pydantic.BaseModel):
    subproblems: List[subProblem] = pydantic.Field(
        description="List of subproblems with clause and goal"
    )

class queryPlan(pydantic.BaseModel):
    steps: List[str] = pydantic.Field(description="Step-by-step plan to generate the query")
    aggregations: List[str] = pydantic.Field(description="List of aggregations to be used")
    filters: List[str] = pydantic.Field(description="List of filters to be applied")
    group_bys: List[str] = pydantic.Field(description="List of GROUP BY clauses to be used")
    order_bys: List[str] = pydantic.Field(description="List of ORDER BY clauses to be used")

class correctionPlan(pydantic.BaseModel):
    errors: List[str] = pydantic.Field()
    corrections: List[str] = pydantic.Field()


#==============================#
# ---  2. DSPy Signatures ---  #
#==============================#
class schemaLinkingAgent(dspy.Signature):
    """Identify relevant tables/columns/joins for the question.
    Return STRICT structured JSON as dbSchema.
    Tables must be qualified with a dataset (e.g. dataset.table)"""

    question: str = dspy.InputField()
    db_schema: str = dspy.InputField()
    schemaLink: dbSchema = dspy.OutputField()

class subproblemLinkingAgent(dspy.Signature):
    """You are a Subproblem Agent. Given the user request and the schema info, you decomposes the query into clause-level 
    subproblems (e.g., WHERE, GROUP BY, JOIN, DISTINCT, ORDER BY, HAVING, EXCEPT, LIMIT, UNION)."""

    question: str = dspy.InputField()
    schemaLink: dbSchema = dspy.InputField()
    subProblems: decomposition = dspy.OutputField()

class queryPlanAgent(dspy.Signature):
    """You are a BigQuery SQL Planning Agent. Given the user request, schema info, and subproblems, you create a step-by-step plan 
    to construct a query that will be used to solve the user's request. You produce only the procedural plan and are explicitly restricted from generating 
    executable SQL at this stage."""
    
    question: str = dspy.InputField()
    schemaLink: dbSchema = dspy.InputField()
    subProblems: decomposition = dspy.InputField()
    plan: queryPlan = dspy.OutputField()

class sqlQueryAgent(dspy.Signature):
    """You are a SQL Query Agent. Given the user request, schema info, subproblems, and query plan, you generate the final executable SQL query.
    The SQL query must be valid and compatible with Google BigQuery syntax and should accurately reflect the user's intent as outlined in the query plan.
    You must adhere to the provided rules to ensure the SQL is efficient, safe, and correct."""
    
    question: str = dspy.InputField()
    schemaLink: dbSchema = dspy.InputField()
    subProblems: decomposition = dspy.InputField()
    plan: queryPlan = dspy.InputField()
    rules: List[str] = dspy.InputField()
    sql: str = dspy.OutputField(
        desc=(
            "The final executable SQL query that accurately reflects the user's intent as outlined in the query plan." \
            "In markdown format with SQL syntax highlighting."
        )
    )

class executeSQLAgent(dspy.Signature):
    """You are a SQL Execution Agent. Given an executable SQL query, you execute it against the connected database and return the results.
    Ensure that the execution is safe and does not compromise the integrity of the database.
    ***Dry run only.***"""

    sql: str = dspy.InputField()
    results: List[Dict[str, str]] = dspy.OutputField(
        desc="The results of executing the SQL query, formatted as a list of dictionaries where each dictionary represents a row with column names as keys."
    )
    errors: List[str] = dspy.OutputField(
        desc="Any errors encountered during SQL execution, or null if execution was successful."
    )

class sqlCorrectionPlanAgent(dspy.Signature):
    """You are a SQL Correction Agent. Given an SQL query and any errors encountered during its execution, you analyze the errors and provide corrections.
    Your goal is to refine the SQL query to ensure it executes successfully and meets the user's original intent.
    You ONLY return the correction plan. You do not execute the corrected SQL."""

    sql: str = dspy.InputField()
    errors: List[str] = dspy.InputField()
    correctPlan: correctionPlan = dspy.OutputField()

class sqlCorrectionAgent(dspy.Signature):
    """You are a SQL Correction Agent. Given an SQL query and a correction plan, you apply the corrections to the SQL query.
    Your goal is to produce a revised SQL query that addresses the issues identified in the correction plan and is ready for execution.
    You ONLY return the corrected SQL. You do not execute the corrected SQL."""

    sql: str = dspy.InputField()
    correctPlan: correctionPlan = dspy.InputField()
    correctedSQL: str = dspy.OutputField(
        desc="The revised SQL query that incorporates the corrections outlined in the correction plan."
    )

#===============================#
# --- 3. TextToSQL Pipeline --- #
#===============================#
async def Main(question):
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()
            # List available tools
            tools = await session.list_tools()

            # Convert MCP tools to DSPy tools
            dspy_tools = []
            for tool in tools.tools:
                dspy_tools.append(dspy.Tool.from_mcp_tool(session, tool))

            #schemaAgent = dspy.ReAct(schemaLinkingAgent, tools=dspy_tools)
            # Use ReAct for shcema linking using tools
            schemaAgent = dspy.Predict(schemaLinkingAgent)
            schemaInfo = await schemaAgent.acall(question=question, db_schema=db_schema)

            subproblemAgent = dspy.Predict(subproblemLinkingAgent)
            subproblems = await subproblemAgent.acall(schemaLink=schemaInfo.schemaLink, question=question)

            planAgent = dspy.ChainOfThought(queryPlanAgent)
            queryPlan = await planAgent.acall(schemaLink=schemaInfo.schemaLink, question=question, subProblems=subproblems.subProblems)

            sqlAgent = dspy.Predict(sqlQueryAgent)
            sqlQuery = await sqlAgent.acall(
                schemaLink=schemaInfo.schemaLink,
                question=question,
                subProblems=subproblems.subProblems,
                rules=RULES,
                plan=queryPlan.plan
            )

            sqlRunAgent = dspy.ReAct(executeSQLAgent, tools=dspy_tools)
            execution = await sqlRunAgent.acall(sql=sqlQuery.sql)
            
            if execution.errors:
                print(" --- Errors detected. Attempting SQL correction... ---")
                correctionPlanAgent = dspy.ReAct(sqlCorrectionPlanAgent, tools=dspy_tools)
                correction = await correctionPlanAgent.acall(sql=sqlQuery.sql, errors=execution.errors)

                correctionAgent = dspy.Predict(sqlCorrectionAgent)
                correctedSQL = await correctionAgent.acall(sql=sqlQuery.sql, correctPlan=correction.correctPlan)
                print("Corrected SQL: ", correctedSQL.correctedSQL)
            else:
                print("SQL Results: ", sqlQuery.sql)


if __name__ == "__main__":
    import asyncio

    # Please help me find github repos related to finance, their license type, and last commmit message.
    # Please help me find all github repos.
    asyncio.run(Main("Please help me find github repos related to finance, their license type, and last commmit message."))
