"""
Interactive CLI for the HR Assist ADK agent.

Exercises the full stack in one session: get a token -> agent -> tool call
-> Apigee -> verify -> AuthZ -> mint -> Cloud Run.

Requires (same directory): agent.py, tools.py, and a .env with your
Apigee proxy URL and Okta app config.

Usage:
    python hr_assistant_cli.py
"""

import asyncio
import base64
import json
import sys

from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

load_dotenv()

from agent import build_hr_assist_agent

APP_NAME = "hr_assist_cli"


def get_token_by_paste() -> str:
    """Prompt for a pre-obtained access token instead of a real login flow."""
    print("=== HR Assistant Login (paste-token mode) ===")
    print("Get a token first (e.g. python get_user_token.py ...), then paste it below.\n")
    token = input("Access token: ").strip()

    if not token:
        print("No token provided. Exiting.")
        sys.exit(1)

    _print_persona_banner(token)
    return token


def _print_persona_banner(token: str) -> None:
    """Decode (not verify — that's Apigee's job) the token just to show
    who's logged in and as what role, for a friendlier CLI experience."""
    try:
        payload_b64 = token.split(".")[1]
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded))
        email = claims.get("sub", "unknown")
        role = claims.get("role", "unknown")
        if isinstance(role, list):
            role = role[0] if role else "unknown"
        print(f"\nLogged in as {email} (role: {role})\n")
    except Exception:
        print("\nLogged in (token could not be decoded for display, continuing anyway)\n")


async def chat_loop(user_token: str) -> None:
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id="cli-user",
        state={"user_token": user_token},
    )

    runner = Runner(
        app_name=APP_NAME,
        agent=build_hr_assist_agent(user_token),
        session_service=session_service,
    )

    print("Type your question, or 'exit' to quit.\n")
    while True:
        try:
            query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not query:
            continue
        if query.lower() in ("exit", "quit"):
            print("Goodbye.")
            break

        message = types.Content(role="user", parts=[types.Part(text=query)])

        async for event in runner.run_async(
            user_id="cli-user",
            session_id=session.id,
            new_message=message,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                print(f"Agent: {event.content.parts[0].text}\n")


def main() -> None:
    token = get_token_by_paste()
    asyncio.run(chat_loop(token))


if __name__ == "__main__":
    main()