import { Link } from "react-router-dom";
import { Activity, ArrowUpRight } from "lucide-react";
import { api } from "../services/api";
import { Panel, State, useResource, Badge, utc } from "../common";
function Health({ name, read }: { name: string; read: typeof api.opsHealth }) {
  const check = useResource(read,name);
  return (
    <div className="row">
      <span>{name}</span>
      <Badge>
        {check.error
          ? "Offline"
          : check.data?.status === "ok"
            ? "Online"
            : "Checking"}
      </Badge>
    </div>
  );
}
export default function Overview() {
  const s = useResource(api.summary,"summary"),
    incidents = useResource(api.incidents,"incidents"),
    payments = useResource(api.payments,"payments");
  const m = s.data;
  return (
    <>
      <h2>Incident inspector</h2>
      <section className="incident-focus" aria-label="Recent incident activity">
        {incidents.data ? (
          incidents.data.map((i) => (
            <Link className="incident-row" key={i.id} to={"/incidents/" + i.id}>
              <Badge>{i.severity}</Badge>
              <div>
                <small>
                  {i.id} / {i.service}
                </small>
                <strong>{i.title}</strong>
                <small>
                  {i.timeline.at(-1)?.title} / {utc(i.timeline.at(-1)!.time)}
                </small>
              </div>
              <ArrowUpRight size={18} />
            </Link>
          ))
        ) : (
          <State error={incidents.error} retry={incidents.refresh} />
        )}
      </section>
      {incidents.data?.find(i=>i.id==="SNT-001")?.timeline.map((e,index)=><div className="eventline" key={index}><time>{utc(e.time)}</time>{e.title}</div>)}
      {m ? (
        <>
          <h2 className="metric-heading">Reliability indicators <small>{m.source}</small></h2>
          <div className="metrics">
            {m.metrics.map((x) => (
              <div key={x.name}>
                <small>{x.name}</small>
                <strong>{x.value}</strong>
              </div>
            ))}
          </div>
          <div className="columns">
            <Panel
              title="Payment latency"
              meta={<Badge>{m.source}</Badge>}
            >
              <div className="latency-reading">{m.metrics.find(metric => metric.name === "p95 latency")?.value}<small>95th percentile</small></div>
              <div className="chart">
                <div className="axis">
                  <small>5 s</small>
                  <small>2.5 s</small>
                  <small>0 s</small>
                </div>
                <svg
                  viewBox="0 0 600 130"
                  preserveAspectRatio="none"
                  role="img"
                  aria-label={m.source + " p95 payment latency"}
                >
                  {[0, 65, 129].map((y) => (
                    <line
                      key={y}
                      x1="0"
                      x2="600"
                      y1={y}
                      y2={y}
                      className="gridline"
                    />
                  ))}
                  <polyline
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="3"
                    vectorEffect="non-scaling-stroke"
                    points={m.latency_ms
                      .map((v, i) =>
                        [
                          (i * 600) / Math.max(1, m.latency_ms.length - 1),
                          130 - (v * 130) / 5000,
                        ].join(","),
                      )
                      .join(" ")}
                  />
                </svg>
              </div>
              <div className="row chart-label">
                <small>{m.times[0]} UTC</small>
                <small>p95 latency</small>
                <small>{m.times.at(-1)} UTC</small>
              </div>
            </Panel>
            <Panel title="Service health" meta={<Activity size={16} />}>
              <Health name="SentinelOps API" read={api.opsHealth} />
              <Health name="PayFlow API" read={api.payHealth} />
              <div className="row">
                <span>Active incidents</span>
                <b>{m.active}</b>
              </div>
              <div className="row">
                <span>Resolved incidents</span>
                <b>{m.resolved}</b>
              </div>
            </Panel>
          </div>
        </>
      ) : (
        <State error={s.error} retry={s.refresh} />
      )}
      <Panel
        title="Payment activity"
        meta={<Link to="/payflow">Open PayFlow</Link>}
      >
        {payments.data ? (
          <p>
            {payments.data.length} requests recorded /{" "}
            {payments.data.filter((p) => p.status === "FAILED").length} failed
          </p>
        ) : (
          <State error={payments.error} retry={payments.refresh} />
        )}
      </Panel>
    </>
  );
}
