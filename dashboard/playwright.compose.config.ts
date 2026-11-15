import { defineConfig } from "@playwright/test";
export default defineConfig({ testDir:"./compose-tests", workers:1, timeout:120000, use:{baseURL:process.env.COMPOSE_DASHBOARD_URL || "http://localhost:8080"} });
