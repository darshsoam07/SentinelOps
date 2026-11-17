import { useEffect, useState, type ReactNode, type KeyboardEvent } from "react";
import {
  Activity,
  AudioWaveform,
  ArrowRight,
  Database,
  Eye,
  EyeOff,
  Fingerprint,
  KeyRound,
  LockKeyhole,
  Pause,
  Play,
  Terminal,
  UserRound,
} from "lucide-react";
import "./login-portal.css";

const logLines = [
  "TLS 1.3 handshake initiated",
  "Certificate chain accepted",
  "Zero-trust policy evaluated",
  "Operator challenge issued",
  "Session boundary verified",
];
function Showcase() {
  const [now, setNow] = useState(() => new Date()),
    [tick, setTick] = useState(0),
    [paused, setPaused] = useState(false);
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  useEffect(() => {
    if (paused) return;
    const id = setInterval(() => setTick((v) => v + 1), 3200);
    return () => clearInterval(id);
  }, [paused]);
  return (
    <section className="showcase">
      <div className="protocol">
        <i /> SYS.AUTH // PROTOCOL v2.4{" "}
        <time>{now.toISOString().slice(11, 19)} UTC</time>
      </div>
      <h2>
        Autonomous
        <br />
        Resilience &amp;
        <br />
        <span>Payment Telemetry.</span>
      </h2>
      <div className="demo-label">Simulated telemetry</div>
      <div className="bento">
        <article>
          <div className="module-title">
            <Activity size={16} /> Node SNT-001
          </div>
          <div className="node-stat">
            99.998<span>% SLA</span>
          </div>
          <svg
            className="spark"
            viewBox="0 0 220 36"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <path d="M0 25H24l4 -4 5 7 5 -6h30l5 -6 5 8 7 -19 8 28 6 -14 5 4h19l4 -3 5 4h28l5 -8 5 12 7 -19 6 13h39" />
          </svg>
          <small className="online">● ONLINE</small>
        </article>
        <article>
          <div className="module-title">
            <Database size={16} /> PayFlow
          </div>
          <strong>Settlement Engine</strong>
          <small className="verified">HTTP 201 VERIFIED</small>
          <div className="db-line">
            p95: 14.2ms
            <br />
            PGSQL: 0001 HEAD
          </div>
        </article>
        <article className="log">
          <div className="module-title">
            <Terminal size={16} /> Security log{" "}
            <button
              type="button"
              aria-label={paused ? "Resume log" : "Pause log"}
              onClick={() => setPaused((v) => !v)}
            >
              {paused ? <Play size={14} /> : <Pause size={14} />}
            </button>
          </div>
          <div key={tick} className="log-lines">
            {[0, 1, 2].map((offset) => (
              <div key={offset}>
                <span>{String(tick + offset + 1).padStart(4, "0")}</span>{" "}
                {logLines[(tick + offset) % logLines.length]}
              </div>
            ))}
          </div>
        </article>
      </div>
    </section>
  );
}
export function LoginPortal({ children }: { children: ReactNode }) {
  return (
    <main
      className="portal"
      onMouseMove={(e) => {
        const box = e.currentTarget.getBoundingClientRect();
        e.currentTarget.style.setProperty(
          "--mouse-x",
          e.clientX - box.left + "px",
        );
        e.currentTarget.style.setProperty(
          "--mouse-y",
          e.clientY - box.top + "px",
        );
      }}
    >
      <div className="portal-inner">
        <div className="wordmark">
          <AudioWaveform /> SentinelOps
        </div>
        <div className="portal-split">
          <Showcase />
          <section className="auth-terminal">
            <div className="terminal-tag">
              <Fingerprint size={18} /> OPERATOR ACCESS TERMINAL
            </div>
            <h1>Sign in to SentinelOps</h1>
            <p>
              Authenticate with your operator credentials to access the command
              plane.
            </p>
            {children}
            <div className="security">
              <span title="Simulated transport profile">
                Demo · AES-256-GCM
              </span>
              <span>JWT HS256</span>
              {window.location.hostname === "localhost" &&
                window.location.port === "5173" && (
                  <span>LOCAL PORT :5173 VERIFIED</span>
                )}
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
export function Credentials({ busy }: { busy: boolean }) {
  const [show, setShow] = useState(false),
    [caps, setCaps] = useState(false),
    [verify, setVerify] = useState(false);
  useEffect(() => {
    if (!busy) {
      setVerify(false);
      return;
    }
    const timer = setTimeout(() => setVerify(true), 500);
    return () => clearTimeout(timer);
  }, [busy]);
  const checkCaps = (event: KeyboardEvent<HTMLInputElement>) =>
    setCaps(event.getModifierState("CapsLock"));
  return (
    <>
      <label htmlFor="operator-id">OPERATOR_ID</label>
      <div className="entry">
        <UserRound />
        <input
          id="operator-id"
          aria-label="Username"
          autoComplete="username"
          name="username"
          placeholder="Username"
          required
        />
      </div>
      <label htmlFor="operator-pass">
        PASSKEY_SECRET {caps && <span className="caps">Caps Lock on</span>}
      </label>
      <div className="entry">
        <KeyRound />
        <input
          id="operator-pass"
          aria-label="Password"
          type={show ? "text" : "password"}
          autoComplete="current-password"
          name="password"
          placeholder="Password"
          onKeyDown={checkCaps}
          onKeyUp={checkCaps}
          onBlur={() => setCaps(false)}
          required
        />
        <button
          type="button"
          aria-label={show ? "Hide passkey" : "Reveal passkey"}
          aria-pressed={show}
          onClick={() => setShow((v) => !v)}
        >
          {show ? <EyeOff /> : <Eye />}
        </button>
      </div>
      <button
        className="portal-submit"
        aria-label="Sign in"
        type="submit"
        disabled={busy}
      >
        {busy ? <LockKeyhole size={16} /> : <ArrowRight size={16} />}{" "}
        {busy
          ? verify
            ? "Verifying Operator..."
            : location.protocol === "https:"
              ? "Establishing TLS Handshake..."
              : "Establishing connection..."
          : "Sign in"}
        <kbd>↵ Enter</kbd>
      </button>
    </>
  );
}
