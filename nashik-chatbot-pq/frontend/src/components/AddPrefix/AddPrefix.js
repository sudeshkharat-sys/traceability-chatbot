import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Plus, Trash2, Database, Check } from 'lucide-react';
import { backend_url } from '../../services/api/config';
import './AddPrefix.css';

const API_BASE = `${backend_url}/part-labeler`;

const DATA_SOURCES = [
  { key: 'warranty', label: 'Warranty Data' },
  { key: 'rpt', label: 'Offline RPT Data' },
  { key: 'gnovac', label: 'GNOVAC Data' },
  { key: 'rfi', label: 'RFI Data' },
  { key: 'esqa', label: 'e-SQA Data' },
];

function AddPrefix() {
  const navigate = useNavigate();
  const [userId] = useState(() => {
    const id = sessionStorage.getItem('user_id');
    return id ? parseInt(id, 10) : null;
  });

  const [dataSource, setDataSource] = useState('warranty');
  const [prefixes, setPrefixes] = useState([]);
  const [newPrefix, setNewPrefix] = useState('');
  const [newPlant, setNewPlant] = useState('');
  const [savedMessage, setSavedMessage] = useState('');
  const [dsOpen, setDsOpen] = useState(false);

  useEffect(() => {
    if (!userId) {
      navigate('/');
      return;
    }
    loadPrefixes();
  }, [userId, dataSource]);

  const loadPrefixes = () => {
    const key = `prefixes_${dataSource}_${userId}`;
    const stored = localStorage.getItem(key);
    setPrefixes(stored ? JSON.parse(stored) : []);
  };

  const savePrefixes = (updated) => {
    const key = `prefixes_${dataSource}_${userId}`;
    localStorage.setItem(key, JSON.stringify(updated));
    setPrefixes(updated);
  };

  const handleAdd = () => {
    const trimPrefix = newPrefix.trim();
    const trimPlant = newPlant.trim();
    if (!trimPrefix) return;
    const entry = { id: Date.now(), prefix: trimPrefix, plant: trimPlant };
    const updated = [...prefixes, entry];
    savePrefixes(updated);
    setNewPrefix('');
    setNewPlant('');
    setSavedMessage('Prefix added successfully!');
    setTimeout(() => setSavedMessage(''), 2500);
  };

  const handleDelete = (id) => {
    const updated = prefixes.filter(p => p.id !== id);
    savePrefixes(updated);
  };

  const selectedSource = DATA_SOURCES.find(s => s.key === dataSource);

  return (
    <div className="add-prefix-page">
      <div className="add-prefix-header">
        <button className="back-btn" onClick={() => navigate('/')}>
          <ArrowLeft size={16} /> Dashboard
        </button>
        <div className="header-title-area">
          <h1>Add Prefix</h1>
          <p>Manage plant prefix configurations across data sources</p>
        </div>
      </div>

      <div className="add-prefix-content">
        {/* Data Source Selector */}
        <div className="section-card">
          <h3 className="section-heading">
            <Database size={16} /> Data Source
          </h3>
          <div className="ds-selector-wrap">
            {DATA_SOURCES.map(src => (
              <button
                key={src.key}
                className={`ds-pill ${dataSource === src.key ? 'active' : ''}`}
                onClick={() => setDataSource(src.key)}
              >
                {dataSource === src.key && <Check size={12} />}
                {src.label}
              </button>
            ))}
          </div>
        </div>

        {/* Add Prefix Form */}
        <div className="section-card">
          <h3 className="section-heading">
            <Plus size={16} /> Add New Prefix — {selectedSource?.label}
          </h3>
          <div className="prefix-form-row">
            <div className="form-field">
              <label>Prefix</label>
              <input
                type="text"
                value={newPrefix}
                onChange={(e) => setNewPrefix(e.target.value)}
                placeholder="e.g. MA1"
                className="prefix-text-input"
              />
            </div>
            <div className="form-field">
              <label>Plant</label>
              <input
                type="text"
                value={newPlant}
                onChange={(e) => setNewPlant(e.target.value)}
                placeholder="e.g. Nashik Plant"
                className="prefix-text-input"
              />
            </div>
            <button className="add-btn" onClick={handleAdd} disabled={!newPrefix.trim()}>
              <Plus size={16} /> Add
            </button>
          </div>
          {savedMessage && (
            <div className="save-msg">
              <Check size={14} /> {savedMessage}
            </div>
          )}
        </div>

        {/* Prefix List */}
        <div className="section-card">
          <h3 className="section-heading">
            Configured Prefixes — {selectedSource?.label}
          </h3>
          {prefixes.length === 0 ? (
            <p className="empty-list-msg">No prefixes configured for this data source yet.</p>
          ) : (
            <table className="prefix-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Prefix</th>
                  <th>Plant</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {prefixes.map((p, idx) => (
                  <tr key={p.id}>
                    <td>{idx + 1}</td>
                    <td><span className="prefix-badge">{p.prefix}</span></td>
                    <td>{p.plant || '—'}</td>
                    <td>
                      <button className="delete-btn" onClick={() => handleDelete(p.id)}>
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

export default AddPrefix;
