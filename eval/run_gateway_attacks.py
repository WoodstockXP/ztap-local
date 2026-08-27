"""
Tier 1: direct, deterministic attacks against the real gateway. No LLM
involved, this tests the gates' own robustness against malicious or
malformed requests, independent of whether any real agent would ever
construct them. Fast and fully reproducible, a necessary complement to
Tier 2 (run_agent_attacks.py), not a replacement for it, this can't tell
you whether prompt injection would ever get an agent to attempt these
requests in the first place.

Requires Keycloak and the gateway already running (README sections 5-6).
Run as a module from the project root:

    python -m eval.run_gateway_attacks
"""

import time

import httpx
from cryptography.hazmat.primitives.asymmetric import ec

from agent.gateway_session import (
    CLIENT_ID,
    GATEWAY_URL,
    KEYCLOAK_TOKEN_URL,
    GatewayDenied,
    GatewaySession,
    _build_dpop_proof,
    _jwk_from_ec_public_key,
)

from .attack_corpus import (
    GATE1_MALFORMED_REQUESTS,
    GATE3_AGGREGATE_ATTACKS,
    GATEWAY_ATTACKS,
)
from .report import HarnessResult, blocking_rate_report, print_summary


def run_single_request_attacks():
    results = []
    sessions = {}  # one real session per (username, password), auth is slow, don't repeat it
    for case in GATEWAY_ATTACKS:
        key = (case["username"], case["password"])
        if key not in sessions:
            sessions[key] = GatewaySession(*key)
        session = sessions[key]
        try:
            session.call(case["action"], case["resource_id"], case["args"])
            actual = "ALLOW"
        except GatewayDenied:
            actual = "DENY"
        passed = actual == case["expect"]
        results.append(
            HarnessResult(
                case["id"], case["description"], case["gate"], case["expect"], actual, passed
            )
        )
    return results


def run_gate1_malformed_requests():
    results = []
    # One real token + keypair, reused across the malformed variants;
    # only the DPoP proof itself gets broken in each case, keeps the
    # "valid token" part constant so we know each denial is specifically
    # about the proof, not something else going wrong.
    key = ec.generate_private_key(ec.SECP256R1())
    jwk = _jwk_from_ec_public_key(key.public_key())
    token_proof = _build_dpop_proof(key, jwk, "POST", KEYCLOAK_TOKEN_URL)
    resp = httpx.post(
        KEYCLOAK_TOKEN_URL,
        data={
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "username": "alice",
            "password": "alice-pass",
            "scope": "openid",
        },
        headers={"DPoP": token_proof},
    )
    resp.raise_for_status()
    access_token = resp.json()["access_token"]

    body = {"action": "readRecord", "resource_id": "rec-001", "args": {"record_id": "rec-001"}}

    for case in GATE1_MALFORMED_REQUESTS:
        if case["kind"] == "missing_dpop_header":
            headers = {"Authorization": f"DPoP {access_token}"}
        elif case["kind"] == "garbage_dpop_proof":
            headers = {"Authorization": f"DPoP {access_token}", "DPoP": "not-a-real-jwt"}
        elif case["kind"] == "wrong_dpop_key":
            attacker_key = ec.generate_private_key(ec.SECP256R1())
            attacker_jwk = _jwk_from_ec_public_key(attacker_key.public_key())
            bad_proof = _build_dpop_proof(
                attacker_key, attacker_jwk, "POST", GATEWAY_URL, access_token=access_token
            )
            headers = {"Authorization": f"DPoP {access_token}", "DPoP": bad_proof}
        else:
            raise ValueError(f"unknown malformed-request kind: {case['kind']}")

        try:
            r = httpx.post(GATEWAY_URL, json=body, headers=headers)
            actual = "ALLOW" if r.status_code == 200 else "DENY"
        except Exception as exc:  # noqa: BLE001 -- want to record any transport failure as a result, not crash the run
            actual = f"ERROR: {exc}"

        passed = actual == case["expect"]
        results.append(
            HarnessResult(
                case["id"], case["description"], case["gate"], case["expect"], actual, passed
            )
        )
    return results


def run_gate3_aggregate_attacks():
    results = []
    for case in GATE3_AGGREGATE_ATTACKS:
        httpx.post("http://localhost:8001/debug/reset")  # clean slate for THIS case specifically
        session = GatewaySession(case["username"], case["password"])
        outcomes = []
        for _ in range(case["call_count"]):
            try:
                session.call(case["action"], case["resource_id"], case["args"])
                outcomes.append("ALLOW")
            except GatewayDenied:
                outcomes.append("DENY")
            time.sleep(0.05)  # don't hammer the local server unnecessarily fast
        expected = ["ALLOW"] * (case["deny_from_call"] - 1) + ["DENY"] * (
            case["call_count"] - case["deny_from_call"] + 1
        )
        passed = outcomes == expected
        detail = f"expected {case['deny_from_call']-1} ALLOW then DENY; got {outcomes}"
        results.append(
            HarnessResult(
                case["id"],
                case["description"],
                case["gate"],
                "pattern match",
                "match" if passed else "mismatch",
                passed,
                extra=detail,
            )
        )
    return results


def main():
    httpx.post("http://localhost:8001/debug/reset")  # clean Gate 3 state before this run

    run_start = time.time()
    print("=== Tier 1: Gateway Attack Corpus ===\n")

    all_results = []
    all_results += run_single_request_attacks()
    all_results += run_gate1_malformed_requests()
    all_results += run_gate3_aggregate_attacks()

    print_summary(all_results)
    blocking_rate_report(since=run_start)


if __name__ == "__main__":
    main()