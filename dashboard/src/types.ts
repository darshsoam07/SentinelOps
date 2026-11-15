export interface Action {
  action_started_at?: string | null;
  outcome?: "recovered" | "persisted" | "failed" | null;
  id: string;
  operation: string;
  description: string;
  reason: string;
  risk: string;
  status: string;
  requested_at: string;
}
export interface Incident {
  id: string;
  title: string;
  severity: string;
  service: string;
  status: string;
  detected_at: string;
  resolved_at: string | null;
  timeline: { time: string; kind: string; title: string }[];
  actions: Action[];
  investigation: {
    hypothesis: string;
    confidence: string;
    alternatives: string[];
    missing: string[];
    next_steps: string[];
    runbooks: string[];
    evidence: { kind: string; detail: string; reference: string }[];
  };
}
export interface Summary {
  source: string;
  active: number;
  resolved: number;
  metrics: { name: string; value: string }[];
  latency_ms: number[];
  times: string[];
}
export interface Audit {
  id: string;
  incident_id: string;
  action: string;
  actor: string;
  time: string;
  decision: string;
  execution: string;
  note: string;
}
export interface Payment {
  id: string;
  amount: number;
  currency: string;
  status: string;
  created_at: string;
  reason: string | null;
}
export type Fault = "high_latency" | "high_error_rate" | "database_unavailable";
export type Faults = Record<Fault, boolean>;
