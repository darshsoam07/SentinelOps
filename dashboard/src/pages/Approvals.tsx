import { useEffect, useState } from "react";
import { api } from "../services/api";
import { Panel, Badge, State, useResource, utc } from "../common";
export default function Approvals() {
  const q = useResource(api.incidents,"incidents"),
    audit = useResource(api.audit,"audit"),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  const [notes, setNotes] = useState<Record<string,string>>({});
  const awaitingRecovery = q.data?.some(i => i.actions.some(a => a.operation === "clear_database_fault" && a.status === "Approved" && !a.outcome));
  useEffect(() => {
    if (!awaitingRecovery) return;
    const timer = window.setInterval(() => { q.refresh(); audit.refresh(); }, 1000);
    return () => window.clearInterval(timer);
  }, [awaitingRecovery, q.refresh, audit.refresh]);
  async function decide(
    id: string,
    action: string,
    value: "approve" | "reject",
  ) {
    setBusy(true);
    setMessage("");
    try {
      const updated = await api.decide(id, action, value, notes[id + "/" + action]);
      q.setData((old) => old?.map((i) => (i.id === id ? updated : i)));
      audit.refresh();
      setMessage(
        action + " " + updated.actions.find((a) => a.id === action)?.status,
      );
    } catch (e) {
      setMessage((e as Error).message);
      q.refresh();
      audit.refresh();
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <h1>Policy & approvals</h1>
      <p className="subtitle">
        Review simulated recovery actions. Decisions are recorded in the audit
        trail.
      </p>
      <p role="status">{message}</p>
      <Panel title="Remediation requests">
        {q.data ? (
          q.data.flatMap((i) =>
            i.actions.map((a) => (
              <article key={a.id}>
                <div className="row">
                  <small>
                    {a.id} / {i.id} / {i.service}
                  </small>
                  <Badge>{a.outcome === "recovered" ? "Verified" : a.outcome ? "Failed (" + a.outcome + ")" : a.action_started_at ? "Executing" : a.status}</Badge>
                </div>
                <h3>{a.description}</h3>
                <p>{a.reason}</p>
                <small>
                  {a.risk} risk / Requested {utc(a.requested_at)}
                </small>
                {a.status === "Pending" && <label>Decision note (optional)
                  <input maxLength={500} value={notes[i.id + "/" + a.id] || ""}
                    onChange={e => setNotes({...notes, [i.id + "/" + a.id]: e.target.value})}/>
                </label>}
                <div className="buttons">
                  <button
                    disabled={busy || a.status !== "Pending"}
                    onClick={() => decide(i.id, a.id, "approve")}
                  >
                    Approve
                  </button>
                  <button
                    disabled={busy || a.status !== "Pending"}
                    onClick={() => decide(i.id, a.id, "reject")}
                  >
                    Reject
                  </button>
                </div>
              </article>
            )),
          )
        ) : (
          <State error={q.error} retry={q.refresh} />
        )}
      </Panel>
      <Panel title="Audit trail">
        {audit.data ? (
          <div className="scroll">
            <table>
              <thead>
                <tr>
                  {[
                    "Event ID",
                    "Incident",
                    "Action",
                    "Actor",
                    "UTC time",
                    "Decision",
                    "Execution",
                    "Note",
                  ].map((x) => (
                    <th key={x}>{x}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {audit.data.map((a) => (
                  <tr key={a.id}>
                    {[
                      a.id,
                      a.incident_id,
                      a.action,
                      a.actor,
                      utc(a.time),
                      a.decision,
                      a.execution,
                      a.note,
                    ].map((v, n) => (
                      <td key={n}>{v}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <State error={audit.error} retry={audit.refresh} />
        )}
      </Panel>
    </>
  );
}
