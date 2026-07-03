import React, { useState, useEffect, useRef } from "react";
import { backend_url } from "../services/api/config";
import "./QlenseDataGate.css";

const API_BASE = `${backend_url}/part-labeler`;

const DATA_SOURCES = [
  { key: "warranty", label: "Warranty Data",      hint: "THAR ROXX Warranty Excel" },
  { key: "rpt",      label: "Offline RPT Data",   hint: "Offline data Excel" },
  { key: "gnovac",   label: "GNOVAC Data",         hint: "GNOVAC Excel" },
  { key: "rfi",      label: "RFI Data",            hint: "RFI Excel" },
  { key: "esqa",     label: "eSQA Data",           hint: "THAR ROXX e-SQA Excel" },
];

function QlenseDataGate({ userId, onReady }) {
  const [status, setStatus]           = useState(null);
  const [loading, setLoading]         = useState(true);
  const [uploading, setUploading]     = useState(null);
  const [mappingState, setMappingState] = useState(null);
  const fileInputRef = useRef(null);
  const [pendingSource, setPendingSource] = useState(null);

  const fetchStatus = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/data-status?userId=${userId}`);
      const data = await res.json();
      setStatus(data);
    } catch {
      setStatus({});
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchStatus(); }, [userId]);

  const allUploaded = status && DATA_SOURCES.every(s => status[s.key]?.uploaded);

  const handleUploadClick = (sourceKey) => {
    setPendingSource(sourceKey);
    fileInputRef.current.value = "";
    fileInputRef.current.click();
  };

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file || !pendingSource) return;

    setUploading(pendingSource);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_BASE}/warranty-upload`, { method: "POST", body: formData });
      const { tempFilePath, headers } = await res.json();
      setMappingState({ tempFilePath, headers, sourceKey: pendingSource });
    } catch {
      alert("Failed to upload file. Please try again.");
    } finally {
      setUploading(null);
    }
  };

  const handleConfirmMapping = async (mapping) => {
    const { tempFilePath, sourceKey } = mappingState;
    try {
      const res = await fetch(`${API_BASE}/warranty-confirm-mapping`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tempFilePath, mapping, userId, dataSource: sourceKey }),
      });
      const data = await res.json();
      if (data.success) {
        setMappingState(null);
        await fetchStatus();
      } else {
        alert("Failed to process mapping.");
      }
    } catch {
      alert("Failed to process mapping.");
    }
  };

  if (loading) {
    return (
      <div className="qdg-container">
        <div className="qdg-loading">Checking uploaded data sources…</div>
      </div>
    );
  }

  if (mappingState) {
    return (
      <MappingModal
        headers={mappingState.headers}
        sourceKey={mappingState.sourceKey}
        onConfirm={handleConfirmMapping}
        onCancel={() => setMappingState(null)}
      />
    );
  }

  return (
    <div className="qdg-container">
      <input
        type="file"
        ref={fileInputRef}
        style={{ display: "none" }}
        accept=".xlsx,.xls,.csv"
        onChange={handleFileChange}
      />

      <div className="qdg-card">
        <div className="qdg-header">
          <h2 className="qdg-title">QLense Assistant</h2>
          <p className="qdg-subtitle">
            To find quality issues, QLense needs data from your uploaded Excel files.
            Upload any missing sources below, then start the chat.
          </p>
        </div>

        <div className="qdg-sources">
          {DATA_SOURCES.map((src) => {
            const uploaded = status?.[src.key]?.uploaded;
            const rowCount = status?.[src.key]?.row_count || 0;
            const isUploading = uploading === src.key;

            return (
              <div key={src.key} className={`qdg-source-row ${uploaded ? "qdg-uploaded" : "qdg-missing"}`}>
                <div className="qdg-source-info">
                  <span className="qdg-source-icon">{uploaded ? "✓" : "○"}</span>
                  <div>
                    <span className="qdg-source-label">{src.label}</span>
                    <span className="qdg-source-hint">{src.hint}</span>
                  </div>
                </div>
                <div className="qdg-source-action">
                  {uploaded && <span className="qdg-row-count">{rowCount.toLocaleString()} rows</span>}
                  <button
                    className="qdg-upload-btn"
                    onClick={() => handleUploadClick(src.key)}
                    disabled={isUploading}
                  >
                    {isUploading ? "Uploading…" : uploaded ? "Re-upload" : "Upload"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        <div className="qdg-footer">
          <button
            className={`qdg-start-btn ${allUploaded ? "qdg-start-ready" : "qdg-start-disabled"}`}
            onClick={onReady}
            disabled={!allUploaded}
          >
            {allUploaded ? "Start Chat →" : "Upload all sources to continue"}
          </button>
        </div>
      </div>
    </div>
  );
}

// Target keys must match a real column in the corresponding
// process_mapped_*_data() all_cols list in part_labeler_service.py — any
// name that isn't a real column is silently dropped (no error) since it's
// bound as a SQL named parameter that the INSERT statement never references.
// mfg_month/mfg_quarter are always derived server-side from the raw date
// column below, so the date column (not mfg_month) must be the mapping target.
//
// Warranty's "claim_desc" is deliberately NOT mapped: verified against the
// real source data, it only ever holds 4 fixed values ("AS-Normal
// Warranty", "AS-PDI Warranty Claim", ...) — despite its name it's a claim
// category, not a defect description. "dealer_verbatim" is the real
// free-text complaint field (2931/2999 distinct values sampled);
// "complaint_code_desc" is the next-best fallback (320 distinct,
// standardized-but-specific labels).
//
// This must stay in sync with app/tools/qlense_search_tool.py's _TABLE_CONFIG —
// every search_cols/desc_cols/ref_cols/severity_col/model_col/date_col entry
// referenced there needs to actually be captured here, or that column is
// silently empty in Postgres forever and QLense falls back to a blanker/less
// useful field no matter how correct the search tool's SQL is.
const SOURCE_TARGET_COLUMNS = {
  warranty: ["part", "dealer_verbatim", "complaint_code_desc", "material_description", "manufac_yr_mon", "base_model", "mis_bucket", "claim_date", "sap_claim_no", "serial_no"],
  rpt:      ["part", "defect", "part_defect", "defect_category", "model", "date_col", "attribute_name", "shift", "severity_name", "vin_number", "body_sr_no"],
  gnovac:   ["part_name", "defect_name", "pointer", "model_code", "audit_date", "concern_type_name", "pca", "vin_no", "body_no"],
  rfi:      ["part_name", "defect_name", "defect_type_name", "model_name", "date_col", "severity_name", "vin_no", "biw_no"],
  esqa:     ["part_name", "concern_description", "concern_category", "vehicle_model", "concern_report_date", "vendor_name", "concern_severity", "concern_number", "esqa_number"],
};

function MappingModal({ headers, sourceKey, onConfirm, onCancel }) {
  const targets = SOURCE_TARGET_COLUMNS[sourceKey] || [];
  const [mapping, setMapping] = useState(() =>
    Object.fromEntries(targets.map((t) => [t, ""]))
  );
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (target, value) => {
    setMapping((prev) => ({ ...prev, [target]: value }));
  };

  const handleSubmit = async () => {
    if (submitting) return;
    setSubmitting(true);
    try {
      // Only keep selections that match a real column — a typed value
      // that doesn't match any header (searchable input, not a locked
      // dropdown) would otherwise be sent and silently ignored server-side.
      const filtered = Object.fromEntries(
        Object.entries(mapping).filter(([, v]) => v !== "" && headers.includes(v))
      );
      await onConfirm(filtered);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="qdg-container">
      <div className="qdg-card">
        <div className="qdg-header">
          <h2 className="qdg-title">Map Columns</h2>
          <p className="qdg-subtitle">
            Match your Excel columns to the required fields.
          </p>
        </div>

        <div className="qdg-mapping-grid">
          {targets.map((target) => {
            const listId = `qdg-headers-${sourceKey}-${target}`;
            const isValidSelection = mapping[target] === "" || headers.includes(mapping[target]);
            return (
              <div key={target} className="qdg-mapping-row">
                <span className="qdg-mapping-target">{target}</span>
                <input
                  type="text"
                  list={listId}
                  className="qdg-mapping-select"
                  style={!isValidSelection ? { borderColor: "#f87171" } : undefined}
                  placeholder="Type to search columns, or leave blank to skip"
                  value={mapping[target]}
                  onChange={(e) => handleChange(target, e.target.value)}
                />
                <datalist id={listId}>
                  {headers.map((h) => (
                    <option key={h} value={h} />
                  ))}
                </datalist>
              </div>
            );
          })}
        </div>

        <div className="qdg-mapping-actions">
          <button className="qdg-cancel-btn" onClick={onCancel} disabled={submitting}>Cancel</button>
          <button className="qdg-confirm-btn" onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Processing…" : "Confirm & Load"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default QlenseDataGate;
