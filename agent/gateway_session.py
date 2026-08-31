"""
Gateway session for the agent to call through.

One of these represents one authenticated user session: the DPoP-bound
access token is fetched once (matching Frame 1, a user authenticates
once, then the resulting bound token and key travel with every request
made on their behalf for that session), and a fresh DPoP proof is built
for each individual call, since RFC 9449 requires per-request freshness
regardless of how long the underlying token lives.

This is intentionally the *only* place credentials or keys exist in the
agent process. The agent's tools (agent/main.py) never see the token or
private key directly, they only call .call() and get back either a
result dict or a GatewayDenied exception.
"""

import base64
import hashlib
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey

KEYCLOAK_TOKEN_URL = os.environ.get("ZTAP_KEYCLOAK_TOKEN_URL", "http://localhost:8080/realms/ztap/protocol/openid-connect/token")
GATEWAY_URL = os.environ.get("ZTAP_GATEWAY_URL", "http://localhost:8001/invoke")
CLIENT_ID = os.environ.get("ZTAP_CLIENT_ID", "ztap-gateway")


class GatewayDenied(Exception):
    """Raised when the gateway returns a 403. Carries only the generic
    denial message, per Frame 1's design the agent is never told which
    gate denied it or why; that detail only exists in the gateway's audit
    log."""


def _jwk_from_ec_public_key(public_key) -> dict:
    numbers = public_key.public_numbers()
    x = base64.urlsafe_b64encode(numbers.x.to_bytes(32, "big")).rstrip(b"=").decode()
    y = base64.urlsafe_b64encode(numbers.y.to_bytes(32, "big")).rstrip(b"=").decode()
    return {"kty": "EC", "crv": "P-256", "x": x, "y": y}


def _build_dpop_proof(
    private_key: EllipticCurvePrivateKey,
    public_jwk: dict,
    http_method: str,
    http_url: str,
    access_token: Optional[str] = None,
) -> str:
    payload = {
        "jti": str(uuid.uuid4()),
        "htm": http_method,
        "htu": http_url,
        "iat": int(time.time()),
    }
    if access_token is not None:
        payload["ath"] = (
            base64.urlsafe_b64encode(hashlib.sha256(access_token.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
    headers = {"typ": "dpop+jwt", "jwk": public_jwk}
    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)


@dataclass
class GatewaySession:
    """One per authenticated user. The agent process itself is shared
    across tenants (per the Aug 10th feedback decision on one-shared-agent
    vs. one-per-tenant); tenant scoping for a given call comes entirely
    from which session's bound token is used to make it, never from any
    state the agent process itself holds."""

    username: str
    password: str
    _private_key: Any = field(default=None, init=False, repr=False)
    _public_jwk: Dict[str, Any] = field(default=None, init=False, repr=False)
    _access_token: str = field(default=None, init=False, repr=False)

    def __post_init__(self):
        self._private_key = ec.generate_private_key(ec.SECP256R1())
        self._public_jwk = _jwk_from_ec_public_key(self._private_key.public_key())
        self._access_token = self._fetch_dpop_bound_token()

    def _fetch_dpop_bound_token(self) -> str:
        token_proof = _build_dpop_proof(
            self._private_key, self._public_jwk, "POST", KEYCLOAK_TOKEN_URL
        )
        resp = httpx.post(
            KEYCLOAK_TOKEN_URL,
            data={
                "grant_type": "password",
                "client_id": CLIENT_ID,
                "username": self.username,
                "password": self.password,
                "scope": "openid",
            },
            headers={"DPoP": token_proof},
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Keycloak token request failed: {resp.status_code} {resp.text}")
        return resp.json()["access_token"]

    def call(self, action: str, resource_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        proof = _build_dpop_proof(
            self._private_key,
            self._public_jwk,
            "POST",
            GATEWAY_URL,
            access_token=self._access_token,
        )
        body = {"action": action, "resource_id": resource_id, "args": args}
        resp = httpx.post(
            GATEWAY_URL,
            json=body,
            headers={"Authorization": f"DPoP {self._access_token}", "DPoP": proof},
        )
        if resp.status_code == 403:
            detail = resp.json().get("detail", {})
            message = detail.get("detail", "Action not permitted") if isinstance(detail, dict) else str(detail)
            raise GatewayDenied(message)
        resp.raise_for_status()
        return resp.json()