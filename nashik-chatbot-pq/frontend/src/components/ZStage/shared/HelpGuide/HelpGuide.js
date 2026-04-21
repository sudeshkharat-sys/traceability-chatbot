import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X, HelpCircle } from 'lucide-react';
import './HelpGuide.css';

/**
 * HelpGuide — Floating "?" button + slide-in guide panel.
 *
 * Props:
 *   title   — page title shown at top of panel
 *   sections — array of { heading, items: [{ icon, label, desc }] }
 */
function HelpGuide({ title, sections = [] }) {
  const [open, setOpen] = useState(false);
  const panelRef = useRef(null);

  // Close on Escape key
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  // Close on click outside the panel
  useEffect(() => {
    if (!open) return;
    const onClick = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) setOpen(false);
    };
    // Small timeout so the opening click doesn't immediately close it
    const t = setTimeout(() => document.addEventListener('mousedown', onClick), 50);
    return () => { clearTimeout(t); document.removeEventListener('mousedown', onClick); };
  }, [open]);

  return createPortal(
    <>
      {/* Floating trigger button */}
      <button
        className={`help-fab${open ? ' help-fab--active' : ''}`}
        onClick={() => setOpen((v) => !v)}
        title="Help / Guide"
        aria-label="Open help guide"
      >
        <HelpCircle size={20} />
      </button>

      {/* Backdrop */}
      {open && <div className="help-backdrop" />}

      {/* Slide-in panel */}
      <div ref={panelRef} className={`help-panel${open ? ' help-panel--open' : ''}`}>
        <div className="help-panel-header">
          <div className="help-panel-title">
            <HelpCircle size={18} className="help-panel-title-icon" />
            <span>{title || 'Page Guide'}</span>
          </div>
          <button className="help-panel-close" onClick={() => setOpen(false)} title="Close">
            <X size={16} />
          </button>
        </div>

        <div className="help-panel-body">
          {sections.map((sec, si) => (
            <div key={si} className="help-section">
              {sec.heading && (
                <div className="help-section-heading">{sec.heading}</div>
              )}
              <ul className="help-item-list">
                {sec.items.map((item, ii) => (
                  <li key={ii} className="help-item">
                    {item.icon && (
                      <span className="help-item-icon">{item.icon}</span>
                    )}
                    <div className="help-item-text">
                      {item.label && (
                        <span className="help-item-label">{item.label}</span>
                      )}
                      <span className="help-item-desc">{item.desc}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </>,
    document.body
  );
}

export default HelpGuide;
