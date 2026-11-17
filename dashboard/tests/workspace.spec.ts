import { test, expect } from "@playwright/test";
async function signIn(page: import("@playwright/test").Page) {
  await page.getByLabel("Username").fill("operator");
  await page.getByLabel("Password").fill(process.env.SNT_BROWSER_PASSWORD!);
  await page.getByRole("button", { name: "Sign in" }).click();
}
test("inspect the incident and record two independent decisions", async ({
  page,
}) => {
  await page.goto("/");
  await signIn(page);
  await expect(page.getByText("Online", { exact: true })).toHaveCount(2);
  await page
    .getByRole("link", { name: /Payment Service Performance Regression/ })
    .click();
  await expect(
    page.getByRole("heading", { name: "Correlation timeline" }),
  ).toBeVisible();
  await expect(
    page.getByText("Database connection acquisition timed out"),
  ).toBeVisible();
  await page.getByRole("link", { name: "Review recommended actions" }).click();
  await page
    .getByRole("button", { name: "Approve", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("table").getByText("Approved", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Reject", exact: true })
    .nth(1)
    .click();
  await page.reload();
  await expect(
    page.getByRole("table").getByText("Rejected", { exact: true }),
  ).toBeVisible();
});
test("create, retrieve, fault and recover a payment", async ({ page }) => {
  await page.goto("/payflow");
  await signIn(page);
  await expect(page).toHaveURL(/\/$/);
  await page.getByRole("link",{name:"PayFlow lab",exact:true}).click();
  const submit = page.getByRole("button", { name: "Submit payment" });
  const receipt = page.getByLabel("Payment response");
  await submit.click();
  await expect(receipt).toContainText("SUCCESS");
  const id = await page.getByLabel("Payment ID").inputValue();
  await page.getByRole("button", { name: "Retrieve payment" }).click();
  await expect(receipt).toContainText(id);
  const fault = page.getByRole("switch", { name: "Database unavailable" });
  await fault.click();
  await expect(fault).toBeChecked();
  await submit.click();
  await expect(receipt).toContainText("Simulated database outage");
  await fault.click();
  await expect(fault).not.toBeChecked();
  await submit.click();
  await expect(receipt).toContainText("SUCCESS");
});

test("a rejected stored token prompts reauthentication and preserves unrelated storage", async ({page})=>{
 await page.goto("/login");
 await page.evaluate(()=>{localStorage.setItem("access_token","invalid");localStorage.setItem("preference","keep")});
 await page.goto("/payflow");
 await expect(page).toHaveURL(/\/login$/);
 await expect(page.getByRole("status")).toHaveText(/session expired/i);
 expect(await page.evaluate(()=>localStorage.getItem("access_token"))).toBeNull();
 expect(await page.evaluate(()=>localStorage.getItem("preference"))).toBe("keep");
 await signIn(page);
 await expect(page.getByRole("heading",{name:"Operations overview"})).toBeVisible();
 await page.getByRole("button",{name:"Sign out"}).click();
 await expect(page).toHaveURL(/\/login$/);
 expect(await page.evaluate(()=>localStorage.getItem("access_token"))).toBeNull();
});
