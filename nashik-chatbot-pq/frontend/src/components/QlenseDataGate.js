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
                  {uploaded ? (
                    <span className="qdg-row-count">{rowCount.toLocaleString()} rows</span>
                  ) : (
                    <button
                      className="qdg-upload-btn"
                      onClick={() => handleUploadClick(src.key)}
                      disabled={isUploading}
                    >
                      {isUploading ? "Uploading…" : "Upload"}
                    </button>
                  )}
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

const SOURCE_TARGET_COLUMNS = {
  warranty: ["complaint_code_desc", "material_description", "manufac_yr_mon", "base_model", "mis_bucket", "claim_date"],
  rpt:      ["defect_category", "model", "mfg_month", "attribute_name", "shift"],
  gnovac:   ["pointer", "model_code", "mfg_month", "concern", "action"],
  rfi:      ["defect_description", "model_name", "mfg_month", "severity_name"],
  esqa:     ["concern_category", "vehicle_model", "mfg_month", "supplier_name"],
};

function MappingModal({ headers, sourceKey, onConfirm, onCancel }) {
  const targets = SOURCE_TARGET_COLUMNS[sourceKey] || [];
  const [mapping, setMapping] = useState(() =>
    Object.fromEntries(targets.map((t) => [t, ""]))
  );

  const handleChange = (target, value) => {
    setMapping((prev) => ({ ...prev, [target]: value }));
  };

  const handleSubmit = () => {
    const filtered = Object.fromEntries(
      Object.entries(mapping).filter(([, v]) => v !== "")
    );
    onConfirm(filtered);
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
          {targets.map((target) => (
            <div key={target} className="qdg-mapping-row">
              <span className="qdg-mapping-target">{target}</span>
              <select
                className="qdg-mapping-select"
                value={mapping[target]}
                onChange={(e) => handleChange(target, e.target.value)}
              >
                <option value="">— skip —</option>
                {headers.map((h) => (
                  <option key={h} value={h}>{h}</option>
                ))}
              </select>
            </div>
          ))}
        </div>

        <div className="qdg-mapping-actions">
          <button className="qdg-cancel-btn" onClick={onCancel}>Cancel</button>
          <button className="qdg-confirm-btn" onClick={handleSubmit}>Confirm &amp; Load</button>
        </div>
      </div>
    </div>
  );
}

export default QlenseDataGate;
