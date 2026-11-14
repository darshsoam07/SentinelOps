import { defineConfig } from "@playwright/test";
// Isolated processes keep test decisions and fault toggles out of the operator workspace.
const root = process.env.HOME + "/sentinelops";
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
      env: { DASHBOARD_ORIGINS: "http://localhost:5174" },
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
