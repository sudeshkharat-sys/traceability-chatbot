import React, { useState, useRef, useEffect } from 'react';
import Sidebar from './Sidebar/Sidebar';
import LayoutPreparation from './LayoutPreparation/LayoutPreparation';
import InputData from './InputData/InputData';
import ZStageDashboard from './ZStageDashboard/ZStageDashboard';
import { layoutApi } from '../../services/api/layoutApi';
import authService from '../../services/api/authService';
import utilityLogo from '../../assests/image.png';
import './ZStage.css';

function ZStage() {
  const [activeSection, setActiveSection] = useState('layout');
  const userId = authService.getUserId();

  // ── Layout Preparation state lifted to App so Sidebar can trigger it ────────
  const [showAddBoxModal, setShowAddBoxModal] = useState(false);
  const [addBuyoffSignal, setAddBuyoffSignal] = useState(0);
  const [isSaving, setIsSaving] = useState(false);
  const [savedLayouts, setSavedLayouts] = useState([]);

  const saveHandlerRef = useRef(null);
  const loadHandlerRef = useRef(null);

  useEffect(() => {
    layoutApi.getLayouts(userId)
      .then((res) => setSavedLayouts(Array.isArray(res.data) ? res.data : []))
      .catch(() => {});
  }, [userId]);

  const handleSaveLayout = async () => {
    if (!saveHandlerRef.current) return;
    setIsSaving(true);
    const ok = await saveHandlerRef.current();
    setIsSaving(false);
    if (ok) {
      layoutApi.getLayouts(userId)
        .then((res) => setSavedLayouts(Array.isArray(res.data) ? res.data : []))
        .catch(() => {});
    }
  };

  const handleLoadLayout = async (id) => {
    if (loadHandlerRef.current) await loadHandlerRef.current(id);
  };

  const layoutActions = {
    onAddBox: () => setShowAddBoxModal(true),
    onAddBuyoff: () => setAddBuyoffSignal((s) => s + 1),
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
          <img src={utilityLogo} alt="Mahindra Utility Logo" className="zstage-header-logo-right" />
        </div>
        {activeSection === 'layout' && (
          <LayoutPreparation
            showAddBoxModal={showAddBoxModal}
            onCloseAddBoxModal={() => setShowAddBoxModal(false)}
            addBuyoffSignal={addBuyoffSignal}
            onSaveLayout={(fn) => { saveHandlerRef.current = fn; }}
            onLoadLayout={(fn) => { loadHandlerRef.current = fn; }}
            userId={userId}
          />
        )}
        {activeSection === 'input' && (
          <InputData userId={userId} layouts={savedLayouts} />
        )}
        {activeSection === 'dashboard' && (
          <ZStageDashboard userId={userId} />
        )}
      </main>
    </div>
  );
}

export default ZStage;
