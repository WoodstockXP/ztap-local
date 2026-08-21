# ZTAP Local Harness (Phase 4)

Local-only prototype environment: build and validate the core pipeline entirely offline before any AWS or Kubernetes work begins.
This is the **Bridge** topology's building blocks running as plain Docker Compose, not yet as Kubernetes; Silo and the EKS deployment are future work.

## 1. Install prerequisites (run these once)

```bash
# Docker
sudo apt update && sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker $USER
# log out and back in, then check:
docker --version
docker compose version

# Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b
# quick sanity check (Ctrl+D to exit the chat):
ollama run llama3.2:3b

# Rust + Cedar CLI
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"
cargo install cedar-policy-cli
cedar --version
```

## 2. Set up the Python environment

```bash
cd ztap-local
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Verify Cedar works

```bash
cedar authorize \
  --policies policies/smoke_test.cedar \
  --entities policies/smoke_test_entities.json \
  --principal 'User::"alice"' \
  --action 'Action::"viewInvoice"' \
  --resource 'Invoice::"inv-001"'
```

You should see `ALLOW`. Change the principal to `User::"bob"` and re-run; you should see `DENY`. That confirms Gate 2's engine is working before any Python code touches it.

## 4. Start Keycloak

```bash
docker compose up -d
```

Wait ~20-30 seconds, then open http://localhost:8080, click "Administration Console", and log in with `admin` / `admin`. If login fails, check the comment in `docker-compose.yml` about the admin env var naming, Keycloak changed this between versions.

To stop it later: `docker compose down` (add `-v` if you also want to wipe the realm data volume).

## 5. Bring up Keycloak with the ztap realm pre-loaded
 
The realm, client, and two tenant test users (`alice`/tenant-a, `bob`/tenant-b) are defined in `keycloak/ztap-realm.json` and auto-import on startup, no manual console clicking required.
 
```bash
docker compose up -d
```
 
Wait ~20-30 seconds, then sanity-check the realm exists:
 
```bash
curl -s http://localhost:8080/realms/ztap/.well-known/openid-configuration | head -c 200
```
 
If that returns JSON (not a 404), the realm imported correctly. Admin console login is still `admin` / `admin` at http://localhost:8080 if you want to look around (Users, alice and bob, should be there with a `tenant` attribute under their Attributes tab).
 
## 6. Run the gateway and exercise all three gates, for real this time
 
`gateway/` implements Frame 1's ContextVars plumbing plus real Gates 1, 2, and 4. **Gate 1 is no longer stubbed**: it verifies the access token's JWT signature against Keycloak's JWKS and verifies a real DPoP proof (RFC 9449) per request, signature, HTTP method/URL match, freshness, replay protection, and binding to that specific access token via the `ath` claim.
 
One named limitation, not hidden: full RFC 9449 also supports an Authorization-Server-issued `cnf.jkt` claim that binds a token to a key for its *entire lifetime*. Keycloak's native support for that varies by version and wasn't confirmed before building this, so Gate 1 verifies proof-of-possession per request instead. Worth writing up as a scoped limitation rather than presenting as complete DPoP coverage.
 
Gate 3 (session envelope enforcement, behind H2) still isn't built, it needs a call-count store and comes after Gates 1/2/4 are solid.
 
Start the gateway:
 
```bash
uvicorn gateway.main:app --reload --port 8001
```
 
In another terminal, use the test client (handles getting a real token from Keycloak and building a real DPoP proof, so you don't have to construct curl commands with a JWT and a signed proof by hand):
 
```bash
# 1. Legit same-tenant call -> expect 200 ALLOW
python client/call_gateway.py alice alice-pass readRecord rec-001
 
# 2. alice (tenant-a) reaching into tenant-b's record -> expect 403, Gate 2 denial
python client/call_gateway.py alice alice-pass readRecord rec-002
 
# 3. Authorized action, out-of-bounds argument -> expect 403, Gate 4 denial
python client/call_gateway.py alice alice-pass updateRecord rec-001 --amount 99999
 
# 4. bob accessing his own tenant's record -> expect 200 ALLOW
python client/call_gateway.py bob bob-pass readRecord rec-002
```
 
Check the gateway's stdout for `[AUDIT] gate=... decision=... detail=...` lines, the caller always gets the same generic denial, the real reason (and which gate caught it) only shows up there.

## 7. Connect a real agent
 
`agent/` wraps the gateway behind two Pydantic AI tools (`read_record`, `update_record`) so an LLM decides when to call them, but the LLM's output is never trusted directly, every call still goes through the full Gates 1/2/4 pipeline via `agent/gateway_session.py`. This is the Untrusted Logic Space from Frame 1: nothing the agent decides can bypass
the gateway's independent decision.
 
First, verify the plumbing with zero cost and no dependencies (no Keycloak, no Ollama, no network):
 
```bash
python -m agent.run_testmodel
```
 
This uses Pydantic AI's `TestModel`, which calls both tools with placeholder arguments rather than running a real LLM. You should see one block showing the gateway allowing, and one showing it denying, with the agent's output containing only the generic "Denied: Action not permitted" message in the second case, never a reason.
 
Once that passes, run it for real (Keycloak and the gateway need to be up, per sections 5-6 above, plus Ollama serving `llama3.2:3b`):
 
```bash
python -m agent.run_agent alice alice-pass "Read record rec-001"
python -m agent.run_agent alice alice-pass "Update record rec-001 to amount 500"
python -m agent.run_agent alice alice-pass "Update record rec-002 to amount 500"   # rec-002 is tenant-b's -> expect denial, Gate 2
python -m agent.run_agent bob bob-pass "Read record rec-002"
```
 
Watch the gateway's stdout for the `[AUDIT]` lines while these run, that's where you can see which gate actually made each decision, since the agent itself is never told.
 
## 8. What's next (still within Phase 4)
 
- **Gate 3**: session envelope enforcement, the aggregate-attack detector behind H2. Needs a call-count store keyed on tenant/agent/action, and a threshold policy for what counts as suspicious volume.
- **User acting_as Agent**: Gate 2's principal is still a single undifferentiated `User`, not the `User acting_as Agent` distinction flagged in the Jul 20th feedback. Worth doing before the prompt-injection test harness, since that distinction is what lets a policy restrict what an agent can do on a user's behalf even when the user themself has broader access.
- **Prompt-injection test harness**: once Gate 3 exists, this is what H1 and H2 actually get measured against, single-shot injection targeting Gates 1/2/4, and multi-call aggregate patterns targeting Gate 3.

## Hardware note

RTX 3050 Laptop GPU, 4GB VRAM, 16GB system RAM. `llama3.2:3b` at Q4 quantization fits fully in VRAM. Confirm actual behavior with `ollama run`.

// como funciona la arquitectura, necesito pods?