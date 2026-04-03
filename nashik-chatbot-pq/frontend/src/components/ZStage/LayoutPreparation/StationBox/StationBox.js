import React, { useState, useRef, useEffect } from 'react';
import Draggable from 'react-draggable';
import { useXarrow } from 'react-xarrows';
import { ChevronUp, ChevronDown, X } from 'lucide-react';
import './StationBox.css';

function StationBox({
  id,
  name,
  stationIds,
  stationData = {},
  description = '',
  position: parentPosition,
  onPositionChange,
  onDelete,
  onPortMouseDown,
  canvasScale,
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [pos, setPos] = useState(parentPosition || { x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const nodeRef = useRef(null);
  const updateXarrow = useXarrow();

  useEffect(() => {
    if (parentPosition) setPos(parentPosition);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parentPosition?.x, parentPosition?.y]);

  const handleStart = () => {
    setIsDragging(true);
  };

  const handleDrag = (e, data) => {
    setPos({ x: data.x, y: data.y });
    updateXarrow();
  };

  const handleStop = (e, data) => {
    setIsDragging(false);
    if (onPositionChange) onPositionChange(id, { x: data.x, y: data.y });
  };

  const makePortId = (sid) => `${id}__${sid}`;

  const handleSidPortDown = (e, portId) => {
    e.preventDefault();
    e.stopPropagation();
    const rect = e.currentTarget.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    if (onPortMouseDown) onPortMouseDown(portId, cx, cy);
  };

  return (
    <Draggable
      nodeRef={nodeRef}
      position={pos}
      onStart={handleStart}
      onDrag={handleDrag}
      onStop={handleStop}
      handle=".station-box-header"
      scale={canvasScale || 1}
      grid={[40, 40]}
    >
      <div
        ref={nodeRef}
        id={id}
        className={['station-box', collapsed ? 'station-box--collapsed' : ''].join(' ').trim()}
        style={isDragging ? { zIndex: 1000 } : undefined}
      >
        <div className="station-box-header">
          <span className="station-box-title">{name}</span>
          <div className="station-box-controls">
            <button
              className="station-box-ctrl-btn"
              title={collapsed ? 'Expand' : 'Collapse'}
              onClick={(e) => { e.stopPropagation(); setCollapsed((v) => !v); }}
            >
              {collapsed ? <ChevronDown size={12} /> : <ChevronUp size={12} />}
            </button>
            {onDelete && (
              <button
                className="station-box-ctrl-btn station-box-ctrl-btn--delete"
                title="Delete"
                onClick={(e) => { e.stopPropagation(); onDelete(id); }}
              >
                <X size={12} />
              </button>
            )}
          </div>
        </div>

        {!collapsed && (
          <div className="station-box-body">
            <table className="station-grid">
              <thead>
                <tr>
                  {stationIds.map((sid) => {
                    const portId = makePortId(sid);
                    return (
                      <th key={sid} colSpan={2} className="station-grid-header-cell">
                        <div
                          id={portId}
                          className="station-sid-port"
                          onMouseDown={(e) => handleSidPortDown(e, portId)}
                          title="Drag to connect"
                        />
                        {sid}
                      </th>
                    );
                  })}
                </tr>
                {description && (
                  <tr>
                    <td colSpan={stationIds.length * 2} className="station-grid-desc-cell">
                      {description}
                    </td>
                  </tr>
                )}
              </thead>
              <tbody>
                {/* Z row — one cell per station (spans both label+value cols), invisible text */}
                <tr>
                  {stationIds.map((sid) => (
                    <td key={sid} colSpan={2} className="station-grid-label--z">Z</td>
                  ))}
                </tr>
                {['M', 'P', 'D', 'U'].map((label) => (
                  <tr key={label}>
                    {stationIds.map((sid) => (
                      <React.Fragment key={sid}>
                        <td className="station-grid-label">{label}</td>
                        <td className="station-grid-value">
                          {stationData[sid]?.[label] || ''}
                        </td>
                      </React.Fragment>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Draggable>
  );
}

export default StationBox;
