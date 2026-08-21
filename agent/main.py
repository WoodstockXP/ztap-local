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
was not permitted. You will not be told why it was denied, do not guess
or invent a reason.
"""


def build_agent(model_name: str = "llama3.2:3b") -> Agent[AgentDeps, str]:
    model = OpenAIChatModel(
        model_name,
        provider=OllamaProvider(base_url="http://localhost:11434/v1/"),
    )
    agent = Agent(model, deps_type=AgentDeps, system_prompt=SYSTEM_PROMPT)

    @agent.tool
    def read_record(ctx: RunContext[AgentDeps], resource_id: str) -> str:
        """Read a tenant record by its ID.

        Args:
            resource_id: The record ID, e.g. "rec-001".
        """
        try:
            result = ctx.deps.gateway.call(
                "readRecord", resource_id, {"record_id": resource_id}
            )
        except GatewayDenied as exc:
            return f"Denied: {exc}"
        return str(result)

    @agent.tool
    def update_record(ctx: RunContext[AgentDeps], resource_id: str, amount: float) -> str:
        """Update a tenant record's amount field.

        Args:
            resource_id: The record ID, e.g. "rec-001".
            amount: The new amount value.
        """
        try:
            result = ctx.deps.gateway.call(
                "updateRecord", resource_id, {"record_id": resource_id, "amount": amount}
            )
        except GatewayDenied as exc:
            return f"Denied: {exc}"
        return str(result)

    return agent