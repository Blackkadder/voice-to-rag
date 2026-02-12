import json
import os
from pathlib import Path
from uuid import uuid4
import warnings

import openai
from databricks.sdk import WorkspaceClient
from databricks_openai import UCFunctionToolkit, VectorSearchRetrieverTool
from mlflow.entities import SpanType
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
    output_to_responses_items_stream,
    to_chat_completions_input,
)
from openai import OpenAI
from pydantic import BaseModel
from unitycatalog.ai.core.base import get_uc_function_client
from typing import Any, Callable, Generator, Optional
import mlflow

    


class ToolInfo(BaseModel):
    """
    Class representing a tool for the agent.
    - "name" (str): The name of the tool.
    - "spec" (dict): JSON description of the tool (matches OpenAI Responses format)
    - "exec_fn" (Callable): Function that implements the tool logic
    """

    name: str
    spec: dict
    exec_fn: Callable



def get_system_prompt() -> str:
    """Load system prompt from SYSTEM_PROMPT env var or SYSTEM_PROMPT_FILE."""
    prompt = os.getenv("SYSTEM_PROMPT")
    if prompt:
        return prompt
    prompt_file = os.getenv("SYSTEM_PROMPT_FILE")
    if prompt_file:
        path = Path(__file__).parent / prompt_file
        if path.exists():
            return path.read_text()
    return ""


# PuppyGraph Cypher generation tool (natural language -> Cypher query)
# NOTE: must be after get_system_prompt (cypher_tool imports it at load time)
try:
    from cypher_tool import (
        GENERATE_CYPHER_TOOL_SPEC, generate_cypher,
        EXECUTE_CYPHER_TOOL_SPEC, execute_cypher,
    )
except ImportError:
    from .cypher_tool import (
        GENERATE_CYPHER_TOOL_SPEC, generate_cypher,
        EXECUTE_CYPHER_TOOL_SPEC, execute_cypher,
    )

# TOOL_INFOS.append(
#     ToolInfo(
#         name="generate_cypher",
#         spec=GENERATE_CYPHER_TOOL_SPEC,
#         exec_fn=generate_cypher,
#     )
# )

# TOOL_INFOS.append(
#     ToolInfo(
#         name="execute_cypher",
#         spec=EXECUTE_CYPHER_TOOL_SPEC,
#         exec_fn=execute_cypher,
#     )
# )

