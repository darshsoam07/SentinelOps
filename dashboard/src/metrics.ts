export function formatFailureRate(
  requestCountOrPayments: number | { status: string }[],
  failedCount?: number,
): string {
  let count: number;
  let failed: number;

  if (Array.isArray(requestCountOrPayments)) {
    count = requestCountOrPayments.length;
    failed = requestCountOrPayments.filter((p) => p.status === "FAILED").length;
  } else {
    count = requestCountOrPayments;
    failed = failedCount ?? 0;
  }

  if (count === 0) {
    return "Idle (no traffic)";
  }
  const rate = (failed / count) * 100;
  return `${rate.toFixed(1)}%`;
}
