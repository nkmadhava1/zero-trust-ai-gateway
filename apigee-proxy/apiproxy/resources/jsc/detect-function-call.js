var isFunctionCall = false;
try {
  var body = JSON.parse(context.getVariable("response.content"));
  var candidates = body.candidates;
  if (candidates && candidates.length > 0) {
    var parts = candidates[candidates.length - 1].content.parts;
    if (parts && parts.length > 0) {
      var lastPart = parts[parts.length - 1];
      if (lastPart.functionCall) {
        isFunctionCall = true;
      }
    }
  }
} catch (e) {
  isFunctionCall = false;
}

var isEmployeesPath = false;
try {
  var pathsuffix = context.getVariable("proxy.pathsuffix");
  isEmployeesPath = (pathsuffix && pathsuffix.indexOf("/employees/") === 0);
} catch (e) {
  isEmployeesPath = false;
}

context.setVariable("flow.isTextResponse", !isFunctionCall);
context.setVariable("flow.isEmployeesPath", isEmployeesPath);