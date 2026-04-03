import React, { useState, useMemo } from 'react';
import { X } from 'lucide-react';
import './AddBoxModal.css';

function buildAutoIds(prefix, count, reversed) {
  const p = prefix.trim().toUpperCase();
  const ids = Array.from({ length: count }, (_, i) => `${p}-${String(i + 1).padStart(2, '0')}`);
  return reversed ? ids.slice().reverse() : ids;
}

const DEFAULT_FORM = { name: '', prefix: '', stationCount: 5, description: '' };

function AddBoxModal({ onAdd, onClose }) {
  const [form, setForm] = useState(DEFAULT_FORM);
  const [mode, setMode] = useState('auto'); // 'auto' | 'custom'
  const [reversed, setReversed] = useState(false);
  const [customText, setCustomText] = useState('');
  const [errors, setErrors] = useState({});

  const autoIds = useMemo(() => {
    if (!form.prefix.trim() || form.stationCount < 1) return [];
    return buildAutoIds(form.prefix, Number(form.stationCount), reversed);
  }, [form.prefix, form.stationCount, reversed]);

  const handleModeSwitch = (newMode) => {
    if (newMode === 'custom' && mode === 'auto') {
      setCustomText(autoIds.join('\n'));
    }
    setMode(newMode);
    setErrors({});
  };

  const handleFormChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: name === 'stationCount' ? parseInt(value, 10) || '' : value,
    }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: undefined }));
  };

  const parsedCustomIds = useMemo(
    () =>
      customText
        .split(/[\n,]+/)
        .map((s) => s.trim())
        .filter(Boolean),
    [customText],
  );

  const previewIds = mode === 'auto' ? autoIds : parsedCustomIds;

  const validate = () => {
    const errs = {};
    if (!form.name.trim()) errs.name = 'Station / line name is required';
    if (mode === 'auto') {
      if (!form.prefix.trim()) errs.prefix = 'Prefix is required';
      if (!form.stationCount || form.stationCount < 1) errs.stationCount = 'At least 1 station required';
      if (form.stationCount > 60) errs.stationCount = 'Maximum 60 stations';
    } else {
      if (parsedCustomIds.length === 0) errs.customIds = 'Enter at least one station ID';
      if (parsedCustomIds.length > 60) errs.customIds = 'Maximum 60 stations';
    }
    return errs;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length > 0) { setErrors(errs); return; }

    const stationIds = mode === 'auto' ? autoIds : parsedCustomIds;
    onAdd({ name: form.name.trim(), stationIds, description: form.description.trim() });
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">Add Station Box</h2>
          <button className="modal-close-btn" onClick={onClose}><X size={14} /></button>
        </div>

        <form className="modal-form" onSubmit={handleSubmit}>
          {/* Name */}
          <div className="modal-field">
            <label className="modal-label">Station / Line Name</label>
            <input
              className={`modal-input${errors.name ? ' modal-input--error' : ''}`}
              type="text"
              name="name"
              value={form.name}
              onChange={handleFormChange}
              placeholder="e.g. TRIM 1"
              autoFocus
            />
            {errors.name && <span className="modal-error">{errors.name}</span>}
          </div>

          {/* Mode toggle */}
          <div className="modal-mode-toggle">
            <button
              type="button"
              className={`modal-mode-btn${mode === 'auto' ? ' modal-mode-btn--active' : ''}`}
              onClick={() => handleModeSwitch('auto')}
            >
              Auto IDs
            </button>
            <button
              type="button"
              className={`modal-mode-btn${mode === 'custom' ? ' modal-mode-btn--active' : ''}`}
              onClick={() => handleModeSwitch('custom')}
            >
              Custom IDs
            </button>
          </div>

          {/* Auto mode */}
          {mode === 'auto' && (
            <>
              <div className="modal-field">
                <label className="modal-label">Station ID Prefix</label>
                <input
                  className={`modal-input${errors.prefix ? ' modal-input--error' : ''}`}
                  type="text"
                  name="prefix"
                  value={form.prefix}
                  onChange={handleFormChange}
                  placeholder="e.g. T1  →  T1-01, T1-02 …"
                  maxLength={10}
                />
                {errors.prefix && <span className="modal-error">{errors.prefix}</span>}
              </div>

              <div className="modal-field">
                <label className="modal-label">Number of Stations</label>
                <input
                  className={`modal-input${errors.stationCount ? ' modal-input--error' : ''}`}
                  type="number"
                  name="stationCount"
                  value={form.stationCount}
                  onChange={handleFormChange}
                  min={1}
                  max={60}
                />
                {errors.stationCount && <span className="modal-error">{errors.stationCount}</span>}
              </div>

              <div className="modal-field modal-field--inline">
                <label className="modal-label">Reverse Order</label>
                <button
                  type="button"
                  className={`modal-toggle-btn${reversed ? ' modal-toggle-btn--on' : ''}`}
                  onClick={() => setReversed((v) => !v)}
                  title="Generate station IDs from highest to lowest"
                >
                  {reversed ? 'ON' : 'OFF'}
                </button>
                <span className="modal-label-hint">
                  {reversed ? ' — descending (e.g. -05 → -01)' : ' — ascending (e.g. -01 → -05)'}
                </span>
              </div>
            </>
          )}

          {/* Custom mode */}
          {mode === 'custom' && (
            <div className="modal-field">
              <label className="modal-label">
                Station IDs
                <span className="modal-label-hint"> — one per line or comma-separated</span>
              </label>
              <textarea
                className={`modal-textarea${errors.customIds ? ' modal-input--error' : ''}`}
                value={customText}
                onChange={(e) => {
                  setCustomText(e.target.value);
                  if (errors.customIds) setErrors((p) => ({ ...p, customIds: undefined }));
                }}
                placeholder={"T1-01\nT1-02\nT1-03\n…  or  T1-01, T1-02, T1-03"}
                rows={6}
                spellCheck={false}
              />
              {errors.customIds && <span className="modal-error">{errors.customIds}</span>}
            </div>
          )}

          {/* Description — shown below station IDs */}
          <div className="modal-field">
            <label className="modal-label">
              Description
              <span className="modal-label-hint"> — optional, shown below station ID row</span>
            </label>
            <input
              className="modal-input"
              type="text"
              name="description"
              value={form.description}
              onChange={handleFormChange}
              placeholder="e.g. Trim Line A"
              maxLength={60}
            />
          </div>

          {/* ID preview chips */}
          {previewIds.length > 0 && (
            <div className="modal-id-preview">
              <span className="modal-id-preview-label">{previewIds.length} station{previewIds.length !== 1 ? 's' : ''}:</span>
              <div className="modal-id-chips">
                {previewIds.slice(0, 20).map((id) => (
                  <span key={id} className="modal-id-chip">{id}</span>
                ))}
                {previewIds.length > 20 && (
                  <span className="modal-id-chip modal-id-chip--more">+{previewIds.length - 20} more</span>
                )}
              </div>
            </div>
          )}

          <div className="modal-actions">
            <button type="button" className="modal-btn modal-btn--cancel" onClick={onClose}>Cancel</button>
            <button type="submit" className="modal-btn modal-btn--add">Add Box</button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default AddBoxModal;
