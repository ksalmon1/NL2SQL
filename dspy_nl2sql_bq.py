from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv
from typing import List, Optional, Dict
import os
import dspy
import mlflow
import pydantic

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
lm = dspy.LM('anthropic/claude-sonnet-4-20250514', 
             api_key=anthropic_api_key,
             temperature=0.0)
dspy.configure(lm=lm)

#-------------------------------#
#     1. Models (Pydantic)      #
#-------------------------------#
class joinSpec(pydantic.BaseModel):
    left: str
    right: str
    on: str
    type: str | None = pydantic.Field(default=None, description="join type if relevant")

class dbSchema(pydantic.BaseModel):
    tables: Dict[str, List[str]]
    primary_keys: Dict[str, str]
    columns: List[str]
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


#-------------------------------#
#      2. DSPy Signatures       #
#-------------------------------#
class schemaLinkingAgent(dspy.Signature):
    """Identify relevant tables/columns/joins for the question.
    Return STRICT structured JSON as dbSchema."""

    question: str = dspy.InputField()
    schemaLink: dbSchema = dspy.OutputField(
        desc=("relevant schema elements")
    )
    rationale: str = dspy.OutputField()

class subproblemLinkingAgent(dspy.Signature):
    """You are a Subproblem Agent. Given the user request and the schema info, you decomposes the query into clause-level 
    subproblems (e.g., WHERE, GROUP BY, JOIN, DISTINCT, ORDER BY, HAVING, EXCEPT, LIMIT, UNION)."""

    question: str = dspy.InputField()
    schemaLink: dbSchema = dspy.InputField()
    subProblems: subProblem = dspy.OutputField()

class queryPlanAgent(dspy.Signature):
    """You are a Query Plan Agent. Given the user request, schema info, and subproblems, you create a step-by-step query plan 
    that will be used to solve the user's request. You produce only the procedural plan and are explicitly restricted from generating 
    executable SQL at this stage."""
    
    question: str = dspy.InputField()
    schemaLink: dbSchema = dspy.InputField()
    subProblems: subProblem = dspy.InputField()
    plan: queryPlan = dspy.OutputField()

class sqlQueryAgent(dspy.Signature):
    """You are a SQL Query Agent. Given the user request, schema info, subproblems, and query plan, you generate the final executable SQL query."""
    
    question: str = dspy.InputField()
    schemaLink: dbSchema = dspy.InputField()
    subProblems: subProblem = dspy.InputField()
    plan: queryPlan = dspy.InputField()
    sql: str = dspy.OutputField(
        desc=(
            "The final executable SQL query that accurately reflects the user's intent as outlined in the query plan."
        )
    )

#-------------------------------#
#    3. TextToSQL Pipeline      #
#-------------------------------#
async def run(question):
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

            schemaAgent = dspy.ReAct(schemaLinkingAgent, tools=dspy_tools)
            schemaInfo = await schemaAgent.acall(question=question)

            subproblemAgent = dspy.Predict(subproblemLinkingAgent)
            subproblems = await subproblemAgent.acall(schemaLink=schemaInfo.schemaLink, question=question)

            planAgent = dspy.ChainOfThought(queryPlanAgent)
            queryPlan = await planAgent.acall(schemaLink=schemaInfo.schemaLink, question=question, subProblems=subproblems.subProblems)

            sqlAgent = dspy.ChainOfThought(sqlQueryAgent)
            sqlQuery = await sqlAgent.acall(schemaLink=schemaInfo.schemaLink, question=question, subProblems=subproblems.subProblems, plan=queryPlan.plan)

if __name__ == "__main__":
    import asyncio

    asyncio.run(run("Please help me find github repos related to finance, their license type, and last commmit message."))
