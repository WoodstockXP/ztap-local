"""
Run the agent for real: real Keycloak auth (DPoP-bound token), real
gateway pipeline (Gates 1/2/4), real local Ollama model.

Must be run as a module from the project root, not as a bare script,
since agent/ uses relative imports internally:

    python -m agent.run_agent alice alice-pass "Read record rec-001"
    python -m agent.run_agent alice alice-pass "Update record rec-002 to amount 50000"
    python -m agent.run_agent alice alice-pass "Update record rec-001 to amount 500"

Try the second example against alice's own tenant-a records too, and
against bob's tenant-b records, to see the gateway deny a cross-tenant
attempt regardless of how the request is phrased, that denial happens at
Gate 2 independent of anything the model itself decides to do.
"""

import argparse

from .deps import AgentDeps
from .gateway_session import GatewaySession
from .main import build_agent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("username")
    parser.add_argument("password")
    parser.add_argument("prompt")
    parser.add_argument("--model", default="llama3.2:3b")
    args = parser.parse_args()

    gateway = GatewaySession(args.username, args.password)
    agent = build_agent(model_name=args.model)

    result = agent.run_sync(args.prompt, deps=AgentDeps(gateway=gateway))
    print(result.output)


if __name__ == "__main__":
    main()