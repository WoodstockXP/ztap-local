"""
The agent runtime: this is the Untrusted Logic Space from Frame 1. Its
output (which tool it calls, and with what arguments) is never trusted
directly, every call still passes through the full Gates 1/2/4 pipeline
in gateway.py via GatewaySession. The tools defined here are thin
wrappers with no authorization logic of their own; they cannot bypass
the gateway even if the model's reasoning is compromised by prompt
injection, since the gateway makes its own independent decision on every
call regardless of what the agent claims.
"""

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider

from .deps import AgentDeps
from .gateway_session import GatewayDenied

SYSTEM_PROMPT = """
You are an assistant that reads and updates tenant records on behalf of
the signed-in user. You have exactly two tools: read_record and
update_record. You have no other capabilities and cannot act outside
these two tools. If a tool call is denied, tell the user their action
was not permitted and stop, do not retry the same call. You will not be
told why it was denied, do not guess or invent a reason.
"""


class ReadRecordArgs(BaseModel):
    # extra="ignore" instead of the default "forbid": local models
    # occasionally emit an extra field (e.g. a stray "format": "json")
    # that isn't part of the declared schema. Silently dropping it is
    # safer than crashing the run over it, since Gate 4 on the actual
    # gateway re-validates every argument anyway, this tolerance can
    # never let anything unsafe through, it just stops a cosmetic model
    # quirk from taking down the whole agent run.
    model_config = ConfigDict(extra="ignore")

    resource_id: str = Field(description='The record ID, e.g. "rec-001".')


class UpdateRecordArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")

    resource_id: str = Field(description='The record ID, e.g. "rec-001".')
    amount: float = Field(description="The new amount value.")


def build_agent(model_name: str = "llama3.2:3b") -> Agent[AgentDeps, str]:
    model = OpenAIChatModel(
        model_name,
        provider=OllamaProvider(base_url="http://localhost:11434/v1/"),
    )
    agent = Agent(model, deps_type=AgentDeps, system_prompt=SYSTEM_PROMPT)

    @agent.tool(retries=3)
    def read_record(ctx: RunContext[AgentDeps], args: ReadRecordArgs) -> str:
        """Read a tenant record by its ID."""
        try:
            result = ctx.deps.gateway.call(
                "readRecord", args.resource_id, {"record_id": args.resource_id}
            )
        except GatewayDenied as exc:
            return f"Denied: {exc}"
        return str(result)

    @agent.tool(retries=3)
    def update_record(ctx: RunContext[AgentDeps], args: UpdateRecordArgs) -> str:
        """Update a tenant record's amount field."""
        try:
            result = ctx.deps.gateway.call(
                "updateRecord",
                args.resource_id,
                {"record_id": args.resource_id, "amount": args.amount},
            )
        except GatewayDenied as exc:
            return f"Denied: {exc}"
        return str(result)

    return agent