import React, { useState, useEffect, useRef, useCallback } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { layoutApi } from '../../../services/api/layoutApi';
import './ZStage3DLayout.css';

// ── Constants ────────────────────────────────────────────────────────────────
const SCALE        = 0.04;   // canvas px → metres
const CELL_W       = 3.5;    // metres per station cell
const DEPTH        = 5.0;    // station depth (Z)
const HEIGHT       = 4.5;    // station height (Y)
const COL_SIZE     = 0.18;
const BEAM_H       = 0.22;
const FLOOR_T      = 0.12;

const STATUS_HEX = { R: 0xe53935, Y: 0xfdd835, G: 0x43a047, null: 0x90a4ae };

// ── Material helpers ─────────────────────────────────────────────────────────
const mat = (color, opacity = 1, transparent = false) =>
  new THREE.MeshStandardMaterial({ color, opacity, transparent, side: THREE.FrontSide });

// ── Build a station box mesh group ───────────────────────────────────────────
function buildStationShell(box, statusMap) {
  const ids = box.station_ids
    ? box.station_ids.split(',').map(s => s.trim()).filter(Boolean)
    : [];
  const count = ids.length || box.station_count || 1;
  const width = count * CELL_W;
  const ox = (box.position_x || 0) * SCALE;
  const oz = (box.position_y || 0) * SCALE;
  const cx = ox + width / 2;
  const cz = oz + DEPTH / 2;

  const group = new THREE.Group();

  // Floor
  const floor = new THREE.Mesh(
    new THREE.BoxGeometry(width, FLOOR_T, DEPTH),
    mat(0xcfd8dc)
  );
  floor.position.set(cx, FLOOR_T / 2, cz);
  floor.receiveShadow = true;
  group.add(floor);

  // Ceiling (transparent)
  const ceil = new THREE.Mesh(
    new THREE.BoxGeometry(width, 0.12, DEPTH),
    mat(0xb0bec5, 0.25, true)
  );
  ceil.position.set(cx, HEIGHT + BEAM_H / 2, cz);
  group.add(ceil);

  // 4 corner columns
  const corners = [
    [ox, oz], [ox + width, oz],
    [ox, oz + DEPTH], [ox + width, oz + DEPTH],
  ];
  corners.forEach(([x, z]) => {
    const col = new THREE.Mesh(
      new THREE.BoxGeometry(COL_SIZE, HEIGHT, COL_SIZE),
      mat(0x546e7a)
    );
    col.position.set(x, HEIGHT / 2, z);
    col.castShadow = true;
    group.add(col);
  });

  // Perimeter beams
  const beamMat = mat(0x455a64);
  [
    [cx, HEIGHT, oz,         width, BEAM_H, COL_SIZE],
    [cx, HEIGHT, oz + DEPTH, width, BEAM_H, COL_SIZE],
    [ox,         HEIGHT, cz, COL_SIZE, BEAM_H, DEPTH],
    [ox + width, HEIGHT, cz, COL_SIZE, BEAM_H, DEPTH],
  ].forEach(([x, y, z, w, h, d]) => {
    const beam = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), beamMat);
    beam.position.set(x, y, z);
    beam.castShadow = true;
    group.add(beam);
  });

  // Station cell highlights + dividers
  ids.forEach((sid, i) => {
    const statusKey = statusMap?.[sid] ?? null;
    const color = STATUS_HEX[statusKey] ?? STATUS_HEX[null];
    const cellCx = ox + (i + 0.5) * CELL_W;

    // Floor highlight
    const highlight = new THREE.Mesh(
      new THREE.BoxGeometry(CELL_W - 0.1, 0.015, DEPTH - 0.1),
      mat(color, 0.4, true)
    );
    highlight.position.set(cellCx, FLOOR_T + 0.008, cz);
    group.add(highlight);

    // Cell divider
    if (i > 0) {
      const div = new THREE.Mesh(
        new THREE.BoxGeometry(0.04, HEIGHT, DEPTH),
        mat(0x90a4ae, 0.3, true)
      );
      div.position.set(ox + i * CELL_W, HEIGHT / 2, cz);
      group.add(div);
    }

    // Status sphere above station
    const sphere = new THREE.Mesh(
      new THREE.SphereGeometry(0.22, 16, 16),
      new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.5 })
    );
    sphere.position.set(cellCx, HEIGHT - 0.5, cz);
    group.add(sphere);
  });

  return group;
}

// ── Connection beam between two boxes ────────────────────────────────────────
function buildConnection(fromBox, toBox) {
  const fromCount = (fromBox.station_ids?.split(',').length) || fromBox.station_count || 1;
  const fx = (fromBox.position_x || 0) * SCALE + fromCount * CELL_W;
  const fz = (fromBox.position_y || 0) * SCALE + DEPTH / 2;
  const tx = (toBox.position_x   || 0) * SCALE;
  const tz = (toBox.position_y   || 0) * SCALE + DEPTH / 2;

  const len = Math.sqrt((tx - fx) ** 2 + (tz - fz) ** 2);
  if (len < 0.01) return null;

  const beam = new THREE.Mesh(
    new THREE.BoxGeometry(len, 0.08, 0.08),
    mat(0x1976d2, 0.7, true)
  );
  beam.position.set((fx + tx) / 2, 0.8, (fz + tz) / 2);
  beam.rotation.y = -Math.atan2(tz - fz, tx - fx);
  return beam;
}

// ── 3D Scene renderer hook ────────────────────────────────────────────────────
function useThreeScene(canvasRef, layout, statusMap) {
  const rendererRef = useRef(null);
  const frameRef    = useRef(null);

  useEffect(() => {
    if (!canvasRef.current || !layout) return;

    const canvas = canvasRef.current;
    const W = canvas.clientWidth  || canvas.offsetWidth  || 800;
    const H = canvas.clientHeight || canvas.offsetHeight || 600;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    renderer.setSize(W, H);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.shadowMap.enabled = true;
    renderer.setClearColor(0xe8f0fe);
    rendererRef.current = renderer;

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xe8f0fe);
    scene.fog = new THREE.Fog(0xe8f0fe, 80, 200);

    // Camera
    const camera = new THREE.PerspectiveCamera(50, W / H, 0.1, 500);
    camera.position.set(20, 20, 20);

    // Lights
    scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
    dirLight.position.set(30, 40, 20);
    dirLight.castShadow = true;
    scene.add(dirLight);
    scene.add(new THREE.DirectionalLight(0xffffff, 0.4).position.set(-20, 20, -20));

    // Grid
    const grid = new THREE.GridHelper(200, 200, 0x90a4ae, 0xcfd8dc);
    scene.add(grid);

    // Station shells
    const boxes = layout.station_boxes || [];
    const boxById = {};
    boxes.forEach(b => { boxById[b.id] = b; });
    boxes.forEach(b => scene.add(buildStationShell(b, statusMap)));

    // Connections
    (layout.connections || [])
      .filter(c => c.from_box_id != null && c.to_box_id != null)
      .forEach(c => {
        const conn = buildConnection(boxById[c.from_box_id], boxById[c.to_box_id]);
        if (conn) scene.add(conn);
      });

    // Auto-fit camera
    if (boxes.length > 0) {
      let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
      boxes.forEach(b => {
        const cnt = (b.station_ids?.split(',').length) || b.station_count || 1;
        const x0 = (b.position_x || 0) * SCALE;
        const z0 = (b.position_y || 0) * SCALE;
        minX = Math.min(minX, x0); maxX = Math.max(maxX, x0 + cnt * CELL_W);
        minZ = Math.min(minZ, z0); maxZ = Math.max(maxZ, z0 + DEPTH);
      });
      const span = Math.max(maxX - minX, maxZ - minZ, 10);
      const midX = (minX + maxX) / 2;
      const midZ = (minZ + maxZ) / 2;
      camera.position.set(midX + span * 0.9, span * 0.9, midZ + span * 0.9);
      camera.lookAt(midX, 0, midZ);
    }

    // OrbitControls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.07;

    // Resize observer
    const ro = new ResizeObserver(() => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (w && h) {
        renderer.setSize(w, h);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
      }
    });
    ro.observe(canvas);

    // Render loop
    let alive = true;
    const animate = () => {
      if (!alive) return;
      frameRef.current = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      alive = false;
      cancelAnimationFrame(frameRef.current);
      ro.disconnect();
      controls.dispose();
      renderer.dispose();
      // Dispose all scene geometries & materials
      scene.traverse(obj => {
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) {
          if (Array.isArray(obj.material)) obj.material.forEach(m => m.dispose());
          else obj.material.dispose();
        }
      });
    };
  }, [layout, statusMap]); // eslint-disable-line
}

// ── Legend ────────────────────────────────────────────────────────────────────
const LEGEND = [
  { color: '#e53935', label: 'Active concern (R)' },
  { color: '#fdd835', label: 'Under observation (Y)' },
  { color: '#43a047', label: 'Resolved (G)' },
  { color: '#90a4ae', label: 'No data' },
];

function Legend() {
  return (
    <div className="z3d-legend">
      {LEGEND.map(({ color, label }) => (
        <div key={label} className="z3d-legend-item">
          <span className="z3d-legend-dot" style={{ background: color }} />
          <span>{label}</span>
        </div>
      ))}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
function ZStage3DLayout({ userId, savedLayouts = [], activeLayoutId, isActive }) {
  const canvasRef    = useRef(null);
  const [selectedId, setSelectedId] = useState(null);
  const [layout,     setLayout    ] = useState(null);
  const [statusMap,  setStatusMap ] = useState({});
  const [loading,    setLoading   ] = useState(false);
  const [error,      setError     ] = useState(null);

  // Pre-select activeLayoutId
  useEffect(() => {
    if (activeLayoutId && !selectedId) setSelectedId(activeLayoutId);
  }, [activeLayoutId]); // eslint-disable-line

  // Fetch layout
  useEffect(() => {
    if (!selectedId) { setLayout(null); return; }
    setLoading(true);
    setError(null);
    layoutApi.getLayout(selectedId)
      .then(res => setLayout(res.data))
      .catch(() => setError('Failed to load layout.'))
      .finally(() => setLoading(false));
  }, [selectedId]);

  // Fetch status map from input records
  useEffect(() => {
    if (!selectedId || !userId) return;
    layoutApi.getInputRecords?.(userId, selectedId)
      .then(res => {
        const records = Array.isArray(res?.data) ? res.data : [];
        const map = {};
        records.forEach(r => {
          if (!r.stage_no) return;
          const sid = r.stage_no.trim();
          const cur = r.ryg || null;
          const prev = map[sid];
          if (!prev || cur === 'R' || (cur === 'Y' && prev === 'G')) map[sid] = cur;
        });
        setStatusMap(map);
      })
      .catch(() => {});
  }, [selectedId, userId]);

  // Render Three.js scene
  useThreeScene(canvasRef, layout, statusMap);

  return (
    <div className="z3d-root">
      <div className="z3d-toolbar">
        <div className="z3d-toolbar-left">
          <span className="z3d-toolbar-title">🏭 Z-Stage 3D Layout</span>
          <select
            className="z3d-layout-select"
            value={selectedId || ''}
            onChange={e => setSelectedId(Number(e.target.value) || null)}
          >
            <option value="">— Select a layout —</option>
            {savedLayouts.map(l => (
              <option key={l.id} value={l.id}>{l.name || `Layout ${l.id}`}</option>
            ))}
          </select>
        </div>
        <div className="z3d-toolbar-right">
          <Legend />
        </div>
      </div>

      <div className="z3d-canvas-wrapper">
        {!selectedId && !loading && (
          <div className="z3d-placeholder">
            <div className="z3d-placeholder-icon">🏗️</div>
            <p className="z3d-placeholder-title">Select a layout to view its 3D station shells</p>
            <p className="z3d-placeholder-sub">Station boxes will be auto-generated as 3D structures with columns, beams and floor slabs.</p>
          </div>
        )}
        {loading && (
          <div className="z3d-placeholder">
            <div className="z3d-loading-spinner" />
            <p>Loading 3D scene…</p>
          </div>
        )}
        {error && (
          <div className="z3d-placeholder z3d-placeholder--error"><p>{error}</p></div>
        )}
        <canvas
          ref={canvasRef}
          className="z3d-canvas"
          style={{ display: layout && !loading ? 'block' : 'none' }}
        />
        {layout && !loading && (
          <div className="z3d-controls-hint">
            🖱️ Left-drag to orbit · Scroll to zoom · Right-drag to pan
          </div>
        )}
      </div>
    </div>
  );
}

export default ZStage3DLayout;
