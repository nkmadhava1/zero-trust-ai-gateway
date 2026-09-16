# Zero-Trust AI Gateway

An HR assistant agent (Google ADK + Gemini) with real tool calling, sitting
behind an Apigee gateway that owns every identity, authorization, injection-
screening, and credential-delegation decision — independently of whatever
the LLM decides to do.

Companion code for the write-up: **[link to Medium post]**

> **Note on secrets:** nothing in this repo is a real credential. Copy every
> `.env.example` to `.env` and fill in your own values before running
> anything. Double-check before committing that no real Okta domain, client
> ID/secret, project ID, API key, or bearer token ever makes it into a file,
> a Trace export, or a screenshot.

---

## Architecture

```
   User
    |
    v
  Okta  --(JWT)-->  ADK Agent  --(Bearer token)-->  Apigee Gateway
                                                       |   |
                                          Model Armor--+   +--AuthZ-Check
                                          (injection            (role +
                                           screening)          tool + path)
                                                       |
                                                       v
                                          Attach-Agent-Token
                                          (mints scoped, short-lived
                                           delegation JWT)
                                                       |
                                                       v
                                          Cloud Run HR Backend
                                          (independently verifies the
                                           delegation token's signature)
```

- **Identity:** Okta issues a JWT after login. Apigee re-verifies it on
  every request — no session, no implicit trust from a prior login.
- **Authorization:** the gateway checks role, the tool being invoked, *and*
  whether the tool name actually matches the path it's pointed at (see
  Finding #2 below — this second check didn't exist originally).
- **Injection screening:** Model Armor sits in front of every LLM call,
  including the agent's own conversational turns, not just its tool calls.
- **Delegation:** the gateway mints a new, short-lived, purpose-scoped JWT
  for the backend call. The agent never forwards the user's raw credential.
- **Backend:** a mock HR API that independently verifies the delegation
  token's RS256 signature — it does not trust the request just because it
  arrived through the gateway's network path.

---

## Repo layout

```
hr-assist-zero-trust-gateway/
├── apigee-proxy/          Apigee proxy bundle: policies, routing, target endpoints
├── adk-agent/              The ADK agent, its HR tools, and the CLI demo client
├── mock-hr-backend/        Cloud Run HR API — signature verification + path scoping
└── README.md               You are here
```

Each subfolder has its own README with setup steps specific to that piece.

---

## Findings → code map

If you read the blog post first, this is where each finding actually lives:

| Finding | What it's about | Where to look |
|---|---|---|
| #1 — Model Armor blind spots | Injection filter misses one phrasing, catches another; AuthZ is the layer that actually saved the missed case | `apigee-proxy/apiproxy/policies/SUP-Sanitize-User-Prompt.xml`, `SMR-Sanitize-Model-Response.xml` |
| #2 — tool-authorized ≠ resource-authorized | Gateway checked "is this role allowed to use this tool name," never "does this tool name match this path" | `apigee-proxy/apiproxy/resources/jsc/authz.js` (the `PATH_TOOL_MAP` check), `mock-hr-backend/main.py` (the independent check that caught it), `adk-agent/tools.py` (why this gap is unreachable via the agent itself — each function hardcodes its own path + tool name together) |
| #3 — no gateway control for conversational hijacking | An attack that never triggers a tool call has nothing for the gateway to check | `adk-agent/agent.py` (system instruction) |
| Decision-flag bug | An early scope-limiting check got silently un-denied by a later, unrelated check writing to the same flag | `apigee-proxy/apiproxy/resources/jsc/authz.js` (fail-closed accumulator: `authz.denied` starts `false` once, only ever escalates) |
| Backend trusted network, not crypto | Cloud Run originally accepted requests based on network position; fixed with RS256 signature verification | `mock-hr-backend/main.py` |

---

## Setup order

1. **`apigee-proxy/`** — deploy the proxy bundle, wire up Okta as the JWT
   issuer, create and attach the Model Armor template.
2. **`mock-hr-backend/`** — deploy to Cloud Run; this is the second target
   the proxy routes HR-path requests to. Requires
   `apigee-signing-key-public.pem` (the public half of the Apigee signing
   key — not included in this repo; export it from your own Apigee KVM
   entry and drop it in this folder before building the container) and a
   `.env` copied from `.env.example`.
3. **`adk-agent/`** — install dependencies, copy `.env.example` to `.env`,
   point it at your deployed proxy URL, run `get_user_token.py` and grab
   the token, run `hr_assistant_cli.py` and pass the token.

Full walkthrough in each subfolder's README.

---

## License

MIT — see `LICENSE`.
