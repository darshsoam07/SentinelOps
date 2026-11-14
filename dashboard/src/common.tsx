import { useEffect, useState } from "react";
import type { ReactNode } from "react";
export function useResource<T>(read: () => Promise<T>, key = "") {
  const [data, setData] = useState<T>();
  const [error, setError] = useState("");
  const [version, update] = useState(0);
  useEffect(() => {
    let current = true;
    setData(undefined);
    setError("");
    read()
      .then((v) => {
        if (current) setData(v);
      })
      .catch((e) => {
        if (current) setError(String(e.message));
      });
    return () => {
      current = false;
    };
  }, [key, version, read]);
  return { data, error, refresh: () => update((n) => n + 1), setData };
}
export function State({ error, retry }: { error: string; retry: () => void }) {
  return error ? (
    <p role="alert">
      {error} <button onClick={retry}>Retry</button>
    </p>
  ) : (
    <p role="status">Loading...</p>
  );
}
export function Panel({
  title,
  children,
  meta,
}: {
  title: string;
  children: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <section className="panel">
      <header>
        <h2>{title}</h2>
        {meta}
      </header>
      {children}
    </section>
  );
}
export const utc = (value: string) =>
  new Date(value).toISOString().replace("T", " ").slice(0, 19) + " UTC";
export function Badge({ children }: { children: string }) {
  return <span className={"badge " + children.toLowerCase()}>{children}</span>;
}
