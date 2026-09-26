import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, UploadCloud, Download, AlertTriangle, CheckCircle2, ChevronDown, ChevronUp, XCircle } from 'lucide-react';
import { pfmeaApi } from '../../services/api/pfmeaApi';
import './PFMEA.css';

// The AI review is real, billed Azure OpenAI calls per row - losing the
// result to an accidental refresh/back-nav means paying for it again to
// see it. Keeps only the most recent run (sessionStorage, not
// localStorage - a stale review from days ago showing up unprompted would
// be more confusing than losing it, and this already keeps it across a
// same-tab reload/nav which is the actual accident being guarded against).
const SESSION_STORAGE_KEY = 'pfmea_last_result';

function saveResultToSession(fileName, result) {
  try {
    sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({ fileName, result, savedAt: Date.now() }));
  } catch {
    // Storage full/unavailable (private browsing, quota) - the review
    // still works this session, it just won't survive a reload. Not worth
    // surfacing to the user over.
  }
}

function loadResultFromSession() {
  try {
    const raw = sessionStorage.getItem(SESSION_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function clearResultFromSession() {
  try {
    sessionStorage.removeItem(SESSION_STORAGE_KEY);
  } catch {
    // ignore
  }
}

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

function RepeatRunsPanel({ runs, consistent }) {
  const [expanded, setExpanded] = useState(false);
  if (!runs || runs.length < 2) return null; // repeat=1 has nothing to compare

  return (
    <div className={`pfmea-repeat-panel ${consistent ? 'consistent' : 'unstable'}`}>
      <button type="button" className="pfmea-repeat-toggle" onClick={() => setExpanded((v) => !v)}>
        <span>
          {consistent
            ? `All ${runs.length} AI runs agreed`
            : `⚠ ${runs.length} AI runs disagreed — see why below`}
        </span>
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      {expanded && (
        <div className="pfmea-repeat-list">
          {runs.map((r, i) => (
            <div key={i} className={`pfmea-repeat-run ${r.is_winner ? 'winner' : ''}`}>
              <div className="pfmea-repeat-run-header">
                <span>Run {i + 1}{r.is_winner ? ' (used)' : ''}</span>
                <span className="pfmea-repeat-run-scores">
                  S{r.severity ?? '—'} / D{r.detection ?? '—'}
                </span>
              </div>
              {r.reasoning && <p className="pfmea-repeat-run-reasoning">{r.reasoning}</p>}
            </div>
          ))}
        </div>
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

      <RepeatRunsPanel runs={row.ai_repeat_runs} consistent={row.ai_consistent_across_runs} />

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

function UsageReport({ usage }) {
  const [expanded, setExpanded] = useState(false);
  if (!usage || !usage.rows || usage.rows.length === 0) return null;

  return (
    <div className="pfmea-usage-card">
      <button
        type="button"
        className="pfmea-usage-summary"
        onClick={() => setExpanded((v) => !v)}
      >
        <span>
          <strong>{usage.rows.length}</strong> row(s) scored — tokens in{' '}
          <strong>{usage.total_input_tokens.toLocaleString()}</strong>, out{' '}
          <strong>{usage.total_output_tokens.toLocaleString()}</strong>, total{' '}
          <strong>{usage.total_tokens.toLocaleString()}</strong>
          {usage.total_cost_usd != null && (
            <> — est. cost <strong>${usage.total_cost_usd.toFixed(4)}</strong></>
          )}
        </span>
        {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>

      {expanded && (
        <div className="pfmea-usage-table-wrap">
          <p className="pfmea-hint">
            Real per-row token counts from Azure's usage_metadata (not an estimate); cost is
            estimated from a fixed $/1K rate, not read from Azure.
          </p>
          <table className="pfmea-usage-table">
            <thead>
              <tr>
                <th>Sheet</th>
                <th>Failure Mode</th>
                <th>Input</th>
                <th>Output</th>
                <th>Total</th>
                <th>Est. cost</th>
              </tr>
            </thead>
            <tbody>
              {usage.rows.map((r, i) => (
                <tr key={i}>
                  <td>{r.sheet}</td>
                  <td>{r.failure_mode || '—'}</td>
                  <td>{r.input_tokens.toLocaleString()}</td>
                  <td>{r.output_tokens.toLocaleString()}</td>
                  <td>{r.total_tokens.toLocaleString()}</td>
                  <td>{r.cost_usd != null ? `$${r.cost_usd.toFixed(4)}` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
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
  const [scope, setScope] = useState('all'); // 'all' | 'select'
  const [repeat, setRepeat] = useState(3); // how many independent AI passes per row - 2/3/5
  const [loadingSheets, setLoadingSheets] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null); // { sheets: { name: [rows] }, download_token }
  const [activeSheet, setActiveSheet] = useState(null);
  const [restoredFileName, setRestoredFileName] = useState(null);
  const abortControllerRef = useRef(null);

  // Restore the last saved run once, on first mount - e.g. after an
  // accidental refresh or a nav-away-and-back, rather than losing paid-for
  // AI output.
  useEffect(() => {
    const saved = loadResultFromSession();
    if (saved?.result) {
      setResult(saved.result);
      setRestoredFileName(saved.fileName || null);
      const firstSheet = Object.keys(saved.result.sheets || {})[0];
      setActiveSheet(firstSheet || null);
    }
  }, []);

  const handleFileChange = async (e) => {
    const chosen = e.target.files?.[0];
    if (!chosen) return;
    setFile(chosen);
    setResult(null);
    setRestoredFileName(null);
    clearResultFromSession();
    setError('');
    setSheetNames([]);
    setSelectedSheets([]);
    setScope('all');
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
    if (scope === 'select' && selectedSheets.length === 0) return;
    setAnalyzing(true);
    setError('');
    setResult(null);
    setRestoredFileName(null);
    const controller = new AbortController();
    abortControllerRef.current = controller;
    try {
      const sheetsToRun = scope === 'all' ? [] : selectedSheets;
      const res = await pfmeaApi.analyze(file, sheetsToRun, repeat, controller.signal);
      setResult(res.data);
      saveResultToSession(file.name, res.data);
      const firstSheet = Object.keys(res.data.sheets || {})[0];
      setActiveSheet(firstSheet || null);
    } catch (err) {
      if (axios.isCancel?.(err) || err.code === 'ERR_CANCELED') {
        setError('Review cancelled - no further rows were sent for scoring.');
      } else {
        setError(err?.response?.data?.detail || 'PFMEA analysis failed.');
      }
    } finally {
      setAnalyzing(false);
      abortControllerRef.current = null;
    }
  };

  const handleCancel = () => {
    abortControllerRef.current?.abort();
  };

  const rows = result && activeSheet ? result.sheets[activeSheet] || [] : [];
  const mismatchCount = rows.filter((r) => !r.agree).length;

  return (
    <div className="pfmea-page">
      <div className="pfmea-header">
        <div className="header-title-group">
          <button className="sidebar-back-btn" onClick={() => navigate('/')}>
            <ArrowLeft size={16} /><span>Dashboard</span>
          </button>
          <div className="header-title">
            <h1>PFMEA Assistant</h1>
            <p>AI-reviewed Severity and Detection suggestions for your PFMEA sheet</p>
          </div>
        </div>
        {result && (
          <div className="header-stats">
            <div className="stat-card">
              <span className="stat-value">{rows.length}</span>
              <span className="stat-label">Rows reviewed</span>
            </div>
            <div className="stat-card">
              <span className="stat-value">{mismatchCount}</span>
              <span className="stat-label">Differ from plant</span>
            </div>
          </div>
        )}
      </div>

      <div className="pfmea-scroll-body">
      <div className="pfmea-upload-card">
        <label className="pfmea-upload-label">
          <UploadCloud size={20} />
          <span>{file ? file.name : 'Choose a PFMEA Excel file'}</span>
          <input type="file" accept=".xlsx" onChange={handleFileChange} hidden />
        </label>

        {loadingSheets && <p className="pfmea-hint">Reading sheet names…</p>}

        {sheetNames.length > 0 && (
          <div className="pfmea-sheet-picker">
            <p className="pfmea-hint">What should the AI review run on?</p>
            <div className="pfmea-scope-toggle">
              <button
                type="button"
                className={`pfmea-scope-btn ${scope === 'all' ? 'active' : ''}`}
                onClick={() => setScope('all')}
              >
                Full sheet — all {sheetNames.length} tab{sheetNames.length !== 1 ? 's' : ''}
              </button>
              <button
                type="button"
                className={`pfmea-scope-btn ${scope === 'select' ? 'active' : ''}`}
                onClick={() => setScope('select')}
              >
                Choose specific tabs
              </button>
            </div>

            {scope === 'select' && (
              <>
                <p className="pfmea-hint">Select the tab(s) to review:</p>
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
              </>
            )}

            <p className="pfmea-hint">
              AI passes per row — more passes cost more (repeat × LLM calls) but catch
              sampling noise better:
            </p>
            <div className="pfmea-scope-toggle">
              {[2, 3, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  className={`pfmea-scope-btn ${repeat === n ? 'active' : ''}`}
                  onClick={() => setRepeat(n)}
                >
                  {n} passes{n === 3 ? ' (recommended)' : ''}
                </button>
              ))}
            </div>
          </div>
        )}

        {file && sheetNames.length > 0 && (
          <div className="pfmea-run-row">
            <button
              className="pfmea-analyze-btn"
              onClick={handleAnalyze}
              disabled={analyzing || (scope === 'select' && selectedSheets.length === 0)}
            >
              {analyzing
                ? 'Running AI review… this can take a few minutes'
                : scope === 'all'
                ? `Run PFMEA AI Review — full sheet (${sheetNames.length} tab${sheetNames.length !== 1 ? 's' : ''})`
                : `Run PFMEA AI Review — ${selectedSheets.length} tab${selectedSheets.length !== 1 ? 's' : ''} selected`}
            </button>
            {analyzing && (
              <button className="pfmea-cancel-btn" onClick={handleCancel}>
                <XCircle size={16} /> Cancel
              </button>
            )}
          </div>
        )}

        {error && <p className="pfmea-error">{error}</p>}
      </div>

      {result && (
        <div className="pfmea-results">
          {restoredFileName && (
            <div className="pfmea-restored-banner">
              Showing your last review ({restoredFileName}) restored from this browser session.
              <button
                className="pfmea-restored-dismiss"
                onClick={() => {
                  setResult(null);
                  setRestoredFileName(null);
                  clearResultFromSession();
                }}
              >
                Clear
              </button>
            </div>
          )}

          <UsageReport usage={result.usage} />

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
    </div>
  );
}

export default PFMEA;
