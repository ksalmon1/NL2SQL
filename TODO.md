[X] 1. Refactor into a DSPy module
[ ] 2. Add a context clarifying agent. Determine which columns are needed to answer the question.
[ ] 3. While dspy uses the OutputField type hint to parse the LLM's output into a Pydantic       object, it does not automatically parse string inputs back into Pydantic objects for InputField. The InputField type hint is primarily for documentation.

To make your pipeline robust, the signatures should explicitly expect the data format they will actually receive: a string.

Fix: Change the type hints for any Pydantic model inputs in your signatures from the model type (e.g., dbSchema) to str.