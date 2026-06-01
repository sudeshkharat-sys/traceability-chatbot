import React, { useState, useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { layoutApi } from '../../../services/api/layoutApi';
import './ZStage3DLayout.css';

// ── Constants ──────────────────────────────────────────────────────────────────
const SCALE    = 0.04;
const CELL_W   = 3.5;   // metres per station cell
const DEPTH    = 5.0;   // station depth
const HEIGHT   = 4.5;   // column height
const COL_R    = 0.12;  // column radius
const BEAM_H   = 0.18;
const FLOOR_T  = 0.10;
const PATH_W   = 2.0;   // walking-path width (metres)

const STATUS_HEX = { R: 0xe53935, Y: 0xfdd835, G: 0x43a047, null: 0x90a4ae };

// ── Canvas-texture text sprite ─────────────────────────────────────────────────
function makeLabel(text, { fontSize = 52, color = '#0d47a1', bg = null,
                           canvasW = 512, canvasH = 96,
                           scaleX = 3.5, scaleY = 0.65 } = {}) {
  const canvas = document.createElement('canvas');
  canvas.width  = canvasW;
  canvas.height = canvasH;
  const ctx = canvas.getContext('2d');
  if (bg) {
    ctx.fillStyle = bg;
    ctx.roundRect(4, 4, canvasW - 8, canvasH - 8, 12);
    ctx.fill();
  }
  ctx.font = `bold ${fontSize}px Arial, sans-serif`;
  ctx.fillStyle = color;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, canvasW / 2, canvasH / 2);
  const tex = new THREE.CanvasTexture(canvas);
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false });
  const sprite = new THREE.Sprite(mat);
  sprite.scale.set(scaleX, scaleY, 1);
  return sprite;
}

// ── Shop sign board ────────────────────────────────────────────────────────────
function makeShopBoard(shopName) {
  const group = new THREE.Group();

  // board backing
  const board = new THREE.Mesh(
    new THREE.BoxGeometry(2.2, 0.8, 0.08),
    new THREE.MeshStandardMaterial({ color: 0x1565c0 })
  );
  board.position.set(0, 0, 0);
  group.add(board);

  // text label on the board
  const lbl = makeLabel(shopName, {
    fontSize: 56, color: '#ffffff', canvasW: 512, canvasH: 128,
    scaleX: 2.0, scaleY: 0.7,
  });
  lbl.position.set(0, 0, 0.06);
  group.add(lbl);

  return group;
}

// ── Build one station shell ────────────────────────────────────────────────────
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

  // derive shop prefix from first station id (e.g. "T1-01" → "T1")
  const shopPrefix = ids[0] ? ids[0].split('-')[0] : (box.name || 'STA');

  const group = new THREE.Group();
  const colMat = new THREE.MeshStandardMaterial({ color: 0x455a64, metalness: 0.3, roughness: 0.6 });
  const beamMat = new THREE.MeshStandardMaterial({ color: 0x37474f, metalness: 0.4, roughness: 0.5 });

  // ── Floor slab ──
  const floorMesh = new THREE.Mesh(
    new THREE.BoxGeometry(width, FLOOR_T, DEPTH),
    new THREE.MeshStandardMaterial({ color: 0xcfd8dc, roughness: 0.8 })
  );
  floorMesh.position.set(cx, FLOOR_T / 2, cz);
  floorMesh.receiveShadow = true;
  group.add(floorMesh);

  // ── Columns at every cell boundary (front + back rows) ──
  // positions along X: ox, ox+CELL_W, ox+2*CELL_W … ox+count*CELL_W  → count+1 columns per row
  const colGeo = new THREE.CylinderGeometry(COL_R, COL_R, HEIGHT, 8);
  for (let i = 0; i <= count; i++) {
    const x = ox + i * CELL_W;
    [oz, oz + DEPTH].forEach(z => {
      const col = new THREE.Mesh(colGeo, colMat);
      col.position.set(x, HEIGHT / 2, z);
      col.castShadow = true;
      group.add(col);
    });
  }

  // ── Top beams along the length (front + back) ──
  const frontBeam = new THREE.Mesh(
    new THREE.BoxGeometry(width, BEAM_H, COL_R * 2),
    beamMat
  );
  frontBeam.position.set(cx, HEIGHT, oz);
  group.add(frontBeam);

  const backBeam = frontBeam.clone();
  backBeam.position.set(cx, HEIGHT, oz + DEPTH);
  group.add(backBeam);

  // ── Cross beams at each column line ──
  for (let i = 0; i <= count; i++) {
    const x = ox + i * CELL_W;
    const crossBeam = new THREE.Mesh(
      new THREE.BoxGeometry(COL_R * 2, BEAM_H, DEPTH),
      beamMat
    );
    crossBeam.position.set(x, HEIGHT, cz);
    group.add(crossBeam);
  }

  // ── Per-cell: floor highlight + station-ID label ──
  ids.forEach((sid, i) => {
    const statusKey = statusMap?.[sid] ?? null;
    const color = STATUS_HEX[statusKey] ?? STATUS_HEX[null];
    const cellCx = ox + (i + 0.5) * CELL_W;

    // floor tile colour
    const tile = new THREE.Mesh(
      new THREE.BoxGeometry(CELL_W - 0.15, 0.012, DEPTH - 0.15),
      new THREE.MeshStandardMaterial({ color, transparent: true, opacity: 0.35 })
    );
    tile.position.set(cellCx, FLOOR_T + 0.007, cz);
    group.add(tile);

    // status sphere near top of column
    const sphere = new THREE.Mesh(
      new THREE.SphereGeometry(0.2, 16, 16),
      new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.55 })
    );
    sphere.position.set(cellCx, HEIGHT - 0.4, cz);
    group.add(sphere);

    // station-ID label on floor
    const idLabel = makeLabel(sid, {
      fontSize: 44, color: '#1a237e',
      canvasW: 256, canvasH: 80,
      scaleX: 1.8, scaleY: 0.55,
    });
    idLabel.position.set(cellCx, FLOOR_T + 0.05, cz);
    idLabel.rotation.x = -Math.PI / 2;
    // sprites don't rotate — use a plane instead
    const idCanvas = document.createElement('canvas');
    idCanvas.width = 256; idCanvas.height = 80;
    const idCtx = idCanvas.getContext('2d');
    idCtx.font = 'bold 40px Arial';
    idCtx.fillStyle = '#1a237e';
    idCtx.textAlign = 'center';
    idCtx.textBaseline = 'middle';
    idCtx.fillText(sid, 128, 40);
    const idTex = new THREE.CanvasTexture(idCanvas);
    const idPlane = new THREE.Mesh(
      new THREE.PlaneGeometry(1.8, 0.55),
      new THREE.MeshBasicMaterial({ map: idTex, transparent: true, depthWrite: false, side: THREE.DoubleSide })
    );
    idPlane.rotation.x = -Math.PI / 2;
    idPlane.position.set(cellCx, FLOOR_T + 0.02, cz);
    group.add(idPlane);
  });

  // ── Box name floating label (above structure) ──
  const boxLabel = makeLabel(box.name || `Box ${box.id}`, {
    fontSize: 52, color: '#0d47a1',
    canvasW: 512, canvasH: 96,
    scaleX: 3.8, scaleY: 0.7,
  });
  boxLabel.position.set(cx, HEIGHT + 0.9, cz);
  group.add(boxLabel);

  // ── Shop sign board at entry (front face, centred) ──
  const board = makeShopBoard(shopPrefix);
  board.position.set(cx, HEIGHT - 1.2, oz - 0.15);
  group.add(board);

  return group;
}

// ── Walking path between two connected boxes ───────────────────────────────────
function buildWalkingPath(fromBox, toBox) {
  const fromCount = (fromBox.station_ids?.split(',').length) || fromBox.station_count || 1;
  const fromEndX  = (fromBox.position_x || 0) * SCALE + fromCount * CELL_W;
  const toStartX  = (toBox.position_x   || 0) * SCALE;
  const pathLen   = toStartX - fromEndX;
  if (pathLen <= 0.05) return null;

  const fromCZ = (fromBox.position_y || 0) * SCALE + DEPTH / 2;
  const toCZ   = (toBox.position_y   || 0) * SCALE + DEPTH / 2;
  const midX   = fromEndX + pathLen / 2;
  const midZ   = (fromCZ + toCZ) / 2;

  const group = new THREE.Group();

  // main path floor
  const pathFloor = new THREE.Mesh(
    new THREE.BoxGeometry(pathLen, FLOOR_T * 0.8, PATH_W),
    new THREE.MeshStandardMaterial({ color: 0xfff176, roughness: 0.6 })
  );
  pathFloor.position.set(midX, FLOOR_T * 0.4, midZ);
  pathFloor.receiveShadow = true;
  group.add(pathFloor);

  // yellow safety stripes
  const stripeCount = Math.max(1, Math.floor(pathLen / 1.5));
  for (let i = 0; i < stripeCount; i++) {
    const sx = fromEndX + (i + 0.5) * (pathLen / stripeCount);
    const stripe = new THREE.Mesh(
      new THREE.BoxGeometry(0.15, FLOOR_T * 0.82, PATH_W * 0.85),
      new THREE.MeshStandardMaterial({ color: 0xf9a825 })
    );
    stripe.position.set(sx, FLOOR_T * 0.41, midZ);
    group.add(stripe);
  }

  // "WALKWAY" text on path
  const walkCanvas = document.createElement('canvas');
  walkCanvas.width = 256; walkCanvas.height = 64;
  const wCtx = walkCanvas.getContext('2d');
  wCtx.fillStyle = '#f57f17';
  wCtx.font = 'bold 28px Arial';
  wCtx.textAlign = 'center';
  wCtx.textBaseline = 'middle';
  wCtx.fillText('WALKWAY', 128, 32);
  const walkPlane = new THREE.Mesh(
    new THREE.PlaneGeometry(Math.min(pathLen * 0.8, 2.5), 0.5),
    new THREE.MeshBasicMaterial({
      map: new THREE.CanvasTexture(walkCanvas),
      transparent: true, depthWrite: false, side: THREE.DoubleSide,
    })
  );
  walkPlane.rotation.x = -Math.PI / 2;
  walkPlane.position.set(midX, FLOOR_T + 0.02, midZ);
  group.add(walkPlane);

  return group;
}

// ── Three.js scene hook ────────────────────────────────────────────────────────
function useThreeScene(canvasRef, layout, statusMap) {
  const frameRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current || !layout) return;

    const canvas = canvasRef.current;
    const W = canvas.clientWidth  || 800;
    const H = canvas.clientHeight || 600;

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    renderer.setSize(W, H, false);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.shadowMap.enabled = true;
    renderer.setClearColor(0xeceff1);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xeceff1);
    scene.fog = new THREE.Fog(0xeceff1, 80, 200);

    const camera = new THREE.PerspectiveCamera(50, W / H, 0.1, 500);
    camera.position.set(20, 20, 20);

    scene.add(new THREE.AmbientLight(0xffffff, 0.75));
    const sun = new THREE.DirectionalLight(0xffffff, 1.1);
    sun.position.set(30, 40, 20);
    sun.castShadow = true;
    scene.add(sun);
    scene.add(new THREE.DirectionalLight(0xffffff, 0.35).position.set(-15, 20, -15));

    scene.add(new THREE.GridHelper(300, 300, 0xb0bec5, 0xcfd8dc));

    const boxes = layout.station_boxes || [];
    const boxById = {};
    boxes.forEach(b => { boxById[b.id] = b; });

    // Station shells
    boxes.forEach(b => scene.add(buildStationShell(b, statusMap)));

    // Walking paths between connected boxes
    const seen = new Set();
    (layout.connections || [])
      .filter(c => c.from_box_id != null && c.to_box_id != null)
      .forEach(c => {
        const key = `${c.from_box_id}-${c.to_box_id}`;
        if (seen.has(key)) return;
        seen.add(key);
        const from = boxById[c.from_box_id];
        const to   = boxById[c.to_box_id];
        if (!from || !to) return;
        const path = buildWalkingPath(from, to);
        if (path) scene.add(path);
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
      camera.position.set(midX + span * 0.9, span * 0.85, midZ + span * 0.9);
      camera.lookAt(midX, 0, midZ);
    }

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.07;

    const ro = new ResizeObserver(() => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (w && h) {
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
      }
    });
    ro.observe(canvas);

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
      scene.traverse(obj => {
        obj.geometry?.dispose();
        if (obj.material) {
          const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
          mats.forEach(m => { m.map?.dispose(); m.dispose(); });
        }
      });
    };
  }, [layout, statusMap]); // eslint-disable-line
}

// ── Legend ─────────────────────────────────────────────────────────────────────
const LEGEND = [
  { color: '#e53935', label: 'Active concern (R)' },
  { color: '#fdd835', label: 'Under observation (Y)' },
  { color: '#43a047', label: 'Resolved (G)' },
  { color: '#90a4ae', label: 'No data' },
  { color: '#fff176', label: 'Walking path' },
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

// ── Main component ─────────────────────────────────────────────────────────────
function ZStage3DLayout({ userId, savedLayouts = [], activeLayoutId, isActive }) {
  const canvasRef  = useRef(null);
  const [selectedId, setSelectedId] = useState(null);
  const [layout,     setLayout    ] = useState(null);
  const [statusMap,  setStatusMap ] = useState({});
  const [loading,    setLoading   ] = useState(false);
  const [error,      setError     ] = useState(null);

  useEffect(() => {
    if (activeLayoutId && !selectedId) setSelectedId(activeLayoutId);
  }, [activeLayoutId]); // eslint-disable-line

  useEffect(() => {
    if (!selectedId) { setLayout(null); return; }
    setLoading(true);
    setError(null);
    layoutApi.getLayout(selectedId)
      .then(res => setLayout(res.data))
      .catch(() => setError('Failed to load layout.'))
      .finally(() => setLoading(false));
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId || !userId) return;
    layoutApi.getInputRecords?.(userId, selectedId)
      .then(res => {
        const records = Array.isArray(res?.data) ? res.data : [];
        const map = {};
        records.forEach(r => {
          if (!r.stage_no) return;
          const sid = r.stage_no.trim();
          const cur  = r.ryg || null;
          const prev = map[sid];
          if (!prev || cur === 'R' || (cur === 'Y' && prev === 'G')) map[sid] = cur;
        });
        setStatusMap(map);
      })
      .catch(() => {});
  }, [selectedId, userId]);

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
        <div className="z3d-toolbar-right"><Legend /></div>
      </div>

      <div className="z3d-canvas-wrapper">
        {!selectedId && !loading && (
          <div className="z3d-placeholder">
            <div className="z3d-placeholder-icon">🏗️</div>
            <p className="z3d-placeholder-title">Select a layout to view its 3D station shells</p>
            <p className="z3d-placeholder-sub">Stations auto-generate with columns, shop boards, station-ID labels and walking paths.</p>
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
