import React from "react";
import "./QueryResultsTable.css";

// Renders QLense Phase-1 SQL results as a real HTML table, fed by
// structured JSON (parsed out of the response by queryTableUtils.js)
// instead of relying on the LLM's markdown table formatting.
const QueryResultsTable = ({ rows }) => {
  if (!rows || rows.length === 0) return null;

  // Column order/labels are fixed to match the QLense prompt's schema.
  // Fall back to whatever keys are present if the expected ones are missing.
  const expectedColumns = [
    { key: "num", label: "#" },
    { key: "source", label: "Source" },
    { key: "description", label: "Issue Description" },
    { key: "model", label: "Model" },
    { key: "date", label: "Date" },
    { key: "severity", label: "Severity" },
    { key: "ref", label: "Ref" },
  ];
  const columns = expectedColumns.some((c) => c.key in rows[0])
    ? expectedColumns
    : Object.keys(rows[0]).map((k) => ({ key: k, label: k }));

  return (
    <div className="query-results-container">
      <div className="query-results-table-wrapper">
        <table className="query-results-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col.key}>{col.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index}>
                {columns.map((col) => (
                  <td key={col.key} className={col.key === "num" ? "num-cell" : undefined}>
                    {row[col.key] ?? "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default QueryResultsTable;
