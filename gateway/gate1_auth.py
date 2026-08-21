"""
Gate 1: Authentication and Tenant Resolution.

JWT signature verification against Keycloak's JWKS, plus full RFC 9449
DPoP verification, both the Authorization-Server-issued lifetime binding
(cnf.jkt on the access token, confirmed available in Keycloak 26.4+ as of
Oct 2025, no longer preview) and the required per-request proof checks
(signature, htm/htu match, freshness, replay, ath binding). RFC 9449 still
requires the resource server to do the per-request checks even when the
AS also binds the token at issuance, so both layers stay in place.

Depends on the client having "Require DPoP bound tokens" enabled in
Keycloak (see keycloak/ztap-realm.json). The realm-import attribute name
used there is inferred from Keycloak's existing naming convention for the
equivalent mTLS setting (tls.client.certificate.bound.access.tokens) and
was not confirmed against current docs, verify it actually took effect
via the admin console (Clients -> ztap-gateway -> Capability config ->
"Require DPoP bound tokens" toggle) before trusting this in the paper.
"""

import base64
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Dict

import jwt
from jwt import PyJWKClient
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

from .context import SecurityContext, get_security_context

KEYCLOAK_ISSUER = "http://localhost:8080/realms/ztap"
JWKS_URL = f"{KEYCLOAK_ISSUER}/protocol/openid-connect/certs"
EXPECTED_CLIENT_ID = "ztap-gateway"

DPOP_FRESHNESS_WINDOW_SECONDS = 60

_jwk_client = PyJWKClient(JWKS_URL)
_seen_dpop_jti: Dict[str, float] = {}  # jti -> expiry epoch (replay cache)


class Gate1Denied(Exception):
    pass


@dataclass
class Gate1Result:
    principal: str
    tenant: str


def evaluate_gate1(http_method: str, http_url: str) -> Gate1Result:
    ctx: SecurityContext = get_security_context()

    if not ctx.raw_token:
        raise Gate1Denied("Missing access token")
    if not ctx.raw_dpop_proof:
        raise Gate1Denied("Missing DPoP proof")

    signing_key = _fetch_signing_key(ctx.raw_token)
    claims = _verify_access_token_claims(ctx.raw_token, signing_key)

    expected_jkt = claims.get("cnf", {}).get("jkt")
    if not expected_jkt:
        raise Gate1Denied(
            "Access token is not DPoP-bound (missing cnf.jkt claim) -- "
            "check 'Require DPoP bound tokens' is enabled on the client"
        )

    _verify_dpop_proof(ctx.raw_dpop_proof, ctx.raw_token, http_method, http_url, expected_jkt)

    tenant = claims.get("tenant")
    principal = claims.get("preferred_username") or claims.get("sub")
    if not tenant or not principal:
        raise Gate1Denied("Token missing required tenant/principal claims")

    ctx.verified_principal = principal
    ctx.verified_tenant = tenant
    return Gate1Result(principal=principal, tenant=tenant)


def _fetch_signing_key(token: str):
    try:
        return _jwk_client.get_signing_key_from_jwt(token).key
    except jwt.PyJWTError as exc:
        raise Gate1Denied(f"Could not resolve signing key: {exc}") from exc


def _verify_access_token_claims(token: str, signing_key) -> Dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256", "ES256"],
            issuer=KEYCLOAK_ISSUER,
            # Keycloak's direct-grant tokens default `aud` to "account"
            # rather than the requesting client ID, a known quirk. `azp`
            # (authorized party) is checked explicitly below instead of
            # relying on audience validation here.
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        raise Gate1Denied(f"Access token verification failed: {exc}") from exc

    if claims.get("azp") != EXPECTED_CLIENT_ID:
        raise Gate1Denied("Access token was not issued to the expected client")

    return claims


def _verify_dpop_proof(
    proof: str, access_token: str, http_method: str, http_url: str, expected_jkt: str
) -> None:
    try:
        header = jwt.get_unverified_header(proof)
    except jwt.PyJWTError as exc:
        raise Gate1Denied(f"Malformed DPoP proof header: {exc}") from exc

    if header.get("typ") != "dpop+jwt":
        raise Gate1Denied("DPoP proof missing typ=dpop+jwt header")

    jwk_data = header.get("jwk")
    if not jwk_data:
        raise Gate1Denied("DPoP proof missing embedded jwk")

    # AS-issued lifetime binding: does this proof's key match the key the
    # access token was actually bound to at issuance?
    if _jwk_thumbprint(jwk_data) != expected_jkt:
        raise Gate1Denied(
            "DPoP proof key does not match the key this access token was "
            "bound to at issuance (jkt mismatch)"
        )

    key = _public_key_from_jwk(jwk_data)

    try:
        claims = jwt.decode(
            proof,
            key=key,
            algorithms=[header.get("alg")],
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        raise Gate1Denied(f"DPoP proof signature invalid: {exc}") from exc

    # Per-request checks, still required even with AS-side binding in place.
    if claims.get("htm") != http_method:
        raise Gate1Denied("DPoP proof htm does not match request method")
    if claims.get("htu") != http_url:
        raise Gate1Denied("DPoP proof htu does not match request URL")

    now = time.time()
    iat = claims.get("iat", 0)
    if abs(now - iat) > DPOP_FRESHNESS_WINDOW_SECONDS:
        raise Gate1Denied("DPoP proof is stale")

    jti = claims.get("jti")
    if not jti:
        raise Gate1Denied("DPoP proof missing jti")
    _purge_expired_jti(now)
    if jti in _seen_dpop_jti:
        raise Gate1Denied("DPoP proof replay detected")
    _seen_dpop_jti[jti] = now + DPOP_FRESHNESS_WINDOW_SECONDS

    expected_ath = (
        base64.urlsafe_b64encode(hashlib.sha256(access_token.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    if claims.get("ath") != expected_ath:
        raise Gate1Denied("DPoP proof is not bound to this access token (ath mismatch)")


def _purge_expired_jti(now: float) -> None:
    expired = [jti for jti, expiry in _seen_dpop_jti.items() if expiry < now]
    for jti in expired:
        del _seen_dpop_jti[jti]


def _jwk_thumbprint(jwk_data: dict) -> str:
    """RFC 7638 JWK thumbprint: SHA-256 over required members only, in
    lexicographic key order. Verified against the RFC's own test vector
    before use here."""
    kty = jwk_data.get("kty")
    if kty == "EC":
        canonical = {
            "crv": jwk_data["crv"],
            "kty": "EC",
            "x": jwk_data["x"],
            "y": jwk_data["y"],
        }
    elif kty == "RSA":
        canonical = {"e": jwk_data["e"], "kty": "RSA", "n": jwk_data["n"]}
    else:
        raise Gate1Denied(f"Unsupported key type for thumbprint: {kty}")

    canonical_json = json.dumps(canonical, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(canonical_json.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _public_key_from_jwk(jwk_data: dict):
    kty = jwk_data.get("kty")
    jwk_json = json.dumps(jwk_data)
    if kty == "EC":
        return ECAlgorithm(ECAlgorithm.SHA256).from_jwk(jwk_json)
    if kty == "RSA":
        return RSAAlgorithm(RSAAlgorithm.SHA256).from_jwk(jwk_json)
    raise Gate1Denied(f"Unsupported DPoP key type: {kty}")