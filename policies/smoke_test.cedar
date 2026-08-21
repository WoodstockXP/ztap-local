// Trivial policy just to confirm the Cedar CLI works end to end.
// Not a real Gate 2 policy yet -- that comes once you formalize
// the User/Agent principal distinction from the Jul 20th feedback
// (principal == User::"alice" acting_as Agent::"invoice-agent-v2").

permit (
    principal == User::"alice",
    action == Action::"viewInvoice",
    resource == Invoice::"inv-001"
);
