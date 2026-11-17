import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReactNode, SetStateAction } from "react";
export function useResource<T>(read: () => Promise<T>, key: string) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: [key], queryFn: read });
  return {
    data: query.data,
    error: query.error?.message || "",
    refresh: () => client.invalidateQueries({ queryKey: [key] }),
    setData: (update: SetStateAction<T | undefined>) => {
      client.setQueryData<T>([key], update);
    },
  };
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
export function Badge({ children, className = "" }: { children: string; className?: string }) {
  return <span className={"badge " + children.toLowerCase() + (className ? " " + className : "")}>{children}</span>;
}
export { formatFailureRate } from "./metrics";
