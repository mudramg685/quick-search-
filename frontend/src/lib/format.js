export const fmtInt = (n) => (n ?? 0).toLocaleString("en-US");

export function fmtMs(ms) {
  if (ms == null) return "–";
  if (ms < 1) return `${ms.toFixed(2)} ms`;
  if (ms < 100) return `${ms.toFixed(1)} ms`;
  return `${Math.round(ms)} ms`;
}

export function fmtBytes(b) {
  if (!b) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(units.length - 1, Math.floor(Math.log(b) / Math.log(1024)));
  return `${(b / 1024 ** i).toFixed(i ? 1 : 0)} ${units[i]}`;
}

export const fmtPct = (x, digits = 0) => `${((x ?? 0) * 100).toFixed(digits)}%`;

export function timeAgo(value) {
  if (!value) return "–";
  const t = typeof value === "number" ? value * 1000 : Date.parse(value.endsWith("Z") || value.includes("+") ? value : value + "Z");
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}

export function prettyUrl(url) {
  try {
    const u = new URL(url);
    const path = decodeURIComponent(u.pathname).replace(/\/$/, "").split("/").filter(Boolean);
    return { host: u.host, crumbs: path.slice(-3) };
  } catch {
    return { host: url, crumbs: [] };
  }
}
