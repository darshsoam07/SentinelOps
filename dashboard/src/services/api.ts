import type {
  Audit,
  Fault,
  Faults,
  Incident,
  Payment,
  Summary,
} from "../types";
const ops = import.meta.env.VITE_SENTINELOPS_API_URL || "http://localhost:8000";
const pay = import.meta.env.VITE_PAYFLOW_API_URL || "http://localhost:8001";
export async function request<T>(
  base: string,
  path: string,
  body?: unknown,
  acceptFailedPayment = false,
): Promise<T> {
  const headers: Record<string, string> = {};
  const bearer = token;
  if (bearer) headers.Authorization = "Bearer " + bearer;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const url = base + (path === "/health" ? path : "/api/v1" + path);
  const res = await fetch(url, {
    headers,
    method: body === undefined ? "GET" : "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 401 && bearer && bearer === token) setToken("");
  const data = await res.json();
  if (
    !res.ok &&
    !(acceptFailedPayment && data.status === "FAILED" && data.id)
  ) {
    throw Error(
      typeof data.detail === "string"
        ? data.detail
        : "Request failed (HTTP " + res.status + ")",
    );
  }
  return data;
}
export const api = {
  incidents: () => request<Incident[]>(ops, "/incidents"),
  incident: (id: string) =>
    request<Incident>(ops, "/incidents/" + encodeURIComponent(id)),
  summary: () => request<Summary>(ops, "/metrics/summary"),
  audit: () => request<Audit[]>(ops, "/audit-logs"),
  decide: (id: string, action_id: string, decision: "approve" | "reject") =>
    request<Incident>(
      ops,
      "/incidents/" + encodeURIComponent(id) + "/" + decision,
      { action_id },
    ),
  payments: () => request<Payment[]>(pay, "/payments"),
  payment: (id: string) =>
    request<Payment>(pay, "/payments/" + encodeURIComponent(id)),
  submit: (amount: number, currency: string) =>
    request<Payment>(pay, "/payments", { amount, currency }, true),
  faults: () => request<Faults>(pay, "/simulation/faults"),
  toggle: (fault: Fault, enabled: boolean) =>
    request<Faults>(pay, "/simulation/faults", { fault, enabled }),
  opsHealth: () => request<{ status: string }>(ops, "/health"),
  payHealth: () => request<{ status: string }>(pay, "/health"),
};

let token = "";
const listeners = new Set<() => void>();
export const sessionToken = () => token;
export const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};
export function setToken(value: string) {
  token = value;
  listeners.forEach((listener) => listener());
}
export async function login(username: string, password: string) {
  const response = await fetch(ops + "/api/v1/auth/login", {
    method: "POST",
    body: new URLSearchParams({ username, password }),
  });
  const data = await response.json();
  if (!response.ok) throw Error(data.detail || "Sign in failed");
  setToken(data.access_token);
}
