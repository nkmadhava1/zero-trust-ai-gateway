"""
get_user_token.py

A small local CLI helper that performs a real Okta Authorization Code + PKCE
login for ONE persona at a time, and prints the resulting access token to
stdout so you can export it as DEMO_USER_ACCESS_TOKEN (see agent.py / README.md
in this same folder).

USAGE:
    python get_user_token.py \
      --okta-domain XXX-XXXXXXXX.okta.com \
      --client-id YOUR_WEB_APP_CLIENT_ID \
      --client-secret YOUR_WEB_APP_CLIENT_SECRET
      --scope "openid profile email hr.read:self"

Run this once per persona: log in as demo.employee@test.org for one run,
demo.manager@test.org for another, etc. -- Okta will prompt you to log out
and back in as a different user if you're already authenticated as someone
else in your browser session.
"""

# --- Standard library imports -------------------------------------------------
import argparse
import base64
import hashlib
import http.server
import secrets
import threading
import urllib.parse
import webbrowser
import requests

# --- Constants ---------------------------------------------------------------
REDIRECT_PORT = 8080

REDIRECT_PATH = "/authorization-code/callback"


def generate_pkce_pair():
    """
    Generates a PKCE code_verifier and its corresponding code_challenge.

    Returns:
        A tuple of (code_verifier, code_challenge) strings.
    """
    
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")

    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    return code_verifier, code_challenge


class _CallbackState:
    """
    A tiny shared object used to pass the captured authorization code (or an
    error) out of the background HTTP server thread and back to the main
    thread, since we can't easily `return` a value from inside the request
    handler class the http.server module expects.
    """
    def __init__(self):
        self.auth_code = None
        self.error = None


def _build_callback_handler(expected_state: str, state_holder: _CallbackState):
    """
    Constructs a request-handler class (http.server requires a class, not an
    instance) that knows about this specific login attempt's expected
    `state` value and where to stash the result.
    """

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            # Parse the incoming redirect URL's query parameters.
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != REDIRECT_PATH:
                # Ignore any stray requests (e.g. browser favicon fetches)
                # that aren't the actual OAuth redirect.
                self.send_response(404)
                self.end_headers()
                return

            query = urllib.parse.parse_qs(parsed.query)

            # Verify the `state` parameter matches what we sent, to guard
            # against cross-site request forgery on this local callback.
            returned_state = query.get("state", [None])[0]
            if returned_state != expected_state:
                state_holder.error = "State mismatch -- possible CSRF or stale login attempt."
            elif "error" in query:
                # Okta reports login errors (e.g. access_denied) via query params.
                state_holder.error = query.get("error_description", query.get("error"))[0]
            else:
                state_holder.auth_code = query.get("code", [None])[0]

            # Respond to the browser so the user sees a clean confirmation
            # instead of a hung tab or a raw error page.
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            if state_holder.auth_code:
                self.wfile.write(b"<html><body><h3>Login successful. You can close this tab.</h3></body></html>")
            else:
                self.wfile.write(b"<html><body><h3>Login failed. Check your terminal for details.</h3></body></html>")

        def log_message(self, format, *args):
            # Silence the default per-request console logging so it doesn't
            # clutter the script's own output.
            pass

    return CallbackHandler


def get_user_access_token(
    okta_domain: str,
    client_id: str,
    client_secret: str,
    scope: str = "openid profile email",
) -> str:
    """
    Runs the full interactive Authorization Code + PKCE flow against Okta
    and returns the resulting access token.

    Args:
        okta_domain: Your Okta org's domain, e.g. "dev-XXXXXXXX.okta.com"
            (no https:// prefix).
        client_id: The Client ID of your Okta Web Application client
            (a confidential OIDC client, distinct from the agent's own
            delegation-signing identity).
        client_secret: The Client Secret of that same client.
        scope: Space-separated OAuth scopes to request. Defaults to just
            the standard OIDC scopes, which always matches Okta's fallback
            Access Policy rule regardless of which persona is logging in.

            IMPORTANT -- if you've set up per-group Access Policy rules
            in Okta, its "Scopes requested: the following scopes"
            condition requires the ENTIRE requested scope set to be a
            SUBSET of a rule's allowed list for that rule to match at
            all -- it does NOT silently drop/down-scope extra scopes. So
            you must explicitly pass only the scopes this persona is
            actually entitled to, e.g.:
                Employee:  "openid profile email hr.read:self"
                Manager:   "openid profile email hr.read:self hr.read:team"
                HR Admin:  "openid profile email hr.read:self hr.read:team hr.read:all"
            Requesting more than a persona's rule allows will NOT get
            silently trimmed -- it will fail the whole request with
            "no_matching_policy", since no rule's scope list is a superset
            of what was asked for. That failure mode is actually a useful,
            more realistic negative test case in its own right -- just
            don't use it as your default for normal persona logins.

    Returns:
        The access token string.
    """
    code_verifier, code_challenge = generate_pkce_pair()

    # A random value we'll check against the redirect's `state` param, to
    # confirm the redirect we receive corresponds to the login we started
    # (and isn't, e.g., a leftover from a previous run or an injected request).
    state = secrets.token_urlsafe(16)

    redirect_uri = f"http://localhost:{REDIRECT_PORT}{REDIRECT_PATH}"

    # Build the /authorize URL Okta expects, per the OIDC Authorization Code
    # + PKCE flow.
    authorize_params = {
        "client_id": client_id,
        "response_type": "code",
        "scope": scope,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    authorize_url = f"https://{okta_domain}/oauth2/default/v1/authorize?" + urllib.parse.urlencode(authorize_params)

    # Start the temporary local server in a background thread so the main
    # thread can block waiting for the browser round-trip to complete.
    state_holder = _CallbackState()
    handler_class = _build_callback_handler(expected_state=state, state_holder=state_holder)
    server = http.server.HTTPServer(("localhost", REDIRECT_PORT), handler_class)

    server_thread = threading.Thread(target=server.handle_request)
    # handle_request() serves exactly ONE request then returns -- we only
    # ever expect exactly one redirect per login attempt.
    server_thread.start()

    print(f"Opening your browser to log in to Okta...\n{authorize_url}\n")
    webbrowser.open(authorize_url)

    # Block until the single expected redirect request has been handled.
    server_thread.join(timeout=180)

    if state_holder.error:
        raise RuntimeError(f"Okta login failed: {state_holder.error}")
    if not state_holder.auth_code:
        raise RuntimeError("Timed out waiting for the Okta login redirect. Try again.")

    # Exchange the authorization code for tokens. This step also sends the
    # code_verifier, which Okta hashes and compares against the
    # code_challenge we sent earlier -- proving this exchange request came
    # from the same script instance that started the login, not an
    # intercepted redirect replayed by someone else.
    token_response = requests.post(
        f"https://{okta_domain}/oauth2/default/v1/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        auth=(client_id, client_secret),
        # HTTP Basic auth with the client's own credentials -- appropriate
        # here because this is a confidential Web Application client,
        # which is allowed to hold a secret.
        data={
            "grant_type": "authorization_code",
            "code": state_holder.auth_code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        },
        timeout=15,
    )
    token_response.raise_for_status()
    token_data = token_response.json()

    return token_data["access_token"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Obtain a real Okta user access token via Authorization Code + PKCE.")
    parser.add_argument("--okta-domain", required=True, help="e.g. dev-XXXXXXXX.okta.com (no https://)")
    parser.add_argument("--client-id", required=True, help="Okta Web Application client ID (confidential OIDC client)")
    parser.add_argument("--client-secret", required=True, help="Okta Web Application client secret (same client as --client-id)")
    parser.add_argument(
        "--scope",
        default="openid profile email",
        help=(
            "Space-separated OAuth scopes to request. Defaults to the safe "
            "standard OIDC scopes, which match Okta's fallback rule for any "
            "persona. If you've set up per-group Access Policy rules, "
            "explicitly pass only the hr.read:* scopes this specific "
            "persona is entitled to -- requesting more than their rule "
            "allows will fail with no_matching_policy rather than being "
            "silently trimmed."
        ),
    )
    args = parser.parse_args()

    token = get_user_access_token(
        okta_domain=args.okta_domain,
        client_id=args.client_id,
        client_secret=args.client_secret,
        scope=args.scope,
    )

    print("\n--- Access token (export this as DEMO_USER_ACCESS_TOKEN) ---")
    print(token)
