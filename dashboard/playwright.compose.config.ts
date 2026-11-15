import { defineConfig } from "@playwright/test";
export default defineConfig({ testDir:"./compose-tests", workers:1, timeout:120000, use:{baseURL:"http://localhost:8080"} });
