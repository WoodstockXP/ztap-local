"""
No-gateway baseline agent. Same model, same system prompt, same tool
names and argument shapes as agent/main.py, the only difference is that
these tools call baseline/no_gateway_backend.py directly instead of going
through GatewaySession and the four-gate pipeline. This isolates what the
gateway contributes: if this agent happily reads another tenant's record
or writes a malicious value and the gated version doesn't, that
difference is the pipeline's actual contribution, not an artifact of a
differently-behaved agent.
"""

import os

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider

from baseline import no_gateway_backend

from .prompts import SYSTEM_PROMPT

OLLAMA_BASE_URL = os.environ.get("ZTAP_OLLAMA_BASE_URL", "http://localhost:11434/v1/")

class ReadRecordArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")
    resource_id: str = Field(description='The record ID, e.g. "rec-001".')


class UpdateRecordArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")
    resource_id: str = Field(description='The record ID, e.g. "rec-001".')
    amount: float = Field(description="The new amount value.")


def build_no_gateway_agent(model_name: str = "llama3.2:3b") -> Agent[None, str]:
    model = OpenAIChatModel(
        model_name,
        base_url=OLLAMA_BASE_URL,
        provider=OllamaProvider(base_url=OLLAMA_BASE_URL),
    )
    agent = Agent(model, system_prompt=SYSTEM_PROMPT)

    @agent.tool_plain(retries=3)
    def read_record(args: ReadRecordArgs) -> str:
        """Read a tenant record by its ID."""
        return str(no_gateway_backend.read_record(args.resource_id))

    @agent.tool_plain(retries=3)
    def update_record(args: UpdateRecordArgs) -> str:
        """Update a tenant record's amount field."""
        return str(no_gateway_backend.update_record(args.resource_id, args.amount))

    return agent