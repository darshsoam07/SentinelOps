import { useState } from "react";
import { api } from "../services/api";
import type { Fault, Payment } from "../types";
import { Panel, State, Badge, useResource, utc } from "../common";
const labels: Record<Fault, string> = {
  high_latency: "High latency",
  high_error_rate: "High error rate",
  database_unavailable: "Database unavailable",
};
export default function Payflow() {
  const payments = useResource(api.payments),
    faults = useResource(api.faults);
  const [amount, setAmount] = useState("500"),
    [currency, setCurrency] = useState("INR"),
    [id, setId] = useState("");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [result, setResult] = useState<Payment>();
  async function run(job: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await job();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <h1>PayFlow traffic lab</h1>
      <p className="subtitle">
        Submit test transactions and observe controlled service faults.
      </p>
      {error && <p role="alert">{error}</p>}
      <div className="columns">
        <Panel title="Test payment">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              run(async () => {
                const p = await api.submit(Number(amount), currency);
                setResult(p);
                setId(p.id);
                payments.refresh();
              });
            }}
          >
            <label>
              Amount
              <input
                type="number"
                min="0.01"
                step="0.01"
                value={amount}
                required
                onChange={(e) => setAmount(e.target.value)}
              />
            </label>
            <label>
              Currency
              <input
                pattern="[A-Z]{3}"
                maxLength={3}
                required
                value={currency}
                onChange={(e) => setCurrency(e.target.value.toUpperCase())}
              />
            </label>
            <button disabled={busy}>Submit payment</button>
          </form>
        </Panel>
        <Panel title="Fault simulation">
          {faults.data ? (
            (Object.keys(labels) as Fault[]).map((k) => (
              <div className="row" key={k}>
                <span>{labels[k]}</span>
                <button
                  role="switch"
                  aria-label={labels[k]}
                  aria-checked={faults.data![k]}
                  disabled={busy}
                  onClick={() =>
                    run(async () =>
                      faults.setData(await api.toggle(k, !faults.data![k])),
                    )
                  }
                >
                  {faults.data![k] ? "On" : "Off"}
                </button>
              </div>
            ))
          ) : (
            <State error={faults.error} retry={faults.refresh} />
          )}
        </Panel>
      </div>
      <Panel title="Transaction lookup">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              setResult(undefined);
              setResult(await api.payment(id.trim()));
            });
          }}
        >
          <label>
            Payment ID
            <input
              required
              value={id}
              onChange={(e) => setId(e.target.value)}
            />
          </label>
          <button disabled={busy}>Retrieve payment</button>
        </form>
        {result && (
          <pre aria-label="Payment response">
            {JSON.stringify(result, null, 2)}
          </pre>
        )}
      </Panel>
      <Panel title="Recent transactions">
        {payments.data ? (
          payments.data.length ? (
            payments.data.map((p) => (
              <div className="row" key={p.id}>
                <div>
                  <strong>
                    {p.amount} {p.currency}
                  </strong>
                  <small>
                    {p.id} / {utc(p.created_at)}
                  </small>
                </div>
                <Badge>{p.status}</Badge>
              </div>
            ))
          ) : (
            <p>No transactions yet.</p>
          )
        ) : (
          <State error={payments.error} retry={payments.refresh} />
        )}
      </Panel>
    </>
  );
}
