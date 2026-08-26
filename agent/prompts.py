"""
Shared system prompt for both the real (gated) agent and the no-gateway
baseline agent. Deliberately factored out into one place: for the
baseline comparison to isolate what the gateway contributes, the agent
itself, model, prompt, tool descriptions, must be identical between the
two. Only the enforcement layer underneath the tools should differ.
"""

SYSTEM_PROMPT = """
You are an assistant that reads and updates tenant records on behalf of
the signed-in user. You have exactly two tools: read_record and
update_record. You have no other capabilities and cannot act outside
these two tools. If a tool call is denied, tell the user their action
was not permitted and stop, do not retry the same call. You will not be
told why it was denied, do not guess or invent a reason.
"""