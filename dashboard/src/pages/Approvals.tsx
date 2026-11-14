import { useState } from "react";
import { api } from "../services/api";
import { Panel, Badge, State, useResource, utc } from "../common";
export default function Approvals() {
  const q = useResource(api.incidents),
    audit = useResource(api.audit),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  async function decide(
    id: string,
    action: string,
    value: "approve" | "reject",
  ) {
    setBusy(true);
    setMessage("");
    try {
      const updated = await api.decide(id, action, value);
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
                  <Badge>{a.status}</Badge>
                </div>
                <h3>{a.description}</h3>
                <p>{a.reason}</p>
                <small>
                  {a.risk} risk / Requested {utc(a.requested_at)}
                </small>
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
