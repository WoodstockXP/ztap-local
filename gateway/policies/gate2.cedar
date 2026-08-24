// Gate 2: Role-Based Tool Authorization.

// Two independent checks. User/Agent distinction (the emerging AuthZen profile: human user as principal/
// Subject, acting agent's scope as part of Context):
//   1. principal.tenant == resource.tenant -- the human user may only touch records in their own tenant.
//   2. action in context.agent.allowedActions -- the specific agent acting on the user's behalf may be scoped MORE narrowly than the user themself, e.g. a read-only agent, even when the user could have performed the action directly. Both must hold.

permit (
    principal,
    action in [Action::"readRecord", Action::"updateRecord"],
    resource
) when {
    principal.tenant == resource.tenant && action in context.agent.allowedActions
};