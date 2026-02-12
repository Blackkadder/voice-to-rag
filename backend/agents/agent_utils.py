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


def create_tool_info(tool_spec, exec_fn_param: Optional[Callable] = None):
    tool_spec["function"].pop("strict", None)
    tool_name = tool_spec["function"]["name"]
    udf_name = tool_name.replace("__", ".")

    # Define a wrapper that accepts kwargs for the UC tool call,
    # then passes them to the UC tool execution client
    def exec_fn(**kwargs):
        function_result = uc_function_client.execute_function(udf_name, kwargs)
        if function_result.error is not None:
            return function_result.error
        else:
            return function_result.value
    return ToolInfo(name=tool_name, spec=tool_spec, exec_fn=exec_fn_param or exec_fn)


TOOL_INFOS = []

# You can use UDFs in Unity Catalog as agent tools
# TODO: Add additional tools
UC_TOOL_NAMES = []

# uc_toolkit = UCFunctionToolkit(function_names=UC_TOOL_NAMES)
# uc_function_client = get_uc_function_client()
# for tool_spec in uc_toolkit.tools:
#     TOOL_INFOS.append(create_tool_info(tool_spec))


# Use Databricks vector search indexes as tools
# See [docs](https://docs.databricks.com/generative-ai/agent-framework/unstructured-retrieval-tools.html) for details

# # (Optional) Use Databricks vector search indexes as tools
# # See https://docs.databricks.com/generative-ai/agent-framework/unstructured-retrieval-tools.html
# # for details
VECTOR_SEARCH_TOOLS = []
# # TODO: Add vector search indexes as tools or delete this block
# VECTOR_SEARCH_TOOLS.append(
#         VectorSearchRetrieverTool(
#         index_name="",
#         # filters="..."
#     )
# )
for vs_tool in VECTOR_SEARCH_TOOLS:
    TOOL_INFOS.append(create_tool_info(vs_tool.tool, vs_tool.execute))


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
    from cypher_tool import GENERATE_CYPHER_TOOL_SPEC, generate_cypher
except ImportError:
    from .cypher_tool import GENERATE_CYPHER_TOOL_SPEC, generate_cypher

TOOL_INFOS.append(
    ToolInfo(
        name="generate_cypher",
        spec=GENERATE_CYPHER_TOOL_SPEC,
        exec_fn=generate_cypher,
    )
)

