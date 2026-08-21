// Gate 2: Role-Based Tool Authorization.

// A user may read or update a record only when that record belongs to the same tenant as the user. This is a coarse, boolean check, it does not look at argument content (that's Gate 4's job).

// NOTE: this still uses a single undifferentiated principal type (User). The Jul 20th feedback flagged that Gate 2's principal should formally distinguish the human user from the acting agent (principal == User::"alice" acting_as Agent::"invoice-agent-v2"), per the emerging AuthZen profile. Deliberately deferred until the single-principal version is working end to end.

permit (
    principal,
    action in [Action::"readRecord", Action::"updateRecord"],
    resource
) when {
    principal.tenant == resource.tenant
};