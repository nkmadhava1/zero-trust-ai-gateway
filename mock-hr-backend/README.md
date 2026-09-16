# Mock HR Backend (Cloud Run)

A small HR API standing in for a real backend. Deliberately trust-nothing
by design: it does not assume a request came through Apigee just because
of its network path.

## Files

| File | Purpose |
|---|---|
| `main.py` | Route handlers for `/employees/me`, `/employees/team`, `/employees/all`. Verifies the delegation token's RS256 signature against Apigee's public key before trusting anything else in the request. Path-based scoping independent of any header. |
| `requirements.txt` | Python dependencies. |
| `Dockerfile` | Container build for Cloud Run deployment. |

## The two things this backend has to get right

1. **Signature verification, not network trust.** Originally this backend
   accepted requests based on "this probably came through the gateway."
   Fixed by independently verifying the delegation JWT's RS256 signature
   against the gateway's public key — confirmed by testing that a
   genuinely valid token, signed by the *wrong* key (a real Okta user
   token, sent directly), gets correctly rejected.
2. **Independent path scoping.** This is what actually caught Finding #2
   at the time — a Manager token, using a tool name it was genuinely
   entitled to, pointed at `/employees/all`. The gateway let it through;
   this backend's own path check didn't.

## Deploy

```bash
gcloud run deploy mock-hr-api --source . --region us-central1
```
