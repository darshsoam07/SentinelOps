import { useState, useSyncExternalStore, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { sessionToken, subscribe, login, setToken } from "./services/api";

function Workspace({ children }: { children: ReactNode }) {
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { retry: false } } }),
  );
  return (
    <QueryClientProvider client={client}>
      {children}
      <button className="logout" onClick={() => setToken("")}>
        Sign out
      </button>
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}
export default function Session({ children }: { children: ReactNode }) {
  const token = useSyncExternalStore(subscribe, sessionToken);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  if (token) return <Workspace key={token}>{children}</Workspace>;
  return (
    <main className="content">
      <h1>Sign in to SentinelOps</h1>
      <form
        style={{ maxWidth: 400 }}
        onSubmit={async (e) => {
          e.preventDefault();
          const form = new FormData(e.currentTarget);
          setBusy(true);
          setError("");
          try {
            await login(
              String(form.get("username")),
              String(form.get("password")),
            );
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Username
          <input autoComplete="username" name="username" required />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="current-password"
            name="password"
            required
          />
        </label>
        <button disabled={busy}>Sign in</button>
        {error && <p role="alert">{error}</p>}
      </form>
    </main>
  );
}
