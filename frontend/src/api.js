// Empty base = same origin (production, and dev via the Vite proxy).
// Set VITE_API_BASE_URL at build time to point at a separately hosted backend.
const BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export const MODES = [
  { id: "overview", label: "Overview", path: (s) => `/api/v1/financials/${s}`, usesPeriod: true },
  { id: "pnl", label: "Profit & Loss", path: (s) => `/api/v1/profit-loss/${s}`, usesPeriod: true },
  { id: "bs", label: "Balance Sheet", path: (s) => `/api/v1/balance-sheet/${s}`, usesPeriod: false },
  { id: "cf", label: "Cash Flow", path: (s) => `/api/v1/cash-flow/${s}`, usesPeriod: false },
  { id: "annual", label: "Annual Report", path: (s) => `/api/v1/annual-report/${s}`, usesPeriod: false },
];

export async function fetchFinancials({ mode, symbol, reportType, period, signal }) {
  const m = MODES.find((x) => x.id === mode);
  const params = new URLSearchParams({ report_type: reportType });
  if (m.usesPeriod) params.set("period", period);

  const res = await fetch(`${BASE}${m.path(encodeURIComponent(symbol))}?${params}`, { signal });
  let body = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON error body */
  }
  if (!res.ok) {
    const err = new Error(body?.detail || `Request failed (HTTP ${res.status})`);
    err.status = res.status;
    throw err;
  }
  return body;
}

export async function checkHealth() {
  try {
    const res = await fetch(`${BASE}/health`);
    return res.ok;
  } catch {
    return false;
  }
}
