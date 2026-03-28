import React, { useState, useRef, useEffect } from 'react';
import Draggable from 'react-draggable';
import { useXarrow } from 'react-xarrows';
import { GitBranch, X, Trash2 } from 'lucide-react';
import './BypassIcon.css';

function BypassIcon({ id, position: parentPosition, onPositionChange, onDelete, onPortMouseDown, canvasScale }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [pos, setPos] = useState(parentPosition || { x: 0, y: 0 });
  const nodeRef = useRef(null);
  const updateXarrow = useXarrow();

  useEffect(() => {
    if (parentPosition) setPos(parentPosition);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parentPosition?.x, parentPosition?.y]);

  const handleDrag = (e, data) => {
    setPos({ x: data.x, y: data.y });
    updateXarrow();
  };

  const handleDragStop = (e, data) => {
    if (onPositionChange) onPositionChange(id, { x: data.x, y: data.y });
  };

  const toggleExpand = (e) => {
    e.stopPropagation();
    setIsExpanded((prev) => !prev);
  };

  const handlePortDown = (e) => {
    e.preventDefault();
    e.stopPropagation();
    const rect = e.currentTarget.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    if (onPortMouseDown) onPortMouseDown(id, cx, cy);
  };

  return (
    <Draggable
      nodeRef={nodeRef}
      position={pos}
      onDrag={handleDrag}
      onStop={handleDragStop}
      handle=".bypass-drag-handle"
      scale={canvasScale || 1}
      grid={[40, 40]}
    >
      <div ref={nodeRef} id={id} className="bypass-icon-wrapper">
        <div className="bypass-drag-handle bypass-diamond" onClick={toggleExpand} title="Bypass / Connect">
          <span className="bypass-diamond-inner"><GitBranch size={14} /></span>
        </div>

        {/* Connection ports — visible on hover */}
        <button className="bypass-port bypass-port--right" onMouseDown={handlePortDown} title="Drag to connect" />
        <button className="bypass-port bypass-port--left"  onMouseDown={handlePortDown} title="Drag to connect" />
        <button className="bypass-port bypass-port--top"   onMouseDown={handlePortDown} title="Drag to connect" />
        <button className="bypass-port bypass-port--bottom" onMouseDown={handlePortDown} title="Drag to connect" />

        {isExpanded && (
          <div className="bypass-accordion">
            <div className="bypass-accordion-header">
              <span>Bypass Connection</span>
              <button className="bypass-close-btn" onClick={toggleExpand}><X size={12} /></button>
            </div>
            <div className="bypass-accordion-body">
              <div className="bypass-connection-row">
                <span className="bypass-dot bypass-dot--in"></span>
                <span className="bypass-connection-label">In</span>
              </div>
              <div className="bypass-connection-row">
                <span className="bypass-dot bypass-dot--out"></span>
                <span className="bypass-connection-label">Out</span>
              </div>
              <div className="bypass-connection-row">
                <span className="bypass-dot bypass-dot--bypass"></span>
                <span className="bypass-connection-label">Bypass</span>
              </div>
            </div>
            {onDelete && (
              <button className="bypass-delete-btn" onClick={() => onDelete(id)}>
                <Trash2 size={12} />
                Remove
              </button>
            )}
          </div>
        )}
      </div>
    </Draggable>
  );
}

export default BypassIcon;
