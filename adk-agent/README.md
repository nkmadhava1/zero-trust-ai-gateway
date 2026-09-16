# ADK Agent — HR Assist

Google ADK agent with real HR tool calling, wrapped so that **every** LLM
call — conversational and tool-invoking — routes through the Apigee
gateway, not just the tool calls.

## Files

| File | Purpose |
|---|---|
| `get_user_token.py` | Local CLI helper that performs a real Okta Authorization Code + PKCE login for one persona and prints the resulting access token to stdout. Run this **first**, once per persona, to get the token `hr_assistant_cli.py` needs. See "Getting a token" below. |
| `agent.py` | Builds the `LlmAgent`, wired to `ApigeeLlm` so conversational turns also go through Apigee/Model Armor. Built as a factory function per session, not a module-level singleton, since the user's token isn't known at import time. |
| `tools.py` | The HR tool functions (`get_my_salary_info`, `get_team_salary_info`, `get_all_salary_info`). Each function hardcodes its own path **and** matching `X-Tool-Name` header together — this is why Finding #2's gap is only reachable by bypassing the agent, not through it. |
| `hr_assistant_cli.py` | Interactive `You:` / `Agent:` CLI demo — exercises the full stack: paste token → agent → tool call → Apigee → verify → AuthZ → mint → Cloud Run. |
| `.env.example` | Copy to `.env` and fill in your Apigee proxy URL, Okta app config, etc. |
| `requirements.txt` | Python dependencies. |

## Getting a token

Okta's Authorization Code flow needs a real browser redirect — there's no
way to `curl` a human login. `get_user_token.py` bridges that gap the same
way `gcloud auth login` does: it opens your system browser to Okta's
`/authorize` endpoint, spins up a temporary local server to catch the
redirect (the "loopback" pattern), and exchanges the returned code for a
token using your Okta Web Application client's ID and secret.

```bash
python get_user_token.py \
  --okta-domain YOUR-OKTA-DOMAIN.okta.com \
  --client-id YOUR_WEB_APP_CLIENT_ID \
  --client-secret YOUR_WEB_APP_CLIENT_SECRET \
  --scope "openid profile email"
```

- `--okta-domain` — no `https://` prefix, e.g. `dev-XXXXXXXX.okta.com`.
- `--client-id` / `--client-secret` — your Okta **Web Application** client's
  credentials (not the agent's own delegation-signing identity).
- `--scope` — optional, defaults to `openid profile email`. If you've set
  up per-persona Access Policy rules in Okta, pass only the `hr.read:*`
  scopes that specific persona is entitled to — requesting more than the
  rule allows fails with `no_matching_policy` rather than silently
  trimming.

Log in as `demo.employee@test.org` for one run, `demo.manager@test.org`
for another, etc. — Okta will prompt you to log out and back in as a
different user if your browser session is already authenticated as
someone else.

The script prints the access token to stdout. Copy it — `hr_assistant_cli.py`
will prompt you to paste it in (paste-token mode, not a live login flow).

## Setup

```bash
cp .env.example .env        # fill in your values
pip install -r requirements.txt
python get_user_token.py --okta-domain ... --client-id ... --client-secret ...
python hr_assistant_cli.py  # paste the token when prompted
```
