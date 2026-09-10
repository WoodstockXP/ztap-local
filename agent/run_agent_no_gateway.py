"""
Run the no-gateway baseline agent. No Keycloak, no auth, no tenant
concept at all, that's the point, this is the "what if there were no
enforcement layer" comparison.

Must be run as a module from the project root:

    python -m agent.run_agent_no_gateway "Read record rec-001"
    python -m agent.run_agent_no_gateway "Update record rec-002 to amount 999999"
"""

import argparse

from pydantic_ai.usage import UsageLimits

from .no_gateway_main import build_no_gateway_agent

DEFAULT_REQUEST_LIMIT = 10


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--request-limit", type=int, default=DEFAULT_REQUEST_LIMIT)
    args = parser.parse_args()

    agent = build_no_gateway_agent(model_name=args.model)
    result = agent.run_sync(
        args.prompt, usage_limits=UsageLimits(request_limit=args.request_limit)
    )
    print(result.output)


if __name__ == "__main__":
    main()