import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, UploadCloud, Download, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { pfmeaApi } from '../../services/api/pfmeaApi';
import './PFMEA.css';

// Severity/Detection 1-10: colour band purely for the at-a-glance badge -
// matches the AIAG-VDA table's own rough grouping (see
// pfmea_engine/step5_severity_llm.py's SEVERITY_TABLE_TEXT), not an exact
// cutoff the standard itself defines.
function scoreBand(score) {
  if (score == null) return 'unknown';
  if (score >= 9) return 'high';
  if (score >= 7) return 'medium';
  if (score >= 4) return 'low';
  return 'minimal';
}

function ScoreBadge({ label, plantValue, aiValue }) {
  const mismatch = plantValue != null && aiValue != null && plantValue !== aiValue;
  return (
    <div className="pfmea-score-badge">
      <span className="pfmea-score-label">{label}</span>
      <span className={`pfmea-score-pill band-${scoreBand(aiValue)}`}>
        AI {aiValue ?? '—'}
      </span>
      {plantValue != null && (
        <span className={`pfmea-score-plant ${mismatch ? 'mismatch' : ''}`}>
          Plant {plantValue}
        </span>
      )}
    </div>
  );
}

function RowCard({ row }) {
  const flags = [];
  if (row.ai_row_completeness_note) flags.push(row.ai_row_completeness_note);
  if (row.ai_cause_mode_mismatch && row.ai_cause_mode_mismatch_note) {
    flags.push(`Cause/Mode mismatch: ${row.ai_cause_mode_mismatch_note}`);
  }
  if (row.ai_merged_modes_detected && row.ai_merged_modes_detected.length > 1) {
    flags.push(`Merged failure mode (${row.ai_merged_modes_detected.length} distinct modes detected)`);
  }

  return (
    <div className="pfmea-card">
      <div className="pfmea-card-header">
        <h4>{row.failure_mode || '(no Failure Mode recorded)'}</h4>
        {row.agree ? (
          <span className="pfmea-agree-badge agree"><CheckCircle2 size={14} /> Matches plant</span>
        ) : (
          <span className="pfmea-agree-badge differs"><AlertTriangle size={14} /> Differs from plant</span>
        )}
      </div>

      <div className="pfmea-card-scores">
        <ScoreBadge label="Severity" plantValue={row.plant_recorded_severity} aiValue={row.ai_suggested_severity} />
        <ScoreBadge label="Detection" plantValue={row.plant_recorded_detection} aiValue={row.ai_suggested_detection} />
      </div>

      {row.ai_possible_severities && (
        <div className="pfmea-ambiguous">
          <strong>Ambiguous — review before finalizing:</strong>
          <ul>
            {row.ai_possible_severities.map((p, i) => (
              <li key={i}>S{p.severity} — {p.effect_used}</li>
            ))}
          </ul>
        </div>
      )}

      {row.ai_reasoning && (
        <p className="pfmea-reasoning"><strong>Severity note:</strong> {row.ai_reasoning}</p>
      )}

      {row.ai_recommended_action && (
        <p className="pfmea-recommendation"><strong>Prevention:</strong> {row.ai_recommended_action}</p>
      )}

      {row.ai_detection_recommendation && (
        <p className="pfmea-recommendation"><strong>Detection action:</strong> {row.ai_detection_recommendation}</p>
      )}

      {flags.length > 0 && (
        <div className="pfmea-flags">
          {flags.map((f, i) => (
            <span key={i} className="pfmea-flag-chip">{f}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function PFMEA() {
  const navigate = useNavigate();

  const [file, setFile] = useState(null);
  const [sheetNames, setSheetNames] = useState([]);
  const [selectedSheets, setSelectedSheets] = useState([]);
  const [loadingSheets, setLoadingSheets] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null); // { sheets: { name: [rows] }, download_token }
  const [activeSheet, setActiveSheet] = useState(null);

  const handleFileChange = async (e) => {
    const chosen = e.target.files?.[0];
    if (!chosen) return;
    setFile(chosen);
    setResult(null);
    setError('');
    setSheetNames([]);
    setSelectedSheets([]);
    setLoadingSheets(true);
    try {
      const res = await pfmeaApi.listSheets(chosen);
      setSheetNames(res.data.sheets || []);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not read that workbook.');
    } finally {
      setLoadingSheets(false);
    }
  };

  const toggleSheet = (name) => {
    setSelectedSheets((prev) =>
      prev.includes(name) ? prev.filter((s) => s !== name) : [...prev, name]
    );
  };

  const handleAnalyze = async () => {
    if (!file) return;
    setAnalyzing(true);
    setError('');
    setResult(null);
    try {
      const res = await pfmeaApi.analyze(file, selectedSheets);
      setResult(res.data);
      const firstSheet = Object.keys(res.data.sheets || {})[0];
      setActiveSheet(firstSheet || null);
    } catch (err) {
      setError(err?.response?.data?.detail || 'PFMEA analysis failed.');
    } finally {
      setAnalyzing(false);
    }
  };

  const rows = result && activeSheet ? result.sheets[activeSheet] || [] : [];
  const mismatchCount = rows.filter((r) => !r.agree).length;

  return (
    <div className="pfmea-page">
      <div className="pfmea-header">
        <button className="pfmea-back-btn" onClick={() => navigate('/')}>
          <ArrowLeft size={16} /><span>Dashboard</span>
        </button>
        <h2>PFMEA Assistant</h2>
      </div>

      <div className="pfmea-upload-card">
        <label className="pfmea-upload-label">
          <UploadCloud size={20} />
          <span>{file ? file.name : 'Choose a PFMEA Excel file'}</span>
          <input type="file" accept=".xlsx" onChange={handleFileChange} hidden />
        </label>

        {loadingSheets && <p className="pfmea-hint">Reading sheet names…</p>}

        {sheetNames.length > 0 && (
          <div className="pfmea-sheet-picker">
            <p className="pfmea-hint">Pick sheet(s) to review (none selected = all sheets):</p>
            <div className="pfmea-sheet-chips">
              {sheetNames.map((name) => (
                <button
                  key={name}
                  className={`pfmea-sheet-chip ${selectedSheets.includes(name) ? 'selected' : ''}`}
                  onClick={() => toggleSheet(name)}
                >
                  {name}
                </button>
              ))}
            </div>
          </div>
        )}

        {file && sheetNames.length > 0 && (
          <button className="pfmea-analyze-btn" onClick={handleAnalyze} disabled={analyzing}>
            {analyzing ? 'Running AI review… this can take a few minutes' : 'Run PFMEA AI Review'}
          </button>
        )}

        {error && <p className="pfmea-error">{error}</p>}
      </div>

      {result && (
        <div className="pfmea-results">
          <div className="pfmea-results-toolbar">
            <div className="pfmea-sheet-tabs">
              {Object.keys(result.sheets).map((name) => (
                <button
                  key={name}
                  className={`pfmea-sheet-tab ${activeSheet === name ? 'active' : ''}`}
                  onClick={() => setActiveSheet(name)}
                >
                  {name} ({result.sheets[name].length})
                </button>
              ))}
            </div>
            <div className="pfmea-results-summary">
              <span>{rows.length} row(s) reviewed</span>
              <span className={mismatchCount > 0 ? 'pfmea-summary-warn' : ''}>
                {mismatchCount} differ from plant Severity
              </span>
              <a
                className="pfmea-download-btn"
                href={pfmeaApi.downloadUrl(result.download_token)}
                download
              >
                <Download size={16} /> Download annotated Excel
              </a>
            </div>
          </div>

          <div className="pfmea-card-grid">
            {rows.map((row, i) => (
              <RowCard key={i} row={row} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default PFMEA;
