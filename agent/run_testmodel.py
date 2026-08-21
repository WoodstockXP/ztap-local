"""
Verify the agent's tool wiring without touching Keycloak, the gateway, or
Ollama. Pydantic AI's TestModel calls every registered tool with
placeholder arguments instead of running a real LLM, deterministic and
free. Useful to confirm the plumbing (tool signatures, deps injection,
gateway call handling, denial handling) is correct before spending GPU
time or needing real auth up and running.

Run as a module from the project root:
    python -m agent.run_testmodel
"""

from unittest.mock import MagicMock

from pydantic_ai.models.test import TestModel

from .deps import AgentDeps
from .gateway_session import GatewayDenied
from .main import build_agent


def main():
    print("--- Gateway allows ---")
    fake_gateway = MagicMock()
    fake_gateway.call.return_value = {
        "decision": "ALLOW",
        "action": "readRecord",
        "validated_args": {"record_id": "rec-001"},
    }
    agent = build_agent()
    with agent.override(model=TestModel()):
        result = agent.run_sync("Read record rec-001", deps=AgentDeps(gateway=fake_gateway))
    print("Agent output:", result.output)
    print("Gateway.call invocations:", fake_gateway.call.call_args_list)

    print()
    print("--- Gateway denies ---")
    fake_gateway2 = MagicMock()
    fake_gateway2.call.side_effect = GatewayDenied("Action not permitted")
    with agent.override(model=TestModel()):
        result2 = agent.run_sync(
            "Update record rec-002 to amount 500", deps=AgentDeps(gateway=fake_gateway2)
        )
    print("Agent output:", result2.output)


if __name__ == "__main__":
    main()