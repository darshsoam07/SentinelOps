import {Ledger} from "../ReceiptLedger";
import { useCreatePayment, usePayments } from "../hooks/usePayments";
import { useState } from "react";
import { api } from "../services/api";
import type { Fault, Payment } from "../types";
import { Panel, State, useResource } from "../common";
const labels: Record<Fault, string> = {
  high_latency: "High latency",
  high_error_rate: "High error rate",
  database_unavailable: "Database unavailable",
};
export default function Payflow({embedded=false}:{embedded?:boolean}) {
  const creation = useCreatePayment();
  const payments = usePayments(),
    faults = useResource(api.faults, "faults");
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
      <div className="dispatch">{embedded?<h2>Settlement terminal</h2>:<h1>PayFlow traffic lab</h1>}<small>// PAYFLOW_DISPATCH</small>
      <p className="subtitle">
        Submit test transactions and observe controlled service faults.
      </p>
      {(error || creation.error) && (
        <p role="alert">{error || creation.error?.message}</p>
      )}
      <div className="columns">
        <Panel title="Test payment">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              creation.mutate(
                { amount: Number(amount), currency },
                {
                  onSuccess: (p) => {
                    setResult(p);
                    setId(p.id);
                    setError("");
                  },
                },
              );
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
            <div className="presets">{[25,100,500,1000].map(n=><button type="button" key={n} onClick={()=>{setAmount(String(n));setCurrency("USD")}}>+${n.toLocaleString("en-US")}</button>)}</div>
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
            <button disabled={busy || creation.isPending}>
              Submit payment
            </button>
          </form>
          <small>IDEMPOTENCY SHIELD: ARMED · UI submit lock only</small>
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
                  disabled={busy || creation.isPending}
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
          <button disabled={busy || creation.isPending}>
            Retrieve payment
          </button>
        </form>
        {result && (
          <pre aria-label="Payment response">
            {JSON.stringify(result, null, 2)}
          </pre>
        )}
      </Panel>
      </div><div className="ledgerpanel"><Panel title="Recent transactions">
        {payments.data ? (
          payments.data.length ? (
            <Ledger rows={payments.data}/>
          ) : (
            <p>No transactions yet.</p>
          )
        ) : (
          <State error={payments.error} retry={payments.refresh} />
        )}
      </Panel></div>
    </>
  );
}
