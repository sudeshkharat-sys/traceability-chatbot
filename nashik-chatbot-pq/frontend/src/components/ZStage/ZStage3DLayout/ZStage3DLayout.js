import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { TransformControls } from 'three/examples/jsm/controls/TransformControls';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader';
import { layoutApi, inputApi } from '../../../services/api/layoutApi';
import './ZStage3DLayout.css';

// ── Constants ──────────────────────────────────────────────────────────────────
const SCALE      = 0.04;
const CELL_W     = 6.0;   // station box width
const DEPTH      = 6.0;   // station box depth — square-ish box, NOT tunnel
const HEIGHT     = 5.0;   // column height
const IB_FLANGE  = 0.40;
const IB_WEB     = 0.08;
const IB_FT      = 0.08;
const PATH_W     = 3.0;
const ZEBRA_W    = 0.8;

const STATUS_HEX = { R: 0xe53935, Y: 0xfdd835, G: 0x43a047, null: 0x90a4ae };
const LS_KEY     = 'z3d_placed_objects';

// ── Canvas text sprite ─────────────────────────────────────────────────────────
function makeLabel(text, { fontSize = 48, color = '#ffffff', bgColor = null, padding = 10, scale = 1 } = {}) {
  const canvas = document.createElement('canvas');
  const ctx    = canvas.getContext('2d');
  ctx.font     = `bold ${fontSize}px Arial`;
  const tw     = ctx.measureText(text).width;
  canvas.width  = tw + padding * 2;
  canvas.height = fontSize + padding * 2;
  if (bgColor) {
    ctx.fillStyle = bgColor;
    ctx.beginPath();
    ctx.roundRect(0, 0, canvas.width, canvas.height, 8);
    ctx.fill();
  }
  ctx.font = `bold ${fontSize}px Arial`;
  ctx.fillStyle = color;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, canvas.width / 2, canvas.height / 2);
  const tex = new THREE.CanvasTexture(canvas);
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false });
  const spr = new THREE.Sprite(mat);
  spr.scale.set((canvas.width / canvas.height) * scale, scale, 1);
  return spr;
}

function makeShopBoard(shopName) {
  const W = 256, H = 80;
  const canvas = document.createElement('canvas');
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#1565C0';
  ctx.beginPath(); ctx.roundRect(0, 0, W, H, 10); ctx.fill();
  ctx.strokeStyle = '#BBDEFB'; ctx.lineWidth = 3;
  ctx.beginPath(); ctx.roundRect(4, 4, W - 8, H - 8, 7); ctx.stroke();
  ctx.fillStyle = '#ffffff'; ctx.font = 'bold 36px Arial';
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(shopName, W / 2, H / 2);
  const tex = new THREE.CanvasTexture(canvas);
  const geo = new THREE.PlaneGeometry(2.0, 0.625);
  const mat = new THREE.MeshBasicMaterial({ map: tex, transparent: true, side: THREE.DoubleSide });
  return new THREE.Mesh(geo, mat);
}

function makeFloorLabel(text, width, fontSize = 36) {
  const canvas = document.createElement('canvas');
  canvas.width = 512; canvas.height = 128;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, 512, 128);
  ctx.fillStyle = 'rgba(255,255,255,0.15)'; ctx.fillRect(0, 0, 512, 128);
  ctx.fillStyle = '#ffffff'; ctx.font = `bold ${fontSize}px Arial`;
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(text, 256, 64);
  const tex = new THREE.CanvasTexture(canvas);
  const geo = new THREE.PlaneGeometry(width, width * (128 / 512));
  const mat = new THREE.MeshBasicMaterial({ map: tex, transparent: true, side: THREE.DoubleSide, depthWrite: false });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.rotation.x = -Math.PI / 2;
  return mesh;
}

// ── I-beam helper ──────────────────────────────────────────────────────────────
function makeIBeam(length, mat, orientation) {
  const group = new THREE.Group();
  if (orientation === 'vertical') {
    group.add(new THREE.Mesh(new THREE.BoxGeometry(IB_WEB, length, IB_FLANGE), mat));
    const fGeo = new THREE.BoxGeometry(IB_FLANGE, IB_FT, IB_FLANGE);
    const tf = new THREE.Mesh(fGeo, mat); tf.position.y =  length / 2 - IB_FT / 2; group.add(tf);
    const bf = new THREE.Mesh(fGeo, mat); bf.position.y = -(length / 2 - IB_FT / 2); group.add(bf);
  } else if (orientation === 'horizontal-x') {
    group.add(new THREE.Mesh(new THREE.BoxGeometry(length, IB_FLANGE, IB_WEB), mat));
    const fGeo = new THREE.BoxGeometry(length, IB_FT, IB_FLANGE);
    const tf = new THREE.Mesh(fGeo, mat); tf.position.y =  IB_FLANGE / 2 - IB_FT / 2; group.add(tf);
    const bf = new THREE.Mesh(fGeo, mat); bf.position.y = -(IB_FLANGE / 2 - IB_FT / 2); group.add(bf);
  } else {
    group.add(new THREE.Mesh(new THREE.BoxGeometry(IB_WEB, IB_FLANGE, length), mat));
    const fGeo = new THREE.BoxGeometry(IB_FLANGE, IB_FT, length);
    const tf = new THREE.Mesh(fGeo, mat); tf.position.y =  IB_FLANGE / 2 - IB_FT / 2; group.add(tf);
    const bf = new THREE.Mesh(fGeo, mat); bf.position.y = -(IB_FLANGE / 2 - IB_FT / 2); group.add(bf);
  }
  return group;
}

// ── Green path between cells ───────────────────────────────────────────────────
function buildZebraCrossing(cellCX, originZ, group) {
  const cellCZ = originZ + DEPTH / 2;
  const fillGeo = new THREE.PlaneGeometry(CELL_W - 0.1, ZEBRA_W - 0.08);
  const fillMat = new THREE.MeshBasicMaterial({ color: 0xa5d6a7, transparent: true, opacity: 0.7, side: THREE.DoubleSide });
  const fill = new THREE.Mesh(fillGeo, fillMat);
  fill.rotation.x = -Math.PI / 2;
  fill.position.set(cellCX, 0.19, cellCZ);
  group.add(fill);
  const borderMat = new THREE.MeshBasicMaterial({ color: 0x2e7d32, side: THREE.DoubleSide });
  const T = 0.08;
  [
    { geo: new THREE.PlaneGeometry(CELL_W, T), pos: [cellCX, 0.20, cellCZ - ZEBRA_W / 2 + T / 2] },
    { geo: new THREE.PlaneGeometry(CELL_W, T), pos: [cellCX, 0.20, cellCZ + ZEBRA_W / 2 - T / 2] },
    { geo: new THREE.PlaneGeometry(T, ZEBRA_W), pos: [cellCX - CELL_W / 2 + T / 2, 0.20, cellCZ] },
    { geo: new THREE.PlaneGeometry(T, ZEBRA_W), pos: [cellCX + CELL_W / 2 - T / 2, 0.20, cellCZ] },
  ].forEach(({ geo, pos }) => {
    const mesh = new THREE.Mesh(geo, borderMat);
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.set(...pos);
    group.add(mesh);
  });
}

// ── Cantilever sign — one per station cell ─────────────────────────────────────
// Rod attaches to front beam at cell centre, sticks out +Z toward viewer.
// Boards hang down from rod tip: [Station ID] [Z/E badge]
const ZE_SIGN_COLOR = {
  red:    { bg: '#b71c1c', text: '#ffffff' },
  yellow: { bg: '#d97706', text: '#ffffff' },
  green:  { bg: '#155724', text: '#a5d6a7' },
};

function makeCantileverSign(stnId, ze, zeStatus) {
  const group    = new THREE.Group();
  const rodLen   = 2.5;   // how far it sticks out in +Z
  const poleMat  = new THREE.MeshLambertMaterial({ color: 0x546e7a });

  // Horizontal cantilever rod pointing in +Z
  const rod = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.07, rodLen), poleMat);
  rod.position.set(0, 0, rodLen / 2);   // starts at column, extends outward
  group.add(rod);

  // Small vertical drop at rod tip to mount boards
  const dropH = 0.08;
  const drop  = new THREE.Mesh(new THREE.BoxGeometry(0.07, dropH, 0.07), poleMat);
  drop.position.set(0, -dropH / 2, rodLen);
  group.add(drop);

  // ── Station ID board ────────────────────────────────────────────────────────
  const idCW = 512, idCH = 256;
  const idCanvas = document.createElement('canvas');
  idCanvas.width = idCW; idCanvas.height = idCH;
  const ic = idCanvas.getContext('2d');
  const idBg = ze ? '#c62828' : '#1a237e';
  ic.fillStyle = idBg;
  ic.beginPath(); ic.roundRect(0, 0, idCW, idCH, 18); ic.fill();
  ic.strokeStyle = 'rgba(255,255,255,0.45)'; ic.lineWidth = 5;
  ic.beginPath(); ic.roundRect(7, 7, idCW - 14, idCH - 14, 13); ic.stroke();
  ic.fillStyle = '#ffffff';
  ic.font = 'bold 130px Arial';
  ic.textAlign = 'center'; ic.textBaseline = 'middle';
  ic.fillText(stnId, idCW / 2, idCH / 2);

  const idBoardW = 1.4, idBoardH = idBoardW * (idCH / idCW);
  const idMesh = new THREE.Mesh(
    new THREE.PlaneGeometry(idBoardW, idBoardH),
    new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(idCanvas), transparent: true, side: THREE.DoubleSide })
  );
  // Rotate 90° around Y so board faces sideways (parallel to rod, readable from aisle)
  // ID board starts close to column (low Z), Z/E goes beside it further out
  idMesh.rotation.y = Math.PI / 2;
  // ID board further along rod (higher Z = seen first from front camera)
  const zeBoardW = idBoardW * 0.5;
  const idStartZ = ze ? 0.15 + zeBoardW + 0.06 : 0.15;
  idMesh.position.set(0, -dropH - idBoardH / 2, idStartZ + idBoardW / 2);
  group.add(idMesh);

  // ── Z/E badge board — stacked below ID board ────────────────────────────────
  if (ze) {
    const zeCW = 256, zeCH = 256;
    const zeCanvas = document.createElement('canvas');
    zeCanvas.width = zeCW; zeCanvas.height = zeCH;
    const zc = zeCanvas.getContext('2d');
    const theme = ZE_SIGN_COLOR[zeStatus] || { bg: '#37474f', text: '#ffffff' };
    zc.fillStyle = theme.bg;
    zc.beginPath(); zc.roundRect(0, 0, zeCW, zeCH, 18); zc.fill();
    zc.strokeStyle = 'rgba(255,255,255,0.45)'; zc.lineWidth = 5;
    zc.beginPath(); zc.roundRect(7, 7, zeCW - 14, zeCH - 14, 13); zc.stroke();
    zc.fillStyle = theme.text;
    zc.font = 'bold 150px Arial';
    zc.textAlign = 'center'; zc.textBaseline = 'middle';
    zc.fillText(ze, zeCW / 2, zeCH / 2);

    const zeBoardH = zeBoardW;
    const zeMesh = new THREE.Mesh(
      new THREE.PlaneGeometry(zeBoardW, zeBoardH),
      new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(zeCanvas), transparent: true, side: THREE.DoubleSide })
    );
    zeMesh.rotation.y = Math.PI / 2;
    // Z/E closer to column (lower Z), ID is further out
    zeMesh.position.set(0, -dropH - idBoardH / 2, 0.15 + zeBoardW / 2);
    group.add(zeMesh);
  }

  return group;
}

// ── Station shell ──────────────────────────────────────────────────────────────
function buildStationShell(box, statusMap, zeMap, scene) {
  const group   = new THREE.Group();
  const count   = box.station_count || 1;
  const totalW  = count * CELL_W;
  const originX = (box.position_x || 0) * SCALE;
  const originZ = (box.position_y || 0) * SCALE;
  const structMat = new THREE.MeshLambertMaterial({ color: 0x78909c });

  // ── 4 corner columns ──
  [[originX, originZ], [originX + totalW, originZ],
   [originX, originZ + DEPTH], [originX + totalW, originZ + DEPTH]]
    .forEach(([cx, cz]) => {
      const col = makeIBeam(HEIGHT, structMat, 'vertical');
      col.position.set(cx, HEIGHT / 2, cz);
      group.add(col);
    });

  // ── Middle columns on FRONT and BACK faces only (door-frame look) ──
  // One middle column per cell boundary on front (Z=originZ) and back (Z=originZ+DEPTH)
  for (let i = 1; i < count; i++) {
    const mx = originX + i * CELL_W;
    [originZ, originZ + DEPTH].forEach(cz => {
      const col = makeIBeam(HEIGHT, structMat, 'vertical');
      col.position.set(mx, HEIGHT / 2, cz);
      group.add(col);
    });
  }

  // ── Top beams ──
  [
    { orient: 'horizontal-x', pos: [originX + totalW / 2, HEIGHT, originZ],         len: totalW },
    { orient: 'horizontal-x', pos: [originX + totalW / 2, HEIGHT, originZ + DEPTH], len: totalW },
    { orient: 'horizontal-z', pos: [originX,          HEIGHT, originZ + DEPTH / 2], len: DEPTH  },
    { orient: 'horizontal-z', pos: [originX + totalW, HEIGHT, originZ + DEPTH / 2], len: DEPTH  },
  ].forEach(({ orient, pos, len }) => {
    const beam = makeIBeam(len, structMat, orient);
    beam.position.set(...pos);
    group.add(beam);
  });

  // ── Per-cell: floor + status sphere + floor label + nameplate ──
  // Parse station_data for names and description
  let stationNames = [];
  let boxDesc      = '';
  try {
    const sd = JSON.parse(box.station_data || '{}');
    stationNames = Array.isArray(sd.__station_names__) ? sd.__station_names__ : [];
    boxDesc      = sd.__box_desc__ || '';
  } catch (_) {}

  const stationIds = (box.station_ids || '').split(',').map(s => s.trim()).filter(Boolean);

  for (let i = 0; i < count; i++) {
    const cellX  = originX + i * CELL_W;
    const cellCX = cellX + CELL_W / 2;
    const cellCZ = originZ + DEPTH / 2;
    const stnId  = stationIds[i] || `STN-${i + 1}`;
    const color  = STATUS_HEX[statusMap[stnId] || null] ?? STATUS_HEX.null;

    // Gray floor — full cell width
    const floor  = new THREE.Mesh(
      new THREE.BoxGeometry(CELL_W - 0.05, 0.18, DEPTH - 0.05),
      new THREE.MeshLambertMaterial({ color: 0xb0bec5, transparent: true, opacity: 0.80 })
    );
    floor.position.set(cellCX, 0.09, cellCZ);
    group.add(floor);

    // Green center path strip running through middle of this station
    buildZebraCrossing(cellCX, originZ, group);

    // Status sphere on top
    const sph = new THREE.Mesh(new THREE.SphereGeometry(0.22, 12, 12), new THREE.MeshLambertMaterial({ color }));
    sph.position.set(cellCX, HEIGHT + 0.35, cellCZ);
    group.add(sph);

    // Floor station-ID label
    if (stnId) {
      const lbl = makeFloorLabel(stnId, CELL_W * 0.65);
      lbl.position.set(cellCX, 0.02, cellCZ);
      group.add(lbl);
    }

    const stnName = stationNames[i] || '';

    // Z/E data from input records (via zeMap)
    const { ze = null, zeStatus = null } = zeMap[stnId] || {};

    // Cantilever rod + boards at front beam centre, sticking out toward viewer
    const sign = makeCantileverSign(stnId, ze, zeStatus);
    sign.position.set(cellCX, HEIGHT, originZ + DEPTH);
    group.add(sign);
  }

  // ── Single floating box name above the whole structure ──
  const nameSprite = makeLabel(box.name || 'Box', { fontSize: 52, color: '#1a237e', bgColor: 'rgba(255,255,255,0.85)', padding: 14, scale: 2.8 });
  nameSprite.position.set(originX + totalW / 2, HEIGHT + 1.3, originZ + DEPTH / 2);
  group.add(nameSprite);

  scene.add(group);
}

function buildWalkingPath(fromBox, toBox, scene) {
  const fW      = (fromBox.station_count || 1) * CELL_W;
  const fEndX   = (fromBox.position_x || 0) * SCALE + fW;
  const tStartX = (toBox.position_x || 0) * SCALE;
  const pathLen = tStartX - fEndX;
  if (pathLen <= 0.1) return;
  const pathCX = fEndX + pathLen / 2;
  const pathCZ = ((fromBox.position_y || 0) * SCALE) + DEPTH / 2;
  const floor  = new THREE.Mesh(
    new THREE.PlaneGeometry(pathLen, PATH_W),
    new THREE.MeshLambertMaterial({ color: 0xfdd835, transparent: true, opacity: 0.65, side: THREE.DoubleSide })
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(pathCX, 0.015, pathCZ);
  scene.add(floor);
  const stripeMat = new THREE.MeshBasicMaterial({ color: 0xff6f00 });
  const n = Math.max(1, Math.floor(pathLen / 1.2));
  for (let s = 0; s <= n; s++) {
    const sm = new THREE.Mesh(new THREE.PlaneGeometry(0.1, PATH_W), stripeMat);
    sm.rotation.x = -Math.PI / 2;
    sm.position.set(fEndX + (s / n) * pathLen, 0.02, pathCZ);
    scene.add(sm);
  }
  const wlbl = makeFloorLabel('WALKWAY', Math.min(pathLen * 0.8, 3.0), 40);
  wlbl.position.set(pathCX, 0.025, pathCZ);
  scene.add(wlbl);
}

// ── Walk mode controller ───────────────────────────────────────────────────────
class WalkController {
  constructor(camera) {
    this.camera = camera; this.keys = {}; this.speed = 0.08; this.yaw = 0; this.pitch = 0;
    this._onKey  = (e) => { this.keys[e.code] = e.type === 'keydown'; };
    this._onMove = (e) => this._mouseMove(e);
    document.addEventListener('keydown', this._onKey);
    document.addEventListener('keyup',   this._onKey);
  }
  attachMouseLook(canvas) { this._canvas = canvas; canvas.addEventListener('mousemove', this._onMove); canvas.requestPointerLock(); }
  detachMouseLook() { if (this._canvas) { this._canvas.removeEventListener('mousemove', this._onMove); this._canvas = null; } document.exitPointerLock(); }
  _mouseMove(e) {
    if (document.pointerLockElement !== this._canvas) return;
    this.yaw   -= e.movementX * 0.002;
    this.pitch -= e.movementY * 0.002;
    this.pitch  = Math.max(-Math.PI / 2.5, Math.min(Math.PI / 2.5, this.pitch));
  }
  update() {
    const { camera, keys } = this;
    camera.quaternion.setFromEuler(new THREE.Euler(this.pitch, this.yaw, 0, 'YXZ'));
    const dir = new THREE.Vector3();
    const fwd = new THREE.Vector3(-Math.sin(this.yaw), 0, -Math.cos(this.yaw));
    const rgt = new THREE.Vector3( Math.cos(this.yaw), 0, -Math.sin(this.yaw));
    if (keys['KeyW'] || keys['ArrowUp'])    dir.add(fwd);
    if (keys['KeyS'] || keys['ArrowDown'])  dir.sub(fwd);
    if (keys['KeyA'] || keys['ArrowLeft'])  dir.sub(rgt);
    if (keys['KeyD'] || keys['ArrowRight']) dir.add(rgt);
    if (dir.length() > 0) { dir.normalize().multiplyScalar(this.speed); camera.position.add(dir); camera.position.y = Math.max(1.6, camera.position.y); }
  }
  destroy() { document.removeEventListener('keydown', this._onKey); document.removeEventListener('keyup', this._onKey); this.detachMouseLook(); }
}

// ── Three.js scene hook ────────────────────────────────────────────────────────
function useThreeScene(canvasRef, layout, statusMap, zeMap, walkMode, onObjectsChange) {
  const sceneRef       = useRef(null);
  const rendererRef    = useRef(null);
  const cameraRef      = useRef(null);
  const orbitRef       = useRef(null);
  const walkRef        = useRef(null);
  const transformRef   = useRef(null);
  const rafRef         = useRef(null);
  const placedRef      = useRef([]);   // [{ id, mesh, labelSprite, name }]
  const selectedRef    = useRef(null);
  const sceneCenterRef = useRef(new THREE.Vector3(0, 0, 0));
  const sceneSpanRef   = useRef(20);
  const walkModeRef    = useRef(walkMode);
  useEffect(() => { walkModeRef.current = walkMode; }, [walkMode]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !layout) return;

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(canvas.clientWidth, canvas.clientHeight);
    renderer.setClearColor(0xf0f2f5);
    rendererRef.current = renderer;

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0xf0f2f5, 80, 250);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(60, canvas.clientWidth / canvas.clientHeight, 0.1, 300);
    cameraRef.current = camera;

    scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const dir = new THREE.DirectionalLight(0xffffff, 0.8);
    dir.position.set(20, 30, 20); scene.add(dir);
    scene.add(new THREE.GridHelper(200, 100, 0xb0bec5, 0xdde1e7));

    const boxes = layout.station_boxes || [];
    boxes.forEach(box => buildStationShell(box, statusMap, zeMap, scene));
    (layout.connections || []).forEach(conn => {
      const f = boxes.find(b => b.id === conn.from_box_id);
      const t = boxes.find(b => b.id === conn.to_box_id);
      if (f && t) buildWalkingPath(f, t, scene);
    });

    let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
    boxes.forEach(b => {
      const x0 = (b.position_x || 0) * SCALE, x1 = x0 + (b.station_count || 1) * CELL_W;
      const z0 = (b.position_y || 0) * SCALE, z1 = z0 + DEPTH;
      if (x0 < minX) minX = x0; if (x1 > maxX) maxX = x1;
      if (z0 < minZ) minZ = z0; if (z1 > maxZ) maxZ = z1;
    });
    if (boxes.length) {
      const cx = (minX + maxX) / 2, cz = (minZ + maxZ) / 2;
      const span = Math.max(maxX - minX, maxZ - minZ, 10);
      sceneCenterRef.current.set(cx, 0, cz);
      sceneSpanRef.current = span;
      camera.position.set(cx, span * 0.8, cz + span * 0.9);
      camera.lookAt(cx, 0, cz);
    } else {
      camera.position.set(0, 20, 30); camera.lookAt(0, 0, 0);
    }

    const orbit = new OrbitControls(camera, renderer.domElement);
    orbit.enableDamping = true; orbit.dampingFactor = 0.08;
    orbit.minDistance = 2; orbit.maxDistance = 200;
    orbitRef.current = orbit;

    // TransformControls
    const tc = new TransformControls(camera, renderer.domElement);
    tc.addEventListener('dragging-changed', (e) => { orbit.enabled = !e.value; });
    scene.add(tc);
    transformRef.current = tc;

    const walk = new WalkController(camera);
    walkRef.current = walk;

    // Restore previously placed objects from localStorage
    const saved = JSON.parse(localStorage.getItem(LS_KEY + '_' + layout.id) || '[]');
    // (geometry only — we can't restore loaded meshes, only positions for session)

    const ro = new ResizeObserver(() => {
      if (!canvas.clientWidth || !canvas.clientHeight) return;
      renderer.setSize(canvas.clientWidth, canvas.clientHeight);
      camera.aspect = canvas.clientWidth / canvas.clientHeight;
      camera.updateProjectionMatrix();
    });
    ro.observe(canvas);

    const animate = () => {
      rafRef.current = requestAnimationFrame(animate);
      if (walkModeRef.current) { walk.update(); orbit.enabled = false; }
      else { if (!tc.dragging) orbit.enabled = true; orbit.update(); }
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
      walk.destroy();
      tc.dispose();
      orbit.dispose();
      renderer.dispose();
      placedRef.current = [];
      selectedRef.current = null;
    };
  }, [canvasRef, layout, statusMap, zeMap]); // eslint-disable-line

  // Walk mode toggle
  useEffect(() => {
    const walk = walkRef.current, canvas = canvasRef.current, camera = cameraRef.current;
    if (!walk || !canvas || !camera) return;
    if (walkMode) { walk.yaw = 0; walk.pitch = 0; camera.position.y = 1.8; walk.attachMouseLook(canvas); }
    else { walk.detachMouseLook(); }
  }, [walkMode, canvasRef]);

  // Snap view
  const snapView = useCallback((view) => {
    const camera = cameraRef.current, orbit = orbitRef.current;
    if (!camera || !orbit) return;
    const c = sceneCenterRef.current, span = sceneSpanRef.current, d = span * 0.9;
    const presets = {
      top:   { pos: [c.x,     d * 1.4, c.z      ], up: [0, 0, -1] },
      front: { pos: [c.x,     d * 0.4, c.z + d  ], up: [0, 1,  0] },
      back:  { pos: [c.x,     d * 0.4, c.z - d  ], up: [0, 1,  0] },
      left:  { pos: [c.x - d, d * 0.4, c.z      ], up: [0, 1,  0] },
      right: { pos: [c.x + d, d * 0.4, c.z      ], up: [0, 1,  0] },
      '3d':  { pos: [c.x + d * 0.8, d * 0.8, c.z + d * 0.9], up: [0, 1, 0] },
    };
    const p = presets[view]; if (!p) return;
    camera.position.set(...p.pos);
    camera.up.set(...p.up);
    orbit.target.copy(c);
    orbit.update();
    camera.lookAt(c);
  }, []);

  // Set transform mode (translate / rotate / scale)
  const setTransformMode = useCallback((mode) => {
    if (transformRef.current) transformRef.current.setMode(mode);
  }, []);

  // Load and place a 3D object file
  const placeObject = useCallback((file, name, layoutId) => {
    const scene = sceneRef.current;
    if (!scene) return;
    const ext = file.name.split('.').pop().toLowerCase();
    const url  = URL.createObjectURL(file);

    const onLoaded = (obj) => {
      URL.revokeObjectURL(url);

      // Strip any existing text/label children from the loaded model
      obj.traverse(child => {
        if (child.isSprite || (child.material && child.material.map === null && child.isLine)) {
          child.visible = false;
        }
      });

      // Auto-scale to ~2m
      const bbox = new THREE.Box3().setFromObject(obj);
      const size = new THREE.Vector3();
      bbox.getSize(size);
      const maxDim = Math.max(size.x, size.y, size.z);
      if (maxDim > 0) obj.scale.setScalar(2.0 / maxDim);

      // Re-compute after scale and sit on floor (y=0)
      const bbox2 = new THREE.Box3().setFromObject(obj);
      obj.position.y = -bbox2.min.y;

      // Place at scene centre
      const c = sceneCenterRef.current;
      obj.position.x = c.x;
      obj.position.z = c.z;

      obj.userData.isPlaced = true;
      obj.userData.objId    = Date.now().toString();
      obj.userData.objName  = name;

      scene.add(obj);

      const entry = { id: obj.userData.objId, mesh: obj, label: null, name };
      placedRef.current = [...placedRef.current, entry];

      // Select immediately and set mode to translate
      if (transformRef.current) {
        transformRef.current.setMode('translate');
        transformRef.current.attach(obj);
        selectedRef.current = entry;
      }

      onObjectsChange([...placedRef.current]);
    };

    if (ext === 'glb' || ext === 'gltf') {
      new GLTFLoader().load(url, (gltf) => onLoaded(gltf.scene));
    } else if (ext === 'obj') {
      new OBJLoader().load(url, onLoaded);
    }
  }, [onObjectsChange]); // eslint-disable-line

  // Select object by click on canvas
  const handleCanvasClick = useCallback((e) => {
    const canvas = canvasRef.current, camera = cameraRef.current, scene = sceneRef.current;
    if (!canvas || !camera || !scene || walkModeRef.current) return;
    const rect   = canvas.getBoundingClientRect();
    const mouse  = new THREE.Vector2(
      ((e.clientX - rect.left) / rect.width)  *  2 - 1,
      ((e.clientY - rect.top)  / rect.height) * -2 + 1
    );
    const ray    = new THREE.Raycaster();
    ray.setFromCamera(mouse, camera);
    const placed = placedRef.current.map(p => p.mesh);
    const hits   = ray.intersectObjects(placed, true);
    if (hits.length > 0) {
      let obj = hits[0].object;
      while (obj.parent && !obj.userData.isPlaced) obj = obj.parent;
      const entry = placedRef.current.find(p => p.mesh === obj);
      if (entry) {
        selectedRef.current = entry;
        if (transformRef.current) transformRef.current.attach(obj);
      }
    } else {
      // Deselect if clicked empty space
      if (transformRef.current) transformRef.current.detach();
      selectedRef.current = null;
    }
    onObjectsChange([...placedRef.current]);
  }, [canvasRef, onObjectsChange]);

  // Select object by id (called from panel)
  const selectById = useCallback((id) => {
    const entry = placedRef.current.find(p => p.id === id);
    if (!entry) return;
    selectedRef.current = entry;
    if (transformRef.current) {
      transformRef.current.attach(entry.mesh);
    }
    onObjectsChange([...placedRef.current]);
  }, [onObjectsChange]);

  // Delete object by id
  const deleteById = useCallback((id) => {
    const scene = sceneRef.current;
    const entry = placedRef.current.find(p => p.id === id);
    if (!entry || !scene) return;
    if (transformRef.current && selectedRef.current?.id === id) transformRef.current.detach();
    scene.remove(entry.mesh);
    if (entry.label) scene.remove(entry.label);
    placedRef.current = placedRef.current.filter(p => p.id !== id);
    if (selectedRef.current?.id === id) selectedRef.current = null;
    onObjectsChange([...placedRef.current]);
  }, [onObjectsChange]);

  // Rename label by id
  const renameById = useCallback((id, newName) => {
    const scene = sceneRef.current;
    const entry = placedRef.current.find(p => p.id === id);
    if (!entry || !scene) return;
    entry.name = newName;
    entry.mesh.userData.objName = newName;
    if (entry.label) scene.remove(entry.label);
    const lbl = makeLabel(newName, { fontSize: 44, color: '#ffff00', bgColor: 'rgba(0,0,0,0.7)', padding: 10, scale: 1.8 });
    lbl.userData.isLabel  = true;
    lbl.userData.parentId = id;
    scene.add(lbl);
    entry.label = lbl;
    onObjectsChange([...placedRef.current]);
  }, [onObjectsChange]);

  // Label follows mesh position
  useEffect(() => {
    const tid = setInterval(() => {
      placedRef.current.forEach(({ mesh, label }) => {
        if (mesh && label) {
          const box = new THREE.Box3().setFromObject(mesh);
          label.position.set(mesh.position.x, box.max.y + 0.6, mesh.position.z);
        }
      });
    }, 50);
    return () => clearInterval(tid);
  }, []);

  return { snapView, setTransformMode, placeObject, handleCanvasClick, selectById, deleteById, renameById };
}

// ── Compute Z/E status per station from input records (mirrors ZStageDashboard logic) ──
function computeZeMap(records) {
  const stationIds = [...new Set(records.map(r => r.stage_no).filter(Boolean))];
  const map = {};
  for (const sid of stationIds) {
    const sr    = records.filter(r => r.stage_no === sid);
    const eRecs = sr.filter(r => r.z_e === 'E');
    const zRecs = sr.filter(r => r.z_e === 'Z');
    let ze = null, zeStatus = null;
    if (eRecs.length > 0) {
      ze = 'E';
      if (eRecs.filter(r => r.status_3m === 'R').some(r => (r.total_incidences || 0) > 0)) zeStatus = 'red';
      else if (eRecs.filter(r => r.status_3m === 'Y').some(r => (r.total_incidences || 0) > 0)) zeStatus = 'yellow';
      else zeStatus = 'green';
    } else if (zRecs.length > 0) {
      ze = 'Z';
      if (zRecs.filter(r => r.status_3m === 'R').some(r => (r.total_incidences || 0) > 0)) zeStatus = 'red';
      else if (zRecs.filter(r => r.status_3m === 'Y').some(r => (r.total_incidences || 0) > 0)) zeStatus = 'yellow';
      else zeStatus = 'green';
    }
    if (ze) map[sid] = { ze, zeStatus };
  }
  return map;
}

function saveToLS(layoutId) {
  // Save object metadata (name + position) — mesh can't be serialised
  // Full save would need backend; this is session persistence via localStorage
}

// ── Main component ─────────────────────────────────────────────────────────────
function ZStage3DLayout({ userId, savedLayouts = [], activeLayoutId, isActive }) {
  const canvasRef          = useRef(null);
  const fileInputRef       = useRef(null);
  const [selectedLayoutId, setSelectedLayoutId] = useState(null);
  const [layout,    setLayout]    = useState(null);
  const [statusMap, setStatusMap] = useState({});
  const [zeMap,     setZeMap]     = useState({});
  const [walkMode,  setWalkMode]  = useState(false);
  const [placedObjects, setPlacedObjects] = useState([]);
  const [selectedId,    setSelectedId]    = useState(null);
  const [transformMode, setTransformModeState] = useState('translate');
  const [renameVal,     setRenameVal]     = useState('');
  const [showObjPanel,  setShowObjPanel]  = useState(false);

  useEffect(() => {
    if (activeLayoutId && !selectedLayoutId) setSelectedLayoutId(activeLayoutId);
  }, [activeLayoutId]); // eslint-disable-line

  useEffect(() => {
    if (!selectedLayoutId) return;
    layoutApi.getLayout(selectedLayoutId).then(res => setLayout(res.data)).catch(() => {});
  }, [selectedLayoutId]);

  useEffect(() => {
    if (!layout) return;
    const map = {};
    (layout.station_boxes || []).forEach(box => {
      (box.station_ids || '').split(',').forEach(id => {
        const sid = id.trim(); if (!sid) return;
        try { const d = JSON.parse(box.station_data || '{}'); if (d[sid]) map[sid] = d[sid].status || null; } catch (_) {}
      });
    });
    setStatusMap(map);

    // Fetch input records to compute Z/E status per station
    if (userId && layout.id) {
      inputApi.getRecords(userId, layout.id)
        .then(res => setZeMap(computeZeMap(Array.isArray(res.data) ? res.data : [])))
        .catch(() => setZeMap({}));
    }
  }, [layout, userId]);

  const onObjectsChange = useCallback((objs) => {
    setPlacedObjects(objs);
  }, []);

  const { snapView, setTransformMode, placeObject, handleCanvasClick, selectById, deleteById, renameById } =
    useThreeScene(canvasRef, layout, statusMap, zeMap, walkMode, onObjectsChange);

  const handleLayoutChange = useCallback((e) => {
    setSelectedLayoutId(Number(e.target.value) || null);
    setLayout(null); setWalkMode(false); setPlacedObjects([]); setSelectedId(null);
  }, []);

  const handleFileUpload = useCallback((e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const name = file.name.replace(/\.[^/.]+$/, '');
    placeObject(file, name, selectedLayoutId);
    setShowObjPanel(true);
    e.target.value = '';
  }, [placeObject, selectedLayoutId]);

  const handleModeChange = useCallback((mode) => {
    setTransformModeState(mode);
    setTransformMode(mode);
  }, [setTransformMode]);

  const handleSelect = useCallback((id) => {
    setSelectedId(id);
    setRenameVal(placedObjects.find(o => o.id === id)?.name || '');
    selectById(id);
  }, [placedObjects, selectById]);

  const handleDelete = useCallback((id) => {
    deleteById(id);
    if (selectedId === id) setSelectedId(null);
  }, [deleteById, selectedId]);

  const handleRename = useCallback(() => {
    if (!renameVal.trim() || !selectedId) return;
    renameById(selectedId, renameVal.trim());
  }, [renameVal, renameById, selectedId]);

  const currentSelected = placedObjects.find(o => o.id === selectedId);

  return (
    <div className="z3d-root">
      {/* ── Toolbar ── */}
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
              {['3D','Top','Front','Back','Left','Right'].map(v => (
                <button key={v} className="z3d-view-btn" onClick={() => snapView(v.toLowerCase())}>{v}</button>
              ))}
            </div>

            {/* Upload object */}
            <button className="z3d-upload-btn" onClick={() => fileInputRef.current?.click()} title="Upload GLB or OBJ file">
              ⬆ Upload Object
            </button>
            <input ref={fileInputRef} type="file" accept=".glb,.gltf,.obj" style={{ display: 'none' }} onChange={handleFileUpload} />

            {/* Object list toggle */}
            <button className={`z3d-walk-btn${showObjPanel ? ' z3d-walk-btn--active' : ''}`} onClick={() => setShowObjPanel(v => !v)}>
              📦 Objects {placedObjects.length > 0 && `(${placedObjects.length})`}
            </button>

            {/* Walk mode */}
            <button className={`z3d-walk-btn${walkMode ? ' z3d-walk-btn--active' : ''}`} onClick={() => setWalkMode(v => !v)}>
              {walkMode ? '🧍 Exit Walk' : '🚶 Walk Mode'}
            </button>
          </>
        )}

        <div className="z3d-legend">
          <span className="z3d-legend-item"><span className="z3d-legend-dot z3d-legend-dot--r"/>Red</span>
          <span className="z3d-legend-item"><span className="z3d-legend-dot z3d-legend-dot--y"/>Yellow</span>
          <span className="z3d-legend-item"><span className="z3d-legend-dot z3d-legend-dot--g"/>Green</span>
          <span className="z3d-legend-item"><span className="z3d-legend-dot z3d-legend-dot--na"/>N/A</span>
          <span className="z3d-legend-item"><span className="z3d-legend-dot z3d-legend-dot--path"/>Path</span>
        </div>
      </div>

      <div className="z3d-body">
        {/* ── Object panel (left sidebar) ── */}
        {showObjPanel && layout && (
          <div className="z3d-obj-panel">
            <div className="z3d-obj-panel-title">Placed Objects</div>

            {/* Transform mode */}
            {currentSelected && (
              <div className="z3d-transform-group">
                {[['translate','Move'],['rotate','Rotate'],['scale','Scale']].map(([m, lbl]) => (
                  <button
                    key={m}
                    className={`z3d-transform-btn${transformMode === m ? ' z3d-transform-btn--active' : ''}`}
                    onClick={() => handleModeChange(m)}
                  >{lbl}</button>
                ))}
              </div>
            )}

            {/* Rename */}
            {currentSelected && (
              <div className="z3d-rename-row">
                <input
                  className="z3d-rename-input"
                  value={renameVal}
                  onChange={e => setRenameVal(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleRename()}
                  placeholder="Label name"
                />
                <button className="z3d-rename-btn" onClick={handleRename}>✓</button>
              </div>
            )}

            {/* Object list */}
            <div className="z3d-obj-list">
              {placedObjects.length === 0 && <div className="z3d-obj-empty">No objects placed yet</div>}
              {placedObjects.map(obj => (
                <div
                  key={obj.id}
                  className={`z3d-obj-item${selectedId === obj.id ? ' z3d-obj-item--active' : ''}`}
                  onClick={() => handleSelect(obj.id)}
                >
                  <span className="z3d-obj-icon">📦</span>
                  <span className="z3d-obj-name">{obj.name}</span>
                  <button
                    className="z3d-obj-del"
                    title="Delete"
                    onClick={e => { e.stopPropagation(); handleDelete(obj.id); }}
                  >✕</button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Canvas area ── */}
        <div className="z3d-canvas-wrapper">
          {!layout ? (
            <div className="z3d-placeholder">
              <span className="z3d-placeholder-icon">🏭</span>
              <span>{savedLayouts.length === 0 ? 'No layouts saved yet' : 'Select a layout to view the 3D scene'}</span>
            </div>
          ) : (
            <>
              <canvas ref={canvasRef} className="z3d-canvas" onClick={handleCanvasClick} />
              <div className="z3d-walk-hint">
                {walkMode
                  ? 'WASD / Arrow keys to move · Mouse to look · Click canvas to capture mouse'
                  : currentSelected
                    ? 'Drag handles to move · Click empty space to deselect'
                    : 'Left drag to orbit · Scroll to zoom · Click object to select'}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default ZStage3DLayout;
