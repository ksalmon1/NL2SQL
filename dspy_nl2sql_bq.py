from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

import os
import dspy
import mlflow

load_dotenv()

anthropic_api_key = os.getenv('anthropic_api_key')

mlflow.set_tracking_uri("http://localhost:5000")
mlflow.set_experiment("DSPy")
mlflow.dspy.autolog()

# Create server parameters for stdio connection
server_params = StdioServerParameters(
    command="C:\\Users\\Kenny\\dspy_playground\\toolbox.exe",
    args=["--prebuilt","bigquery","--stdio"],
    env={"BIGQUERY_PROJECT": "deep-circuits"}
)

class schemaLinkingAgent(dspy.Signature):
    """You are a Schema Linking Agent who parses the natural language question in conjunction with the database schema to identify the relevant tables and columns
required for answering the query. In addition, you extract structural information such as primary keys,
foreign keys, and join relationships. You do not create or run SQL queries at this stage. You do not create a 
query strategy."""

    user_request: str = dspy.InputField()
    process_result: str = dspy.OutputField(
        desc=(
            "Forms the foundation for subsequent steps by constraining SQL generation to schema-relevant entities." \
            "Your output should be a concise technical summary of the relevant schema elements and their relationships."
        )
    )

class subproblemLinkingAgent(dspy.Signature):
    """You are a Subproblem Agent. Given the user request and the schema info, you decomposes the query into clause-level 
    subproblems (e.g., WHERE, GROUP BY, JOIN, DISTINCT, ORDER BY, HAVING, EXCEPT, LIMIT, UNION)."""

    schema_info: str = dspy.InputField()
    user_request: str = dspy.InputField()
    process_result: str = dspy.OutputField(
        desc=(
            "Each identified clause is expressed as a key/value pair in a structured JSON object, where the key "
            "is the clause type and the value is the partially completed clause expression. This decomposition "
            "provides a modular representation of the query intent, enabling downstream agents to reason over "
            "smaller, well-defined units."
        )
    )

class queryPlanAgent(dspy.Signature):
    """You are a Query Plan Agent. Given the user request, schema info, and subproblems, you create a step-by-step query plan 
    that will be used to solve the user's request. You produce only the procedural plan and are explicitly restricted from generating 
    executable SQL at this stage."""
    
    schema_info: str = dspy.InputField()
    user_request: str = dspy.InputField()
    sub_problems: str = dspy.InputField()
    process_result: str = dspy.OutputField(
        desc=(
            "A step-by-step execution plan that maps the user’s intent to the schema and subproblems"
        )
    )

class sqlQueryAgent(dspy.Signature):
    """You are a SQL Query Agent. Given the user request, schema info, subproblems, and query plan, you generate the final executable SQL query.
    Remove extraneous artifacts such as trailing semicolons or natural language fragments, ensuring the query is syntactically valid."""
    
    schema_info: str = dspy.InputField()
    user_request: str = dspy.InputField()
    sub_problems: str = dspy.InputField()
    query_plan: str = dspy.InputField()
    process_result: str = dspy.OutputField(
        desc=(
            "The final executable SQL query that accurately reflects the user's intent as outlined in the query plan."
        )
    )

lm = dspy.LM('anthropic/claude-sonnet-4-20250514', 
             api_key=anthropic_api_key,
             temperature=0.0)
dspy.configure(lm=lm)

async def run(user_request):
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
            schemaInfo = await schemaAgent.acall(user_request=user_request)

            subproblemAgent = dspy.Predict(subproblemLinkingAgent)
            subproblems = await subproblemAgent.acall(schema_info=schemaInfo.process_result, user_request=user_request)

            planAgent = dspy.ChainOfThought(queryPlanAgent)
            queryPlan = await planAgent.acall(schema_info=schemaInfo.process_result, user_request=user_request, sub_problems=subproblems.process_result)

            sqlAgent = dspy.ChainOfThought(sqlQueryAgent)
            sqlQuery = await sqlAgent.acall(schema_info=schemaInfo.process_result, user_request=user_request, sub_problems=subproblems.process_result, query_plan=queryPlan.process_result)

if __name__ == "__main__":
    import asyncio

    asyncio.run(run("Please help me find github repos related to finance, their license type, and last commmit message."))