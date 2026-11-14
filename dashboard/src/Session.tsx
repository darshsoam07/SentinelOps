import {LoginPortal,Credentials} from "./LoginPortal";
import { useState, useSyncExternalStore, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { Navigate, useLocation } from "react-router-dom";
import { sessionExpired, sessionToken, subscribe, login } from "./services/api";

function Workspace({ children }: { children: ReactNode }) {
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { retry: false } } }),
  );
  return (
    <QueryClientProvider client={client}>
      {children}
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}
export default function Session({ children }: { children: ReactNode }) {
  const token = useSyncExternalStore(subscribe, sessionToken);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const {pathname}=useLocation();
  if (!token && pathname!=="/login") return <Navigate to="/login" replace />;
  if (token && pathname==="/login") return <Navigate to="/" replace />;
  if (token) return <Workspace key={token}>{children}</Workspace>;
  return (
    <LoginPortal>
      {sessionExpired && <p role="status">Your session expired. Sign in again to continue.</p>}
      <form

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
        <Credentials busy={busy}/>
        {error && <p role="alert">{error}</p>}
      </form>
    </LoginPortal>
  );
}
