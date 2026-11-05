import { useMemo, useState } from "react";

// Flatten nested objects into { "section.sub.key": value }, preserving order.
function flatten(obj, prefix = "", out = {}) {
  if (obj === null || obj === undefined) return out;
  if (typeof obj !== "object" || Array.isArray(obj)) {
    out[prefix] = obj;
    return out;
  }
  for (const [k, v] of Object.entries(obj)) {
    flatten(v, prefix ? `${prefix}.${k}` : k, out);
  }
  return out;
}

const humanize = (s) =>
  s
    .replace(/_/g, " ")
    .replace(/\bpct\b/gi, "%")
    .replace(/\b(eps|ppe|nci|npa|cet1|ind as)\b/gi, (m) => m.toUpperCase())
    .replace(/^./, (c) => c.toUpperCase());

function fmt(v) {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "number") {
    return v.toLocaleString("en-IN", { maximumFractionDigits: 2 });
  }
  return String(v);
}

const isNum = (v) => typeof v === "number";

/**
 * columns: [{ key, label, sub, data }]  — each column is one filing; `data` is any (nested) object.
 * Rows are the union of all leaf paths; first path segment becomes a collapsible section.
 */
export default function StatementTable({ columns, collapsedSections = ["general_info"] }) {
  const [collapsed, setCollapsed] = useState(() => new Set(collapsedSections));

  const { sections } = useMemo(() => {
    const flat = columns.map((c) => flatten(c.data));
    const order = [];
    const seen = new Set();
    flat.forEach((f) => {
      Object.keys(f).forEach((p) => {
        if (!seen.has(p)) {
          seen.add(p);
          order.push(p);
        }
      });
    });
    // Drop rows that are empty in every column.
    const rows = order.filter((p) => flat.some((f) => f[p] !== null && f[p] !== undefined && f[p] !== ""));

    const grouped = new Map();
    rows.forEach((p) => {
      const parts = p.split(".");
      const section = parts.length > 1 ? parts[0] : "_root";
      const label = parts.length > 1 ? parts.slice(1).map(humanize).join(" › ") : humanize(parts[0]);
      if (!grouped.has(section)) grouped.set(section, []);
      grouped.get(section).push({ path: p, label, values: flat.map((f) => f[p]) });
    });
    return { sections: [...grouped.entries()] };
  }, [columns]);

  if (!columns.length) return <p className="muted">No filings returned.</p>;
  if (!sections.length) return <p className="muted">Filings were found but no values could be parsed from them.</p>;

  const toggle = (s) =>
    setCollapsed((prev) => {
      const n = new Set(prev);
      n.has(s) ? n.delete(s) : n.add(s);
      return n;
    });

  return (
    <div className="table-wrap">
      <table className="stmt">
        <thead>
          <tr>
            <th className="sticky-col">Line item</th>
            {columns.map((c) => (
              <th key={c.key}>
                <div>{c.label}</div>
                {c.sub && <div className="sub">{c.sub}</div>}
              </th>
            ))}
          </tr>
        </thead>
        {sections.map(([section, rows]) => {
          const isCollapsed = collapsed.has(section);
          return (
            <tbody key={section}>
              {section !== "_root" && (
                <tr className="section-row" onClick={() => toggle(section)}>
                  <td colSpan={columns.length + 1}>
                    <span className="chev">{isCollapsed ? "▸" : "▾"}</span> {humanize(section)}
                  </td>
                </tr>
              )}
              {!isCollapsed &&
                rows.map((r) => (
                  <tr key={r.path}>
                    <td className="sticky-col">{r.label}</td>
                    {r.values.map((v, i) => (
                      <td
                        key={i}
                        className={isNum(v) ? `num${v < 0 ? " neg" : ""}` : "txt"}
                      >
                        {fmt(v)}
                      </td>
                    ))}
                  </tr>
                ))}
            </tbody>
          );
        })}
      </table>
    </div>
  );
}

// ---- helpers to turn API payloads into table columns ----

export function pnlColumns(payload) {
  return (payload?.filings || []).map((f, i) => ({
    key: `${f.seq_number ?? i}`,
    label: f.to_date || f.relating_to || `Filing ${i + 1}`,
    sub: [f.nature, f.period, f.audited].filter(Boolean).join(" · "),
    data: f.financial_data,
  }));
}

export function bsColumns(payload) {
  return (payload?.filings || []).map((f, i) => ({
    key: `${f.quarter_ended}-${f.nature}-${i}`,
    label: f.quarter_ended || `Filing ${i + 1}`,
    sub: [f.nature, f.audited].filter(Boolean).join(" · "),
    data: f.balance_sheet,
  }));
}

export function cfColumns(payload) {
  return (payload?.filings || []).map((f, i) => ({
    key: `${f.quarter_ended}-${f.nature}-${i}`,
    label: f.quarter_ended || `Filing ${i + 1}`,
    sub: [f.nature, f.audited].filter(Boolean).join(" · "),
    data: f.cash_flow,
  }));
}

export function annualColumns(payload) {
  return (payload?.filings || []).map((f, i) => ({
    key: `${f.quarter_ended}-${f.nature}-${i}`,
    label: f.quarter_ended || `Filing ${i + 1}`,
    sub: [f.nature, f.audited].filter(Boolean).join(" · "),
    data: { summary: f.summary, ...(f.financial_data || {}) },
  }));
}
