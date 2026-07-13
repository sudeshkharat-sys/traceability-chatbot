import React, { useState, useEffect, useCallback } from 'react';
import { carModelApi, lineModelMappingApi, z3dModelApi } from '../../../services/api/layoutApi';
import { lineNeedsCarModel } from '../lineUtils';
import '../ZStage3DLayout/ZStage3DLayout.css';

// Lightweight version of the object-assignment step, meant to live on the
// station box itself in Layout Preparation: pick a car model (if this line
// needs one) and a library object, then save. No transform fields here —
// position/rotation/scale is the model's own global preset, adjusted in the
// 3D Layout view where you can actually see the object.
export default function AssignObjectPopup({ layoutId, lineGroupId, onClose, onApplied }) {
  const [carModels, setCarModels] = useState([]);
  const [libraryModels, setLibraryModels] = useState([]);
  const [mappings, setMappings] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const needsCarModel = lineNeedsCarModel(lineGroupId);

  const [carModel, setCarModel] = useState('');
  const [modelName, setModelName] = useState('');
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadName, setUploadName] = useState('');
  const [showNewCarModel, setShowNewCarModel] = useState(false);
  const [newCarModelName, setNewCarModelName] = useState('');

  const reloadAll = useCallback(() => {
    setLoading(true);
    Promise.all([
      carModelApi.list().then(r => setCarModels(r.data || [])),
      z3dModelApi.listLibrary().then(r => setLibraryModels(r.data || [])),
      lineModelMappingApi.listByLayout(layoutId).then(r =>
        setMappings((r.data || []).filter(m => m.line_group_id === lineGroupId))
      ),
    ]).catch(err => setError(err?.response?.data?.detail || err.message))
      .finally(() => setLoading(false));
  }, [layoutId, lineGroupId]);

  useEffect(() => { reloadAll(); }, [reloadAll]);

  const sortedLibraryModels = React.useMemo(() => {
    const cm = carModels.find(c => String(c.id) === String(carModel));
    if (!cm) return libraryModels;
    const needle = cm.name.toLowerCase();
    const matches = libraryModels.filter(m => m.name.toLowerCase().includes(needle));
    const rest = libraryModels.filter(m => !m.name.toLowerCase().includes(needle));
    return [...matches, ...rest];
  }, [libraryModels, carModels, carModel]);

  const createCarModel = useCallback(() => {
    if (!newCarModelName.trim()) { setError('Enter a car model name.'); return; }
    setError('');
    setLoading(true);
    carModelApi.create({ name: newCarModelName.trim() })
      .then((r) => {
        setNewCarModelName(''); setShowNewCarModel(false);
        return carModelApi.list().then(res => {
          setCarModels(res.data || []);
          if (r?.data?.id) setCarModel(String(r.data.id));
        });
      })
      .catch(err => setError(err?.response?.data?.detail || err.message))
      .finally(() => setLoading(false));
  }, [newCarModelName]);

  const uploadNewModel = useCallback(() => {
    if (!uploadFile) { setError('Choose a file to upload.'); return; }
    const name = uploadName || uploadFile.name.replace(/\.[^/.]+$/, '');
    setError('');
    setLoading(true);
    z3dModelApi.uploadToLibrary(uploadFile, { name })
      .then(() => { setUploadFile(null); setUploadName(''); setModelName(name); reloadAll(); })
      .catch(err => setError(err?.response?.data?.detail || err.message))
      .finally(() => setLoading(false));
  }, [uploadFile, uploadName, reloadAll]);

  const deleteModel = useCallback((name) => {
    if (!window.confirm(`Delete "${name}" from the library? This removes it from every line/layout using it.`)) return;
    setLoading(true);
    z3dModelApi.deleteLibraryModel(name)
      .then(() => { if (modelName === name) setModelName(''); reloadAll(); onApplied && onApplied(); })
      .catch(err => setError(err?.response?.data?.detail || err.message))
      .finally(() => setLoading(false));
  }, [modelName, reloadAll, onApplied]);

  const save = useCallback(() => {
    if (!modelName) { setError('Choose an object.'); return; }
    if (needsCarModel && !carModel) { setError('Choose a car model for this line.'); return; }
    setError('');
    setLoading(true);
    lineModelMappingApi.create({
      layoutId, lineGroupId,
      carModelId: needsCarModel ? Number(carModel) : null,
      modelName,
    }).then(() => {
      reloadAll();
      onApplied && onApplied();
    }).catch(err => setError(err?.response?.data?.detail || err.message))
      .finally(() => setLoading(false));
  }, [layoutId, lineGroupId, carModel, modelName, needsCarModel, reloadAll, onApplied]);

  const removeMapping = useCallback((id) => {
    setLoading(true);
    lineModelMappingApi.delete(id)
      .then(() => { reloadAll(); onApplied && onApplied(); })
      .catch(err => setError(err?.response?.data?.detail || err.message))
      .finally(() => setLoading(false));
  }, [reloadAll, onApplied]);

  const carModelLabel = (id) => {
    if (id == null) return 'All / single model';
    const c = carModels.find(c => c.id === id);
    return c ? c.name : `#${id}`;
  };

  return (
    <div className="z3d-modal-overlay" onClick={onClose}>
      <div className="z3d-modal-box" style={{ width: 480, maxWidth: '90vw', maxHeight: '85vh', overflowY: 'auto' }} onClick={e => e.stopPropagation()}>
        <div className="z3d-modal-title">Assign Object — {lineGroupId}</div>

        {error && <div style={{ color: '#e53935', marginBottom: 10, fontSize: 13 }}>{error}</div>}

        {needsCarModel && (
          <>
            <label className="z3d-modal-label">Car Model</label>
            <div style={{ display: 'flex', gap: 8, marginBottom: showNewCarModel ? 8 : undefined }}>
              <select className="z3d-modal-select" style={{ flex: 1 }} value={carModel} onChange={e => setCarModel(e.target.value)}>
                <option value="">— Select car model —</option>
                {carModels.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <button type="button" className="z3d-modal-cancel" onClick={() => setShowNewCarModel(v => !v)}>+ New</button>
            </div>
            {showNewCarModel && (
              <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                <input
                  className="z3d-modal-select" style={{ flex: 1 }} placeholder="New car model name"
                  value={newCarModelName} onChange={e => setNewCarModelName(e.target.value)}
                />
                <button type="button" className="z3d-modal-confirm" disabled={loading} onClick={createCarModel}>Add</button>
              </div>
            )}
          </>
        )}

        <label className="z3d-modal-label">
          Object{carModel ? ' (matching models shown first)' : ''}
        </label>
        <div style={{ maxHeight: 140, overflowY: 'auto', border: '1px solid #30363d', borderRadius: 6, marginBottom: 8 }}>
          {libraryModels.length === 0 && <div className="z3d-modal-hint" style={{ padding: 8 }}>No models uploaded yet.</div>}
          {sortedLibraryModels.map(m => (
            <div
              key={m.name}
              className={`z3d-mapping-row${modelName === m.name ? ' z3d-mapping-row--active' : ''}`}
              onClick={() => setModelName(m.name)}
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

        <div className="z3d-modal-hint" style={{ marginBottom: 10 }}>
          Fine-tune position/rotation/scale in the 3D Layout view — that's the object's
          global preset, reused everywhere it's assigned.
        </div>

        <div className="z3d-modal-actions">
          <button type="button" className="z3d-modal-confirm" disabled={loading} onClick={save}>Save</button>
        </div>

        {mappings.length > 0 && (
          <div style={{ marginTop: 16, borderTop: '1px solid #30363d', paddingTop: 10 }}>
            <div className="z3d-modal-label">Currently assigned</div>
            {mappings.map(m => (
              <div key={m.id} className="z3d-mapping-row-static">
                <span>{carModelLabel(m.car_model_id)} → {m.model_name}</span>
                <button type="button" className="z3d-modal-cancel" onClick={() => removeMapping(m.id)}>Remove</button>
              </div>
            ))}
          </div>
        )}

        <div className="z3d-modal-actions" style={{ marginTop: 16 }}>
          <button type="button" className="z3d-modal-cancel" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
