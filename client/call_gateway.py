"""
Local test client for the /invoke endpoint.

Gets a DPoP-bound OAuth 2.0 access token from Keycloak (Direct Access
Grant -- i.e. Resource Owner Password Credentials. Fine for a local test
harness where the "client" is a trusted script holding credentials
directly, but not a grant type to carry into anything production-facing),
then builds fresh RFC 9449 DPoP proofs, one for the token request itself
(so Keycloak binds the issued token to this key via cnf.jkt) and one per
subsequent gateway call using the same keypair.

Usage:
    python client/call_gateway.py alice alice-pass readRecord rec-001
    python client/call_gateway.py alice alice-pass readRecord rec-002   # cross-tenant -> expect DENY
    python client/call_gateway.py alice alice-pass updateRecord rec-001 --amount 99999  # expect DENY (Gate 4)
"""

import argparse
import base64
import hashlib
import os
import time
import uuid

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import ec

KEYCLOAK_TOKEN_URL = os.environ.get("ZTAP_KEYCLOAK_TOKEN_URL", "http://localhost:8080/realms/ztap/protocol/openid-connect/token")
GATEWAY_URL = os.environ.get("ZTAP_GATEWAY_URL", "http://localhost:8001/invoke")
CLIENT_ID = os.environ.get("ZTAP_CLIENT_ID", "ztap-gateway")


def jwk_from_ec_public_key(public_key) -> dict:
    numbers = public_key.public_numbers()
    x = base64.urlsafe_b64encode(numbers.x.to_bytes(32, "big")).rstrip(b"=").decode()
    y = base64.urlsafe_b64encode(numbers.y.to_bytes(32, "big")).rstrip(b"=").decode()
    return {"kty": "EC", "crv": "P-256", "x": x, "y": y}


def build_dpop_proof(
    private_key, public_jwk: dict, http_method: str, http_url: str, access_token: str = None
) -> str:
    payload = {
        "jti": str(uuid.uuid4()),
        "htm": http_method,
        "htu": http_url,
        "iat": int(time.time()),
    }
    if access_token is not None:
        # Only present on proofs sent alongside an already-issued token,
        # not on the proof used for the initial token request itself.
        payload["ath"] = (
            base64.urlsafe_b64encode(hashlib.sha256(access_token.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
    headers = {"typ": "dpop+jwt", "jwk": public_jwk}
    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)


def get_dpop_bound_access_token(username: str, password: str, private_key, public_jwk: dict) -> str:
    token_proof = build_dpop_proof(private_key, public_jwk, "POST", KEYCLOAK_TOKEN_URL)
    resp = httpx.post(
        KEYCLOAK_TOKEN_URL,
        data={
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "username": username,
            "password": password,
            "scope": "openid",
        },
        headers={"DPoP": token_proof},
    )
    if resp.status_code >= 400:
        print("Keycloak token endpoint error:", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()["access_token"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("username")
    parser.add_argument("password")
    parser.add_argument("action")
    parser.add_argument("resource_id")
    parser.add_argument("--amount", type=float, default=100.0)
    args = parser.parse_args()

    private_key = ec.generate_private_key(ec.SECP256R1())
    public_jwk = jwk_from_ec_public_key(private_key.public_key())

    access_token = get_dpop_bound_access_token(args.username, args.password, private_key, public_jwk)

    proof = build_dpop_proof(private_key, public_jwk, "POST", GATEWAY_URL, access_token=access_token)

    if args.action == "updateRecord":
        call_args = {"record_id": args.resource_id, "amount": args.amount}
    else:
        call_args = {"record_id": args.resource_id}

    body = {"action": args.action, "resource_id": args.resource_id, "args": call_args}
    resp = httpx.post(
        GATEWAY_URL,
        json=body,
        headers={"Authorization": f"DPoP {access_token}", "DPoP": proof},
    )
    print(resp.status_code, resp.json())


if __name__ == "__main__":
    main()