import { useCallback, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../services/api";
import { Panel, Badge, State, useResource, utc } from "../common";
export function Incidents() {
  const q = useResource(api.incidents),
    [severity, setSeverity] = useState("All"),
    [status, setStatus] = useState("All");
  const rows = q.data?.filter(
    (i) =>
      (severity === "All" || severity === i.severity) &&
      (status === "All" || status === i.status),
  );
  return (
    <>
      <h1>Incidents</h1>
      <p className="subtitle">
        Review detection, impact and investigation findings.
      </p>
      <div className="filters">
        <label>
          Severity
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value)}
          >
            {["All", "Critical", "High", "Medium", "Low"].map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </label>
        <label>
          Status
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            {["All", "Investigating", "Resolved"].map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </label>
      </div>
      <Panel title="Incident register">
        {rows ? (
          rows.length ? (
            rows.map((i) => (
              <article key={i.id}>
                <small>
                  {i.id} / {i.service}
                </small>
                <h3>
                  <Link to={"/incidents/" + i.id}>{i.title}</Link>
                </h3>
                <Badge>{i.severity}</Badge> <Badge>{i.status}</Badge>
                <p>{i.investigation.hypothesis}</p>
                <small>
                  Detected {utc(i.detected_at)} / Resolved{" "}
                  {i.resolved_at ? utc(i.resolved_at) : "Pending"}
                </small>
              </article>
            ))
          ) : (
            <p>No matching incidents.</p>
          )
        ) : (
          <State error={q.error} retry={q.refresh} />
        )}
      </Panel>
    </>
  );
}
export function Detail() {
  const { id = "" } = useParams(),
    q = useResource(useCallback(() => api.incident(id), [id])),
    i = q.data;
  if (!i) return <State error={q.error} retry={q.refresh} />;
  const inv = i.investigation;
  return (
    <>
      <small>
        {i.id} / {i.service}
      </small>
      <h1>{i.title}</h1>
      <Badge>{i.severity}</Badge> <Badge>{i.status}</Badge>
      <div className="columns">
        <Panel title="Correlation timeline">
          <ol className="timeline">
            {i.timeline.map((e, n) => (
              <li key={n}>
                <Badge>{e.kind}</Badge>
                <strong>{e.title}</strong>
                <small>{utc(e.time)}</small>
              </li>
            ))}
          </ol>
        </Panel>
        <Panel title="AI investigation" meta={<Badge>Seeded</Badge>}>
          <h3>Probable root cause</h3>
          <p>{inv.hypothesis}</p>
          <small>Confidence: {inv.confidence}</small>
          {Object.entries({
            "Alternative hypotheses": inv.alternatives,
            "Missing evidence": inv.missing,
            "Next steps": inv.next_steps,
            Runbooks: inv.runbooks,
          }).map(([title, items]) => (
            <div key={title}>
              <h3>{title}</h3>
              <ul>
                {items.map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
            </div>
          ))}
        </Panel>
      </div>
      <Panel title="Supporting evidence">
        {inv.evidence.map((e) => (
          <article key={e.kind} id={e.reference}>
            <small>{e.kind}</small>
            <p>{e.detail}</p>
            <a href={"#" + e.reference}>Demo reference / {e.reference}</a>
          </article>
        ))}
      </Panel>
      <Link to="/approvals">Review recommended actions</Link>
    </>
  );
}
