import React, { useState, useEffect, useCallback } from 'react';
import { carModelApi, lineModelMappingApi, z3dModelApi } from '../../../services/api/layoutApi';

// Lines matching one of these keywords need a per-car-model mapping (a line can
// build several car models, each shown as a different 3D object). Every other
// line (Chassis, Engine, ...) uses a single object regardless of car model.
const MULTI_MODEL_KEYWORDS = ['final', 'trim', 'ub', 'underbody'];
function normalizeLineName(name) {
  return (name || '').toLowerCase().replace(/[^a-z0-9]/g, '');
}
export function lineNeedsCarModel(lineName) {
  const n = normalizeLineName(lineName);
  return MULTI_MODEL_KEYWORDS.some(k => n.includes(k));
}

const deg2rad = (d) => (Number(d) || 0) * Math.PI / 180;
const rad2deg = (r) => (Number(r) || 0) * 180 / Math.PI;
const EMPTY_XFORM = { px: 0, py: 0, pz: 0, rx: 0, ry: 0, rz: 0, sx: 1, sy: 1, sz: 1 };

const TABS = [
  { key: 'mapping', label: 'Line Mapping' },
  { key: 'carModels', label: 'Car Models' },
];

// The line -> [car model] -> library model MAPPING is per-layout — each
// layout keeps its own choice of which object represents a line, so
// different layouts can be styled differently. The object's own
// position/rotation/scale (its "preset", stored on the library model) IS
// global: whichever layout maps a model onto a line, it renders with the
// same saved transform.
export default function ModelMappingModal({ layoutId, shopList, onClose, onApplied }) {
  const [tab, setTab] = useState('mapping');

  const [carModels, setCarModels] = useState([]);
  const [libraryModels, setLibraryModels] = useState([]);
  const [mappings, setMappings] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const reloadAll = useCallback(() => {
    setLoading(true);
    Promise.all([
      carModelApi.list().then(r => setCarModels(r.data || [])),
      z3dModelApi.listLibrary().then(r => setLibraryModels(r.data || [])),
      layoutId ? lineModelMappingApi.listByLayout(layoutId).then(r => setMappings(r.data || [])) : Promise.resolve(),
    ]).catch(err => setError(err?.response?.data?.detail || err.message))
      .finally(() => setLoading(false));
  }, [layoutId]);

  useEffect(() => { reloadAll(); }, [reloadAll]);

  // ── Mapping tab state ─────────────────────────────────────────────────────
  const [mapLine, setMapLine] = useState('');
  const [mapCarModel, setMapCarModel] = useState('');
  const [selectedModelName, setSelectedModelName] = useState('');
  const [xform, setXform] = useState(EMPTY_XFORM);
  const needsCarModel = mapLine ? lineNeedsCarModel(mapLine) : false;

  // Once a car model is chosen, models whose name mentions it (e.g. picking
  // "Thar" surfaces "Thar_Skid", "XUV_Thar_Roxx", ...) float to the top —
  // saves hunting through the full library for the right variant.
  const sortedLibraryModels = React.useMemo(() => {
    const carModel = carModels.find(c => String(c.id) === String(mapCarModel));
    if (!carModel) return libraryModels;
    const needle = carModel.name.toLowerCase();
    const matches = libraryModels.filter(m => m.name.toLowerCase().includes(needle));
    const rest = libraryModels.filter(m => !m.name.toLowerCase().includes(needle));
    return [...matches, ...rest];
  }, [libraryModels, carModels, mapCarModel]);

  // Loading a model into the picker pre-fills the transform fields from its
  // saved defaults (which double as the reusable "preset" for that model).
  const pickModel = useCallback((name) => {
    setSelectedModelName(name);
    const m = libraryModels.find(lm => lm.name === name);
    if (m) {
      setXform({
        px: m.default_px ?? 0, py: m.default_py ?? 0, pz: m.default_pz ?? 0,
        rx: rad2deg(m.default_rx), ry: rad2deg(m.default_ry), rz: rad2deg(m.default_rz),
        sx: m.default_sx ?? 1, sy: m.default_sy ?? 1, sz: m.default_sz ?? 1,
      });
    } else {
      setXform(EMPTY_XFORM);
    }
  }, [libraryModels]);

  const setXformField = (field, value) => setXform(prev => ({ ...prev, [field]: value }));

  // ── Upload-new-model state ────────────────────────────────────────────────
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadName, setUploadName] = useState('');

  const uploadNewModel = useCallback(() => {
    if (!uploadFile) { setError('Choose a file to upload.'); return; }
    const name = uploadName || uploadFile.name.replace(/\.[^/.]+$/, '');
    setError('');
    setLoading(true);
    z3dModelApi.uploadToLibrary(uploadFile, { name })
      .then(() => {
        setUploadFile(null); setUploadName('');
        reloadAll();
        pickModel(name);
      })
      .catch(err => setError(err?.response?.data?.detail || err.message))
      .finally(() => setLoading(false));
  }, [uploadFile, uploadName, reloadAll, pickModel]);

  const deleteModel = useCallback((name) => {
    if (!window.confirm(`Delete "${name}" from the library? This removes it from every line/layout using it.`)) return;
    setLoading(true);
    z3dModelApi.deleteLibraryModel(name)
      .then(() => {
        if (selectedModelName === name) { setSelectedModelName(''); setXform(EMPTY_XFORM); }
        reloadAll();
        onApplied && onApplied();
      })
      .catch(err => setError(err?.response?.data?.detail || err.message))
      .finally(() => setLoading(false));
  }, [selectedModelName, reloadAll, onApplied]);

  const saveMapping = useCallback(() => {
    if (!mapLine || !selectedModelName) { setError('Choose a line and an object.'); return; }
    if (needsCarModel && !mapCarModel) { setError('Choose a car model for this line.'); return; }
    setError('');
    setLoading(true);
    // Persist the transform onto the model's defaults first — this IS the
    // reusable preset, applied wherever this model gets mapped.
    z3dModelApi.saveDefaults(selectedModelName, {
      px: Number(xform.px), py: Number(xform.py), pz: Number(xform.pz),
      rx: deg2rad(xform.rx), ry: deg2rad(xform.ry), rz: deg2rad(xform.rz),
      sx: Number(xform.sx), sy: Number(xform.sy), sz: Number(xform.sz),
    }).then(() => lineModelMappingApi.create({
      layoutId,
      lineGroupId: mapLine,
      carModelId: needsCarModel ? Number(mapCarModel) : null,
      modelName: selectedModelName,
    })).then(() => {
      reloadAll();
      onApplied && onApplied();
    }).catch(err => setError(err?.response?.data?.detail || err.message))
      .finally(() => setLoading(false));
  }, [layoutId, mapLine, mapCarModel, selectedModelName, needsCarModel, xform, reloadAll, onApplied]);

  const deleteMapping = useCallback((id) => {
    setLoading(true);
    lineModelMappingApi.delete(id)
      .then(() => { reloadAll(); onApplied && onApplied(); })
      .catch(err => setError(err?.response?.data?.detail || err.message))
      .finally(() => setLoading(false));
  }, [reloadAll, onApplied]);

  // ── Car models tab state ──────────────────────────────────────────────────
  const [carModelName, setCarModelName] = useState('');
  const [carModelCode, setCarModelCode] = useState('');

  const saveCarModel = useCallback(() => {
    if (!carModelName) { setError('Car model name is required.'); return; }
    setError('');
    setLoading(true);
    carModelApi.create({ name: carModelName, code: carModelCode || null })
      .then(() => { setCarModelName(''); setCarModelCode(''); reloadAll(); })
      .catch(err => setError(err?.response?.data?.detail || err.message))
      .finally(() => setLoading(false));
  }, [carModelName, carModelCode, reloadAll]);

  const deleteCarModel = useCallback((id) => {
    setLoading(true);
    carModelApi.delete(id).then(reloadAll)
      .catch(err => setError(err?.response?.data?.detail || err.message))
      .finally(() => setLoading(false));
  }, [reloadAll]);

  const carModelLabel = (id) => {
    if (id == null) return 'All / single model';
    const c = carModels.find(c => c.id === id);
    return c ? c.name : `#${id}`;
  };

  return (
    <div className="z3d-modal-overlay" onClick={onClose}>
      <div className="z3d-modal-box" style={{ width: 560, maxWidth: '90vw', maxHeight: '85vh', overflowY: 'auto' }} onClick={e => e.stopPropagation()}>
        <div className="z3d-modal-title">3D Model Mapping</div>

        <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
          {TABS.map(t => (
            <button
              key={t.key}
              type="button"
              className="z3d-modal-cancel"
              style={tab === t.key ? { fontWeight: 700, borderColor: '#3b82f6', color: '#3b82f6' } : {}}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {error && <div style={{ color: '#e53935', marginBottom: 10, fontSize: 13 }}>{error}</div>}

        {tab === 'mapping' && (
          <div>
            <div className="z3d-modal-hint" style={{ marginBottom: 10 }}>
              This mapping is saved only for the layout you're currently viewing. The object's
              own position/rotation/scale (below) is remembered globally, so it looks the same
              wherever it's used.
            </div>

            <label className="z3d-modal-label">Line</label>
            <select className="z3d-modal-select" value={mapLine} onChange={e => { setMapLine(e.target.value); setMapCarModel(''); }}>
              <option value="">— Select line —</option>
              {shopList.map(s => <option key={s} value={s}>{s}</option>)}
            </select>

            {needsCarModel && (
              <>
                <label className="z3d-modal-label">Car Model</label>
                <select className="z3d-modal-select" value={mapCarModel} onChange={e => setMapCarModel(e.target.value)}>
                  <option value="">— Select car model —</option>
                  {carModels.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </>
            )}

            <label className="z3d-modal-label">
              Object{mapCarModel ? ' (matching models shown first)' : ''}
            </label>
            <div style={{ maxHeight: 140, overflowY: 'auto', border: '1px solid #30363d', borderRadius: 6, marginBottom: 8 }}>
              {libraryModels.length === 0 && <div className="z3d-modal-hint" style={{ padding: 8 }}>No models uploaded yet.</div>}
              {sortedLibraryModels.map(m => (
                <div
                  key={m.name}
                  className={`z3d-mapping-row${selectedModelName === m.name ? ' z3d-mapping-row--active' : ''}`}
                  onClick={() => pickModel(m.name)}
                >
                  <span>{m.name}</span>
                  <button type="button" className="z3d-modal-cancel" onClick={(e) => { e.stopPropagation(); deleteModel(m.name); }}>Delete</button>
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 10 }}>
              <input type="file" accept=".glb,.gltf,.obj,.stl" onChange={e => setUploadFile(e.target.files?.[0] || null)} />
              <input
                className="z3d-modal-select" style={{ flex: 1 }} placeholder="Name (optional)"
                value={uploadName} onChange={e => setUploadName(e.target.value)}
              />
              <button type="button" className="z3d-modal-confirm" disabled={loading || !uploadFile} onClick={uploadNewModel}>Upload New</button>
            </div>

            {selectedModelName && (
              <>
                <div className="z3d-modal-label">Preset — Movement / Scale / Rotation for "{selectedModelName}"</div>
                <div className="z3d-modal-hint" style={{ marginBottom: 8 }}>
                  Adjust how this object sits on the station, then Save Preset below. These
                  numbers get remembered as this model's preset globally — wherever "{selectedModelName}"
                  is used, on any line, in any layout, it'll use these same values.
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 8 }}>
                  {['px', 'py', 'pz'].map(f => (
                    <div key={f}>
                      <label className="z3d-modal-label">{f.toUpperCase()} (move)</label>
                      <input type="number" step="0.1" className="z3d-modal-select" value={xform[f]} onChange={e => setXformField(f, e.target.value)} />
                    </div>
                  ))}
                  {['rx', 'ry', 'rz'].map(f => (
                    <div key={f}>
                      <label className="z3d-modal-label">{f.toUpperCase()} (rotate °)</label>
                      <input type="number" step="1" className="z3d-modal-select" value={xform[f]} onChange={e => setXformField(f, e.target.value)} />
                    </div>
                  ))}
                  {['sx', 'sy', 'sz'].map(f => (
                    <div key={f}>
                      <label className="z3d-modal-label">{f.toUpperCase()} (scale)</label>
                      <input type="number" step="0.1" className="z3d-modal-select" value={xform[f]} onChange={e => setXformField(f, e.target.value)} />
                    </div>
                  ))}
                </div>
              </>
            )}

            <div className="z3d-modal-actions">
              <button type="button" className="z3d-modal-confirm" disabled={loading} onClick={saveMapping}>
                Save Preset — Apply to This Line
              </button>
            </div>
            <div className="z3d-modal-hint">
              Saved automatically — reopening this layout will show this object on this line
              with these exact values, no re-setup needed.
            </div>

            <div style={{ marginTop: 16, borderTop: '1px solid #30363d', paddingTop: 10 }}>
              <div className="z3d-modal-label">Current mappings (this layout)</div>
              {mappings.length === 0 && <div className="z3d-modal-hint">No mappings yet.</div>}
              {mappings.map(m => (
                <div key={m.id} className="z3d-mapping-row-static">
                  <span><b>{m.line_group_id}</b> · {carModelLabel(m.car_model_id)} → {m.model_name}</span>
                  <button type="button" className="z3d-modal-cancel" onClick={() => deleteMapping(m.id)}>Remove</button>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === 'carModels' && (
          <div>
            <label className="z3d-modal-label">Car Model Name</label>
            <input className="z3d-modal-select" value={carModelName} onChange={e => setCarModelName(e.target.value)} placeholder="e.g. Model A" />

            <label className="z3d-modal-label">Code (optional)</label>
            <input className="z3d-modal-select" value={carModelCode} onChange={e => setCarModelCode(e.target.value)} placeholder="e.g. MA" />

            <div className="z3d-modal-actions">
              <button type="button" className="z3d-modal-confirm" disabled={loading} onClick={saveCarModel}>Add Car Model</button>
            </div>

            <div style={{ marginTop: 16, borderTop: '1px solid #30363d', paddingTop: 10 }}>
              <div className="z3d-modal-label">Car models</div>
              {carModels.length === 0 && <div className="z3d-modal-hint">No car models yet.</div>}
              {carModels.map(c => (
                <div key={c.id} className="z3d-mapping-row-static">
                  <span>{c.name}{c.code ? ` (${c.code})` : ''}</span>
                  <button type="button" className="z3d-modal-cancel" onClick={() => deleteCarModel(c.id)}>Delete</button>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="z3d-modal-actions" style={{ marginTop: 16 }}>
          <button type="button" className="z3d-modal-cancel" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
