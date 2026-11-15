import { test, expect } from "@playwright/test";

test("approve a firing database fault and observe verified recovery", async ({ page, request }) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill("operator");
  await page.getByLabel("Password").fill(process.env.SNT_BROWSER_PASSWORD!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading",{name:"Operations overview"})).toBeVisible();
  const headers = {Authorization:"Bearer " + await page.evaluate(()=>localStorage.getItem("access_token"))};
  const pay = "http://localhost:8001/api/v1";
  const ops = "http://localhost:8000/api/v1";
  const toggle = (enabled:boolean)=>request.post(pay+"/simulation/faults",{headers,data:{fault:"database_unavailable",enabled}});
  const before = await (await request.get(ops+"/incidents",{headers})).json();
  expect((await toggle(true)).ok()).toBeTruthy();
  try {
    let id = "";
    await expect.poll(async()=>{
      expect((await request.post(pay+"/payments",{headers,data:{amount:1,currency:"USD"}})).status()).toBe(503);
      const rows = await (await request.get(ops+"/incidents",{headers})).json();
      id = rows.find((i:{id:string;actions:{operation:string}[]})=>!before.some((b:{id:string})=>b.id===i.id) && i.actions.some(a=>a.operation==="clear_database_fault"))?.id;
      return Boolean(id);
    },{timeout:70000,intervals:[1000]}).toBe(true);
    await page.goto("/approvals");
    const card=page.locator("article").filter({hasText:id});
    await card.getByRole("button",{name:"Approve",exact:true}).click();
    await expect(card.getByText("Verified",{exact:true})).toBeVisible({timeout:20000});
    const incident=await (await request.get(ops+"/incidents/"+id,{headers})).json();
    expect(incident.actions[0].outcome).toBe("recovered");
    expect(incident.verified_restored_at).toBeTruthy();
    const audit=await (await request.get(ops+"/audit-logs",{headers})).json();
    for(const state of ["Executing","recovered"]) expect(audit.some((a:{incident_id:string;execution:string;actor:string})=>a.incident_id===id && a.execution===state && a.actor==="operator")).toBe(true);
  } finally { await toggle(false); }
});
