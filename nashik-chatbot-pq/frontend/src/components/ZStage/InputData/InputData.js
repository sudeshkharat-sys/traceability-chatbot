import React, { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Upload, Database, CheckCircle, AlertCircle, Loader, Plus, X, ClipboardList, CalendarCheck, FileWarning } from 'lucide-react';
import { inputApi, layeredAuditApi, layoutApi } from '../../../services/api/layoutApi';
import './InputData.css';

// ── Strict allowed values for constrained master columns ─────────────────────
const STRICT_VALUES = {
  type:        ['WH', 'USV'],
  ryg:         ['R', 'Y', 'G'],
  attri:       ['M&M Design', 'M&M process', 'Supplier Design', 'Supplier Process', 'Under Analysis'],
  z_e:         ['Z', 'E'],
  attribution: ['M', 'P', 'D', 'U'],
  status_3m:   ['R', 'G'],
};

// Helper: get last N months as 'YYYY-MM' keys
function getLastNMonths(n) {
  const now = new Date();
  const months = [];
  for (let i = 1; i <= n; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    months.unshift(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`);
  }
  return months;
}

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

// Long-text fields that always use a <textarea> when editing
const LONG_TEXT_FIELDS = new Set(['concern', 'root_cause', 'action_plan', 'comm', 'ncs']);

// saveFn defaults to the master-data API; pass a different fn for audit tables
function EditableCell({ recordId, fieldKey, value, type, onSaved, saveFn }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value ?? '');
  const [saving, setSaving] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => { setDraft(value ?? ''); }, [value]);
  useEffect(() => { if (editing && inputRef.current) inputRef.current.focus(); }, [editing]);

  const commit = useCallback(async () => {
    setEditing(false);
    const trimmed = draft.trim();
    const original = String(value ?? '');
    if (trimmed === original) return;

    setSaving(true);
    try {
      let fieldValue;
      if (type === 'number') {
        fieldValue = trimmed === '' ? null : Number(trimmed);
      } else {
        fieldValue = trimmed || null;
      }
      const payload = { [fieldKey]: fieldValue };
      const fn = saveFn || inputApi.updateRecord;
      const res = await fn(recordId, payload);
      onSaved(recordId, res.data);
    } catch (err) {
      console.error('Save failed', err);
      setDraft(value ?? '');
    } finally {
      setSaving(false);
    }
  }, [draft, value, fieldKey, type, recordId, onSaved, saveFn]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') commit();
    if (e.key === 'Escape') { setDraft(value ?? ''); setEditing(false); }
  };

  if (saving) return <td className="cell-saving"><Loader size={12} className="spin" /></td>;

  if (editing) {
    const isLong = LONG_TEXT_FIELDS.has(fieldKey) || type === 'longtext';
    return (
      <td className="cell-editing">
        {isLong ? (
          <textarea
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => { if (e.key === 'Escape') { setDraft(value ?? ''); setEditing(false); } }}
            rows={3}
            className="cell-textarea"
          />
        ) : type === 'date' ? (
          <input
            ref={inputRef}
            type="date"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commit}
            onKeyDown={handleKeyDown}
            className="cell-input"
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

// ── Layered Audit column definitions ─────────────────────────────────────────

const LAYERED_AUDIT_COLUMNS = [
  { key: 'model',          label: 'Model',          width: 120, type: 'text'     },
  { key: 'sr_no',          label: 'Sr.No',          width: 200, type: 'text'     },
  { key: 'date_col',       label: 'Date',           width: 110, type: 'text'     },
  { key: 'station_id',     label: 'Station ID',     width: 110, type: 'text'     },
  { key: 'workstation',    label: 'Workstation',    width: 180, type: 'text'     },
  { key: 'auditor',        label: 'Auditor',        width: 200, type: 'text'     },
  { key: 'ncs',            label: "NC's",           width: 280, type: 'longtext' },
  { key: 'action_plan',    label: 'Action Plan',    width: 280, type: 'longtext' },
  { key: 'four_m',         label: '4M',             width: 100, type: 'text'     },
  { key: 'responsibility', label: 'Responsibility', width: 160, type: 'text'     },
  { key: 'target_date',    label: 'Target Date',    width: 110, type: 'text'     },
  { key: 'status',         label: 'Status',         width: 90,  type: 'text'     },
];

const LAYERED_ADHERENCE_COLUMNS = [
  { key: 'stage_no',   label: 'Stage No',   width: 110, type: 'text' },
  { key: 'stage_name', label: 'Stage Name', width: 220, type: 'text' },
  { key: 'auditor',    label: 'Auditor',    width: 200, type: 'text' },
  { key: 'audit_date', label: 'Audit Date', width: 120, type: 'date' },
];

// ── Column filter dropdown ─────────────────────────────────────────────────────
// selectedValues: null = no filter (all shown) | string[] = only these values shown
function ColumnFilterDropdown({ colKey, allValues, selectedValues, onChange }) {
  const [open, setOpen]       = useState(false);
  const [dropPos, setDropPos] = useState({ top: 0, left: 0 });
  const btnRef  = useRef(null);
  const dropRef = useRef(null);

  // Close when clicking outside
  useEffect(() => {
    if (!open) return;
    const h = (e) => {
      if (!btnRef.current?.contains(e.target) && !dropRef.current?.contains(e.target))
        setOpen(false);
    };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [open]);

  const handleToggle = () => {
    if (!open && btnRef.current) {
      const r = btnRef.current.getBoundingClientRect();
      setDropPos({ top: r.bottom + 2, left: r.left });
    }
    setOpen((o) => !o);
  };

  const isFiltered       = selectedValues !== null;
  const effectiveSelected = selectedValues ?? allValues;
  const noneChecked      = isFiltered && selectedValues.length === 0;

  const toggle = (val) => {
    const current = selectedValues !== null ? [...selectedValues] : [...allValues];
    const next = current.includes(val)
      ? current.filter((v) => v !== val)
      : [...current, val];
    // Back to "no filter" when everything is re-selected
    onChange(colKey, next.length === allValues.length ? null : next);
  };

  const btnLabel = noneChecked
    ? '0'
    : isFiltered
      ? `${effectiveSelected.length}/${allValues.length}`
      : '▾';

  return (
    <>
      <button
        ref={btnRef}
        className={`col-filter-btn${isFiltered ? ' col-filter-btn--active' : ''}`}
        onClick={handleToggle}
        title="Filter column values"
      >
        {btnLabel}
      </button>

      {open && createPortal(
        <div
          ref={dropRef}
          className="col-filter-dropdown"
          style={{ position: 'fixed', top: dropPos.top, left: dropPos.left, zIndex: 9999 }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="col-filter-actions">
            <button className="col-filter-action-btn" onClick={() => onChange(colKey, null)}>
              Select All
            </button>
            <button className="col-filter-action-btn col-filter-action-btn--deselect"
                    onClick={() => onChange(colKey, [])}>
              Deselect All
            </button>
          </div>
          <div className="col-filter-list">
            {allValues.length === 0 && <div className="col-filter-empty">No values</div>}
            {allValues.map((val, i) => (
              <label key={i} className="col-filter-item">
                <input
                  type="checkbox"
                  checked={effectiveSelected.includes(val)}
                  onChange={() => toggle(val)}
                />
                <span className="col-filter-val" title={val}>
                  {val !== '' ? val : <em className="col-filter-blank">(blank)</em>}
                </span>
              </label>
            ))}
          </div>
        </div>,
        document.body
      )}
    </>
  );
}

// ── Editable table with per-column dropdown filters ───────────────────────────
// saveFn(id, payload) → Promise<{data: updatedRecord}>
// onSaved(recordId, updatedRecord) — called on successful save
function AuditTable({ columns, records, saveFn, onSaved }) {
  // filters: { [colKey]: null | string[] }  null = no filter (all shown)
  const [filters, setFilters] = useState({});

  // Unique sorted values per column, derived from all records
  const uniqueValues = React.useMemo(() => {
    const map = {};
    columns.forEach((col) => {
      map[col.key] = [
        ...new Set(records.map((r) => String(r[col.key] ?? '')))
      ].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
    });
    return map;
  }, [records, columns]);

  const handleFilterChange = useCallback((key, val) => {
    setFilters((prev) => ({ ...prev, [key]: val }));
  }, []);

  const filteredRecords = React.useMemo(() =>
    records.filter((rec) =>
      columns.every((col) => {
        const f = filters[col.key];
        if (f == null) return true;
        return f.includes(String(rec[col.key] ?? ''));
      })
    ),
    [records, filters, columns]
  );

  if (records.length === 0) return null;

  return (
    <div className="table-wrapper">
      <table className="master-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} style={{ minWidth: col.width }}>
                <div className="col-header-wrap">
                  <span className="col-header-label">{col.label}</span>
                  <ColumnFilterDropdown
                    colKey={col.key}
                    allValues={uniqueValues[col.key] || []}
                    selectedValues={filters[col.key] ?? null}
                    onChange={handleFilterChange}
                  />
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filteredRecords.map((rec) => (
            <tr key={rec.id}>
              {columns.map((col) => (
                <EditableCell
                  key={col.key}
                  recordId={rec.id}
                  fieldKey={col.key}
                  value={rec[col.key]}
                  type={col.type || 'text'}
                  onSaved={onSaved}
                  saveFn={saveFn}
                />
              ))}
            </tr>
          ))}
          {filteredRecords.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="filter-no-results">
                No records match the current filter.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

// ── Reusable audit upload + view panel ────────────────────────────────────────
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

// ── Add Record Modal for InputData ──────────────────────────────────────────
function AddRecordModal({ type, onClose, onSaved, userId, layoutId, layoutStageIds = [] }) {
  const last3Months = getLastNMonths(3);

  const defaultMaster = () => {
    const m = {};
    last3Months.forEach((k) => { m[k] = ''; });
    return {
      sr_no: '', concern_id: '', concern: '', type: '', root_cause: '', action_plan: '',
      target_date: '', closure_date: '', ryg: '', attri: '', comm: '', line: '',
      stage_no: '', z_e: '', attribution: '', part: '', phenomena: '',
      field_defect_after_cutoff: '', status_3m: '', monthly: m,
    };
  };
  const defaultAudit = () => ({
    model: '', sr_no: '', date_col: '', station_id: '',
    workstation: '', auditor: '', ncs: '', action_plan: '',
    four_m: '', responsibility: '', target_date: '', status: '',
  });
  const defaultAdherence = () => ({
    stage_no: '', stage_name: '', auditor: '', audit_date: '',
  });

  const [form, setForm] = useState(
    type === 'master' ? defaultMaster() :
    type === 'layered-audit' ? defaultAudit() :
    defaultAdherence()
  );
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState('');

  const set = (key, val) => setForm((p) => ({ ...p, [key]: val }));
  const setMonthly = (key, val) => setForm((p) => ({ ...p, monthly: { ...p.monthly, [key]: val } }));

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      let res;
      if (type === 'master') {
        const monthlyObj = {};
        Object.entries(form.monthly).forEach(([k, v]) => {
          const n = parseInt(v, 10);
          if (!isNaN(n)) monthlyObj[k] = n;
        });
        const total = Object.values(monthlyObj).reduce((s, v) => s + v, 0);
        const payload = {
          sr_no: form.sr_no ? parseInt(form.sr_no, 10) : null,
          concern_id: form.concern_id || null, concern: form.concern || null,
          type: form.type || null, root_cause: form.root_cause || null,
          action_plan: form.action_plan || null, target_date: form.target_date || null,
          closure_date: form.closure_date || null, ryg: form.ryg || null,
          attri: form.attri || null, comm: form.comm || null, line: form.line || null,
          stage_no: form.stage_no || null, z_e: form.z_e || null,
          attribution: form.attribution || null, part: form.part || null,
          phenomena: form.phenomena || null,
          field_defect_after_cutoff: form.field_defect_after_cutoff ? parseInt(form.field_defect_after_cutoff, 10) : null,
          status_3m: form.status_3m || null,
          monthly_data: Object.keys(monthlyObj).length ? JSON.stringify(monthlyObj) : null,
          total_incidences: total || null,
        };
        res = await inputApi.createRecord(payload, userId, layoutId);
      } else if (type === 'layered-audit') {
        const payload = {
          model: form.model || null, sr_no: form.sr_no || null,
          date_col: form.date_col || null, station_id: form.station_id || null,
          workstation: form.workstation || null, auditor: form.auditor || null,
          ncs: form.ncs || null, action_plan: form.action_plan || null,
          four_m: form.four_m || null, responsibility: form.responsibility || null,
          target_date: form.target_date || null, status: form.status || null,
        };
        res = await layeredAuditApi.createAuditRecord(payload, userId, layoutId);
      } else {
        const payload = {
          stage_no: form.stage_no || null, stage_name: form.stage_name || null,
          auditor: form.auditor || null, audit_date: form.audit_date || null,
        };
        res = await layeredAuditApi.createAdherenceRecord(payload, userId, layoutId);
      }
      onSaved(res.data);
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save record.');
    } finally {
      setSaving(false);
    }
  };

  const sel = (key, opts) => (
    <select className="modal-select" value={form[key] || ''} onChange={(e) => set(key, e.target.value)}>
      <option value="">— select —</option>
      {opts.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  );
  const inp = (key, t = 'text') => (
    <input className="modal-input" type={t} value={form[key] || ''} onChange={(e) => set(key, e.target.value)} />
  );
  const ta = (key) => (
    <textarea className="modal-textarea" rows={2} value={form[key] || ''} onChange={(e) => set(key, e.target.value)} />
  );

  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="add-record-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">Add Record — {
            type === 'master' ? 'Master Data' :
            type === 'layered-audit' ? 'Layered Audit' : 'Audit Adherence'
          }</span>
          <button className="modal-close" onClick={onClose}><X size={16} /></button>
        </div>
        <div className="modal-body modal-body--form">
          {type === 'master' && (
            <div className="modal-form-grid">
              <label>Sr. No{inp('sr_no', 'number')}</label>
              <label>Concern ID{inp('concern_id')}</label>
              <label className="modal-form-full">Concern{ta('concern')}</label>
              <label>Type {sel('type', STRICT_VALUES.type)}</label>
              <label>RYG {sel('ryg', STRICT_VALUES.ryg)}</label>
              <label>Z/E {sel('z_e', STRICT_VALUES.z_e)}</label>
              <label>Attribution {sel('attribution', STRICT_VALUES.attribution)}</label>
              <label>Attri. {sel('attri', STRICT_VALUES.attri)}</label>
              <label>Status (3M) {sel('status_3m', STRICT_VALUES.status_3m)}</label>
              <label>Stage No
                {layoutStageIds.length > 0
                  ? sel('stage_no', layoutStageIds)
                  : inp('stage_no')}
              </label>
              <label>Line{inp('line')}</label>
              <label>Part{inp('part')}</label>
              <label>Phenomena{inp('phenomena')}</label>
              <label>Target Date{inp('target_date')}</label>
              <label>Closure Date{inp('closure_date')}</label>
              <label className="modal-form-full">Root Cause{ta('root_cause')}</label>
              <label className="modal-form-full">Action Plan{ta('action_plan')}</label>
              <label className="modal-form-full">Comm{ta('comm')}</label>
              <label>Field Defect After Cut-off{inp('field_defect_after_cutoff', 'number')}</label>
              <div className="modal-form-full">
                <div className="modal-form-section-title">Monthly Incidences (last 3 months)</div>
                <div className="modal-form-months">
                  {last3Months.map((k) => (
                    <label key={k}>{formatMonthLabel(k)}
                      <input
                        className="modal-input modal-input--month"
                        type="number" min="0"
                        value={form.monthly[k] || ''}
                        onChange={(e) => setMonthly(k, e.target.value)}
                      />
                    </label>
                  ))}
                </div>
                <p className="modal-form-note">
                  ℹ️ To add records for more than 3 months, use the Excel upload. Same format as download.
                </p>
              </div>
            </div>
          )}
          {type === 'layered-audit' && (
            <div className="modal-form-grid">
              <label>Model{inp('model')}</label>
              <label>Sr. No{inp('sr_no')}</label>
              <label>Date{inp('date_col')}</label>
              <label>Station ID{inp('station_id')}</label>
              <label>Workstation{inp('workstation')}</label>
              <label>Auditor{inp('auditor')}</label>
              <label className="modal-form-full">NC's{ta('ncs')}</label>
              <label className="modal-form-full">Action Plan{ta('action_plan')}</label>
              <label>4M{inp('four_m')}</label>
              <label>Responsibility{inp('responsibility')}</label>
              <label>Target Date{inp('target_date')}</label>
              <label>Status{inp('status')}</label>
            </div>
          )}
          {type === 'audit-adherence' && (
            <div className="modal-form-grid">
              <label>Stage No{inp('stage_no')}</label>
              <label>Stage Name{inp('stage_name')}</label>
              <label>Auditor{inp('auditor')}</label>
              <label>Audit Date{inp('audit_date')}</label>
            </div>
          )}
          {error && (
            <div className="modal-error-bar">
              <AlertCircle size={14} /> {error}
            </div>
          )}
        </div>
        <div className="modal-footer">
          <button className="modal-cancel" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="modal-confirm" onClick={handleSave} disabled={saving}>
            {saving ? <><Loader size={13} className="spin" /> Saving…</> : 'Save Record'}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}

// Upload data-type options
const UPLOAD_TYPES = [
  {
    value: 'master',
    label: 'Master Data',
    desc: 'Z-Stage input Excel — Sr.No, Concern ID, Stage No, monthly incidences…',
    viewTab: 'master',
  },
  {
    value: 'layered-audit',
    label: 'Layered Audit',
    desc: 'Layered Audit Excel — Model, Date, Station ID, Workstation, Auditor, NC\'s…',
    viewTab: 'layered-audit',
  },
  {
    value: 'audit-adherence',
    label: 'Audit Adherence',
    desc: 'Audit Adherence Excel — Stage No, Stage Name, Auditor, Audit Date.',
    viewTab: 'audit-adherence',
  },
];

export default function InputData({ userId, layouts = [] }) {
  const [activeTab, setActiveTab] = useState('upload');
  // upload tab state
  const [uploadType, setUploadType] = useState('master');
  const [dragging, setDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const fileInputRef = useRef(null);

  // shared layout selector
  const [selectedLayoutId, setSelectedLayoutId] = useState(null);

  // Master Data state
  const [records, setRecords] = useState([]);
  const [loadingRecords, setLoadingRecords] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [extraMonths, setExtraMonths] = useState(() => {
    try { return JSON.parse(localStorage.getItem(LS_KEY)) || []; } catch { return []; }
  });
  const [showAddMonth, setShowAddMonth] = useState(false);

  // Layered Audit state
  const [auditRecords, setAuditRecords] = useState([]);
  const [loadingAudit, setLoadingAudit] = useState(false);
  const [auditError, setAuditError] = useState(null);

  // Audit Adherence state
  const [adherenceRecords, setAdherenceRecords] = useState([]);
  const [loadingAdherence, setLoadingAdherence] = useState(false);
  const [adherenceError, setAdherenceError] = useState(null);

  // Master Data column filters — { [colKey]: null | string[] }
  const [masterFilters, setMasterFilters] = useState({});
  const handleMasterFilterChange = useCallback((key, val) => {
    setMasterFilters((prev) => ({ ...prev, [key]: val }));
  }, []);

  // Add Record modal state
  const [showAddRecord, setShowAddRecord] = useState(null); // null | 'master' | 'layered-audit' | 'audit-adherence'

  // Stage IDs from the selected layout's station boxes (for Stage No filter)
  const [layoutStageIds, setLayoutStageIds] = useState([]);
  useEffect(() => {
    if (!selectedLayoutId) return;
    layoutApi.getLayout(selectedLayoutId)
      .then((res) => {
        const boxes = res.data?.station_boxes || [];
        const ids = [];
        boxes.forEach((b) => {
          const sids = b.station_ids
            ? (typeof b.station_ids === 'string' ? b.station_ids.split(',') : b.station_ids)
            : [];
          sids.forEach((s) => { if (s && !ids.includes(s)) ids.push(s); });
        });
        setLayoutStageIds(ids.sort());
      })
      .catch(() => setLayoutStageIds([]));
  }, [selectedLayoutId]);

  // Auto-select first layout
  useEffect(() => {
    if (layouts.length > 0 && selectedLayoutId === null) {
      setSelectedLayoutId(layouts[0].id);
    }
  }, [layouts, selectedLayoutId]);

  // ── Master Data load ────────────────────────────────────────────────────────
  const loadRecords = useCallback(async () => {
    setLoadingRecords(true);
    setLoadError(null);
    try {
      const res = await inputApi.getRecords(userId, selectedLayoutId);
      setRecords(Array.isArray(res.data) ? res.data : []);
    } catch {
      setLoadError('Failed to load records. Is the backend running?');
    } finally {
      setLoadingRecords(false);
    }
  }, [userId, selectedLayoutId]);

  useEffect(() => {
    if (activeTab === 'master') loadRecords();
  }, [activeTab, loadRecords]);

  // ── Layered Audit load ──────────────────────────────────────────────────────
  const loadAuditRecords = useCallback(async () => {
    setLoadingAudit(true);
    setAuditError(null);
    try {
      const res = await layeredAuditApi.getAuditRecords(userId, selectedLayoutId);
      setAuditRecords(Array.isArray(res.data) ? res.data : []);
    } catch {
      setAuditError('Failed to load records. Is the backend running?');
    } finally {
      setLoadingAudit(false);
    }
  }, [userId, selectedLayoutId]);

  useEffect(() => {
    if (activeTab === 'layered-audit') loadAuditRecords();
  }, [activeTab, loadAuditRecords]);

  // ── Audit Adherence load ────────────────────────────────────────────────────
  const loadAdherenceRecords = useCallback(async () => {
    setLoadingAdherence(true);
    setAdherenceError(null);
    try {
      const res = await layeredAuditApi.getAdherenceRecords(userId, selectedLayoutId);
      setAdherenceRecords(Array.isArray(res.data) ? res.data : []);
    } catch {
      setAdherenceError('Failed to load records. Is the backend running?');
    } finally {
      setLoadingAdherence(false);
    }
  }, [userId, selectedLayoutId]);

  useEffect(() => {
    if (activeTab === 'audit-adherence') loadAdherenceRecords();
  }, [activeTab, loadAdherenceRecords]);

  const handleRecordSaved = useCallback((recordId, updatedRecord) => {
    setRecords((prev) => prev.map((r) => (r.id === recordId ? updatedRecord : r)));
  }, []);

  const handleAuditRecordSaved = useCallback((recordId, updatedRecord) => {
    setAuditRecords((prev) => prev.map((r) => (r.id === recordId ? updatedRecord : r)));
  }, []);

  const handleAdherenceRecordSaved = useCallback((recordId, updatedRecord) => {
    setAdherenceRecords((prev) => prev.map((r) => (r.id === recordId ? updatedRecord : r)));
  }, []);

  const handleRecordAdded = useCallback((tabType, newRec) => {
    if (tabType === 'master') setRecords((p) => [...p, newRec]);
    else if (tabType === 'layered-audit') setAuditRecords((p) => [...p, newRec]);
    else if (tabType === 'audit-adherence') setAdherenceRecords((p) => [...p, newRec]);
  }, []);

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

  const masterUniqueValues = React.useMemo(() => {
    const allCols = [...FIXED_COLUMNS, ...TRAILING_COLUMNS];
    const map = {};
    allCols.forEach((col) => {
      if (STRICT_VALUES[col.key]) {
        // Use only allowed values for constrained columns — always show fixed options
        map[col.key] = STRICT_VALUES[col.key];
      } else if (col.key === 'stage_no' && layoutStageIds.length > 0) {
        // Stage No: only show stage IDs that exist in the current layout's station boxes
        map[col.key] = layoutStageIds;
      } else {
        map[col.key] = [
          ...new Set(records.map((r) => String(r[col.key] ?? '')))
        ].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
      }
    });
    return map;
  }, [records, layoutStageIds]);

  const filteredMasterRecords = React.useMemo(() => {
    const allCols = [...FIXED_COLUMNS, ...TRAILING_COLUMNS];
    return records.filter((rec) =>
      allCols.every((col) => {
        const f = masterFilters[col.key]; // null | string[]
        if (f == null) return true;
        return f.includes(String(rec[col.key] ?? ''));
      })
    );
  }, [records, masterFilters]);

  const handleAddMonth = (key) => {
    const updated = [...extraMonths, key];
    setExtraMonths(updated);
    localStorage.setItem(LS_KEY, JSON.stringify(updated));
  };

  // ── Upload handler (all types) ──────────────────────────────────────────────
  const handleUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    setUploadResult(null);
    try {
      let res;
      if (uploadType === 'master') {
        res = await inputApi.uploadExcel(selectedFile, userId, selectedLayoutId);
      } else if (uploadType === 'layered-audit') {
        res = await layeredAuditApi.uploadAudit(selectedFile, userId, selectedLayoutId);
      } else {
        res = await layeredAuditApi.uploadAdherence(selectedFile, userId, selectedLayoutId);
      }
      const viewTab = UPLOAD_TYPES.find((t) => t.value === uploadType)?.viewTab || 'master';
      setUploadResult({
        success: true,
        message: res.data.message,
        rowsImported: res.data.rows_imported,
        skippedRows: res.data.skipped_rows || null,
        viewTab,
      });
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err) {
      const detail = err.response?.data?.detail || 'Upload failed. Check the file and try again.';
      setUploadResult({ success: false, message: detail });
    } finally {
      setUploading(false);
    }
  };

  // Layout dropdown shared across all tabs
  const layoutDropdown = layouts.length > 0 && (
    <div className="tabs-layout-select">
      <label className="layout-select-label">Layout:</label>
      <select
        className="layout-select-dropdown"
        value={selectedLayoutId ?? ''}
        onChange={(e) => setSelectedLayoutId(e.target.value ? Number(e.target.value) : null)}
      >
        {layouts.map((l) => (
          <option key={l.id} value={l.id}>{l.name}</option>
        ))}
      </select>
    </div>
  );

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
        <button
          className={`input-tab ${activeTab === 'layered-audit' ? 'active' : ''}`}
          onClick={() => setActiveTab('layered-audit')}
        >
          <ClipboardList size={15} />
          Layered Audit
        </button>
        <button
          className={`input-tab ${activeTab === 'audit-adherence' ? 'active' : ''}`}
          onClick={() => setActiveTab('audit-adherence')}
        >
          <CalendarCheck size={15} />
          Audit Adherence
        </button>
        {layoutDropdown}
      </div>

      {/* ── Upload tab ──────────────────────────────────────────────────────── */}
      {activeTab === 'upload' && (
        <div className="upload-panel">
          <h2 className="panel-title">Upload Excel</h2>

          {/* Data type selector */}
          <div className="upload-type-row">
            <label className="upload-type-label">Data Type:</label>
            <div className="upload-type-options">
              {UPLOAD_TYPES.map((t) => (
                <label key={t.value} className={`upload-type-option ${uploadType === t.value ? 'selected' : ''}`}>
                  <input
                    type="radio"
                    name="uploadType"
                    value={t.value}
                    checked={uploadType === t.value}
                    onChange={() => { setUploadType(t.value); setSelectedFile(null); setUploadResult(null); }}
                  />
                  <span className="upload-type-name">{t.label}</span>
                  <span className="upload-type-desc">{t.desc}</span>
                </label>
              ))}
            </div>
          </div>

          <div
            className={`drop-zone ${dragging ? 'drag-over' : ''} ${selectedFile ? 'has-file' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) setSelectedFile(f); }}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xls"
              className="file-input-hidden"
              onChange={(e) => { const f = e.target.files[0]; if (f) setSelectedFile(f); }}
            />
            <Upload size={36} strokeWidth={1.5} className="drop-icon" />
            {selectedFile ? (
              <><p className="drop-filename">{selectedFile.name}</p><p className="drop-hint">Click to choose a different file</p></>
            ) : (
              <><p className="drop-label">Drag & drop your Excel file here</p><p className="drop-hint">or click to browse — .xlsx / .xls only</p></>
            )}
          </div>

          <button className="upload-btn" disabled={!selectedFile || uploading} onClick={handleUpload}>
            {uploading ? <><Loader size={15} className="spin" /> Uploading…</> : 'Upload File'}
          </button>

          {uploadResult && (
            <div className={`upload-result ${uploadResult.success ? 'result-success' : 'result-error'}`}>
              {uploadResult.success ? <CheckCircle size={18} /> : <AlertCircle size={18} />}
              <div>
                <strong>{uploadResult.success ? 'Success' : 'Error'}</strong>
                <p>{uploadResult.message}</p>
                {uploadResult.success && (
                  <p>{uploadResult.rowsImported} rows imported.{' '}
                    <button className="link-btn" onClick={() => setActiveTab(uploadResult.viewTab)}>View Data →</button>
                  </p>
                )}
                {uploadResult.success && uploadResult.skippedRows && uploadResult.skippedRows.length > 0 && (
                  <div className="upload-skipped">
                    <div className="upload-skipped-title">
                      <FileWarning size={14} /> {uploadResult.skippedRows.length} row{uploadResult.skippedRows.length !== 1 ? 's' : ''} skipped (invalid values):
                    </div>
                    <ul className="upload-skipped-list">
                      {uploadResult.skippedRows.map((s) => (
                        <li key={s.row_number}>Row {s.row_number}: {s.reason}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Layered Audit tab ────────────────────────────────────────────────── */}
      {activeTab === 'layered-audit' && (
        <div className="master-panel">
          <div className="master-header">
            <div>
              <h2 className="panel-title">Layered Audit</h2>
              <p className="panel-subtitle">Click any cell to edit · Changes save automatically</p>
            </div>
            <div className="master-actions">
              <span className="record-count">{auditRecords.length} record{auditRecords.length !== 1 ? 's' : ''}</span>
              <button className="add-record-btn" onClick={() => setShowAddRecord('layered-audit')}>
                <Plus size={13} /> Add Record
              </button>
              <button className="refresh-btn" onClick={loadAuditRecords} disabled={loadingAudit}>
                {loadingAudit ? <Loader size={13} className="spin" /> : '↻'} Refresh
              </button>
            </div>
          </div>
          {loadingAudit && <div className="master-loading"><Loader size={28} className="spin" /><p>Loading records…</p></div>}
          {auditError && !loadingAudit && <div className="master-error"><AlertCircle size={20} /><p>{auditError}</p></div>}
          {!loadingAudit && !auditError && auditRecords.length === 0 && (
            <div className="master-empty">
              <Database size={40} strokeWidth={1} />
              <p>No records yet. Upload a Layered Audit Excel file first.</p>
              <button className="link-btn" onClick={() => { setActiveTab('upload'); setUploadType('layered-audit'); }}>Go to Upload →</button>
            </div>
          )}
          {!loadingAudit && auditRecords.length > 0 && (
            <AuditTable
              columns={LAYERED_AUDIT_COLUMNS}
              records={auditRecords}
              saveFn={layeredAuditApi.updateAuditRecord}
              onSaved={handleAuditRecordSaved}
            />
          )}
        </div>
      )}

      {/* ── Audit Adherence tab ──────────────────────────────────────────────── */}
      {activeTab === 'audit-adherence' && (
        <div className="master-panel">
          <div className="master-header">
            <div>
              <h2 className="panel-title">Audit Adherence</h2>
              <p className="panel-subtitle">Click any cell to edit · Audit Date must be a valid date</p>
            </div>
            <div className="master-actions">
              <span className="record-count">{adherenceRecords.length} record{adherenceRecords.length !== 1 ? 's' : ''}</span>
              <button className="add-record-btn" onClick={() => setShowAddRecord('audit-adherence')}>
                <Plus size={13} /> Add Record
              </button>
              <button className="refresh-btn" onClick={loadAdherenceRecords} disabled={loadingAdherence}>
                {loadingAdherence ? <Loader size={13} className="spin" /> : '↻'} Refresh
              </button>
            </div>
          </div>
          {loadingAdherence && <div className="master-loading"><Loader size={28} className="spin" /><p>Loading records…</p></div>}
          {adherenceError && !loadingAdherence && <div className="master-error"><AlertCircle size={20} /><p>{adherenceError}</p></div>}
          {!loadingAdherence && !adherenceError && adherenceRecords.length === 0 && (
            <div className="master-empty">
              <Database size={40} strokeWidth={1} />
              <p>No records yet. Upload an Audit Adherence Excel file first.</p>
              <button className="link-btn" onClick={() => { setActiveTab('upload'); setUploadType('audit-adherence'); }}>Go to Upload →</button>
            </div>
          )}
          {!loadingAdherence && adherenceRecords.length > 0 && (
            <AuditTable
              columns={LAYERED_ADHERENCE_COLUMNS}
              records={adherenceRecords}
              saveFn={layeredAuditApi.updateAdherenceRecord}
              onSaved={handleAdherenceRecordSaved}
            />
          )}
        </div>
      )}

      {/* ── Master Data tab ──────────────────────────────────────────────────── */}
      {activeTab === 'master' && (
        <div className="master-panel">
          <div className="master-header">
            <h2 className="panel-title">Master Data</h2>
            <div className="master-actions">
              <span className="record-count">{records.length} record{records.length !== 1 ? 's' : ''}</span>
              <button className="add-record-btn" onClick={() => setShowAddRecord('master')}>
                <Plus size={13} /> Add Record
              </button>
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
                      <th key={col.key} style={{ minWidth: col.width }}>
                        <div className="col-header-wrap">
                          <span className="col-header-label">{col.label}</span>
                          <ColumnFilterDropdown
                            colKey={col.key}
                            allValues={masterUniqueValues[col.key] || []}
                            selectedValues={masterFilters[col.key] ?? null}
                            onChange={handleMasterFilterChange}
                          />
                        </div>
                      </th>
                    ))}
                    {allMonths.map((key) => (
                      <th key={key} className="month-header">{formatMonthLabel(key)}</th>
                    ))}
                    {TRAILING_COLUMNS.map((col) => (
                      <th key={col.key} style={{ minWidth: col.width }}>
                        <div className="col-header-wrap">
                          <span className="col-header-label">{col.label}</span>
                          <ColumnFilterDropdown
                            colKey={col.key}
                            allValues={masterUniqueValues[col.key] || []}
                            selectedValues={masterFilters[col.key] ?? null}
                            onChange={handleMasterFilterChange}
                          />
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredMasterRecords.map((rec) => (
                    <tr key={rec.id}>
                      {FIXED_COLUMNS.map((col) => (
                        <EditableCell
                          key={col.key}
                          recordId={rec.id}
                          fieldKey={col.key}
                          value={rec[col.key]}
                          type={col.type}
                          onSaved={handleRecordSaved}
                        />
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
                  {filteredMasterRecords.length === 0 && (
                    <tr>
                      <td
                        colSpan={FIXED_COLUMNS.length + allMonths.length + TRAILING_COLUMNS.length}
                        className="filter-no-results"
                      >
                        No records match the current filter.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Add Record modal ─────────────────────────────────────────────────── */}
      {showAddRecord && (
        <AddRecordModal
          type={showAddRecord}
          onClose={() => setShowAddRecord(null)}
          onSaved={(newRec) => { handleRecordAdded(showAddRecord, newRec); setShowAddRecord(null); }}
          userId={userId}
          layoutId={selectedLayoutId}
          layoutStageIds={layoutStageIds}
        />
      )}
    </div>
  );
}
