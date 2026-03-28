import React from 'react';
import {
  LayoutGrid,
  Inbox,
  BarChart2,
  Plus,
  Diamond,
  Save,
  FolderOpen,
} from 'lucide-react';
import './Sidebar.css';

const NAV_ITEMS = [
  { id: 'layout',    label: 'Layout Preparation', Icon: LayoutGrid },
  { id: 'input',     label: 'Input Data',          Icon: Inbox },
  { id: 'dashboard', label: 'Z-Stage Dashboard',   Icon: BarChart2 },
];

function Sidebar({ activeSection, onSectionChange, layoutActions }) {
  const {
    onAddBox,
    onAddBypass,
    onSaveLayout,
    onLoadLayout,
    savedLayouts = [],
    isSaving,
  } = layoutActions || {};

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <span className="sidebar-logo-text">Z-Stage</span>
      </div>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map(({ id, label, Icon }) => (
          <div key={id}>
            <button
              className={`sidebar-nav-item${activeSection === id ? ' sidebar-nav-item--active' : ''}`}
              onClick={() => onSectionChange(id)}
            >
              <span className="sidebar-nav-icon">
                <Icon size={16} />
              </span>
              <span className="sidebar-nav-label">{label}</span>
            </button>

            {id === 'layout' && activeSection === 'layout' && (
              <div className="sidebar-sub-panel">

                <button className="sidebar-sub-btn sidebar-sub-btn--primary" onClick={onAddBox}>
                  <Plus size={14} />
                  Add Box
                </button>

                <button className="sidebar-sub-btn sidebar-sub-btn--bypass" onClick={onAddBypass}>
                  <Diamond size={14} className="sidebar-diamond-icon" />
                  Add Bypass
                </button>

                <div className="sidebar-sub-divider" />

                <button
                  className="sidebar-sub-btn sidebar-sub-btn--save"
                  onClick={onSaveLayout}
                  disabled={isSaving}
                >
                  <Save size={14} />
                  {isSaving ? 'Saving…' : 'Save Layout'}
                </button>

                {savedLayouts.length > 0 && (
                  <div className="sidebar-load-section">
                    <span className="sidebar-load-label">
                      <FolderOpen size={11} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                      Load saved
                    </span>
                    <select
                      className="sidebar-load-select"
                      defaultValue=""
                      onChange={(e) => {
                        if (e.target.value) onLoadLayout(Number(e.target.value));
                        e.target.value = '';
                      }}
                    >
                      <option value="" disabled>Select layout…</option>
                      {savedLayouts.map((l) => (
                        <option key={l.id} value={l.id}>{l.name}</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </nav>
    </aside>
  );
}

export default Sidebar;
