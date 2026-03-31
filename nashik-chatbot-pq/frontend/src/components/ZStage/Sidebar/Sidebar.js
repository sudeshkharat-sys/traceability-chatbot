import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  LayoutGrid,
  Inbox,
  BarChart2,
  Plus,
  Diamond,
  Save,
  FolderOpen,
} from 'lucide-react';
import { authService } from '../../../services/api';
import './Sidebar.css';

const NAV_ITEMS = [
  { id: 'layout',    label: 'Layout Preparation', Icon: LayoutGrid },
  { id: 'input',     label: 'Input Data',          Icon: Inbox },
  { id: 'dashboard', label: 'Z-Stage Dashboard',   Icon: BarChart2 },
];

function Sidebar({ activeSection, onSectionChange, layoutActions }) {
  const navigate = useNavigate();
  const [showSettingsMenu, setShowSettingsMenu] = useState(false);
  const settingsMenuRef = useRef(null);
  const currentUsername = authService.getFullName();

  const {
    onAddBox,
    onAddBypass,
    onSaveLayout,
    onLoadLayout,
    savedLayouts = [],
    isSaving,
  } = layoutActions || {};

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (settingsMenuRef.current && !settingsMenuRef.current.contains(event.target)) {
        setShowSettingsMenu(false);
      }
    };
    if (showSettingsMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showSettingsMenu]);

  const handleLogout = async () => {
    await authService.logout();
    setShowSettingsMenu(false);
    navigate('/');
    window.location.reload();
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <span className="sidebar-logo-text">Z-Stage</span>
        <button className="sidebar-home-btn" onClick={() => navigate('/')} title="Go to Home">
          <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
            <path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z" />
          </svg>
        </button>
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

      {/* User profile footer */}
      <div className="sidebar-footer">
        <div className="sidebar-user-profile">
          <div className="sidebar-user-avatar">
            <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
              <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
            </svg>
          </div>
          <span className="sidebar-user-name">{currentUsername}</span>
        </div>
        <div className="sidebar-settings-wrapper" ref={settingsMenuRef}>
          <button
            className="sidebar-settings-btn"
            onClick={() => setShowSettingsMenu(!showSettingsMenu)}
            title="Settings"
          >
            <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
              <path d="M19.14,12.94c0.04-0.3,0.06-0.61,0.06-0.94c0-0.32-0.02-0.64-0.07-0.94l2.03-1.58c0.18-0.14,0.23-0.41,0.12-0.61l-1.92-3.32c-0.12-0.22-0.37-0.29-0.59-0.22l-2.39,0.96c-0.5-0.38-1.03-0.7-1.62-0.94L14.4,2.81c-0.04-0.24-0.24-0.41-0.48-0.41h-3.84c-0.24,0-0.43,0.17-0.47,0.41L9.25,5.35C8.66,5.59,8.12,5.92,7.63,6.29L5.24,5.33c-0.22-0.08-0.47,0-0.59,0.22L2.74,8.87C2.62,9.08,2.66,9.34,2.86,9.48l2.03,1.58C4.84,11.36,4.8,11.69,4.8,12s0.02,0.64,0.07,0.94l-2.03,1.58c-0.18,0.14-0.23,0.41-0.12,0.61l1.92,3.32c0.12,0.22,0.37,0.29,0.59,0.22l2.39-0.96c0.5,0.38,1.03,0.7,1.62,0.94l0.36,2.54c0.05,0.24,0.24,0.41,0.48,0.41h3.84c0.24,0,0.44-0.17,0.47-0.41l0.36-2.54c0.59-0.24,1.13-0.56,1.62-0.94l2.39,0.96c0.22,0.08,0.47,0,0.59-0.22l1.92-3.32c0.12-0.22,0.07-0.47-0.12-0.61L19.14,12.94z M12,15.6c-1.98,0-3.6-1.62-3.6-3.6s1.62-3.6,3.6-3.6s3.6,1.62,3.6,3.6S13.98,15.6,12,15.6z" />
            </svg>
          </button>
          {showSettingsMenu && (
            <div className="sidebar-settings-menu">
              <button className="sidebar-settings-menu-item" onClick={handleLogout}>
                <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
                  <path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z" />
                </svg>
                <span>Logout</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
