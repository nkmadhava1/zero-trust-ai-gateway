# Apigee Proxy — `hr-agent-llm-gateway`

Standard Apigee proxy bundle layout. Import this whole folder as your
`apiproxy/` directory (via `apigeecli`, Maven plugin, or the UI's bundle
import).

## Structure

```
apiproxy/
├── proxies/          ProxyEndpoint(s) — default (client-facing) flow
├── targets/           TargetEndpoint(s) — Vertex AI (LLM calls) and
│                       hr-backend (Cloud Run HR API)
├── policies/           All policy XML/JS, in flow order below
└── resources/jsc/      JavaScript used by the JS policies (AuthZ-Check,
                        the two ADK-shape-detection steps, etc.)
```

## Flow order

### ProxyEndpoint `default` — PreFlow (Request)

1. `AM-Normalize-User-Token` — *conditional:* `request.header.X-User-Token != null`.
   Promotes the ADK agent's `X-User-Token` header to `Authorization`, so the
   rest of the flow only ever has to look in one place for the bearer token.
2. `EV-Extract-Bearer` — strips the `Bearer ` prefix into `rawjwt`.
3. `JWT-Verify-Okta-User` — verifies the Okta-issued JWT (RS256, JWKS lookup).
4. `AM-UserClaims` — pulls `user.email` / `user.role` from the verified claims.
5. `JS-ExtractUserRole` — unwraps Okta's role claim (issued as a JSON array)
   down to a single string, and builds `user.act` (the `{sub, role}` object
   later embedded in the delegation token).
6. `JS-AuthZ-Check` — role → tool, tool → path, and agent scope-ceiling
   checks. Sets `authz.denied` / `authz.reason`.
7. `RF-Deny-Unauthorized` — *conditional:* `authz.denied = true`. 403s the
   request before anything downstream (Model Armor, LLM, backend) is touched.
8. `Q-PerUser` — per-user rate limiting, keyed on `user.email`.
9. `KVM-GetSigningKey` — loads the Apigee signing private key from the
   environment-scoped KVM.
10. `KVM-GetIssuer` — loads the configured token issuer string from KVM.
11. `JWT-MintAgentToken` — mints the short-lived, scoped delegation JWT
    (`act` claim = calling user; audience = `backend:hr-api`).
12. `JS-DetectFunctionResponseTurn` — flags whether this request is an
    ADK tool-response turn (no plain `text` part) and whether the path is
    under `/employees/`, so Model Armor's JSONPath extraction doesn't choke
    on a shape it wasn't built for.
13. `SUP-Sanitize-User-Prompt` (Model Armor, inbound) — *conditional:*
    `(flow.isEmployeesPath = false) and (flow.isUserTextTurn = true)`.
    Runs only on genuine LLM-bound conversational turns.

### ProxyEndpoint `default` — PostFlow (Response)

1. `JS-DetectFunctionCall` — same shape-detection logic as step 12, applied
   to the response side (flags `functionCall` turns).
2. `SMR-Sanitize-Model-Response` (Model Armor, outbound) — *conditional:*
   `(flow.isEmployeesPath = false) and (flow.isTextResponse = true)`.
3. `DC-AuditStats` — writes `user.email` / `user.role` / `proxy.pathsuffix` /
   `authz.denied` to the custom-report data collectors.

### DefaultFaultRule (always enforced)

- `DC-FaultStats` — same data collectors as `DC-AuditStats`, plus
  `fault.name`, so a denied or errored request still shows up in reporting.

### Target-specific

- **`hr-backend` (Cloud Run), own PreFlow:** `AM-Attach-Agent-Token` —
  takes the JWT already minted by `JWT-MintAgentToken` back in the
  ProxyEndpoint PreFlow and attaches it as the outbound `Authorization`
  header, plus `X-User-Email` / `X-User-Role` for logging. Note this step
  only *attaches* the token — the actual minting happens once, upstream,
  regardless of which target the request ends up routed to.
- **`default` (Vertex AI):** no target-specific policies; auth to Vertex
  is handled by the target's own `GoogleAccessToken` config.

Routing: `RouteRule to-hr-backend` sends anything matching
`proxy.pathsuffix MatchesPath "/employees/**"` to the `hr-backend` target;
everything else falls through to the `default` (Vertex AI) target.
