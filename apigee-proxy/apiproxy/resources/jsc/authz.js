context.setVariable("authz.denied", false);

var pathsuffix = context.getVariable("proxy.pathsuffix");
var requestedTool = context.getVariable("request.header.X-Tool-Name");
var role = context.getVariable("user.role");

if (requestedTool) {
  var AGENT_MAX_SCOPE = ["get_my_salary_info", "get_team_salary_info"];
  if (AGENT_MAX_SCOPE.indexOf(requestedTool) === -1) {
    context.setVariable("authz.denied", true);
    context.setVariable("authz.reason", "agent_scope_exceeded");
  }

  
  var PATH_TOOL_MAP = {
    "/employees/me":   ["get_my_salary_info"],
    "/employees/team": ["get_team_salary_info"],
    "/employees/all":  ["get_all_salary_info"]
  };
  var allowedForPath = PATH_TOOL_MAP[pathsuffix];
  if (!allowedForPath || allowedForPath.indexOf(requestedTool) === -1) {
    context.setVariable("authz.denied", true);
    context.setVariable("authz.reason", "tool_path_mismatch");
  }

  var allowedForRole = {
    "Employees": ["get_my_salary_info"],
    "Managers":  ["get_my_salary_info", "get_team_salary_info"],
    "HRAdmins":  ["get_my_salary_info", "get_team_salary_info", "get_all_salary_info"]
  };
  if (!allowedForRole[role] || allowedForRole[role].indexOf(requestedTool) === -1) {
    context.setVariable("authz.denied", true);
    context.setVariable("authz.reason", "role_not_authorized");
  }
}