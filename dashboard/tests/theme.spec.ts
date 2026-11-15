import { test, expect } from "@playwright/test";
test("uses the system palette and remembers an explicit theme", async ({page}) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/login");
  await expect(page.locator(".portal")).toHaveCSS("background-color","rgb(244, 245, 247)");
  await page.getByLabel("Color theme").selectOption("dark");
  await page.reload();
  await expect(page.locator(".portal")).toHaveCSS("background-color","rgb(9, 11, 14)");
  await page.getByLabel("Color theme").selectOption("system");
  await expect(page.locator(".portal")).toHaveCSS("background-color","rgb(244, 245, 247)");
});
