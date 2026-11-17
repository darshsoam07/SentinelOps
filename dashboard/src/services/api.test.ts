import { afterEach, expect, it, vi } from "vitest";
import { api } from "./api";
import { formatFailureRate } from "../metrics";
afterEach(() => vi.unstubAllGlobals());
it("posts the action ID to the decision endpoint", async () => {
  const fetch = vi.fn().mockResolvedValue(Response.json({ id: "SNT-001" }));
  vi.stubGlobal("fetch", fetch);
  await api.decide("SNT-001", "ACT-001", "reject");
  expect(fetch).toHaveBeenCalledWith(
    expect.stringMatching(/incidents\/SNT-001\/reject$/),
    expect.objectContaining({
      method: "POST",
      body: '{"action_id":"ACT-001"}',
    }),
  );
});
it("preserves failed payment receipts", async () => {
  const receipt = { id: "payment", status: "FAILED" };
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(Response.json(receipt, { status: 503 })),
  );
  expect(await api.submit(20, "USD")).toEqual(receipt);
});
it("surfaces API error detail", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        Response.json({ detail: "Unknown payment" }, { status: 404 }),
      ),
  );
  await expect(api.payment("missing")).rejects.toThrow("Unknown payment");
});

it("reports the HTTP status for HTML proxy errors", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>Bad gateway</html>", {status: 502})));
  await expect(api.audit()).rejects.toThrow("HTTP 502");
});

it("reports connection failures", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));
  await expect(api.audit()).rejects.toThrow("Cannot reach the API");
});

it("distinguishes idle window from observed 0.0% failure rate", () => {
  // Idle window: zero observed submissions -> Idle (no traffic)
  expect(formatFailureRate(0, 0)).toBe("Idle (no traffic)");
  expect(formatFailureRate([])).toBe("Idle (no traffic)");

  // Observed healthy traffic: submissions present, zero failures -> 0.0%
  expect(formatFailureRate(10, 0)).toBe("0.0%");
  expect(formatFailureRate([{ status: "SUCCESS" }])).toBe("0.0%");

  // Observed failing traffic: submissions present with failures
  expect(formatFailureRate(10, 2)).toBe("20.0%");
  expect(
    formatFailureRate([
      { status: "SUCCESS" },
      { status: "SUCCESS" },
      { status: "FAILED" },
    ]),
  ).toBe("33.3%");
});
