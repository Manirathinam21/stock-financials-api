import { useEffect, useRef, useState } from "react";
import { MODES, checkHealth, fetchFinancials } from "./api.js";
import StatementTable, {
  annualColumns,
  bsColumns,
  cfColumns,
  pnlColumns,
} from "./StatementTable.jsx";

const QUICK_SYMBOLS = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ITC", "SBIN"];

function Section({ title, count, children }) {
  return (
    <section className="card">
      <h2>
        {title} {count !== undefined && <span className="badge">{count} filings</span>}
      </h2>
      {children}
    </section>
  );
}

function Results({ mode, data }) {
  if (mode === "overview") {
    return (
      <>
        <Section title="Profit & Loss" count={data.profit_and_loss?.total_filings}>
          <StatementTable columns={pnlColumns(data.profit_and_loss)} />
        </Section>
        {data.balance_sheet && (
          <Section title="Balance Sheet" count={data.balance_sheet.total_filings}>
            <StatementTable columns={bsColumns(data.balance_sheet)} />
          </Section>
        )}
        {data.cash_flow && (
          <Section title="Cash Flow" count={data.cash_flow.total_filings}>
            <StatementTable columns={cfColumns(data.cash_flow)} />
          </Section>
        )}
        {data.period === "Quarterly" && (
          <p className="muted">Balance Sheet and Cash Flow exist only in annual filings — choose Annual or Both.</p>
        )}
      </>
    );
  }
  const map = {
    pnl: ["Profit & Loss", pnlColumns],
    bs: ["Balance Sheet", bsColumns],
    cf: ["Cash Flow", cfColumns],
    annual: ["Annual Report (P&L + Balance Sheet + Cash Flow + Segments)", annualColumns],
  };
  const [title, toCols] = map[mode];
  return (
    <Section title={title} count={data.total_filings}>
      {data.company_name && <p className="muted">{data.company_name}</p>}
      <StatementTable columns={toCols(data)} />
    </Section>
  );
}

export default function App() {
  const [symbol, setSymbol] = useState("RELIANCE");
  const [mode, setMode] = useState("overview");
  const [reportType, setReportType] = useState("consolidated");
  const [period, setPeriod] = useState("Annual");
  const [state, setState] = useState({ status: "idle" }); // idle | loading | done | error
  const [health, setHealth] = useState(null);
  const abortRef = useRef(null);
  const startRef = useRef(0);
  const [elapsed, setElapsed] = useState(0);

  const current = MODES.find((m) => m.id === mode);

  useEffect(() => {
    checkHealth().then(setHealth);
  }, []);

  useEffect(() => {
    if (state.status !== "loading") return;
    const t = setInterval(() => setElapsed(Math.round((Date.now() - startRef.current) / 1000)), 500);
    return () => clearInterval(t);
  }, [state.status]);

  async function run(e) {
    e?.preventDefault();
    const sym = symbol.trim().toUpperCase();
    if (!sym) return;
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    startRef.current = Date.now();
    setElapsed(0);
    setState({ status: "loading" });
    try {
      const data = await fetchFinancials({ mode, symbol: sym, reportType, period, signal: ctrl.signal });
      setState({ status: "done", data, mode, sym });
    } catch (err) {
      if (err.name === "AbortError") return;
      setState({ status: "error", error: err });
    }
  }

  return (
    <div className="app">
      <header>
        <div>
          <h1>Stock Financials</h1>
          <p className="muted">NSE-listed companies · P&amp;L, Balance Sheet, Cash Flow</p>
        </div>
        <span className={`health ${health === null ? "" : health ? "ok" : "bad"}`}>
          {health === null ? "checking API…" : health ? "API online" : "API unreachable"}
        </span>
      </header>

      <nav className="tabs">
        {MODES.map((m) => (
          <button key={m.id} className={m.id === mode ? "active" : ""} onClick={() => setMode(m.id)} type="button">
            {m.label}
          </button>
        ))}
      </nav>

      <form className="card controls" onSubmit={run}>
        <label>
          Symbol
          <input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            placeholder="e.g. RELIANCE"
            autoCapitalize="characters"
            spellCheck={false}
          />
        </label>
        <label>
          Report type
          <select value={reportType} onChange={(e) => setReportType(e.target.value)}>
            <option value="consolidated">Consolidated</option>
            <option value="standalone">Standalone</option>
            <option value="both">Both</option>
          </select>
        </label>
        {current.usesPeriod && (
          <label>
            Period
            <select value={period} onChange={(e) => setPeriod(e.target.value)}>
              <option value="Quarterly">Quarterly</option>
              <option value="Annual">Annual</option>
              <option value="Both">Both</option>
            </select>
          </label>
        )}
        <button className="primary" type="submit" disabled={state.status === "loading"}>
          {state.status === "loading" ? "Fetching…" : "Get financials"}
        </button>
        <div className="chips">
          {QUICK_SYMBOLS.map((s) => (
            <button key={s} type="button" className="chip" onClick={() => setSymbol(s)}>
              {s}
            </button>
          ))}
        </div>
      </form>

      {state.status === "loading" && (
        <div className="card status">
          <div className="spinner" />
          <div>
            Fetching filings from NSE… {elapsed}s
            <div className="muted">Each filing is downloaded and parsed individually, so this can take 20–60 seconds.</div>
          </div>
        </div>
      )}

      {state.status === "error" && (
        <div className="card error">
          <strong>{state.error.message}</strong>
          <div className="muted">
            {state.error.status === 404
              ? "NSE returned nothing for this request. Check the symbol, or retry — NSE rate-limits and sometimes blocks requests."
              : "The backend could not complete the request. Check the server logs."}
          </div>
        </div>
      )}

      {state.status === "done" && (
        <>
          <h2 className="result-title">
            {state.sym} <span className="muted">· {MODES.find((m) => m.id === state.mode).label}</span>
          </h2>
          <Results mode={state.mode} data={state.data} />
          <details className="card raw">
            <summary>Raw JSON response</summary>
            <pre>{JSON.stringify(state.data, null, 2)}</pre>
          </details>
        </>
      )}

      <footer className="muted">Data sourced from NSE India public APIs. Values in the unit reported by each filing (see General info › Rounding unit).</footer>
    </div>
  );
}
