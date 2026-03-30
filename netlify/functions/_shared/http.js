function jsonResponse(statusCode, payload) {
  return {
    statusCode,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    },
    body: JSON.stringify(payload),
  };
}

function parseJsonBody(event) {
  if (!event.body) return {};
  return JSON.parse(event.body);
}

function routePath(event) {
  const rawPath = event.path || event.rawUrl || "/";
  return String(rawPath)
    .replace(/^https?:\/\/[^/]+/, "")
    .replace(/^\/\.netlify\/functions\/api/, "")
    .replace(/^\/api/, "") || "/";
}

function requireAdmin(event) {
  const expected = String(process.env.ADMIN_WRITE_TOKEN || "").trim();
  const provided =
    String(event.headers["x-admin-token"] || event.headers["X-Admin-Token"] || "").trim();
  if (!expected) {
    throw new Error("ADMIN_WRITE_TOKEN is not configured on Netlify.");
  }
  if (!provided || provided !== expected) {
    const error = new Error("Admin token is missing or invalid.");
    error.statusCode = 401;
    throw error;
  }
}

module.exports = {
  jsonResponse,
  parseJsonBody,
  requireAdmin,
  routePath,
};
