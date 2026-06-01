import React, { useState, useEffect, Suspense, useRef } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { OrbitControls, Grid, Text, Html, PerspectiveCamera } from '@react-three/drei';
import * as THREE from 'three';
import { layoutApi } from '../../../services/api/layoutApi';
import './ZStage3DLayout.css';

// ── Constants ──────────────────────────────────────────────────────────────────
const SCALE         = 0.04;   // canvas px → meters
const CELL_WIDTH    = 3.5;    // meters per station cell (X axis)
const STATION_DEPTH = 5.0;    // meters deep (Z axis)
const STATION_H     = 4.5;    // meters tall (Y axis)
const COL_SIZE      = 0.18;   // column cross-section
const BEAM_H        = 0.22;   // beam height
const FLOOR_T       = 0.12;   // floor thickness

// Status colours derived from input records (passed as statusMap: stationId → 'R'|'Y'|'G'|null)
const STATUS_COLOR = { R: '#e53935', Y: '#fdd835', G: '#43a047', null: '#90a4ae' };

// ── Helpers ────────────────────────────────────────────────────────────────────
function columnMaterial() {
  return <meshStandardMaterial color="#546e7a" metalness={0.3} roughness={0.6} />;
}

function beamMaterial() {
  return <meshStandardMaterial color="#455a64" metalness={0.4} roughness={0.5} />;
}

// ── Single station cell on the floor ──────────────────────────────────────────
function StationCell({ stationId, index, originX, originZ, statusColor }) {
  const cx = originX + (index + 0.5) * CELL_WIDTH;
  const cz = originZ + STATION_DEPTH / 2;

  return (
    <group>
      {/* Floor cell highlight */}
      <mesh position={[cx, FLOOR_T / 2 + 0.001, cz]} receiveShadow>
        <boxGeometry args={[CELL_WIDTH - 0.1, 0.01, STATION_DEPTH - 0.1]} />
        <meshStandardMaterial color={statusColor} transparent opacity={0.35} />
      </mesh>

      {/* Divider wall between cells */}
      {index > 0 && (
        <mesh position={[originX + index * CELL_WIDTH, STATION_H / 2, cz]}>
          <boxGeometry args={[0.04, STATION_H, STATION_DEPTH]} />
          <meshStandardMaterial color="#90a4ae" transparent opacity={0.25} />
        </mesh>
      )}

      {/* Station ID label on floor */}
      <Text
        position={[cx, FLOOR_T + 0.05, cz]}
        rotation={[-Math.PI / 2, 0, 0]}
        fontSize={0.38}
        color="#1a237e"
        anchorX="center"
        anchorY="middle"
        font={undefined}
      >
        {stationId}
      </Text>

      {/* Status indicator sphere above station */}
      <mesh position={[cx, STATION_H - 0.6, cz]}>
        <sphereGeometry args={[0.2, 16, 16]} />
        <meshStandardMaterial color={statusColor} emissive={statusColor} emissiveIntensity={0.4} />
      </mesh>
    </group>
  );
}

// ── Station shell (columns + beams + floor + slab + cells) ────────────────────
function StationShell({ box, statusMap }) {
  const stationIds = box.station_ids
    ? box.station_ids.split(',').map((s) => s.trim()).filter(Boolean)
    : [];
  const count = stationIds.length || box.station_count || 1;

  const width  = count * CELL_WIDTH;
  const depth  = STATION_DEPTH;
  const height = STATION_H;

  // Origin from 2D canvas position scaled to metres
  const ox = (box.position_x || 0) * SCALE;
  const oz = (box.position_y || 0) * SCALE;

  // Centre
  const cx = ox + width / 2;
  const cz = oz + depth / 2;

  // Corner column positions
  const corners = [
    [ox,         height / 2, oz        ],
    [ox + width, height / 2, oz        ],
    [ox,         height / 2, oz + depth],
    [ox + width, height / 2, oz + depth],
  ];

  return (
    <group>
      {/* Floor slab */}
      <mesh position={[cx, FLOOR_T / 2, cz]} receiveShadow>
        <boxGeometry args={[width, FLOOR_T, depth]} />
        <meshStandardMaterial color="#cfd8dc" roughness={0.8} />
      </mesh>

      {/* Ceiling slab — translucent */}
      <mesh position={[cx, height + BEAM_H / 2, cz]}>
        <boxGeometry args={[width, 0.12, depth]} />
        <meshStandardMaterial color="#b0bec5" transparent opacity={0.25} />
      </mesh>

      {/* 4 corner columns */}
      {corners.map((pos, i) => (
        <mesh key={i} position={pos} castShadow>
          <boxGeometry args={[COL_SIZE, height, COL_SIZE]} />
          {columnMaterial()}
        </mesh>
      ))}

      {/* Perimeter beams at top */}
      {/* Front & back (along X) */}
      <mesh position={[cx, height, oz]} castShadow>
        <boxGeometry args={[width, BEAM_H, COL_SIZE]} />
        {beamMaterial()}
      </mesh>
      <mesh position={[cx, height, oz + depth]} castShadow>
        <boxGeometry args={[width, BEAM_H, COL_SIZE]} />
        {beamMaterial()}
      </mesh>
      {/* Left & right (along Z) */}
      <mesh position={[ox,         height, cz]} castShadow>
        <boxGeometry args={[COL_SIZE, BEAM_H, depth]} />
        {beamMaterial()}
      </mesh>
      <mesh position={[ox + width, height, cz]} castShadow>
        <boxGeometry args={[COL_SIZE, BEAM_H, depth]} />
        {beamMaterial()}
      </mesh>

      {/* Station cells on the floor */}
      {stationIds.map((sid, i) => (
        <StationCell
          key={sid}
          stationId={sid}
          index={i}
          originX={ox}
          originZ={oz}
          statusColor={STATUS_COLOR[statusMap?.[sid] ?? null]}
        />
      ))}

      {/* Box name label floating above the shell */}
      <Text
        position={[cx, height + 0.7, cz]}
        fontSize={0.55}
        color="#0d47a1"
        anchorX="center"
        anchorY="middle"
        outlineWidth={0.03}
        outlineColor="#fff"
      >
        {box.name || `Box ${box.id}`}
      </Text>
    </group>
  );
}

// ── Connection beam between two station boxes ──────────────────────────────────
function ConnectionBeam({ fromBox, toBox }) {
  const scale = SCALE;
  const fromCount = (fromBox.station_ids?.split(',').length) || fromBox.station_count || 1;
  const toCount   = (toBox.station_ids?.split(',').length)   || toBox.station_count   || 1;

  const fx = (fromBox.position_x || 0) * scale + fromCount * CELL_WIDTH;
  const fz = (fromBox.position_y || 0) * scale + STATION_DEPTH / 2;
  const tx = (toBox.position_x   || 0) * scale;
  const tz = (toBox.position_y   || 0) * scale + STATION_DEPTH / 2;

  const midX  = (fx + tx) / 2;
  const midZ  = (fz + tz) / 2;
  const len   = Math.sqrt((tx - fx) ** 2 + (tz - fz) ** 2);
  const angle = Math.atan2(tz - fz, tx - fx);
  const y     = 0.8;

  if (len < 0.01) return null;

  return (
    <mesh position={[midX, y, midZ]} rotation={[0, -angle, 0]}>
      <boxGeometry args={[len, 0.08, 0.08]} />
      <meshStandardMaterial color="#1976d2" transparent opacity={0.7} />
    </mesh>
  );
}

// ── Camera auto-fit to scene ───────────────────────────────────────────────────
function CameraRig({ boxes }) {
  const { camera } = useThree();
  useEffect(() => {
    if (!boxes || boxes.length === 0) return;
    let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
    boxes.forEach((b) => {
      const count = (b.station_ids?.split(',').length) || b.station_count || 1;
      const x0 = (b.position_x || 0) * SCALE;
      const z0 = (b.position_y || 0) * SCALE;
      const x1 = x0 + count * CELL_WIDTH;
      const z1 = z0 + STATION_DEPTH;
      if (x0 < minX) minX = x0;
      if (x1 > maxX) maxX = x1;
      if (z0 < minZ) minZ = z0;
      if (z1 > maxZ) maxZ = z1;
    });
    const cx = (minX + maxX) / 2;
    const cz = (minZ + maxZ) / 2;
    const span = Math.max(maxX - minX, maxZ - minZ, 10);
    camera.position.set(cx + span * 0.8, span * 0.9, cz + span * 0.8);
    camera.lookAt(cx, 0, cz);
  }, [boxes, camera]);
  return null;
}

// ── The full 3D scene ──────────────────────────────────────────────────────────
function Scene({ layout, statusMap }) {
  const boxes = layout?.station_boxes || [];
  const conns = layout?.connections   || [];

  // Build id → box map for connection rendering
  const boxById = {};
  boxes.forEach((b) => { boxById[b.id] = b; });

  // Deduplicate connections to only box→box ones
  const boxConns = conns.filter(
    (c) => c.from_box_id != null && c.to_box_id != null
  );

  return (
    <>
      <ambientLight intensity={0.7} />
      <directionalLight
        position={[30, 40, 20]}
        intensity={1.2}
        castShadow
        shadow-mapSize={[2048, 2048]}
      />
      <directionalLight position={[-20, 20, -20]} intensity={0.4} />

      <Grid
        args={[200, 200]}
        cellSize={1}
        cellThickness={0.4}
        cellColor="#cfd8dc"
        sectionSize={5}
        sectionThickness={0.8}
        sectionColor="#90a4ae"
        fadeDistance={120}
        infiniteGrid
      />

      {boxes.map((box) => (
        <StationShell key={box.id} box={box} statusMap={statusMap} />
      ))}

      {boxConns.map((c, i) => {
        const from = boxById[c.from_box_id];
        const to   = boxById[c.to_box_id];
        if (!from || !to) return null;
        return <ConnectionBeam key={i} fromBox={from} toBox={to} />;
      })}

      <CameraRig boxes={boxes} />
      <OrbitControls makeDefault enableDamping dampingFactor={0.07} />
    </>
  );
}

// ── Legend ─────────────────────────────────────────────────────────────────────
function Legend() {
  const items = [
    { color: STATUS_COLOR.R,    label: 'Active concern (Red)' },
    { color: STATUS_COLOR.Y,    label: 'Under observation (Yellow)' },
    { color: STATUS_COLOR.G,    label: 'Resolved (Green)' },
    { color: STATUS_COLOR.null, label: 'No data' },
  ];
  return (
    <div className="z3d-legend">
      {items.map(({ color, label }) => (
        <div key={label} className="z3d-legend-item">
          <span className="z3d-legend-dot" style={{ background: color }} />
          <span>{label}</span>
        </div>
      ))}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────
function ZStage3DLayout({ userId, savedLayouts = [], activeLayoutId, isActive }) {
  const [selectedId, setSelectedId] = useState(null);
  const [layout,     setLayout    ] = useState(null);
  const [statusMap,  setStatusMap ] = useState({});
  const [loading,    setLoading   ] = useState(false);
  const [error,      setError     ] = useState(null);

  // Pre-select activeLayoutId when it changes
  useEffect(() => {
    if (activeLayoutId && !selectedId) setSelectedId(activeLayoutId);
  }, [activeLayoutId]); // eslint-disable-line

  // Fetch full layout when selection changes
  useEffect(() => {
    if (!selectedId) { setLayout(null); return; }
    setLoading(true);
    setError(null);
    layoutApi.getLayout(selectedId)
      .then((res) => setLayout(res.data))
      .catch(() => setError('Failed to load layout data.'))
      .finally(() => setLoading(false));
  }, [selectedId]);

  // Fetch concern status per station from input records
  useEffect(() => {
    if (!selectedId || !userId) return;
    layoutApi.getInputRecords?.(userId, selectedId)
      .then((res) => {
        const records = Array.isArray(res?.data) ? res.data : [];
        const map = {};
        records.forEach((r) => {
          if (!r.stage_no) return;
          const sid = r.stage_no.trim();
          // Worst-status logic: R > Y > G
          const prev = map[sid];
          const cur  = r.ryg || null;
          if (!prev || (cur === 'R') || (cur === 'Y' && prev === 'G') || (cur === 'G' && !prev)) {
            map[sid] = cur;
          }
        });
        setStatusMap(map);
      })
      .catch(() => {});
  }, [selectedId, userId]);

  return (
    <div className="z3d-root">
      {/* Toolbar */}
      <div className="z3d-toolbar">
        <div className="z3d-toolbar-left">
          <span className="z3d-toolbar-title">🏭 Z-Stage 3D Layout</span>
          <select
            className="z3d-layout-select"
            value={selectedId || ''}
            onChange={(e) => setSelectedId(Number(e.target.value) || null)}
          >
            <option value="">— Select a layout —</option>
            {savedLayouts.map((l) => (
              <option key={l.id} value={l.id}>{l.name || `Layout ${l.id}`}</option>
            ))}
          </select>
        </div>
        <div className="z3d-toolbar-right">
          <Legend />
        </div>
      </div>

      {/* Canvas area */}
      <div className="z3d-canvas-wrapper">
        {!selectedId && (
          <div className="z3d-placeholder">
            <div className="z3d-placeholder-icon">🏗️</div>
            <p className="z3d-placeholder-title">Select a layout to view its 3D station shells</p>
            <p className="z3d-placeholder-sub">Station boxes from the Layout editor will be auto-generated as 3D structures with columns, beams and floor slabs.</p>
          </div>
        )}

        {selectedId && loading && (
          <div className="z3d-placeholder">
            <div className="z3d-loading-spinner" />
            <p>Loading 3D scene…</p>
          </div>
        )}

        {selectedId && error && (
          <div className="z3d-placeholder z3d-placeholder--error">
            <p>{error}</p>
          </div>
        )}

        {layout && !loading && (
          <>
            <Canvas
              shadows
              gl={{ antialias: true }}
              style={{ width: '100%', height: '100%', background: 'linear-gradient(180deg, #e3f2fd 0%, #f5f5f5 100%)' }}
            >
              <Suspense fallback={null}>
                <Scene layout={layout} statusMap={statusMap} />
              </Suspense>
            </Canvas>
            <div className="z3d-controls-hint">
              🖱️ Left-drag to orbit &nbsp;·&nbsp; Scroll to zoom &nbsp;·&nbsp; Right-drag to pan
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default ZStage3DLayout;
