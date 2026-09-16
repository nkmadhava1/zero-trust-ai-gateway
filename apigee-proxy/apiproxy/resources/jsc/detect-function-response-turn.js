var isFunctionResponseTurn = false;
try {
  var body = JSON.parse(context.getVariable("request.content"));
  var contents = body.contents;
  if (contents && contents.length > 0) {
    var lastContent = contents[contents.length - 1];
    var parts = lastContent.parts;
    if (parts && parts.length > 0) {
      var lastPart = parts[parts.length - 1];
      if (lastPart.functionResponse) {
        isFunctionResponseTurn = true;
      }
    }
  }
} catch (e) {
  isFunctionResponseTurn = false;
}

var isEmployeesPath = false;
try {
  var pathsuffix = context.getVariable("proxy.pathsuffix");
  isEmployeesPath = (pathsuffix && pathsuffix.indexOf("/employees/") === 0);
} catch (e) {
  isEmployeesPath = false;
}

context.setVariable("flow.isUserTextTurn", !isFunctionResponseTurn);
context.setVariable("flow.isEmployeesPath", isEmployeesPath);