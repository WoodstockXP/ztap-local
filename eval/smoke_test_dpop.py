import argparse
import json
import time
import uuid

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm


def build_dpop_proof(private_key, htm, htu):
    jwk = json.loads(ECAlgorithm.to_jwk(private_key.public_key()))
    payload = {"jti": str(uuid.uuid4()), "htm": htm, "htu": htu, "iat": int(time.time())}
    return jwt.encode(payload, private_key, algorithm="ES256", headers={"typ": "dpop+jwt", "jwk": jwk})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keycloak-url", default="http://localhost:8080/realms/ztap/protocol/openid-connect/token")
    parser.add_argument("--gateway-url", default="http://localhost:8001/invoke")
    parser.add_argument("--username", default="alice")
    parser.add_argument("--password", default="alice-pass")
    args = parser.parse_args()

    private_key = ec.generate_private_key(ec.SECP256R1())

    token_proof = build_dpop_proof(private_key, "POST", args.keycloak_url)
    token_response = httpx.post(
        args.keycloak_url,
        headers={"DPoP": token_proof},
        data={"grant_type": "password", "client_id": "ztap-gateway", "username": args.username, "password": args.password},
    )
    print("token endpoint:", token_response.status_code, token_response.text)
    token_response.raise_for_status()
    access_token = token_response.json()["access_token"]

    invoke_proof = build_dpop_proof(private_key, "POST", args.gateway_url)
    invoke_response = httpx.post(
        args.gateway_url,
        headers={"Authorization": f"Bearer {access_token}", "DPoP": invoke_proof, "Content-Type": "application/json"},
        json={},
    )
    print("gateway endpoint:", invoke_response.status_code, invoke_response.text)


if __name__ == "__main__":
    main()
