import os
import json
from fastapi import FastAPI, HTTPException, Request, Depends
from pathlib import Path
import jwt
import logging
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hr-api")

PUBLIC_KEY_PEM = (Path(__file__).parent / "apigee-signing-key-public.pem").read_text()

ISSUER = os.getenv("ISSUER")
AUDIENCE = os.getenv("AUDIENCE")

def verify_agent_token(request: Request) -> dict:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        logger.warning("AUTH_REJECTED: missing token")
        raise HTTPException(status_code=401, detail="Missing token")

    token = auth_header[7:]
    try:
        decoded = jwt.decode(
            token,
            PUBLIC_KEY_PEM,
            algorithms=["RS256"],   # critical — pin explicitly, see note below
            issuer=ISSUER,
            audience=AUDIENCE,
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"AUTH_REJECTED: {type(e).__name__}: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    act = decoded.get("act", {})
    logger.info(f"AUTH_VERIFIED: email={act.get('sub')} role={act.get('role')} exp={decoded.get('exp')}")
    return {"email": act.get("sub"), "role": act.get("role")}


app = FastAPI()

with open("mock_hr_data.json") as f:
    EMPLOYEES = json.load(f)

def find_by_email(email):
    return next((e for e in EMPLOYEES if e["email"] == email), None)

def find_team(manager_id):
    return [e for e in EMPLOYEES if e["manager_id"] == manager_id]

@app.get("/employees/me")
def get_my_salary(user: dict = Depends(verify_agent_token)):
    email = user["email"]
    role = user["role"]
    record = find_by_email(email)
    if not record:
        raise HTTPException(404, "Employee not found")
    return record

@app.get("/employees/team")
def get_team_salaries(user: dict = Depends(verify_agent_token)):
    email = user["email"]
    role = user["role"]
    if role not in ("Managers", "HRAdmins"):
        raise HTTPException(403, "Insufficient role for team data")
    requester = find_by_email(email)
    if not requester:
        raise HTTPException(404, "Employee not found")
    return find_team(requester["employee_id"])

@app.get("/employees/all")
def get_all_salaries(user: dict = Depends(verify_agent_token)):
    role = user["role"]
    if role != "HRAdmins":
        raise HTTPException(403, "HR Admin role required")
    return EMPLOYEES
