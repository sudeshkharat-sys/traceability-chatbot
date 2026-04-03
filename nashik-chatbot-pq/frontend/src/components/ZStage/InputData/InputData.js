import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Upload, Database, CheckCircle, AlertCircle, Loader, Plus, X } from 'lucide-react';
import { inputApi } from '../../../services/api/layoutApi';
import './InputData.css';

const MONTHLY_KEYS = [
  '2024-01','2024-02','2024-03','2024-04','2024-05','2024-06',
  '2024-07','2024-08','2024-09','2024-10','2024-11','2024-12',
  '2025-01','2025-02','2025-03','2025-04','2025-05','2025-06',
  '2025-07','2025-08','2025-09','2025-10','2025-11','2025-12',
  '2026-01','2026-02','2026-03',
];

const FIXED_COLUMNS = [
  { key: 'sr_no',          label: 'Sr.No',          width: 60,  type: 'number' },
  { key: 'concern_id',     label: 'Concern ID',      width: 130, type: 'text'   },
  { key: 'concern',        label: 'Concern',         width: 260, type: 'text'   },
  { key: 'type',           label: 'Type',            width: 70,  type: 'text'   },
  { key: 'root_cause',     label: 'Root Cause',      width: 220, type: 'text'   },
  { key: 'action_plan',    label: 'Action Plan',     width: 220, type: 'text'   },
  { key: 'target_date',    label: 'Target Date',     width: 110, type: 'text'   },
  { key: 'closure_date',   label: 'Closure Date',    width: 110, type: 'text'   },
  { key: 'ryg',            label: 'RYG',             width: 60,  type: 'text'   },
  { key: 'attri',          label: 'Attri.',          width: 90,  type: 'text'   },
  { key: 'comm',           label: 'Comm',            width: 160, type: 'text'   },
  { key: 'line',           label: 'Line',            width: 120, type: 'text'   },
  { key: 'stage_no',       label: 'Stage No',        width: 90,  type: 'text'   },
  { key: 'z_e',            label: 'Z/E',             width: 55,  type: 'text'   },
  { key: 'attribution',    label: 'Attribution',     width: 90,  type: 'text'   },
  { key: 'part',           label: 'Part',            width: 160, type: 'text'   },
  { key: 'phenomena',      label: 'Phenomena',       width: 160, type: 'text'   },
  { key: 'total_incidences', label: 'Total',         width: 70,  type: 'number' },
];

const TRAILING_COLUMNS = [
  { key: 'field_defect_after_cutoff', label: 'Field Defect After Cut-off', width: 130, type: 'number' },
  { key: 'status_3m',                 label: 'Status (3M)',                 width: 90,  type: 'text'   },
];

function formatMonthLabel(key) {
  const [year, month] = key.split('-');
  const date = new Date(Number(year), Number(month) - 1, 1);
  return date.toLocaleString('default', { month: 'short' }) + ' ' + year.slice(2);
}

function RYGBadge({ value }) {
  if (!value) return <span>—</span>;
  const cls = value === 'G' ? 'ryg-g' : value === 'R' ? 'ryg-r' : value === 'Y' ? 'ryg-y' : '';
  return <span className={`ryg-badge ${cls}`}>{value}</span>;
}

function EditableCell({ recordId, fieldKey, value, type, onSaved }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value ?? '');
  const [saving, setSaving] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    setDraft(value ?? '');
  }, [value]);

  useEffect(() => {
    if (editing && inputRef.current) inputRef.current.focus();
  }, [editing]);

  const commit = useCallback(async () => {
    setEditing(false);
    const trimmed = draft.trim();
    const original = String(value ?? '');
    if (trimmed === original) return;

    setSaving(true);
    try {
      const payload = { [fieldKey]: type === 'number' ? (trimmed === '' ? null : Number(trimmed)) : (trimmed || null) };
      const res = await inputApi.updateRecord(recordId, payload);
      onSaved(recordId, res.data);
    } catch (err) {
      console.error('Save failed', err);
      setDraft(value ?? '');
    } finally {
      setSaving(false);
    }
  }, [draft, value, fieldKey, type, recordId, onSaved]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') commit();
    if (e.key === 'Escape') { setDraft(value ?? ''); setEditing(false); }
  };

  if (saving) return <td className="cell-saving"><Loader size={12} className="spin" /></td>;

  if (editing) {
    return (
      <td className="cell-editing">
        {(fieldKey === 'concern' || fieldKey === 'root_cause' || fieldKey === 'action_plan' || fieldKey === 'comm') ? (
          <textarea
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => { if (e.key === 'Escape') { setDraft(value ?? ''); setEditing(false); } }}
            rows={3}
            className="cell-textarea"
          />
        ) : (
          <input
            ref={inputRef}
            type={type === 'number' ? 'number' : 'text'}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commit}
            onKeyDown={handleKeyDown}
            className="cell-input"
          />
        )}
      </td>
    );
  }

  const display = value ?? '';
  const isEmpty = display === '' || display === null || display === undefined;

  return (
    <td className="cell-view" onClick={() => setEditing(true)} title="Click to edit">
      {isEmpty ? <span className="cell-empty">—</span> : <span>{String(display)}</span>}
    </td>
  );
}

function MonthlyCell({ recordId, monthKey, monthlyData, onSaved }) {
  const parsed = monthlyData ? (() => { try { return JSON.parse(monthlyData); } catch { return {}; } })() : {};
  const value = parsed[monthKey] ?? null;

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value !== null ? String(value) : '');
  const [saving, setSaving] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => { setDraft(value !== null ? String(value) : ''); }, [value]);
  useEffect(() => { if (editing && inputRef.current) inputRef.current.focus(); }, [editing]);

  const commit = useCallback(async () => {
    setEditing(false);
    const newVal = draft.trim() === '' ? null : Number(draft.trim());
    if (newVal === value) return;

    setSaving(true);
    try {
      const newParsed = { ...parsed };
      if (newVal === null) {
        delete newParsed[monthKey];
      } else {
        newParsed[monthKey] = newVal;
      }
      const newTotal = Object.values(newParsed).reduce((sum, v) => sum + v, 0);
      const res = await inputApi.updateRecord(recordId, {
        monthly_data: JSON.stringify(newParsed),
        total_incidences: newTotal,
      });
      onSaved(recordId, res.data);
    } catch (err) {
      console.error('Save failed', err);
      setDraft(value !== null ? String(value) : '');
    } finally {
      setSaving(false);
    }
  }, [draft, value, parsed, monthKey, recordId, onSaved]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') commit();
    if (e.key === 'Escape') { setDraft(value !== null ? String(value) : ''); setEditing(false); }
  };

  if (saving) return <td className="cell-saving monthly-cell"><Loader size={12} className="spin" /></td>;

  if (editing) {
    return (
      <td className="cell-editing monthly-cell">
        <input
          ref={inputRef}
          type="number"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={handleKeyDown}
          className="cell-input"
        />
      </td>
    );
  }

  return (
    <td
      className={`cell-view monthly-cell ${value !== null ? 'has-value' : ''}`}
      onClick={() => setEditing(true)}
      title="Click to edit"
    >
      {value !== null ? value : ''}
    </td>
  );
}

const MONTH_NAMES = ['January','February','March','April','May','June','July','August','September','October','November','December'];
const LS_KEY = 'zstage_extra_months';

function AddMonthModal({ existingMonths, onAdd, onClose }) {
  const [month, setMonth] = useState(String(new Date().getMonth() + 1).padStart(2, '0'));
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [error, setError] = useState('');

  const handleAdd = () => {
    const yr = parseInt(year, 10);
    if (!yr || yr < 2000 || yr > 2100) { setError('Enter a valid year (2000–2100).'); return; }
    const key = `${yr}-${month}`;
    if (existingMonths.includes(key)) { setError(`${formatMonthLabel(key)} already exists.`); return; }
    onAdd(key);
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="add-month-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">Add New Month</span>
          <button className="modal-close" onClick={onClose}><X size={16} /></button>
        </div>
        <div className="modal-body">
          <label className="modal-label">Month</label>
          <select className="modal-select" value={month} onChange={(e) => setMonth(e.target.value)}>
            {MONTH_NAMES.map((name, i) => (
              <option key={i} value={String(i + 1).padStart(2, '0')}>{name}</option>
            ))}
          </select>
          <label className="modal-label" style={{ marginTop: 12 }}>Year</label>
          <input
            className="modal-input"
            type="number"
            value={year}
            onChange={(e) => { setYear(e.target.value); setError(''); }}
            min="2000"
            max="2100"
          />
          {error && <p className="modal-error">{error}</p>}
        </div>
        <div className="modal-footer">
          <button className="modal-cancel" onClick={onClose}>Cancel</button>
          <button className="modal-confirm" onClick={handleAdd}>Add Column</button>
        </div>
      </div>
    </div>
  );
}

export default function InputData({ userId }) {
  const [activeTab, setActiveTab] = useState('upload');
  const [dragging, setDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [records, setRecords] = useState([]);
  const [loadingRecords, setLoadingRecords] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [extraMonths, setExtraMonths] = useState(() => {
    try { return JSON.parse(localStorage.getItem(LS_KEY)) || []; } catch { return []; }
  });
  const [showAddMonth, setShowAddMonth] = useState(false);
  const fileInputRef = useRef(null);

  const loadRecords = useCallback(async () => {
    setLoadingRecords(true);
    setLoadError(null);
    try {
      const res = await inputApi.getRecords(userId, null);
      setRecords(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      setLoadError('Failed to load records. Is the backend running?');
    } finally {
      setLoadingRecords(false);
    }
  }, [userId]);

  useEffect(() => {
    if (activeTab === 'master') loadRecords();
  }, [activeTab, loadRecords]);

  const handleRecordSaved = useCallback((recordId, updatedRecord) => {
    setRecords((prev) => prev.map((r) => (r.id === recordId ? updatedRecord : r)));
  }, []);

  // Derive full sorted month list: base + keys present in data + user-added extras
  const allMonths = React.useMemo(() => {
    const set = new Set(MONTHLY_KEYS);
    records.forEach((rec) => {
      if (rec.monthly_data) {
        try { Object.keys(JSON.parse(rec.monthly_data)).forEach((k) => set.add(k)); } catch {}
      }
    });
    extraMonths.forEach((k) => set.add(k));
    return Array.from(set).sort();
  }, [records, extraMonths]);

  const handleAddMonth = (key) => {
    const updated = [...extraMonths, key];
    setExtraMonths(updated);
    localStorage.setItem(LS_KEY, JSON.stringify(updated));
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) setSelectedFile(file);
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) setSelectedFile(file);
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    setUploadResult(null);
    try {
      const res = await inputApi.uploadExcel(selectedFile, userId, null);
      setUploadResult({ success: true, message: res.data.message, rowsImported: res.data.rows_imported });
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err) {
      const detail = err.response?.data?.detail || 'Upload failed. Check the file and try again.';
      setUploadResult({ success: false, message: detail });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="input-data">
      <div className="input-tabs">
        <button
          className={`input-tab ${activeTab === 'upload' ? 'active' : ''}`}
          onClick={() => setActiveTab('upload')}
        >
          <Upload size={15} />
          Upload
        </button>
        <button
          className={`input-tab ${activeTab === 'master' ? 'active' : ''}`}
          onClick={() => setActiveTab('master')}
        >
          <Database size={15} />
          Master Data
        </button>

      </div>

      {activeTab === 'upload' && (
        <div className="upload-panel">
          <h2 className="panel-title">Upload Input Excel</h2>
          <p className="panel-subtitle">
            Upload the Z-Stage input Excel file (.xlsx). The data will replace existing records for the selected layout.
          </p>

          <div
            className={`drop-zone ${dragging ? 'drag-over' : ''} ${selectedFile ? 'has-file' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xls"
              className="file-input-hidden"
              onChange={handleFileChange}
            />
            <Upload size={36} strokeWidth={1.5} className="drop-icon" />
            {selectedFile ? (
              <>
                <p className="drop-filename">{selectedFile.name}</p>
                <p className="drop-hint">Click to choose a different file</p>
              </>
            ) : (
              <>
                <p className="drop-label">Drag & drop your Excel file here</p>
                <p className="drop-hint">or click to browse — .xlsx / .xls only</p>
              </>
            )}
          </div>

          <button
            className="upload-btn"
            disabled={!selectedFile || uploading}
            onClick={handleUpload}
          >
            {uploading ? <><Loader size={15} className="spin" /> Uploading…</> : 'Upload File'}
          </button>

          {uploadResult && (
            <div className={`upload-result ${uploadResult.success ? 'result-success' : 'result-error'}`}>
              {uploadResult.success
                ? <CheckCircle size={18} />
                : <AlertCircle size={18} />}
              <div>
                <strong>{uploadResult.success ? 'Success' : 'Error'}</strong>
                <p>{uploadResult.message}</p>
                {uploadResult.success && (
                  <p>{uploadResult.rowsImported} rows imported.{' '}
                    <button className="link-btn" onClick={() => setActiveTab('master')}>View Master Data →</button>
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'master' && (
        <div className="master-panel">
          <div className="master-header">
            <h2 className="panel-title">Master Data</h2>
            <div className="master-actions">
              <span className="record-count">{records.length} record{records.length !== 1 ? 's' : ''}</span>
              <button className="add-month-btn" onClick={() => setShowAddMonth(true)}>
                <Plus size={13} /> Add New Month
              </button>
              <button className="refresh-btn" onClick={loadRecords} disabled={loadingRecords}>
                {loadingRecords ? <Loader size={13} className="spin" /> : '↻'} Refresh
              </button>
            </div>
          </div>

          {showAddMonth && (
            <AddMonthModal
              existingMonths={allMonths}
              onAdd={handleAddMonth}
              onClose={() => setShowAddMonth(false)}
            />
          )}

          {loadingRecords && (
            <div className="master-loading">
              <Loader size={28} className="spin" />
              <p>Loading records…</p>
            </div>
          )}

          {loadError && !loadingRecords && (
            <div className="master-error">
              <AlertCircle size={20} />
              <p>{loadError}</p>
            </div>
          )}

          {!loadingRecords && !loadError && records.length === 0 && (
            <div className="master-empty">
              <Database size={40} strokeWidth={1} />
              <p>No records yet. Upload an Excel file first.</p>
              <button className="link-btn" onClick={() => setActiveTab('upload')}>Go to Upload →</button>
            </div>
          )}

          {!loadingRecords && records.length > 0 && (
            <div className="table-wrapper">
              <table className="master-table">
                <thead>
                  <tr>
                    {FIXED_COLUMNS.map((col) => (
                      <th key={col.key} style={{ minWidth: col.width }}>{col.label}</th>
                    ))}
                    {allMonths.map((key) => (
                      <th key={key} className="month-header">{formatMonthLabel(key)}</th>
                    ))}
                    {TRAILING_COLUMNS.map((col) => (
                      <th key={col.key} style={{ minWidth: col.width }}>{col.label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {records.map((rec) => (
                    <tr key={rec.id}>
                      {FIXED_COLUMNS.map((col) => (
                        col.key === 'ryg' || col.key === 'status_3m' ? (
                          <EditableCell
                            key={col.key}
                            recordId={rec.id}
                            fieldKey={col.key}
                            value={rec[col.key]}
                            type={col.type}
                            onSaved={handleRecordSaved}
                          />
                        ) : (
                          <EditableCell
                            key={col.key}
                            recordId={rec.id}
                            fieldKey={col.key}
                            value={rec[col.key]}
                            type={col.type}
                            onSaved={handleRecordSaved}
                          />
                        )
                      ))}
                      {allMonths.map((key) => (
                        <MonthlyCell
                          key={key}
                          recordId={rec.id}
                          monthKey={key}
                          monthlyData={rec.monthly_data}
                          onSaved={handleRecordSaved}
                        />
                      ))}
                      {TRAILING_COLUMNS.map((col) => (
                        <EditableCell
                          key={col.key}
                          recordId={rec.id}
                          fieldKey={col.key}
                          value={rec[col.key]}
                          type={col.type}
                          onSaved={handleRecordSaved}
                        />
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
