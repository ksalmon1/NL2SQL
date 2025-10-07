from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPIError
from dotenv import load_dotenv
from typing import List, Optional, Dict, Any
import os
import dspy
import mlflow
import pydantic
import json

from db_schema_example import example_json_schema

db_schema = example_json_schema()

# Load environment variables
load_dotenv()
anthropic_api_key = os.getenv('anthropic_api_key')
gcloud_bq_project = os.getenv('gcloud_bq_project')

# MLflow configuration
mlflow.dspy.autolog()

# Initialize BigQuery client
try:
    bq_client = bigquery.Client(project=gcloud_bq_project)
except Exception as e:
    print(f"Error initializing BigQuery client: {e}")
    print("Make sure you have credentials configured (GOOGLE_APPLICATION_CREDENTIALS or gcloud auth)")
    exit(1)

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
    "When you use a WHERE clause, use `WHERE 1 = 1` as the first condition to make appending conditions easier. Subsequent conditions should use AND/OR on a new row.",
]

#==============================#
#  ----  BigQuery Functions --- #
#==============================#
def clean_sql(sql: str) -> str:
    """Remove markdown formatting from SQL if present.

    Args:
        sql: The SQL query string, potentially with markdown formatting

    Returns:
        Cleaned SQL string without markdown
    """
    sql_clean = sql.strip()
    if sql_clean.startswith("```sql"):
        sql_clean = sql_clean.split("```sql")[1].split("```")[0].strip()
    elif sql_clean.startswith("```"):
        sql_clean = sql_clean.split("```")[1].split("```")[0].strip()
    return sql_clean

def dry_run_bigquery(sql: str) -> Dict[str, Any]:
    """Perform a dry run of a BigQuery SQL query to validate syntax without executing.

    Args:
        sql: The SQL query to validate

    Returns:
        Dict containing validation results and any errors
    """
    try:
        sql_clean = clean_sql(sql)

        # Configure dry run
        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)

        # Execute dry run
        query_job = bq_client.query(sql_clean, job_config=job_config)

        return {
            "valid": True,
            "message": "Query is valid.",
            "errors": []
        }
    except GoogleAPIError as e:
        return {
            "valid": False,
            "message": f"Query validation failed: {str(e)}",
            "errors": [str(e)]
        }
    except Exception as e:
        return {
            "valid": False,
            "message": f"Unexpected error: {str(e)}",
            "errors": [f"Unexpected error: {str(e)}"]
        }

def get_table_schema(dataset_id: str, table_id: str) -> Dict[str, Any]:
    """Get schema information for a BigQuery table.

    Args:
        dataset_id: The dataset ID
        table_id: The table ID

    Returns:
        Dict containing table schema information
    """
    try:
        table_ref = f"{gcloud_bq_project}.{dataset_id}.{table_id}"
        table = bq_client.get_table(table_ref)

        schema_info = {
            "columns": {},
            "description": table.description or ""
        }

        for field in table.schema:
            schema_info["columns"][field.name] = field.field_type

        return schema_info
    except Exception as e:
        return {"error": str(e)}

# Create DSPy tools from BigQuery functions
bigquery_tools = [
    dspy.Tool(
        dry_run_bigquery,
        name="dry_run_bigquery",
        desc="Validate a SQL query with BigQuery dry run to check syntax and estimate costs without executing"
    ),
    dspy.Tool(
        get_table_schema,
        name="get_table_schema",
        desc="Get schema information for a specific BigQuery table"
    )
]

#==============================#
#  ----  1. Data Models   ---- #
#==============================#
class JoinSpec(pydantic.BaseModel):
    left: str
    right: str
    on: str
    type: str | None = pydantic.Field(default=None, description="join type if relevant")

class DbSchema(pydantic.BaseModel):
    tables: Dict[str, List[str]]
    primary_keys: Dict[str, str]
    columns: Dict[str, str] = pydantic.Field(
        description="The column names and their respective data types (e.g., INT, VARCHAR, DATE)"
    )
    joins: List[JoinSpec] = []

class SubProblem(pydantic.BaseModel):
    clause: str = pydantic.Field(
        description="SQL clause name like WHERE, GROUP BY, HAVING, ORDER BY"
    )
    goal: str = pydantic.Field(description="What this clause should accomplish")

class Decomposition(pydantic.BaseModel):
    subproblems: List[SubProblem] = pydantic.Field(
        description="List of subproblems with clause and goal"
    )

class QueryPlan(pydantic.BaseModel):
    steps: List[str] = pydantic.Field(description="Step-by-step plan to generate the query")
    aggregations: List[str] = pydantic.Field(description="List of aggregations to be used")
    filters: List[str] = pydantic.Field(description="List of filters to be applied")
    group_bys: List[str] = pydantic.Field(description="List of GROUP BY clauses to be used")
    order_bys: List[str] = pydantic.Field(description="List of ORDER BY clauses to be used")



#==============================#
# ---  2. DSPy Signatures ---  #
#==============================#
class schemaLinkingAgent(dspy.Signature):
    """Identify relevant tables/columns/joins for the question.
    Return STRICT structured JSON as DbSchema.
    Tables must be qualified with a dataset (e.g. dataset.table)"""

    question: str = dspy.InputField()
    db_schema: str = dspy.InputField()
    schemaLink: DbSchema = dspy.OutputField()

class subproblemLinkingAgent(dspy.Signature):
    """You are a Subproblem Agent. Given the user request and the schema info, you decomposes the query into clause-level
    subproblems (e.g., WHERE, GROUP BY, JOIN, DISTINCT, ORDER BY, HAVING, EXCEPT, LIMIT, UNION)."""

    question: str = dspy.InputField()
    schemaLink: DbSchema = dspy.InputField()
    subProblems: Decomposition = dspy.OutputField()

class queryPlanAgent(dspy.Signature):
    """You are a BigQuery SQL Planning Agent. Given the user request, schema info, and subproblems, you create a step-by-step plan
    to construct a query that will be used to solve the user's request. You produce only the procedural plan and are explicitly restricted from generating
    executable SQL at this stage."""

    question: str = dspy.InputField()
    schemaLink: DbSchema = dspy.InputField()
    subProblems: Decomposition = dspy.InputField()
    plan: QueryPlan = dspy.OutputField()

class sqlQueryAgent(dspy.Signature):
    """You are a SQL Query Agent. Given the user request, schema info, subproblems, and query plan, you generate the final executable SQL query.
    The SQL query must be valid and compatible with Google BigQuery syntax and should accurately reflect the user's intent as outlined in the query plan.
    You must adhere to the provided rules to ensure the SQL is efficient, safe, and correct."""

    question: str = dspy.InputField()
    schemaLink: DbSchema = dspy.InputField()
    subProblems: Decomposition = dspy.InputField()
    plan: QueryPlan = dspy.InputField()
    rules: List[str] = dspy.InputField()
    sql: str = dspy.OutputField(
        desc=(
            "The final executable SQL query that accurately reflects the user's intent as outlined in the query plan." \
            "In markdown format with SQL syntax highlighting."
        )
    )

class sqlCorrectionAgent(dspy.Signature):
    """You are a SQL Correction Agent. Given an SQL query and errors encountered during validation, you analyze the errors and produce a corrected SQL query.
    Your goal is to fix the SQL so it executes successfully and meets the user's original intent.
    You may use the dry_run_bigquery tool to validate your corrections before returning the final SQL."""

    sql: str = dspy.InputField()
    errors: List[str] = dspy.InputField()
    correctedSQL: str = dspy.OutputField(
        desc="The revised SQL query that fixes all validation errors."
    )

#===============================#
# --- 3. TextToSQL Pipeline --- #
#===============================#

class SQLOfThought(dspy.Module):
    def __init__(self):
        super().__init__()

        self.schemaAgent = dspy.Predict(schemaLinkingAgent)
        self.subproblemAgent = dspy.Predict(subproblemLinkingAgent)
        self.planAgent = dspy.Predict(queryPlanAgent)
        self.sqlAgent = dspy.Predict(sqlQueryAgent)
        self.correctionAgent = dspy.ReAct(sqlCorrectionAgent, bigquery_tools)

    def forward(self, question, max_correction_attempts=3):
        schemaInfo = self.schemaAgent(question=question, db_schema=db_schema)

        subproblems = self.subproblemAgent(
            schemaLink=schemaInfo.schemaLink,
            question=question
        )

        queryPlan = self.planAgent(
            schemaLink=schemaInfo.schemaLink,
            question=question,
            subProblems=subproblems.subProblems
        )

        sqlQuery = self.sqlAgent(
            schemaLink=schemaInfo.schemaLink,
            question=question,
            subProblems=subproblems.subProblems,
            rules=RULES,
            plan=queryPlan.plan
        )

        # Direct dry run validation (no LLM call)
        execution = dry_run_bigquery(sqlQuery.sql)

        # Retry loop for corrections
        current_sql = sqlQuery.sql
        attempt = 0

        while execution["errors"] and attempt < max_correction_attempts:
            attempt += 1
            print(f"\n--- Errors detected during dry run (attempt {attempt}/{max_correction_attempts}). Attempting SQL correction... ---")

            correctedSQL = self.correctionAgent(
                sql=current_sql,
                errors=execution["errors"]
            )

            # Validate corrected SQL (direct function call)
            print(f"\n--- Validating corrected SQL (attempt {attempt})... ---")
            execution = dry_run_bigquery(correctedSQL.correctedSQL)

            current_sql = correctedSQL.correctedSQL

            if not execution["errors"]:
                print("\n--- Corrected SQL validated successfully ---")
                print(f"Valid: {execution['valid']}")
                print(f"Message: {execution['message']}")
                print("\n--- Corrected SQL ---")
                print(current_sql)
                return current_sql

        if execution["errors"]:
            print(f"\n--- Failed to correct SQL after {max_correction_attempts} attempts ---")
            print(f"Errors: {execution['errors']}")
            print("\n--- Final SQL (with errors) ---")
            print(current_sql)
            return current_sql
        else:
            print("\n--- Dry Run Successful ---")
            print(f"Valid: {execution['valid']}")
            print(f"Message: {execution['message']}")
            print("\n--- Generated SQL ---")
            print(current_sql)
            return current_sql


def main():
    sql_of_thought = SQLOfThought()

    question = input("Enter your question: ")
    sql_of_thought(question=question)

if __name__ == "__main__":
    main()

    # Please help me find github repos related to finance, their license type, and last commmit message.
    # Please help me find all github repos.
