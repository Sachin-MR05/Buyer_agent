# Buyer Agent Core

The buyer-side counterpart to `merchant-agent-core` in the Ecommerce-App
repo. Same shape, same think -> act -> observe loop, same LLM-decides /
Executor-enforces split - except this agent's tools are "search the local
merchant registry" and "call another agent's `/agent/message` endpoint"
instead of "call the Java Tool Layer."

## Architecture

```
User (chat UI)
      |
      v
POST /buyer/chat  { chatId?, message }
      v
BuyerAgent.run(chat_id, message)   -- per-chat state, like MerchantAgent's session history
      v
AgentLoop (think -> act -> observe):
   Planner.decide(state) -> LLM -> Decision
   action in SEARCH_MERCHANTS | CONTACT_MERCHANTS | PRESENT_OFFERS
           | ASK_USER | CHECKOUT | CONFIRM_PAYMENT | FINAL_RESPONSE
   Executor.execute(decision, state):
      - SEARCH_MERCHANTS  -> RegistryTool (local, no network)
      - CONTACT_MERCHANTS -> MerchantClient.send_to_many() (parallel HTTP,
                              one thread per shop, each bounded by its own
                              timeout so one slow shop never blocks the rest)
      - CHECKOUT           -> gated: only runs if state.chat.awaiting_confirmation
                              is True, which is only ever set by a prior
                              PRESENT_OFFERS step (see Executor._require_checkout_authorized)
      - CONFIRM_PAYMENT    -> gated: only runs if a checkout is actually
                              AWAITING_PAYMENT for this chat
   loop again with the real observation until a terminal status
```

Every call to a merchant uses the exact wire contract merchant-agent-core's
`app/gateway/routes.py` exposes:

```
POST {agentUrl}
Authorization: {authToken}
{ "requestId": "...", "sessionId": "...", "userId": "...", "message": "...", "channel": "api" }
-> { "requestId", "status", "message", "data", "error" }
```

No merchant-side changes are needed - any shop running that repo's
merchant-agent-core already accepts this.

## Why it stays fast

- **Parallel fan-out.** `MerchantClient.send_to_many()` contacts every
  shortlisted merchant concurrently (`ThreadPoolExecutor`, capped by
  `MAX_PARALLEL_MERCHANTS`), so comparing 4 shops takes as long as the
  slowest one, not the sum of all four.
- **Short per-call timeouts.** `MERCHANT_TIMEOUT_SECONDS` (default 12s) is
  a hard ceiling per shop - a dead or slow merchant becomes a FAILED
  MerchantReply instead of stalling the whole comparison.
- **Local, network-free registry matching.** `RegistryTool` ranks shops by
  keyword overlap in-process - no embedding call, no extra round trip,
  before any merchant is even contacted.
- **Small LLM turns.** The Buyer Agent's own reasoning calls are capped at
  `LLM_MAX_OUTPUT_TOKENS=128` - it only ever needs to emit one short JSON
  decision per iteration, never a long completion.

## The human-in-the-loop checkout gate

Same idea as `TransactionOrchestrator.authorization_check()` on the
merchant side: one fixed, named call site
(`Executor._require_checkout_authorized`) that the LLM cannot route
around. `state.chat.awaiting_confirmation` is set True only by
`PRESENT_OFFERS` and cleared the instant a checkout actually proceeds - so
a `CHECKOUT` decision the very first turn ("just buy whatever iPhone is
cheapest, don't ask") is deterministically blocked, regardless of what the
LLM decided. See `tests/smoke_full_flow.py` for a passing end-to-end run,
including this gate being tripped and recovered from.

## Registry

`POST /registry` accepts the manifest exactly as a shop's `AgentInfo` page
hands it out:

```json
{ "name": "...", "description": "...", "agentUrl": "...", "authToken": "...", "contactPhone": "..." }
```

The auth token is encrypted with a server-side Fernet key
(`REGISTRY_ENCRYPTION_KEY`) the instant it's saved, and no API response -
`POST /registry`, `GET /registry`, or anything else - ever includes it
again, encrypted or not. `RegistryService.resolve_for_call()` is the only
method in the whole service that ever decrypts a token, and it does so
immediately before that one outbound call.

`GET /registry` / `DELETE /registry/{id}` never return or touch
conversation data - registry and chat are fully separate endpoints backed
by separate state, per the UI requirement.

## Running it

Requires a Postgres database.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# paste that into REGISTRY_ENCRYPTION_KEY in .env, set GEMINI_API_KEY,
# and point DATABASE_URL at your Postgres instance, e.g.:
#   createuser buyer_agent -P
#   createdb buyer_agent -O buyer_agent
#   DATABASE_URL=postgresql+psycopg://buyer_agent:<password>@localhost:5432/buyer_agent

uvicorn main:app --reload --port 8010
```

Tables (`merchants`, `chats`, `chat_messages`, `merchant_threads`,
`transcript_lines`) are auto-created on startup via
`Base.metadata.create_all()` - fine for development. For anything you'd
call production, replace that with Alembic migrations; the ORM models in
`app/persistence/models.py` are the source of truth either way.

## Real merchant-agent-core interop

I ran this against the *actual*, unmodified Gateway from
`Sachin-MR05/Ecommerce-App`'s `merchant-agent-core` - real
`app/gateway/routes.py`, real `AgentRequest`/`AgentResponse` contracts,
real `DevAuthenticationService`, real `InMemoryRateLimiter`, real error
handlers - with only the LLM+Java-Tool-Layer-dependent
`AgentOrchestrator` swapped for a scripted stand-in (Gemini/HuggingFace/
OpenAI and the Java backend all need network access this sandbox doesn't
have). That surfaced one real bug: this client was sending
`"channel": "buyer-agent"`, but the merchant gateway's
`validate_incoming_message` only accepts `{web, mobile, api, voice,
chat}` - every checkout call was silently 400'ing. Fixed to
`"channel": "api"` (see `MerchantClient.send`).

With that fix, a full search -> contact -> present offers -> user
confirms -> checkout -> payment link -> user says paid -> payment
verified run passed against the real gateway, and a second, independent
process reload of the chat from Postgres reproduced the full 10-message
history and merchant transcript correctly - not just an in-process
assertion.

**Not yet verified against the real thing:** the actual LLM-driven
reasoning inside `MerchantAgent` (search_products/get_price/etc. tool
calls through the Java backend), since that needs infrastructure this
sandbox can't reach. The wire protocol - the part that determines whether
two independently built agents can talk at all - is confirmed compatible.

## Smoke test

```bash
PYTHONPATH=. python tests/smoke_full_flow.py
```

Spins up a fake merchant agent on `127.0.0.1:9999` implementing the real
wire contract, drives the Buyer Agent through registry -> search -> contact
-> present offers -> user confirms -> checkout -> payment link -> user says
paid -> payment verified, using a scripted LLM so the run is deterministic.
Prints every turn's response and asserts on the terminal states.

## What's not built yet

- **The chat/registry frontend** — see `buyer-agent-frontend/` (separate
  delivery), built and verified to compile against this API shape.
- **Real auth on `/buyer/chat`** - `user_id` is currently hardcoded to
  `"demo-user"`; wire it to whatever session/JWT your ecommerce app already
  uses.
- **A real payment link.** As noted in the design doc, the current merchant
  repo writes a local `payment_page.html` rather than returning a hosted
  URL - fine on one machine, not once buyer and merchant run separately.
- **Verified LLM-driven merchant reasoning.** Only the wire protocol was
  tested against the real merchant-agent-core (see above) - the actual
  search/pricing/inventory tool-calling loop inside it wasn't exercised.
