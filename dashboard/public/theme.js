try {
  const mode = localStorage.getItem("sentinelops.theme");
  if (mode === "light" || mode === "dark") document.documentElement.dataset.theme = mode;
} catch {
  // The system color scheme also works when persistent storage is unavailable.
}
