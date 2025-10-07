### Changed
- Migrated from MCP (Model Context Protocol) tools to direct BigQuery API integration
- Removed async/await pattern - all operations now run synchronously
- Updated all Pydantic model names to follow PascalCase convention:
  - `joinSpec` → `JoinSpec`
  - `dbSchema` → `DbSchema`
  - `subProblem` → `SubProblem`
  - `decomposition` → `Decomposition`
  - `queryPlan` → `QueryPlan`
  - `correctionPlan` → `CorrectionPlan` (later removed)
- Replaced `executeSQLAgent` ReAct wrapper with direct `dry_run_bigquery()` function calls
- Merged `sqlCorrectionPlanAgent` and `sqlCorrectionAgent` into single `sqlCorrectionAgent`
- Changed `planAgent` from `ChainOfThought` to `Predict` for faster execution
- Updated `forward()` method to return the final SQL query
- Fixed type hints: `any` → `Any` throughout codebase

### Added
- `clean_sql()` helper function to extract SQL from markdown formatting
- Error handling for BigQuery client initialization with helpful error messages
- Dry run validation of corrected SQL before returning results
- Retry loop with configurable `max_correction_attempts` (default: 3) for SQL corrections
- BigQuery dry run validation function that returns syntax validation without execution

### Removed
- MCP client dependencies (`mcp`, `ClientSession`, `StdioServerParameters`)
- `asyncio` module and all async operations
- `executeSQLAgent` signature (replaced with direct function call)
- `sqlCorrectionPlanAgent` signature (merged into `sqlCorrectionAgent`)
- `CorrectionPlan` Pydantic model (no longer needed)

### Performance Improvements
- Eliminated 2+ LLM calls per query by removing ReAct wrapper from dry run validation
- Saved 1 LLM call per correction attempt by merging correction planning and execution
- Reduced token overhead by replacing ChainOfThought with Predict for query planning
- **Total reduction**: 3+ fewer LLM calls per successful query execution