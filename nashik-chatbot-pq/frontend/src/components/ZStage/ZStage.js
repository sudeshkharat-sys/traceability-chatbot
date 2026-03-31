import React, { useState, useRef, useEffect } from 'react';
import Sidebar from './Sidebar/Sidebar';
import LayoutPreparation from './LayoutPreparation/LayoutPreparation';
import InputData from './InputData/InputData';
import ZStageDashboard from './ZStageDashboard/ZStageDashboard';
import { layoutApi } from '../../services/api/layoutApi';
import utilityLogo from '../../assests/image.png';
import mahindraRiseLogo from '../../assests/mahindra_rise_logo.png';
import './ZStage.css';

function ZStage() {
  const [activeSection, setActiveSection] = useState('layout');

  // ── Layout Preparation state lifted to App so Sidebar can trigger it ────────
  const [showAddBoxModal, setShowAddBoxModal] = useState(false);
  const [addBypassSignal, setAddBypassSignal] = useState(0);
  const [isSaving, setIsSaving] = useState(false);
  const [savedLayouts, setSavedLayouts] = useState([]);

  const saveHandlerRef = useRef(null);
  const loadHandlerRef = useRef(null);

  useEffect(() => {
    layoutApi.getLayouts()
      .then((res) => setSavedLayouts(Array.isArray(res.data) ? res.data : []))
      .catch(() => {});
  }, []);

  const handleSaveLayout = async () => {
    if (!saveHandlerRef.current) return;
    setIsSaving(true);
    const ok = await saveHandlerRef.current();
    setIsSaving(false);
    if (ok) {
      layoutApi.getLayouts()
        .then((res) => setSavedLayouts(Array.isArray(res.data) ? res.data : []))
        .catch(() => {});
    }
  };

  const handleLoadLayout = async (id) => {
    if (loadHandlerRef.current) await loadHandlerRef.current(id);
  };

  const layoutActions = {
    onAddBox: () => setShowAddBoxModal(true),
    onAddBypass: () => setAddBypassSignal((s) => s + 1),
    onSaveLayout: handleSaveLayout,
    onLoadLayout: handleLoadLayout,
    savedLayouts,
    isSaving,
  };

  return (
    <div className="zstage-app">
      <Sidebar
        activeSection={activeSection}
        onSectionChange={setActiveSection}
        layoutActions={layoutActions}
      />
      <main className="zstage-app-main">
        <div className="zstage-header">
          <img src={utilityLogo} alt="Mahindra Utility Logo" className="zstage-header-logo-left" />
          <img src={mahindraRiseLogo} alt="Mahindra Rise Logo" className="zstage-header-logo-right" />
        </div>
        {activeSection === 'layout' && (
          <LayoutPreparation
            showAddBoxModal={showAddBoxModal}
            onCloseAddBoxModal={() => setShowAddBoxModal(false)}
            addBypassSignal={addBypassSignal}
            onSaveLayout={(fn) => { saveHandlerRef.current = fn; }}
            onLoadLayout={(fn) => { loadHandlerRef.current = fn; }}
          />
        )}
        {activeSection === 'input' && <InputData />}
        {activeSection === 'dashboard' && <ZStageDashboard />}
      </main>
    </div>
  );
}

export default ZStage;
