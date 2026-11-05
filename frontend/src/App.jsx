import { useEffect, useRef, useState } from "react";
import { MODES, checkHealth, downloadJson, fetchFinancials } from "./api.js";
import StatementTable, {
  annualColumns,
  bsColumns,
  cfColumns,
  pnlColumns,
} from "./StatementTable.jsx";

const QUICK_SYMBOLS = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ITC", "SBIN"];

const MODE_ICONS = { overview: "◈", pnl: "₹", bs: "▤", cf: "⇄", annual: "❖" };

const fmtNum = (v) =>
  typeof v === "number" ? v.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : "—";

// Pull headline numbers from the first P&L filing that has data.
function headline(pnl) {
  const filings = pnl?.filings || [];
  const f = filings.find((x) => x.financial_data?.financials?.revenue_from_operations != null) || filings[0];
  const fin = f?.financial_data?.financials || {};
  const eps = f?.financial_data?.eps || {};
  return {
    period: f?.to_date || f?.relating_to || "—",
    unit: f?.financial_data?.general_info?.rounding_unit || "",
    revenue: fin.revenue_from_operations,
    netProfit: fin.net_profit,
    eps: eps.basic_total,
  };
}

function Kpi({ label, value, hint }) {
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {hint && <div className="kpi-hint">{hint}</div>}
    </div>
  );
}

function Section({ title, count, onDownload, children }) {
  return (
    <section className="card">
      <div className="card-head">
        <h2>
          {title} {count !== undefined && <span className="badge">{count} filings</span>}
        </h2>
        {onDownload && (
          <button type="button" className="btn ghost sm" onClick={onDownload}>
            ⭳ JSON
          </button>
        )}
      </div>
      {children}
    </section>
  );
}

function Results({ mode, data, name }) {
  if (mode === "overview") {
    return (
      <>
        <Section
          title="Profit & Loss"
          count={data.profit_and_loss?.total_filings}
          onDownload={() => downloadJson(data.profit_and_loss, `${name}_profit_loss`)}
        >
          <StatementTable columns={pnlColumns(data.profit_and_loss)} />
        </Section>
        {data.balance_sheet && (
          <Section
            title="Balance Sheet"
            count={data.balance_sheet.total_filings}
            onDownload={() => downloadJson(data.balance_sheet, `${name}_balance_sheet`)}
          >
            <StatementTable columns={bsColumns(data.balance_sheet)} />
          </Section>
        )}
        {data.cash_flow && (
          <Section
            title="Cash Flow"
            count={data.cash_flow.total_filings}
            onDownload={() => downloadJson(data.cash_flow, `${name}_cash_flow`)}
          >
            <StatementTable columns={cfColumns(data.cash_flow)} />
          </Section>
        )}
        {data.period === "Quarterly" && (
          <p className="note">Balance Sheet and Cash Flow exist only in annual filings — choose Annual or Both.</p>
        )}
      </>
    );
  }
  const map = {
    pnl: ["Profit & Loss", pnlColumns],
    bs: ["Balance Sheet", bsColumns],
    cf: ["Cash Flow", cfColumns],
    annual: ["Annual Report · P&L, Balance Sheet, Cash Flow, Segments", annualColumns],
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
      setState({ status: "done", data, mode, sym, reportType, period });
    } catch (err) {
      if (err.name === "AbortError") return;
      setState({ status: "error", error: err });
    }
  }

  const done = state.status === "done";
  const fileBase = done
    ? [state.sym, state.mode, state.reportType, MODES.find((m) => m.id === state.mode).usesPeriod ? state.period : null]
        .filter(Boolean)
        .join("_")
        .toLowerCase()
    : "";

  const pnl = done ? (state.mode === "overview" ? state.data.profit_and_loss : state.mode === "pnl" ? state.data : null) : null;
  const hl = pnl ? headline(pnl) : null;
  const company = done ? state.data.company_name || state.data.profit_and_loss?.company_name || "" : "";

  return (
    <>
      <div className="hero">
        <div className="wrap hero-inner">
          <div className="brand">
            <div className="logo">₹</div>
            <div>
              <h1>Stock Financials</h1>
              <p>Profit &amp; Loss · Balance Sheet · Cash Flow for NSE-listed companies</p>
            </div>
          </div>
          <span className={`health ${health === null ? "" : health ? "ok" : "bad"}`}>
            <i /> {health === null ? "Checking API…" : health ? "API online" : "API unreachable"}
          </span>
        </div>
      </div>

      <main className="wrap">
        <form className="card search" onSubmit={run}>
          <nav className="tabs">
            {MODES.map((m) => (
              <button
                key={m.id}
                className={m.id === mode ? "active" : ""}
                onClick={() => setMode(m.id)}
                type="button"
              >
                <span className="ico">{MODE_ICONS[m.id]}</span> {m.label}
              </button>
            ))}
          </nav>

          <div className="controls">
            <label className="grow">
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
            <button className="btn primary" type="submit" disabled={state.status === "loading"}>
              {state.status === "loading" ? "Fetching…" : "Get financials →"}
            </button>
          </div>

          <div className="chips">
            <span className="muted">Try:</span>
            {QUICK_SYMBOLS.map((s) => (
              <button key={s} type="button" className="chip" onClick={() => setSymbol(s)}>
                {s}
              </button>
            ))}
          </div>
        </form>

        {state.status === "idle" && (
          <div className="empty">
            <div className="empty-ico">📊</div>
            <h3>Pick a company to get started</h3>
            <p className="muted">Choose a symbol and statement type above, then hit “Get financials”.</p>
          </div>
        )}

        {state.status === "loading" && (
          <div className="card status">
            <div className="spinner" />
            <div>
              <strong>Fetching filings from NSE… {elapsed}s</strong>
              <div className="muted">
                Each filing is downloaded and parsed individually, so this can take 20–60 seconds.
              </div>
            </div>
          </div>
        )}

        {state.status === "error" && (
          <div className="card error">
            <strong>⚠ {state.error.message}</strong>
            <div className="muted">
              {state.error.status === 404
                ? "NSE returned nothing for this request. Check the symbol, or retry — NSE rate-limits and sometimes blocks requests."
                : "The backend could not complete the request. Check the server logs."}
            </div>
          </div>
        )}

        {done && (
          <>
            <div className="result-head">
              <div>
                <h2 className="result-title">
                  {state.sym} <span className="tag">{MODES.find((m) => m.id === state.mode).label}</span>
                </h2>
                {company && <div className="muted">{company}</div>}
              </div>
              <button type="button" className="btn primary" onClick={() => downloadJson(state.data, fileBase)}>
                ⭳ Download JSON
              </button>
            </div>

            {hl && (
              <div className="kpis">
                <Kpi label="Latest period" value={hl.period} hint={hl.unit && `Amounts in ${hl.unit}`} />
                <Kpi label="Revenue from operations" value={fmtNum(hl.revenue)} />
                <Kpi label="Net profit" value={fmtNum(hl.netProfit)} />
                <Kpi label="Basic EPS" value={fmtNum(hl.eps)} />
              </div>
            )}

            <Results mode={state.mode} data={state.data} name={fileBase} />

            <details className="card raw">
              <summary>Raw JSON response</summary>
              <pre>{JSON.stringify(state.data, null, 2)}</pre>
            </details>
          </>
        )}

        <footer>
          Data sourced from NSE India public filings. Values are in the unit reported by each filing
          (see General info › Rounding unit).
        </footer>
      </main>
    </>
  );
}
