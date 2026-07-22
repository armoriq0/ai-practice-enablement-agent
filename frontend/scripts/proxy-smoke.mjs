import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import http from "node:http";

const backend = http.createServer((request, response) => {
  response.setHeader("content-type", "application/json");
  response.end(JSON.stringify({
    path: request.url,
    authorization: request.headers.authorization ?? null,
    serverlessAuthorization: request.headers["x-serverless-authorization"] ?? null,
  }));
});

await new Promise((resolve) => backend.listen(3198, "127.0.0.1", resolve));
const frontend = spawn(process.execPath, [".next/standalone/server.js"], {
  cwd: process.cwd(),
  env: { ...process.env, PORT: "3199", HOSTNAME: "127.0.0.1", BACKEND_URL: "http://127.0.0.1:3198" },
  stdio: "ignore",
});

try {
  let response;
  for (let attempt = 0; attempt < 30; attempt += 1) {
    try {
      response = await fetch("http://127.0.0.1:3199/api/proxy/api/v1/missions?limit=2", {
        headers: { authorization: "Bearer application-user-token" },
      });
      break;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }
  assert(response, "frontend did not start");
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.path, "/api/v1/missions?limit=2");
  assert.equal(body.authorization, "Bearer application-user-token");
  assert.equal(body.serverlessAuthorization, null);
  process.stdout.write("Proxy smoke passed: path, query, and application authorization preserved.\n");
} finally {
  frontend.kill("SIGTERM");
  await new Promise((resolve) => backend.close(resolve));
}
