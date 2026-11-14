import { randomBytes } from "node:crypto";
import { execFileSync } from "node:child_process";
import { defineConfig } from "@playwright/test";
// Isolated processes keep test decisions and fault toggles out of the operator workspace.
const root = process.env.HOME + "/sentinelops";
const password =
  process.env.SNT_BROWSER_PASSWORD || randomBytes(24).toString("hex");
process.env.SNT_BROWSER_PASSWORD = password;
const secret = randomBytes(32).toString("hex");
const hash = execFileSync(
  root + "/.venv/bin/python",
  [
    "-c",
    "from pwdlib import PasswordHash; import sys; print(PasswordHash.recommended().hash(sys.stdin.read()))",
  ],
  { input: password, encoding: "utf8" },
).trim();
const services = [
  ["backend/api", 8100],
  ["applications/payflow/payment-service", 8101],
] as const;
export default defineConfig({
  testDir: "./tests",
  workers: 1,
  use: { baseURL: "http://localhost:5174" },
  webServer: [
    ...services.map(([path, port]) => ({
      command: root + "/.venv/bin/uvicorn app.main:app --port " + port,
      cwd: root + "/" + path,
      url: "http://127.0.0.1:" + port + "/health",
      env: {
        SENTINELOPS_DATABASE_URL: "",
        PAYFLOW_DATABASE_URL: "",
        SENTINELOPS_OPERATOR: "operator",
        SENTINELOPS_JWT_SECRET: secret,
        SENTINELOPS_PASSWORD_HASH: hash,
        DASHBOARD_ORIGINS: "http://localhost:5174",
      },
    })),
    {
      command: "npm run dev -- --port 5174",
      url: "http://localhost:5174",
      env: {
        VITE_SENTINELOPS_API_URL: "http://127.0.0.1:8100",
        VITE_PAYFLOW_API_URL: "http://127.0.0.1:8101",
      },
    },
  ],
});
