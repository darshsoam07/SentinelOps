export function ThemeSelect() {
  return <select className="theme-select" aria-label="Color theme"
    defaultValue={document.documentElement.dataset.theme || "system"}
    onChange={({currentTarget}) => {
      const mode = currentTarget.value;
      if (mode === "system") delete document.documentElement.dataset.theme;
      else document.documentElement.dataset.theme = mode;
      try { localStorage.setItem("sentinelops.theme", mode); } catch { /* Session-only choice. */ }
    }}>
    <option value="system">System theme</option>
    <option value="light">Light theme</option>
    <option value="dark">Dark theme</option>
  </select>;
}
