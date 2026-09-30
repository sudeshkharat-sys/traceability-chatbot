import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, UploadCloud, Download, AlertTriangle, CheckCircle2, ChevronDown, ChevronUp, XCircle, Loader2, RefreshCw } from 'lucide-react';
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

// How often the frontend polls /pfmea/progress while a review is running.
const POLL_INTERVAL_MS = 1500;

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

// Cost/token usage is deliberately not shown in this UI for now (product
// call: reviewers shouldn't see per-run $ figures here). The backend still
// computes and returns result.usage in full - see UsageReport in git
// history, or pfmea_service.py's usage dict - so it's a one-line change to
// bring back if that changes later; there's just no component rendering
// it right now.

const CARD_FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'differs', label: 'Differs from plant' },
  { key: 'ambiguous', label: 'Ambiguous' },
];

function ConversionPreview({ conversion, confirmed, onConfirm, onDiscard }) {
  const [active, setActive] = useState(conversion.sheets[0]?.name);
  const sheet = conversion.sheets.find((s) => s.name === active) || conversion.sheets[0];
  return (
    <div className="pfmea-convert-preview">
      <div className="pfmea-sheet-tabs">
        {conversion.sheets.map((s) => (
          <button
            key={s.name}
            className={`pfmea-sheet-tab ${active === s.name ? 'active' : ''}`}
            onClick={() => setActive(s.name)}
          >
            {s.name} ({s.rows.length} rows · {s.from_label} → Nashik)
          </button>
        ))}
      </div>
      <div className="pfmea-table-wrap">
        <table className="pfmea-table">
          <thead>
            <tr>
              <th>Src row</th><th>Step</th><th>Failure Effect (original → Nashik)</th><th>S</th>
              <th>Failure Mode</th><th>Failure Cause</th><th>Prevention</th><th>O</th>
              <th>Detection control</th><th>D</th>
            </tr>
          </thead>
          <tbody>
            {sheet.rows.map((r, i) => (
              <tr key={i}>
                <td>{r.source_row}</td>
                <td>{r.step}</td>
                <td>
                  <div className="pfmea-before">{r.effect_before}</div>
                  <div className="pfmea-after">{r.effect_after}</div>
                </td>
                <td>{r.severity}</td>
                <td>{r.mode}</td>
                <td>{r.cause}</td>
                <td>{r.prevention}</td>
                <td>{r.occurrence}</td>
                <td>{r.detection_ctrl}</td>
                <td>{r.detection}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="pfmea-convert-actions">
        {confirmed ? (
          <span className="pfmea-agree-badge agree"><CheckCircle2 size={14} /> Conversion confirmed — you can run the AI</span>
        ) : (
          <>
            <button className="pfmea-analyze-btn" onClick={onConfirm}>Looks right — confirm</button>
            <button className="pfmea-cancel-btn" onClick={onDiscard}>Discard</button>
          </>
        )}
        <a className="pfmea-download-btn" href={pfmeaApi.convertedUrl(conversion.convert_token)} download>
          <Download size={16} /> Open converted Excel
        </a>
      </div>
    </div>
  );
}

function Change({ plant, ai }) {
  if (ai == null && plant == null) return <span>—</span>;
  const changed = plant != null && ai != null && plant !== ai;
  return (
    <span className={changed ? 'pfmea-changed' : ''}>
      {plant ?? '—'} → <strong>{ai ?? '—'}</strong>
    </span>
  );
}

function ChangesTable({ rows }) {
  return (
    <div className="pfmea-table-wrap">
      <table className="pfmea-table">
        <thead>
          <tr>
            <th>Excel row</th><th>Failure Mode</th><th>Severity (plant → AI)</th>
            <th>Detection (plant → AI)</th><th>AI prevention</th><th>AI detection action</th><th>Severity note</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className={r.agree ? '' : 'pfmea-row-differs'}>
              <td>{(r.source_excel_rows || []).join(', ')}</td>
              <td>{r.failure_mode}</td>
              <td><Change plant={r.plant_recorded_severity} ai={r.ai_suggested_severity} /></td>
              <td><Change plant={r.plant_recorded_detection} ai={r.ai_suggested_detection} /></td>
              <td>{r.ai_recommended_action}</td>
              <td>{r.ai_detection_recommendation}</td>
              <td>{r.ai_reasoning}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StepBadge({ n }) {
  return <span className="pfmea-step-badge">{n}</span>;
}

function PFMEA() {
  const navigate = useNavigate();

  const [file, setFile] = useState(null);
  const [sheetNames, setSheetNames] = useState([]);
  const [selectedSheets, setSelectedSheets] = useState([]);
  const [scope, setScope] = useState('all'); // 'all' | 'select'
  const [layout, setLayout] = useState('auto'); // 'auto' | a layout id from the backend registry
  const [layouts, setLayouts] = useState([]); // [{ id, label }] selectable sheet formats
  const [sheetLayouts, setSheetLayouts] = useState({}); // { sheetName: layoutId | null } as auto-detected
  const [repeat, setRepeat] = useState(3); // 1 ("None") - 5 independent AI passes per row
  const [loadingSheets, setLoadingSheets] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [progress, setProgress] = useState(null); // { completed_rows, total_rows, current_sheet }
  const [runToken, setRunToken] = useState(null);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null); // { sheets: { name: [rows] }, download_token, usage }
  const [activeSheet, setActiveSheet] = useState(null);
  const [cardFilter, setCardFilter] = useState('all');
  const [restoredFileName, setRestoredFileName] = useState(null);
  const [converting, setConverting] = useState(false);
  const [conversion, setConversion] = useState(null); // backend /convert payload
  const [conversionConfirmed, setConversionConfirmed] = useState(false);
  const [resultView, setResultView] = useState('table'); // 'table' | 'cards'
  const pollRef = useRef(null);

  // Sheets auto-detected as a plant format other than Nashik - these must be
  // converted (and the conversion confirmed) before any AI call is spent.
  const nonNashikSheets = sheetNames.filter(
    (n) => sheetLayouts[n] && sheetLayouts[n] !== 'nashik_vda'
  );
  const needsConversion = layout === 'auto' && nonNashikSheets.length > 0 && !conversionConfirmed;

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

  useEffect(() => () => clearInterval(pollRef.current), []);

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
    setLayout('auto');
    setSheetLayouts({});
    setScope('all');
    setConversion(null);
    setConversionConfirmed(false);
    setLoadingSheets(true);
    try {
      const res = await pfmeaApi.listSheets(chosen);
      setSheetNames(res.data.sheets || []);
      setLayouts(res.data.layouts || []);
      setSheetLayouts(res.data.sheet_layouts || {});
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

  const stopPolling = () => {
    clearInterval(pollRef.current);
    pollRef.current = null;
  };

  const pollProgress = (token) => {
    pollRef.current = setInterval(async () => {
      try {
        const res = await pfmeaApi.getProgress(token);
        const state = res.data;
        setProgress(state);

        // Still running - leave analyzing/cancelling untouched and wait
        // for the next tick. This used to fall through to a `finally`
        // block that ran setAnalyzing(false) on EVERY tick including this
        // early return (finally always runs after a try, `return` or
        // not) - flipping the Run button back to idle red and hiding the
        // whole progress block on the very first poll, even though the
        // job was still running fine in the background.
        if (state.status === 'running') return;

        stopPolling();
        if (state.status === 'error') {
          setError(state.error || 'PFMEA analysis failed.');
          setAnalyzing(false);
          setCancelling(false);
          return;
        }

        // done or cancelled - fetch the final payload
        const resultRes = await pfmeaApi.getResult(token);
        setResult(resultRes.data);
        saveResultToSession(file?.name, resultRes.data);
        const firstSheet = Object.keys(resultRes.data.sheets || {})[0];
        setActiveSheet(firstSheet || null);
        if (state.status === 'cancelled') {
          setError('Review cancelled - rows already in progress were kept, no further rows were scored.');
        }
        setAnalyzing(false);
        setCancelling(false);
      } catch (err) {
        stopPolling();
        setError(err?.response?.data?.detail || 'PFMEA analysis failed.');
        setAnalyzing(false);
        setCancelling(false);
      }
    }, POLL_INTERVAL_MS);
  };

  const handleConvert = async () => {
    if (!file) return;
    setConverting(true);
    setError('');
    try {
      const res = await pfmeaApi.convertToNashik(file, layout);
      setConversion(res.data);
      if (!res.data.converted) setConversionConfirmed(true); // nothing to convert
    } catch (err) {
      setError(err?.response?.data?.detail || 'Conversion failed.');
    } finally {
      setConverting(false);
    }
  };

  const handleAnalyze = async () => {
    if (!file) return;
    if (scope === 'select' && selectedSheets.length === 0) return;
    setAnalyzing(true);
    setCancelling(false);
    setError('');
    setResult(null);
    setRestoredFileName(null);
    setProgress({ completed_rows: 0, total_rows: 0, current_sheet: null, current_failure_mode: null });
    try {
      const sheetsToRun = scope === 'all' ? [] : selectedSheets;
      const res = await pfmeaApi.startAnalysis(
        file,
        sheetsToRun,
        repeat,
        layout,
        conversionConfirmed && conversion?.converted ? conversion.convert_token : null
      );
      setRunToken(res.data.token);
      pollProgress(res.data.token);
    } catch (err) {
      setError(err?.response?.data?.detail || 'PFMEA analysis failed to start.');
      setAnalyzing(false);
    }
  };

  const handleCancel = async () => {
    if (!runToken) return;
    setCancelling(true);
    try {
      await pfmeaApi.cancelRun(runToken);
    } catch {
      // Progress polling will surface the real state either way.
    }
  };

  const allRows = result && activeSheet ? result.sheets[activeSheet] || [] : [];
  const rows = allRows.filter((r) => {
    if (cardFilter === 'differs') return !r.agree;
    if (cardFilter === 'ambiguous') return !!r.ai_possible_severities;
    return true;
  });
  const mismatchCount = allRows.filter((r) => !r.agree).length;

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
              <span className="stat-value">{allRows.length}</span>
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
        <div className="pfmea-step-card">
          <div className="pfmea-step-heading">
            <StepBadge n={1} />
            <span>Upload</span>
          </div>
          <label className="pfmea-upload-label">
            <UploadCloud size={20} />
            <span>{file ? file.name : 'Choose a PFMEA Excel file'}</span>
            <input type="file" accept=".xlsx" onChange={handleFileChange} hidden />
          </label>
          {loadingSheets && <p className="pfmea-hint">Reading sheet names…</p>}
        </div>

        {nonNashikSheets.length > 0 && layout === 'auto' && (
          <div className="pfmea-step-card pfmea-convert-card">
            <div className="pfmea-step-heading">
              <StepBadge n="↻" />
              <span>Format check</span>
            </div>
            <p className="pfmea-convert-msg">
              {nonNashikSheets.map((n) => {
                const label = (layouts.find((l) => l.id === sheetLayouts[n]) || {}).label;
                return `"${n}" is ${label}`;
              }).join('; ')}
              {' '}— not the Nashik AIAG-VDA format. Convert it first, check the result, then run the AI.
            </p>
            {!conversion && (
              <button className="pfmea-analyze-btn" onClick={handleConvert} disabled={converting}>
                {converting ? <Loader2 size={16} className="pfmea-spin" /> : <RefreshCw size={16} />}
                {converting ? 'Converting…' : 'Convert to Nashik format'}
              </button>
            )}
            {conversion?.converted && (
              <ConversionPreview
                conversion={conversion}
                confirmed={conversionConfirmed}
                onConfirm={() => setConversionConfirmed(true)}
                onDiscard={() => { setConversion(null); setConversionConfirmed(false); }}
              />
            )}
          </div>
        )}

        {sheetNames.length > 0 && (
          <div className="pfmea-step-card">
            <div className="pfmea-step-heading">
              <StepBadge n={2} />
              <span>Options</span>
            </div>

            <div className="pfmea-options-bar">
              <div className="pfmea-option-group">
                <label className="pfmea-option-label">Run on</label>
                <div className="pfmea-scope-toggle">
                  <button
                    type="button"
                    className={`pfmea-scope-btn ${scope === 'all' ? 'active' : ''}`}
                    onClick={() => setScope('all')}
                  >
                    Full sheet ({sheetNames.length})
                  </button>
                  <button
                    type="button"
                    className={`pfmea-scope-btn ${scope === 'select' ? 'active' : ''}`}
                    onClick={() => setScope('select')}
                  >
                    Choose tabs
                  </button>
                </div>
              </div>

              <div className="pfmea-option-group">
                <label className="pfmea-option-label" htmlFor="pfmea-layout-select">Sheet format</label>
                <select
                  id="pfmea-layout-select"
                  className="pfmea-repeat-select"
                  value={layout}
                  onChange={(e) => setLayout(e.target.value)}
                  disabled={analyzing}
                >
                  <option value="auto">Auto-detect (recommended)</option>
                  {layouts.map((l) => (
                    <option key={l.id} value={l.id}>{l.label}</option>
                  ))}
                </select>
              </div>

              <div className="pfmea-option-group">
                <label className="pfmea-option-label" htmlFor="pfmea-repeat-select">AI passes per row</label>
                <select
                  id="pfmea-repeat-select"
                  className="pfmea-repeat-select"
                  value={repeat}
                  onChange={(e) => setRepeat(Number(e.target.value))}
                >
                  <option value={1}>None</option>
                  <option value={2}>2</option>
                  <option value={3}>3 (recommended)</option>
                  <option value={4}>4</option>
                  <option value={5}>5</option>
                </select>
              </div>

              <div className="pfmea-option-group pfmea-run-group">
                <button
                  className={`pfmea-analyze-btn ${analyzing ? 'running' : ''}`}
                  onClick={handleAnalyze}
                  disabled={analyzing || needsConversion || (scope === 'select' && selectedSheets.length === 0)}
                  title={needsConversion ? 'Convert to Nashik format and confirm first' : undefined}
                >
                  {analyzing ? <Loader2 size={16} className="pfmea-spin" /> : null}
                  {analyzing ? 'Running…' : 'Run'}
                </button>
                {analyzing && (
                  <button className="pfmea-cancel-btn" onClick={handleCancel} disabled={cancelling}>
                    <XCircle size={16} /> {cancelling ? 'Cancelling…' : 'Cancel'}
                  </button>
                )}
              </div>
            </div>

            {scope === 'select' && (
              <div className="pfmea-sheet-chips">
                {sheetNames.map((name) => (
                  <button
                    key={name}
                    className={`pfmea-sheet-chip ${selectedSheets.includes(name) ? 'selected' : ''}`}
                    onClick={() => toggleSheet(name)}
                  >
                    {name}
                    <span className="pfmea-sheet-format">
                      {(layouts.find((l) => l.id === sheetLayouts[name]) || {}).label || 'not recognized'}
                    </span>
                  </button>
                ))}
              </div>
            )}

            {analyzing && progress && (
              <>
                <div className="pfmea-progress-status">
                  <span className="pfmea-progress-dot" />
                  <span>
                    {progress.current_failure_mode
                      ? `Scoring "${progress.current_failure_mode}"…`
                      : progress.current_sheet
                      ? `Reading "${progress.current_sheet}"…`
                      : 'Starting the review…'}
                  </span>
                </div>
                <div className="pfmea-progress-row">
                  <div className="pfmea-progress-track">
                    <div
                      className="pfmea-progress-fill"
                      style={{
                        width: progress.total_rows
                          ? `${Math.min(100, (progress.completed_rows / progress.total_rows) * 100)}%`
                          : '4%',
                      }}
                    />
                  </div>
                  <span className="pfmea-progress-label">
                    {progress.total_rows ? `Row ${progress.completed_rows} of ${progress.total_rows}` : 'Starting…'}
                  </span>
                </div>
              </>
            )}

            {error && <p className="pfmea-error">{error}</p>}
          </div>
        )}

        {result && (
          <div className="pfmea-step-card pfmea-results">
            <div className="pfmea-step-heading">
              <StepBadge n={3} />
              <span>Results</span>
            </div>

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

            <div className="pfmea-card-filters">
              {CARD_FILTERS.map((f) => (
                <button
                  key={f.key}
                  className={`pfmea-filter-chip ${cardFilter === f.key ? 'active' : ''}`}
                  onClick={() => setCardFilter(f.key)}
                >
                  {f.label}
                </button>
              ))}
              <span className="pfmea-filter-count">{rows.length} shown</span>
              <span className="pfmea-view-toggle">
                {['table', 'cards'].map((v) => (
                  <button
                    key={v}
                    className={`pfmea-filter-chip ${resultView === v ? 'active' : ''}`}
                    onClick={() => setResultView(v)}
                  >
                    {v === 'table' ? 'Changes table' : 'Cards'}
                  </button>
                ))}
              </span>
            </div>

            {resultView === 'table' ? (
              <ChangesTable rows={rows} />
            ) : (
              <div className="pfmea-card-grid">
                {rows.map((row, i) => (
                  <RowCard key={i} row={row} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default PFMEA;
