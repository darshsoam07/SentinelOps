import { test, expect } from "@playwright/test";

const ops = process.env.COMPOSE_OPS_URL || "http://localhost:8000/api/v1";
const pay = process.env.COMPOSE_PAYFLOW_URL || "http://localhost:8001/api/v1";

test("approve a firing database fault and observe verified recovery", async ({ page, request }) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill("operator");
  await page.getByLabel("Password").fill(process.env.SNT_BROWSER_PASSWORD!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading",{name:"Operations overview"})).toBeVisible();
  const headers = {Authorization:"Bearer " + await page.evaluate(()=>localStorage.getItem("access_token"))};
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

test("record a persisted fault when readiness passes but another fault remains", async ({ request }) => {
  test.setTimeout(180000);
  const login = await request.post(ops + "/auth/login", {
    form: { username: "operator", password: process.env.SNT_BROWSER_PASSWORD! },
  });
  expect(login.ok()).toBeTruthy();
  const headers = { Authorization: "Bearer " + (await login.json()).access_token };
  type Episode = { id: string; title: string; resolved_at: string | null; actions: {id: string; outcome: string | null}[] };
  const episodes = async (): Promise<Episode[]> => (await request.get(ops + "/incidents", {headers})).json();
  const toggle = async (fault: string, enabled: boolean) => {
    const result = await request.post(pay + "/simulation/faults", { headers, data: { fault, enabled } });
    expect(result.ok()).toBeTruthy();
  };
  // Wait for the previous trial's rule window and resolved notification before injecting again.
  await expect.poll(async () => (await episodes()).filter(i => i.title === "PayFlow payment errors" && !i.resolved_at).length,
    {timeout:90000, intervals:[1000]}).toBe(0);
  const before = new Set((await episodes()).map(i=>i.id));
  try {
    await toggle("database_unavailable", true);
    await toggle("high_error_rate", true);
    let episode: Episode | undefined;
    await expect.poll(async () => {
      const receipt = await request.post(pay + "/payments", {headers, data:{amount:1, currency:"USD"}});
      expect(receipt.status()).toBe(503);
      episode = (await episodes()).find(i => !before.has(i.id) && i.title === "PayFlow payment errors");
      return episode?.actions.length;
    }, {timeout:65000, intervals:[1000]}).toBe(1);
    const path = ops + "/incidents/" + episode!.id;
    const decision = {headers, data:{action_id:episode!.actions[0].id}};
    expect((await request.post(path + "/approve",decision)).ok()).toBeTruthy();
    expect((await request.post(path + "/approve",decision)).status()).toBe(409);
    await expect.poll(async () => (await (await request.get(path,{headers})).json()).actions[0].outcome).toBe("persisted");
    expect((await (await request.get(path,{headers})).json()).verified_restored_at).toBeNull();
    const states = await (await request.get(pay + "/simulation/faults",{headers})).json();
    expect(states.database_unavailable).toBe(false);
    expect(states.high_error_rate).toBe(true);
  } finally {
    await toggle("database_unavailable",false);
    await toggle("high_error_rate",false);
  }
});
