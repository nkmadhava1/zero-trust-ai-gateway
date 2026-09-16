var raw = context.getVariable("user.role");
var role = null;

if (raw) {
  try {
    var parsed = JSON.parse(raw);
    role = Array.isArray(parsed) ? parsed[0] : parsed;
  } catch (e) {
    role = raw;
  }
}

context.setVariable("user.role", role);
var email = context.getVariable("user.email");
context.setVariable("user.act", JSON.stringify({ sub: email, role: role }));