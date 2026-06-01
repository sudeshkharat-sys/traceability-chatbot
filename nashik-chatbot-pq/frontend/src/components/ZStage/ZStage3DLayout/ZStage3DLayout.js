import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { layoutApi } from '../../../services/api/layoutApi';
import './ZStage3DLayout.css';

// ── Constants ──────────────────────────────────────────────────────────────────
const SCALE   = 0.04;   // canvas px → metres
const CELL_W  = 5.0;    // metres per station cell width
const DEPTH   = 20.0;   // station depth (Z axis) — long tunnel
const HEIGHT  = 5.0;    // column / beam height
const COL_W   = 0.30;   // column width (rectangular)
const COL_D   = 0.30;   // column depth (rectangular)
const PATH_W  = 3.0;    // walking path width
const ZEBRA_W = 0.8;    // zebra stripe width between cells

const STATUS_HEX = {
  R: 0xe53935,
  Y: 0xfdd835,
  G: 0x43a047,
  null: 0x90a4ae,
};

// ── Helpers ────────────────────────────────────────────────────────────────────
function makeLabel(text, { fontSize = 48, color = '#ffffff', bgColor = null, padding = 10, scale = 1 } = {}) {
  const canvas  = document.createElement('canvas');
  const ctx     = canvas.getContext('2d');
  ctx.font      = `bold ${fontSize}px Arial`;
  const tw      = ctx.measureText(text).width;
  canvas.width  = tw + padding * 2;
  canvas.height = fontSize + padding * 2;

  if (bgColor) {
    ctx.fillStyle = bgColor;
    ctx.beginPath();
    ctx.roundRect(0, 0, canvas.width, canvas.height, 8);
    ctx.fill();
  }

  ctx.font      = `bold ${fontSize}px Arial`;
  ctx.fillStyle = color;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, canvas.width / 2, canvas.height / 2);

  const tex = new THREE.CanvasTexture(canvas);
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false });
  const spr = new THREE.Sprite(mat);
  const aspect = canvas.width / canvas.height;
  spr.scale.set(aspect * scale, scale, 1);
  return spr;
}

function makeShopBoard(shopName) {
  const W = 256, H = 80;
  const canvas = document.createElement('canvas');
  canvas.width  = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d');

  ctx.fillStyle = '#1565C0';
  ctx.beginPath();
  ctx.roundRect(0, 0, W, H, 10);
  ctx.fill();

  ctx.strokeStyle = '#BBDEFB';
  ctx.lineWidth   = 3;
  ctx.beginPath();
  ctx.roundRect(4, 4, W - 8, H - 8, 7);
  ctx.stroke();

  ctx.fillStyle    = '#ffffff';
  ctx.font         = 'bold 36px Arial';
  ctx.textAlign    = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(shopName, W / 2, H / 2);

  const tex = new THREE.CanvasTexture(canvas);
  const geo = new THREE.PlaneGeometry(2.0, 0.625);
  const mat = new THREE.MeshBasicMaterial({ map: tex, transparent: true, side: THREE.DoubleSide });
  return new THREE.Mesh(geo, mat);
}

function makeFloorLabel(text, width, fontSize = 36) {
  const canvas  = document.createElement('canvas');
  canvas.width  = 512;
  canvas.height = 128;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, 512, 128);
  ctx.fillStyle    = 'rgba(255,255,255,0.15)';
  ctx.fillRect(0, 0, 512, 128);
  ctx.fillStyle    = '#ffffff';
  ctx.font         = `bold ${fontSize}px Arial`;
  ctx.textAlign    = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, 256, 64);
  const tex = new THREE.CanvasTexture(canvas);
  const geo = new THREE.PlaneGeometry(width, width * (128 / 512));
  const mat = new THREE.MeshBasicMaterial({ map: tex, transparent: true, side: THREE.DoubleSide, depthWrite: false });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.rotation.x = -Math.PI / 2;
  return mesh;
}

// ── Green walking path strip between two adjacent cells ───────────────────────
function buildZebraCrossing(x, originZ, group) {
  // Light green fill
  const fillGeo = new THREE.PlaneGeometry(ZEBRA_W - 0.08, DEPTH - 0.1);
  const fillMat = new THREE.MeshBasicMaterial({ color: 0xa5d6a7, transparent: true, opacity: 0.7, side: THREE.DoubleSide });
  const fill    = new THREE.Mesh(fillGeo, fillMat);
  fill.rotation.x = -Math.PI / 2;
  fill.position.set(x, 0.02, originZ + DEPTH / 2);
  group.add(fill);

  // Green border — 4 thin edge strips
  const borderMat = new THREE.MeshBasicMaterial({ color: 0x2e7d32, side: THREE.DoubleSide });
  const T = 0.08; // border thickness
  [
    // left edge
    { geo: new THREE.PlaneGeometry(T, DEPTH),      pos: [x - ZEBRA_W / 2 + T / 2, 0.025, originZ + DEPTH / 2] },
    // right edge
    { geo: new THREE.PlaneGeometry(T, DEPTH),      pos: [x + ZEBRA_W / 2 - T / 2, 0.025, originZ + DEPTH / 2] },
    // front edge
    { geo: new THREE.PlaneGeometry(ZEBRA_W, T),    pos: [x, 0.025, originZ + T / 2] },
    // back edge
    { geo: new THREE.PlaneGeometry(ZEBRA_W, T),    pos: [x, 0.025, originZ + DEPTH - T / 2] },
  ].forEach(({ geo, pos }) => {
    const mesh = new THREE.Mesh(geo, borderMat);
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.set(...pos);
    group.add(mesh);
  });
}

// ── Build one station "shell" (4-corner rect columns + beams + floor + labels) ──
function buildStationShell(box, statusMap, scene) {
  const group   = new THREE.Group();
  const count   = box.station_count || 1;
  const totalW  = count * CELL_W;
  const originX = (box.position_x || 0) * SCALE;
  const originZ = (box.position_y || 0) * SCALE;

  const colMat  = new THREE.MeshLambertMaterial({ color: 0xcfd8dc });
  const beamMat = new THREE.MeshLambertMaterial({ color: 0x90a4ae });

  // ── 4 corner columns only (rectangular) ──
  const corners = [
    [originX,          originZ],
    [originX + totalW, originZ],
    [originX,          originZ + DEPTH],
    [originX + totalW, originZ + DEPTH],
  ];
  corners.forEach(([cx, cz]) => {
    const geo  = new THREE.BoxGeometry(COL_W, HEIGHT, COL_D);
    const mesh = new THREE.Mesh(geo, colMat);
    mesh.position.set(cx, HEIGHT / 2, cz);
    group.add(mesh);
  });

  // ── Top beams: front, back, left, right ──
  const beams = [
    { pos: [originX + totalW / 2, HEIGHT, originZ],          size: [totalW, 0.18, 0.18] },
    { pos: [originX + totalW / 2, HEIGHT, originZ + DEPTH],  size: [totalW, 0.18, 0.18] },
    { pos: [originX,          HEIGHT, originZ + DEPTH / 2],  size: [0.18, 0.18, DEPTH]  },
    { pos: [originX + totalW, HEIGHT, originZ + DEPTH / 2],  size: [0.18, 0.18, DEPTH]  },
  ];
  beams.forEach(({ pos, size }) => {
    const geo  = new THREE.BoxGeometry(...size);
    const mesh = new THREE.Mesh(geo, beamMat);
    mesh.position.set(...pos);
    group.add(mesh);
  });

  // ── Per-cell floor tiles + status sphere + station-ID label + zebra ──
  const stationIds = (box.station_ids || '').split(',').map(s => s.trim()).filter(Boolean);

  for (let i = 0; i < count; i++) {
    const cellX  = originX + i * CELL_W;
    const cellCX = cellX + CELL_W / 2;
    const cellCZ = originZ + DEPTH / 2;
    const stnId  = stationIds[i] || '';
    const status = statusMap[stnId] || null;
    const color  = STATUS_HEX[status] ?? STATUS_HEX.null;

    // Floor tile (slight gap for zebra crossing between cells)
    const floorW = i < count - 1 ? CELL_W - ZEBRA_W : CELL_W - 0.05;
    const fGeo   = new THREE.PlaneGeometry(floorW, DEPTH - 0.05);
    const fMat   = new THREE.MeshLambertMaterial({ color, transparent: true, opacity: 0.38, side: THREE.DoubleSide });
    const floor  = new THREE.Mesh(fGeo, fMat);
    floor.rotation.x = -Math.PI / 2;
    // Shift left slightly so gap is at right edge of cell
    const floorOffsetX = i < count - 1 ? -ZEBRA_W / 2 : 0;
    floor.position.set(cellCX + floorOffsetX, 0.01, cellCZ);
    group.add(floor);

    // Zebra crossing at right boundary between this cell and next
    if (i < count - 1) {
      buildZebraCrossing(cellX + CELL_W, originZ, group);
    }

    // Status sphere above cell
    const sGeo = new THREE.SphereGeometry(0.25, 12, 12);
    const sMat = new THREE.MeshLambertMaterial({ color });
    const sph  = new THREE.Mesh(sGeo, sMat);
    sph.position.set(cellCX, HEIGHT + 0.4, cellCZ);
    group.add(sph);

    // Station ID floor label
    if (stnId) {
      const lbl = makeFloorLabel(stnId, CELL_W * 0.7);
      lbl.position.set(cellCX, 0.02, cellCZ);
      group.add(lbl);
    }
  }

  // ── Box name floating label ──
  const nameSprite = makeLabel(box.name || 'Box', { fontSize: 52, color: '#ffffff', bgColor: 'rgba(0,0,0,0.6)', padding: 14, scale: 3.0 });
  nameSprite.position.set(originX + totalW / 2, HEIGHT + 1.2, originZ + DEPTH / 2);
  group.add(nameSprite);

  // ── Shop sign board at entry ──
  const shopPrefix = (stationIds[0] || box.name || 'SHOP').split('-')[0];
  const board = makeShopBoard(shopPrefix);
  board.position.set(originX + totalW / 2, 2.2, originZ - 0.05);
  group.add(board);

  scene.add(group);
}

// ── Walking path between two connected boxes ───────────────────────────────────
function buildWalkingPath(fromBox, toBox, scene) {
  const fW     = (fromBox.station_count || 1) * CELL_W;
  const fEndX  = (fromBox.position_x || 0) * SCALE + fW;
  const tStartX = (toBox.position_x || 0) * SCALE;
  const pathLen = tStartX - fEndX;
  if (pathLen <= 0.1) return;

  const pathCX  = fEndX + pathLen / 2;
  const pathCZ  = ((fromBox.position_y || 0) * SCALE) + DEPTH / 2;

  // Yellow path floor
  const geo = new THREE.PlaneGeometry(pathLen, PATH_W);
  const mat = new THREE.MeshLambertMaterial({ color: 0xfdd835, transparent: true, opacity: 0.65, side: THREE.DoubleSide });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.rotation.x = -Math.PI / 2;
  mesh.position.set(pathCX, 0.015, pathCZ);
  scene.add(mesh);

  // Orange stripe lines
  const stripeCount = Math.max(1, Math.floor(pathLen / 1.2));
  const stripeMat   = new THREE.MeshBasicMaterial({ color: 0xff6f00 });
  for (let s = 0; s <= stripeCount; s++) {
    const sx   = fEndX + (s / stripeCount) * pathLen;
    const sGeo = new THREE.PlaneGeometry(0.1, PATH_W);
    const sm   = new THREE.Mesh(sGeo, stripeMat);
    sm.rotation.x = -Math.PI / 2;
    sm.position.set(sx, 0.02, pathCZ);
    scene.add(sm);
  }

  // "WALKWAY" floor text
  const wlbl = makeFloorLabel('WALKWAY', Math.min(pathLen * 0.8, 3.0), 40);
  wlbl.position.set(pathCX, 0.025, pathCZ);
  scene.add(wlbl);
}

// ── Walk mode keys ─────────────────────────────────────────────────────────────
class WalkController {
  constructor(camera) {
    this.camera  = camera;
    this.keys    = {};
    this.speed   = 0.08;
    this.yaw     = 0;
    this.pitch   = 0;
    this._onKey  = (e) => { this.keys[e.code] = e.type === 'keydown'; };
    this._onMove = (e) => this._mouseMove(e);
    document.addEventListener('keydown', this._onKey);
    document.addEventListener('keyup',   this._onKey);
  }
  attachMouseLook(canvas) {
    this._canvas = canvas;
    canvas.addEventListener('mousemove', this._onMove);
    canvas.requestPointerLock();
  }
  detachMouseLook() {
    if (this._canvas) {
      this._canvas.removeEventListener('mousemove', this._onMove);
      this._canvas = null;
    }
    document.exitPointerLock();
  }
  _mouseMove(e) {
    if (document.pointerLockElement !== this._canvas) return;
    this.yaw   -= e.movementX * 0.002;
    this.pitch -= e.movementY * 0.002;
    this.pitch  = Math.max(-Math.PI / 2.5, Math.min(Math.PI / 2.5, this.pitch));
  }
  update() {
    const { camera, keys } = this;
    const euler = new THREE.Euler(this.pitch, this.yaw, 0, 'YXZ');
    camera.quaternion.setFromEuler(euler);

    const dir = new THREE.Vector3();
    const fwd = new THREE.Vector3(-Math.sin(this.yaw), 0, -Math.cos(this.yaw));
    const rgt = new THREE.Vector3(Math.cos(this.yaw), 0, -Math.sin(this.yaw));

    if (keys['KeyW'] || keys['ArrowUp'])    dir.add(fwd);
    if (keys['KeyS'] || keys['ArrowDown'])  dir.sub(fwd);
    if (keys['KeyA'] || keys['ArrowLeft'])  dir.sub(rgt);
    if (keys['KeyD'] || keys['ArrowRight']) dir.add(rgt);

    if (dir.length() > 0) {
      dir.normalize().multiplyScalar(this.speed);
      camera.position.add(dir);
      camera.position.y = Math.max(1.6, camera.position.y); // keep above floor
    }
  }
  destroy() {
    document.removeEventListener('keydown', this._onKey);
    document.removeEventListener('keyup',   this._onKey);
    this.detachMouseLook();
  }
}

// ── Three.js scene hook ────────────────────────────────────────────────────────
function useThreeScene(canvasRef, layout, statusMap, walkMode) {
  const sceneRef    = useRef(null);
  const rendererRef = useRef(null);
  const cameraRef   = useRef(null);
  const orbitRef    = useRef(null);
  const walkRef     = useRef(null);
  const rafRef      = useRef(null);
  const sceneCenterRef = useRef(new THREE.Vector3(0, 0, 0));
  const sceneSpanRef   = useRef(20);

  const walkModeRef = useRef(walkMode);
  useEffect(() => { walkModeRef.current = walkMode; }, [walkMode]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !layout) return;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(canvas.clientWidth, canvas.clientHeight);
    renderer.setClearColor(0x0d1117);
    rendererRef.current = renderer;

    // Scene
    const scene = new THREE.Scene();
    scene.fog   = new THREE.Fog(0x0d1117, 50, 200);
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(60, canvas.clientWidth / canvas.clientHeight, 0.1, 300);
    cameraRef.current = camera;

    // Lights
    scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const dir = new THREE.DirectionalLight(0xffffff, 0.8);
    dir.position.set(20, 30, 20);
    scene.add(dir);

    // Grid
    const grid = new THREE.GridHelper(200, 100, 0x2d333b, 0x21262d);
    grid.position.y = -0.01;
    scene.add(grid);

    // Build station shells
    const boxes = layout.station_boxes || [];
    boxes.forEach(box => buildStationShell(box, statusMap, scene));

    // Build walking paths
    const connections = layout.connections || [];
    connections.forEach(conn => {
      const fromBox = boxes.find(b => b.id === conn.from_box_id);
      const toBox   = boxes.find(b => b.id === conn.to_box_id);
      if (fromBox && toBox) buildWalkingPath(fromBox, toBox, scene);
    });

    // Camera auto-fit (overview)
    let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
    boxes.forEach(b => {
      const x0 = (b.position_x || 0) * SCALE;
      const x1 = x0 + (b.station_count || 1) * CELL_W;
      const z0 = (b.position_y || 0) * SCALE;
      const z1 = z0 + DEPTH;
      if (x0 < minX) minX = x0;
      if (x1 > maxX) maxX = x1;
      if (z0 < minZ) minZ = z0;
      if (z1 > maxZ) maxZ = z1;
    });
    if (boxes.length) {
      const cx   = (minX + maxX) / 2;
      const cz   = (minZ + maxZ) / 2;
      const span = Math.max(maxX - minX, maxZ - minZ, 10);
      sceneCenterRef.current.set(cx, 0, cz);
      sceneSpanRef.current = span;
      camera.position.set(cx, span * 0.8, cz + span * 0.9);
      camera.lookAt(cx, 0, cz);
    } else {
      camera.position.set(0, 20, 30);
      camera.lookAt(0, 0, 0);
    }

    // Orbit controls
    const orbit = new OrbitControls(camera, renderer.domElement);
    orbit.enableDamping = true;
    orbit.dampingFactor  = 0.08;
    orbit.minDistance    = 2;
    orbit.maxDistance    = 200;
    orbitRef.current = orbit;

    // Walk controller
    const walk = new WalkController(camera);
    walkRef.current = walk;

    // Resize observer
    const ro = new ResizeObserver(() => {
      if (!canvas.clientWidth || !canvas.clientHeight) return;
      renderer.setSize(canvas.clientWidth, canvas.clientHeight);
      camera.aspect = canvas.clientWidth / canvas.clientHeight;
      camera.updateProjectionMatrix();
    });
    ro.observe(canvas);

    // Animation loop
    const animate = () => {
      rafRef.current = requestAnimationFrame(animate);
      if (walkModeRef.current) {
        walk.update();
        orbit.enabled = false;
      } else {
        orbit.enabled = true;
        orbit.update();
      }
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
      walk.destroy();
      orbit.dispose();
      renderer.dispose();
    };
  }, [canvasRef, layout, statusMap]); // eslint-disable-line

  // Toggle walk mode: attach/detach pointer lock and reset camera pos
  useEffect(() => {
    const walk   = walkRef.current;
    const canvas = canvasRef.current;
    const camera = cameraRef.current;
    if (!walk || !canvas || !camera) return;

    if (walkMode) {
      walk.yaw   = 0;
      walk.pitch = 0;
      camera.position.y = 1.8;
      walk.attachMouseLook(canvas);
    } else {
      walk.detachMouseLook();
    }
  }, [walkMode, canvasRef]);

  // Snap camera to a named view preset
  const snapView = useCallback((view) => {
    const camera = cameraRef.current;
    const orbit  = orbitRef.current;
    if (!camera || !orbit) return;

    const c    = sceneCenterRef.current;
    const span = sceneSpanRef.current;
    const d    = span * 0.9;

    const presets = {
      top:    { pos: [c.x,     d * 1.4,  c.z      ], up: [0, 0, -1] },
      front:  { pos: [c.x,     d * 0.4,  c.z + d  ], up: [0, 1,  0] },
      back:   { pos: [c.x,     d * 0.4,  c.z - d  ], up: [0, 1,  0] },
      left:   { pos: [c.x - d, d * 0.4,  c.z      ], up: [0, 1,  0] },
      right:  { pos: [c.x + d, d * 0.4,  c.z      ], up: [0, 1,  0] },
      '3d':   { pos: [c.x + d * 0.8, d * 0.8, c.z + d * 0.9], up: [0, 1, 0] },
    };
    const p = presets[view];
    if (!p) return;

    camera.position.set(...p.pos);
    camera.up.set(...p.up);
    orbit.target.copy(c);
    orbit.update();
    camera.lookAt(c);
  }, []);

  return { snapView };
}

// ── Main component ─────────────────────────────────────────────────────────────
function ZStage3DLayout({ userId, savedLayouts = [], activeLayoutId, isActive }) {
  const canvasRef   = useRef(null);
  const [selectedLayoutId, setSelectedLayoutId] = useState(null);
  const [layout,    setLayout]    = useState(null);
  const [statusMap, setStatusMap] = useState({});
  const [walkMode,  setWalkMode]  = useState(false);

  // Auto-select active layout when provided
  useEffect(() => {
    if (activeLayoutId && !selectedLayoutId) {
      setSelectedLayoutId(activeLayoutId);
    }
  }, [activeLayoutId]); // eslint-disable-line

  // Fetch layout data
  useEffect(() => {
    if (!selectedLayoutId) return;
    layoutApi.getLayout(selectedLayoutId)
      .then(res => setLayout(res.data))
      .catch(() => {});
  }, [selectedLayoutId]);

  // Derive status map from input records (if layout has records)
  useEffect(() => {
    if (!layout) return;
    const map = {};
    (layout.station_boxes || []).forEach(box => {
      (box.station_ids || '').split(',').forEach(id => {
        const sid = id.trim();
        if (!sid) return;
        // Use station_data if available, otherwise null → grey
        try {
          const data = JSON.parse(box.station_data || '{}');
          if (data[sid]) map[sid] = data[sid].status || null;
        } catch (_) {}
      });
    });
    setStatusMap(map);
  }, [layout]);

  const { snapView } = useThreeScene(canvasRef, layout, statusMap, walkMode);

  const handleLayoutChange = useCallback((e) => {
    setSelectedLayoutId(Number(e.target.value) || null);
    setLayout(null);
    setWalkMode(false);
  }, []);

  return (
    <div className="z3d-root">
      <div className="z3d-toolbar">
        <span className="z3d-toolbar-title">Z-Stage 3D Layout</span>

        <select className="z3d-layout-select" value={selectedLayoutId || ''} onChange={handleLayoutChange}>
          <option value="">— Select Layout —</option>
          {savedLayouts.map(l => (
            <option key={l.id} value={l.id}>{l.name || `Layout ${l.id}`}</option>
          ))}
        </select>

        {layout && (
          <>
            {/* View presets */}
            <div className="z3d-view-group">
              {[
                { id: '3d',    label: '3D'    },
                { id: 'top',   label: 'Top'   },
                { id: 'front', label: 'Front' },
                { id: 'back',  label: 'Back'  },
                { id: 'left',  label: 'Left'  },
                { id: 'right', label: 'Right' },
              ].map(v => (
                <button key={v.id} className="z3d-view-btn" onClick={() => snapView(v.id)} title={`${v.label} view`}>
                  {v.label}
                </button>
              ))}
            </div>

            {/* Walk mode */}
            <button
              className={`z3d-walk-btn${walkMode ? ' z3d-walk-btn--active' : ''}`}
              onClick={() => setWalkMode(v => !v)}
              title={walkMode ? 'Exit walk mode' : 'Enter first-person walk mode'}
            >
              {walkMode ? '🧍 Exit Walk' : '🚶 Walk Mode'}
            </button>
          </>
        )}

        <div className="z3d-legend">
          <span className="z3d-legend-item"><span className="z3d-legend-dot z3d-legend-dot--r" />Red</span>
          <span className="z3d-legend-item"><span className="z3d-legend-dot z3d-legend-dot--y" />Yellow</span>
          <span className="z3d-legend-item"><span className="z3d-legend-dot z3d-legend-dot--g" />Green</span>
          <span className="z3d-legend-item"><span className="z3d-legend-dot z3d-legend-dot--na" />N/A</span>
          <span className="z3d-legend-item"><span className="z3d-legend-dot z3d-legend-dot--path" />Walking Path</span>
        </div>
      </div>

      <div className="z3d-canvas-wrapper">
        {!layout ? (
          <div className="z3d-placeholder">
            <span className="z3d-placeholder-icon">🏭</span>
            <span>{savedLayouts.length === 0 ? 'No layouts saved yet' : 'Select a layout to view the 3D scene'}</span>
          </div>
        ) : (
          <>
            <canvas ref={canvasRef} className="z3d-canvas" />
            <div className="z3d-walk-hint">
              {walkMode
                ? 'WASD / Arrow keys to move · Mouse to look · Click canvas to capture mouse'
                : 'Left drag to orbit · Scroll to zoom · Right drag to pan'}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default ZStage3DLayout;
