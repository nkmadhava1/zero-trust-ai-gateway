import os
import requests

APIGEE_PROXY_BASE_URL = os.environ["APIGEE_PROXY_BASE_URL"]

def get_my_salary_info(tool_context) -> dict:
    """Fetch the caller's own HR record."""
    resp = requests.get(
        f"{APIGEE_PROXY_BASE_URL}/employees/me",
        headers={
            "Authorization": f"Bearer {tool_context.state['user_token']}",
            "X-Tool-Name": "get_my_salary_info",
        },
    )
    if resp.status_code == 403:
        return {"error": "You don't have permission to view this."}
    resp.raise_for_status()
    return resp.json()

def get_team_salary_info(tool_context) -> dict:
    """Fetch salary info for the caller's direct reports (Manager/HR Admin only)."""
    resp = requests.get(
        f"{APIGEE_PROXY_BASE_URL}/employees/team",
        headers={
            "Authorization": f"Bearer {tool_context.state['user_token']}",
            "X-Tool-Name": "get_team_salary_info",
        },
    )
    if resp.status_code == 403:
        return {"error": "You don't have permission to view team salary data."}
    resp.raise_for_status()
    return resp.json()

def get_all_salary_info(tool_context) -> dict:
    """Fetch salary info for all employees (HR Admin only)."""
    resp = requests.get(
        f"{APIGEE_PROXY_BASE_URL}/employees/all",
        headers={
            "Authorization": f"Bearer {tool_context.state['user_token']}",
            "X-Tool-Name": "get_all_salary_info",
        },
    )
    if resp.status_code == 403:
        return {"error": "You don't have permission to view all salary data."}
    resp.raise_for_status()
    return resp.json()
