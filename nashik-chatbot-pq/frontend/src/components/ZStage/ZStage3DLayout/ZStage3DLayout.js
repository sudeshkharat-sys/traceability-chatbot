import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { TransformControls } from 'three/examples/jsm/controls/TransformControls';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader';
import { VRMLLoader } from 'three/examples/jsm/loaders/VRMLLoader';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader';
import { RefreshCw } from 'lucide-react';
import { layoutApi, inputApi } from '../../../services/api/layoutApi';
import { layeredAuditApi } from '../../../services/api/layoutApi';
import { StationDetailModal, MONTHLY_KEYS } from '../ZStageDashboard/ZStageDashboard';
import '../ZStageDashboard/ZStageDashboard.css';
import { backend_url } from '../../../services/api/config';
import './ZStage3DLayout.css';

// GLTFLoader pre-wired with DRACOLoader so Blender-compressed GLB files load correctly.
// Draco decoder WASM is served from the Three.js CDN (no local copy needed).
function makeGLTFLoader() {
  const draco = new DRACOLoader();
  draco.setDecoderPath('https://unpkg.com/three@0.168.0/examples/jsm/libs/draco/');
  const loader = new GLTFLoader();
  loader.setDRACOLoader(draco);
  return loader;
}

// Clone a Three.js object sharing geometry + material buffers (no deep copy).
// Avoids the N×fileSize GPU cost of clone(true) for line-placement groups.
function sharedClone(src) {
  const dst = src.clone(false); // shallow — does NOT copy geometry/material
  dst.copy(src, false);
  src.children.forEach(child => dst.add(sharedClone(child)));
  return dst;
}

// ── Constants ──────────────────────────────────────────────────────────────────
const SCALE      = 0.04;
const CELL_W     = 6.0;   // station box width
const DEPTH      = 6.0;   // station box depth — square-ish box, NOT tunnel
const HEIGHT     = 5.0;   // column height
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
// Solid rectangular column / beam — single filled box, no I-shape.
// "vertical"     — square post along Y
// "horizontal-x" — rectangular bar along X
// "horizontal-z" — rectangular bar along Z
const COL_W = 0.35;  // column / beam cross-section width
const COL_H = 0.22;  // beam cross-section height (thinner for horizontal)
function makeIBeam(length, mat, orientation) {
  let geo;
  if (orientation === 'vertical')     geo = new THREE.BoxGeometry(COL_W, length, COL_W);
  else if (orientation === 'horizontal-x') geo = new THREE.BoxGeometry(length, COL_H, COL_W);
  else                                geo = new THREE.BoxGeometry(COL_W, COL_H, length);
  return new THREE.Mesh(geo, mat);
}

// ── Green center strip inside each station cell ────────────────────────────────
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

// Creates a double-sided board readable from both +X and -X faces
function makeDoubleSidedBoard(canvas, boardW, boardH) {
  const group = new THREE.Group();

  // Front face (readable from -X, looking in +X direction)
  const texF = new THREE.CanvasTexture(canvas);
  const front = new THREE.Mesh(
    new THREE.PlaneGeometry(boardW, boardH),
    new THREE.MeshBasicMaterial({ map: texF, transparent: true, side: THREE.FrontSide })
  );
  group.add(front);

  // Back face — pre-mirror canvas so text is readable from +X side too
  const flipped = document.createElement('canvas');
  flipped.width = canvas.width; flipped.height = canvas.height;
  const ctx2 = flipped.getContext('2d');
  ctx2.translate(canvas.width, 0); ctx2.scale(-1, 1);
  ctx2.drawImage(canvas, 0, 0);
  const texB = new THREE.CanvasTexture(flipped);
  const back = new THREE.Mesh(
    new THREE.PlaneGeometry(boardW, boardH),
    new THREE.MeshBasicMaterial({ map: texB, transparent: true, side: THREE.BackSide })
  );
  group.add(back);

  return group;
}

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
  const idBg = '#1a237e';
  ic.fillStyle = idBg;
  ic.beginPath(); ic.roundRect(0, 0, idCW, idCH, 18); ic.fill();
  ic.strokeStyle = 'rgba(255,255,255,0.45)'; ic.lineWidth = 5;
  ic.beginPath(); ic.roundRect(7, 7, idCW - 14, idCH - 14, 13); ic.stroke();
  ic.fillStyle = '#ffffff';
  ic.font = 'bold 130px Arial';
  ic.textAlign = 'center'; ic.textBaseline = 'middle';
  ic.fillText(stnId, idCW / 2, idCH / 2);

  const idBoardW = 1.4, idBoardH = idBoardW * (idCH / idCW);
  const zeBoardW = idBoardW * 0.5;
  const idCentreZ = ze ? (0.55 + idBoardW / 2) : (rodLen / 2);
  const idBoard = makeDoubleSidedBoard(idCanvas, idBoardW, idBoardH);
  idBoard.rotation.y = Math.PI / 2;
  idBoard.position.set(0, -dropH - idBoardH / 2, idCentreZ);
  group.add(idBoard);

  // ── Z/E badge board ──────────────────────────────────────────────────────────
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
    const zeBoard = makeDoubleSidedBoard(zeCanvas, zeBoardW, zeBoardH);
    zeBoard.rotation.y = Math.PI / 2;
    zeBoard.position.set(0, -dropH - idBoardH / 2, 0.55 + idBoardW + 0.06 + zeBoardW / 2);
    group.add(zeBoard);
  }

  return group;
}

// ── Station shell ──────────────────────────────────────────────────────────────
function buildStationShell(box, statusMap, zeMap, scene) {
  const group   = new THREE.Group();
  const count   = box.station_count || 1;
  const totalW  = count * CELL_W;
  const originX = box._x3d ?? (box.position_x || 0) * SCALE;
  const originZ = box._z3d ?? (box.position_y || 0) * SCALE;
  // Steel-look: dark blue-grey with specular highlight via Phong
  const structMat = new THREE.MeshPhongMaterial({
    color: 0x546e7a, specular: 0x90a4ae, shininess: 60,
  });

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

    // Concrete-look floor — solid dark grey
    const floor  = new THREE.Mesh(
      new THREE.BoxGeometry(CELL_W - 0.05, 0.15, DEPTH - 0.05),
      new THREE.MeshPhongMaterial({ color: 0x455a64, specular: 0x607d8b, shininess: 20 })
    );
    floor.position.set(cellCX, 0.09, cellCZ);
    floor.userData.stationId = stnId;
    group.add(floor);

    // Green center path strip running through middle of this station
    buildZebraCrossing(cellCX, originZ, group);

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
    sign.traverse(child => { child.userData.stationId = stnId; });
    sign.position.set(cellCX, HEIGHT, originZ + DEPTH);
    group.add(sign);
  }

  // ── Box name boards on outer face of end columns, hanging from top beam ──
  // White bg + navy text; top edge flush with top beam at HEIGHT
  const boxLabel = box.name || 'Box';
  const bW = 512, bH = 128;
  const bCanvas = document.createElement('canvas');
  bCanvas.width = bW; bCanvas.height = bH;
  const bc = bCanvas.getContext('2d');
  bc.fillStyle = '#ffffff';
  bc.beginPath(); bc.roundRect(0, 0, bW, bH, 14); bc.fill();
  bc.strokeStyle = '#1a237e'; bc.lineWidth = 6;
  bc.beginPath(); bc.roundRect(5, 5, bW - 10, bH - 10, 10); bc.stroke();
  bc.fillStyle = '#1a237e'; bc.font = 'bold 68px Arial';
  bc.textAlign = 'center'; bc.textBaseline = 'middle';
  bc.fillText(boxLabel, bW / 2, bH / 2);
  const boardW3d = 3.5;
  const boardH3d = boardW3d * (bH / bW);
  [originX, originX + totalW].forEach((colX, side) => {
    const board = makeDoubleSidedBoard(bCanvas, boardW3d, boardH3d);
    board.rotation.y = side === 0 ? -Math.PI / 2 : Math.PI / 2;
    board.position.set(colX, HEIGHT - boardH3d / 2, originZ + DEPTH / 2);
    group.add(board);
  });

  scene.add(group);
}

// ── Dotted green path between station boxes ────────────────────────────────────
function buildWalkingPath(fromBox, toBox, scene) {
  const fx0 = fromBox._x3d ?? (fromBox.position_x || 0) * SCALE;
  const fx1 = fx0 + (fromBox.station_count || 1) * CELL_W;
  const fz0 = fromBox._z3d ?? (fromBox.position_y || 0) * SCALE;
  const fz1 = fz0 + DEPTH;
  const fCX = (fx0 + fx1) / 2, fCZ = (fz0 + fz1) / 2;

  const tx0 = toBox._x3d ?? (toBox.position_x || 0) * SCALE;
  const tx1 = tx0 + (toBox.station_count || 1) * CELL_W;
  const tz0 = toBox._z3d ?? (toBox.position_y || 0) * SCALE;
  const tz1 = tz0 + DEPTH;
  const tCX = (tx0 + tx1) / 2, tCZ = (tz0 + tz1) / 2;

  const Y = 0.05; // just above floor
  const dashMat = new THREE.LineDashedMaterial({
    color: 0x00e676,
    dashSize: 0.55,
    gapSize:  0.30,
    linewidth: 2,
  });

  const addLine = (points) => {
    const geo = new THREE.BufferGeometry().setFromPoints(points);
    const line = new THREE.Line(geo, dashMat);
    line.computeLineDistances();
    scene.add(line);
  };

  const sameRow = Math.abs(fCZ - tCZ) < 1.0;
  const sameCol = Math.abs(fCX - tCX) < 1.0;

  if (sameRow) {
    const x0 = Math.min(fx1, tx1), x1 = Math.max(fx0, tx0);
    if (x1 > x0) addLine([new THREE.Vector3(x0, Y, fCZ), new THREE.Vector3(x1, Y, fCZ)]);
  } else if (sameCol) {
    const z0 = Math.min(fz1, tz1), z1 = Math.max(fz0, tz0);
    if (z1 > z0) addLine([new THREE.Vector3(fCX, Y, z0), new THREE.Vector3(fCX, Y, z1)]);
  } else {
    const aisleNear = Math.min(fz1, tz1);
    const aisleFar  = Math.max(fz0, tz0);
    if (aisleFar > aisleNear) {
      const aisleMid = (aisleNear + aisleFar) / 2;
      // L-path: vertical from from-box edge → aisle, then horizontal, then vertical to to-box edge
      addLine([
        new THREE.Vector3(fCX, Y, fCZ > aisleMid ? fz0 : fz1),
        new THREE.Vector3(fCX, Y, aisleMid),
        new THREE.Vector3(tCX, Y, aisleMid),
        new THREE.Vector3(tCX, Y, tCZ > aisleMid ? tz0 : tz1),
      ]);
    } else {
      // Overlapping Z — simple L through centres
      addLine([
        new THREE.Vector3(fCX, Y, fCZ),
        new THREE.Vector3(tCX, Y, fCZ),
        new THREE.Vector3(tCX, Y, tCZ),
      ]);
    }
  }
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
function useThreeScene(canvasRef, layout, statusMapProp, zeMapProp, walkMode, onObjectsChange, onConvertStart, onConvertEnd, onStationClick, isActive, onSceneReady) {
  // Keep latest statusMap/zeMap in refs so scene reads current values
  // without triggering a full scene rebuild on every API response
  const statusMapRef = useRef(statusMapProp);
  const zeMapRef     = useRef(zeMapProp);
  useEffect(() => { statusMapRef.current = statusMapProp; }, [statusMapProp]);
  useEffect(() => { zeMapRef.current     = zeMapProp;     }, [zeMapProp]);
  const sceneRef       = useRef(null);
  const rendererRef    = useRef(null);
  const cameraRef      = useRef(null);
  const orbitRef       = useRef(null);
  const walkRef        = useRef(null);
  const transformRef   = useRef(null);
  const rafRef         = useRef(null);
  const placedRef      = useRef([]);   // [{ id, mesh, labelSprite, name, stationId }]
  const selectedRef    = useRef(null);
  const sceneCenterRef = useRef(new THREE.Vector3(0, 0, 0));
  const sceneSpanRef   = useRef(20);
  const walkModeRef    = useRef(walkMode);
  const layoutIdRef    = useRef(null);   // kept in sync by the scene effect
  const stationPosRef  = useRef({});     // stationId → { x, z, shopName }
  const animationsRef  = useRef([]);     // active tweens
  const blobCacheRef   = useRef({});     // objId → Blob — keeps file data alive across IDB updates
  useEffect(() => { walkModeRef.current = walkMode; }, [walkMode]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !layout) return;

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    // Guard against 0×0 when tab is hidden — ResizeObserver will correct once visible
    renderer.setSize(Math.max(1, canvas.clientWidth), Math.max(1, canvas.clientHeight));
    renderer.setClearColor(0xf0f2f5);
    rendererRef.current = renderer;

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0xf0f2f5, 80, 250);
    sceneRef.current = scene;

    const aspect = canvas.clientWidth && canvas.clientHeight
      ? canvas.clientWidth / canvas.clientHeight : 1;
    const camera = new THREE.PerspectiveCamera(60, aspect, 0.1, 300);
    cameraRef.current = camera;

    scene.add(new THREE.AmbientLight(0xffffff, 0.55));
    const dir = new THREE.DirectionalLight(0xffffff, 1.1);
    dir.position.set(20, 40, 25); scene.add(dir);
    // Fill light from opposite side to reduce harsh shadows
    const fill = new THREE.DirectionalLight(0xdce8ff, 0.35);
    fill.position.set(-20, 10, -20); scene.add(fill);
    scene.add(new THREE.GridHelper(200, 100, 0xb0bec5, 0xdde1e7));

    const boxes = layout.station_boxes || [];

    // Scale 2D canvas positions proportionally into 3D, but enforce a minimum
    // gap of 2 × CELL_W (two station-id cells) between any two adjacent boxes.
    const GRID_2D  = 40;
    const BOX_H_2D = 5 * GRID_2D; // 200px
    const scaleX   = CELL_W / (GRID_2D * 1.5);  // ~0.10 — compressed to bring boxes closer in x
    const scaleZ   = DEPTH  / BOX_H_2D; // 0.03
    const MIN_GAP  = CELL_W * 1.5;  // minimum clearance = 1.5 station-id cell widths

    // Group boxes into rows using floor(position_y / BOX_H_2D) — any two boxes
    // within the same 200px band (one box-height) are treated as the same row.
    // This is more robust than snapping to 40px grid which fails when boxes in
    // the same visual row differ by more than 20px in position_y.
    const rowBand  = v => Math.floor((v || 0) / BOX_H_2D);
    // Representative y for each band = band index * BOX_H_2D
    const bandSet  = [...new Set(boxes.map(b => rowBand(b.position_y)))].sort((a, b) => a - b);

    const zMap = {};   // keyed by band index
    let curZ = 0;
    bandSet.forEach((band, i) => {
      zMap[band] = curZ;
      if (i < bandSet.length - 1) {
        const scaledStep = (bandSet[i + 1] - band) * BOX_H_2D * scaleZ; // = (bandDiff) * DEPTH
        curZ += Math.max(scaledStep, DEPTH + MIN_GAP);
      }
    });

    const layoutBoxes = boxes.map(b => ({
      ...b,
      _x3d: (b.position_x || 0) * scaleX,
      _z3d: zMap[rowBand(b.position_y)] ?? 0,
    }));

    layoutBoxes.forEach(box => buildStationShell(box, statusMapRef.current, zeMapRef.current, scene));

    // Build station-position lookup for snap placement & animation waypoints
    const stationPosMap = {};
    layoutBoxes.forEach(box => {
      const cnt    = box.station_count || 1;
      const oX     = box._x3d;
      const oZ     = box._z3d;
      const stnIds = (box.station_ids || '').split(',').map(s => s.trim()).filter(Boolean);
      for (let i = 0; i < cnt; i++) {
        const sid = stnIds[i] || `STN-${i + 1}`;
        stationPosMap[sid] = { x: oX + i * CELL_W + CELL_W / 2, z: oZ + DEPTH / 2, shopName: box.name || '' };
      }
    });
    stationPosRef.current = stationPosMap;

    (layout.connections || []).forEach(conn => {
      const f = layoutBoxes.find(b => b.id === conn.from_box_id);
      const t = layoutBoxes.find(b => b.id === conn.to_box_id);
      if (f && t) buildWalkingPath(f, t, scene);
    });

    let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
    layoutBoxes.forEach(b => {
      const x0 = b._x3d, x1 = x0 + (b.station_count || 1) * CELL_W;
      const z0 = b._z3d, z1 = z0 + DEPTH;
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
    tc.addEventListener('dragging-changed', (e) => {
      orbit.enabled = !e.value;
      // Drag finished — persist updated transform to IDB (include blob so object survives reload)
      if (!e.value && selectedRef.current && layoutIdRef.current) {
        const { mesh, id, name, lineGroupId } = selectedRef.current;
        z3dPut({
          key: `${layoutIdRef.current}_${id}`,
          layoutId: layoutIdRef.current,
          id, name,
          ext: mesh.userData.objExt || 'glb',
          fileBlob: blobCacheRef.current[id] || undefined,
          lineGroupId: lineGroupId || null,
          px: mesh.position.x, py: mesh.position.y, pz: mesh.position.z,
          rx: mesh.rotation.x, ry: mesh.rotation.y, rz: mesh.rotation.z,
          sx: mesh.scale.x,    sy: mesh.scale.y,    sz: mesh.scale.z,
        });
      }
    });
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

    // Track current layoutId for IDB saves inside event handlers
    layoutIdRef.current = layout.id;

    // Reload previously saved placed objects from IDB.
    // Group records by lineGroupId (or individual id) so each unique GLB blob
    // is parsed only ONCE, then shallow-cloned for every station — avoids
    // parsing a 70 MB file N times for a line-placement group.
    z3dGetAll(layout.id).then(saved => {
      // Build groups: lineGroupId -> [record, ...] or individual records
      const groups = new Map();
      saved.forEach(record => {
        const gKey = record.lineGroupId || record.id;
        if (!groups.has(gKey)) groups.set(gKey, []);
        groups.get(gKey).push(record);
      });

      groups.forEach(records => {
        const first = records[0];
        const blob  = first.fileBlob;
        if (!blob) return;
        const ext = first.ext || 'glb';
        const url = URL.createObjectURL(blob);

        const applyRecord = (template, record) => {
          // Clone for every record after the first so geometry buffers are shared
          const obj = record === first ? template : sharedClone(template);
          obj.traverse(child => {
            if (child.isSprite || (child.material && child.material.map === null && child.isLine)) child.visible = false;
          });
          obj.position.set(record.px ?? 0, record.py ?? 0, record.pz ?? 0);
          obj.rotation.set(record.rx ?? 0, record.ry ?? 0, record.rz ?? 0);
          obj.scale.set(record.sx ?? 1,    record.sy ?? 1,    record.sz ?? 1);
          obj.userData.isPlaced   = true;
          obj.userData.objId      = record.id;
          obj.userData.objName    = record.name;
          obj.userData.objExt     = ext;
          blobCacheRef.current[record.id] = blob;
          scene.add(obj);
          const entry = {
            id: record.id, mesh: obj, label: null, name: record.name,
            stationId: record.stationId || null,
            lineGroupId: record.lineGroupId || null,
          };
          placedRef.current = [...placedRef.current, entry];
          onObjectsChange([...placedRef.current]);
        };

        const onTemplate = (template) => {
          URL.revokeObjectURL(url);
          records.forEach(record => applyRecord(template, record));
        };

        try {
          if (ext === 'glb' || ext === 'gltf') makeGLTFLoader().load(url, g => onTemplate(g.scene), undefined, (err) => console.error('[Z3D] GLB reload failed:', err));
          else if (ext === 'obj') new OBJLoader().load(url, onTemplate);
          else if (ext === 'stl') new STLLoader().load(url, geo => {
            geo.computeVertexNormals();
            onTemplate(new THREE.Mesh(geo, new THREE.MeshLambertMaterial({ color: 0x90a4ae })));
          });
        } catch {}
      });
    });

    // Signal that the scene is built and ready to display
    onSceneReady && onSceneReady();

    const animate = () => {
      rafRef.current = requestAnimationFrame(animate);
      try {
        if (walkModeRef.current) { walk.update(); orbit.enabled = false; }
        else { if (!tc.dragging) orbit.enabled = true; orbit.update(); }

        // Process active tweens — collect completions first, then fire callbacks
        // so that runSegment's push() isn't overwritten by the filter assignment
        const now = performance.now();
        const done = [];
        animationsRef.current = animationsRef.current.filter(anim => {
          const raw  = Math.min((now - anim.startTime) / anim.durationMs, 1);
          const ease = raw < 0.5 ? 2 * raw * raw : -1 + (4 - 2 * raw) * raw;
          anim.mesh.position.x = anim.fromX + (anim.toX - anim.fromX) * ease;
          anim.mesh.position.z = anim.fromZ + (anim.toZ - anim.fromZ) * ease;
          if (raw >= 1) { done.push(anim); return false; }
          return true;
        });
        done.forEach(anim => anim.onComplete && anim.onComplete());

        renderer.render(scene, camera);
      } catch (err) {
        console.error('[Z3D animate error]', err);
      }
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
  // statusMap/zeMap intentionally excluded — they update via refs to avoid scene rebuilds
  }, [canvasRef, layout]); // eslint-disable-line

  // Walk mode toggle
  useEffect(() => {
    const walk = walkRef.current, canvas = canvasRef.current, camera = cameraRef.current;
    if (!walk || !canvas || !camera) return;
    if (walkMode) { walk.yaw = 0; walk.pitch = 0; camera.position.y = 1.8; walk.attachMouseLook(canvas); }
    else { walk.detachMouseLook(); }
  }, [walkMode, canvasRef]);

  // Force renderer resize when tab becomes visible.
  // ResizeObserver on the canvas doesn't fire reliably when an ancestor
  // toggles display:none → display:flex, so we handle it explicitly here.
  // onSceneReady is called again after the resize so the loading overlay clears.
  useEffect(() => {
    if (!isActive) return;
    const canvas   = canvasRef.current;
    const renderer = rendererRef.current;
    const camera   = cameraRef.current;
    if (!canvas || !renderer || !camera) return;
    const doResize = () => {
      const w = canvas.clientWidth, h = canvas.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    doResize();
    const tid = setTimeout(() => { doResize(); onSceneReady && onSceneReady(); }, 120);
    return () => clearTimeout(tid);
  }, [isActive, canvasRef]); // eslint-disable-line

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
  // options: { stationId? }  — if stationId is provided the object snaps to that station
  const placeObject = useCallback((file, name, layoutId, options = {}) => {
    const scene = sceneRef.current;
    if (!scene) return;
    const ext = file.name.split('.').pop().toLowerCase();

    // WRL and STP need server-side conversion to GLB first
    const needsConversion = ext === 'wrl' || ext === 'stp' || ext === 'step';
    if (needsConversion) {
      onConvertStart && onConvertStart();
      let pct = 0;
      const ticker = setInterval(() => {
        pct = Math.min(pct + (pct < 60 ? 3 : pct < 85 ? 1 : 0.3), 92);
        onConvertStart && onConvertStart(pct);
      }, 400);
      const form = new FormData();
      form.append('file', file);
      fetch(`${backend_url}/z-stage/convert-model/`, { method: 'POST', body: form })
        .then(res => {
          if (!res.ok) return res.json().then(e => { throw new Error(e.detail || 'Conversion failed'); });
          return res.blob();
        })
        .then(blob => {
          clearInterval(ticker);
          onConvertEnd && onConvertEnd(true);
          const glbFile = new File([blob], name + '.glb', { type: 'model/gltf-binary' });
          placeObject(glbFile, name, layoutId, options);
        })
        .catch(err => {
          clearInterval(ticker);
          onConvertEnd && onConvertEnd(false);
          alert(`Conversion failed: ${err.message}`);
        });
      return;
    }

    const url  = URL.createObjectURL(file);

    const onLoaded = (obj) => {
      URL.revokeObjectURL(url);

      // Strip any existing text/label children from the loaded model
      obj.traverse(child => {
        if (child.isSprite || (child.material && child.material.map === null && child.isLine)) {
          child.visible = false;
        }
      });

      // Reset position/rotation before measuring so bbox is in clean local space
      obj.position.set(0, 0, 0);

      // Auto-scale to ~2m
      const bbox = new THREE.Box3().setFromObject(obj);
      const size = new THREE.Vector3();
      bbox.getSize(size);
      const maxDim = Math.max(size.x, size.y, size.z);
      const autoScale = maxDim > 0 ? 2.0 / maxDim : 1;
      if (maxDim > 0) obj.scale.setScalar(autoScale);
      obj.userData.baseScale = autoScale;

      // Re-compute after scale — snap bottom of object exactly to floor (y=0)
      const bbox2 = new THREE.Box3().setFromObject(obj);
      obj.position.y = -bbox2.min.y;

      // Place at station centre or scene centre
      const stnPos = options.stationId ? stationPosRef.current[options.stationId] : null;
      if (options.stationId) {
        console.log('[Z3D] place stationId=', options.stationId,
          'posMap keys=', Object.keys(stationPosRef.current),
          'found=', stnPos);
      }
      const c = sceneCenterRef.current;
      obj.position.x = stnPos ? stnPos.x : c.x;
      obj.position.z = stnPos ? stnPos.z : c.z;

      const objId = Date.now().toString();
      obj.userData.isPlaced       = true;
      obj.userData.objId          = objId;
      obj.userData.objName        = name;
      obj.userData.objExt         = ext;
      obj.userData.assignedStation = options.stationId || null;

      scene.add(obj);

      const entry = { id: objId, mesh: obj, label: null, name, stationId: options.stationId || null };
      placedRef.current = [...placedRef.current, entry];

      // Persist to IDB (file blob + initial transform) and cache blob for later updates
      if (layoutId) {
        file.arrayBuffer().then(buf => {
          const blob = new Blob([buf], { type: file.type || 'application/octet-stream' });
          blobCacheRef.current[objId] = blob;
          z3dPut({
            key: `${layoutId}_${objId}`,
            layoutId, id: objId, name, ext,
            fileBlob: blob,
            px: obj.position.x, py: obj.position.y, pz: obj.position.z,
            rx: obj.rotation.x, ry: obj.rotation.y, rz: obj.rotation.z,
            sx: obj.scale.x,    sy: obj.scale.y,    sz: obj.scale.z,
          });
        }).catch(() => {});
      }

      // Select immediately and set mode to translate
      if (transformRef.current) {
        transformRef.current.setMode('translate');
        transformRef.current.attach(obj);
        selectedRef.current = entry;
      }

      onObjectsChange([...placedRef.current]);
    };

    if (ext === 'glb' || ext === 'gltf') {
      makeGLTFLoader().load(url, (gltf) => onLoaded(gltf.scene), undefined, (err) => {
        console.error('[Z3D] GLB upload failed:', err);
        alert('Failed to load GLB: ' + (err?.message || err));
      });
    } else if (ext === 'obj') {
      new OBJLoader().load(url, onLoaded);
    } else if (ext === 'wrl') {
      new VRMLLoader().load(url, onLoaded);
    } else if (ext === 'stl') {
      new STLLoader().load(url, (geometry) => {
        geometry.computeVertexNormals();
        const mesh = new THREE.Mesh(
          geometry,
          new THREE.MeshLambertMaterial({ color: 0x90a4ae })
        );
        onLoaded(mesh);
      });
    }
  }, [onObjectsChange]); // eslint-disable-line

  const getRaycast = useCallback((e) => {
    const canvas = canvasRef.current, camera = cameraRef.current, scene = sceneRef.current;
    if (!canvas || !camera || !scene || walkModeRef.current) return null;
    const rect  = canvas.getBoundingClientRect();
    const mouse = new THREE.Vector2(
      ((e.clientX - rect.left) / rect.width)  *  2 - 1,
      ((e.clientY - rect.top)  / rect.height) * -2 + 1
    );
    const ray = new THREE.Raycaster();
    ray.setFromCamera(mouse, camera);
    return { ray, scene };
  }, [canvasRef]);

  // Single click — select placed objects only
  const handleCanvasClick = useCallback((e) => {
    const res = getRaycast(e);
    if (!res) return;
    const { ray } = res;
    const placed = placedRef.current.map(p => p.mesh);
    const placedHits = ray.intersectObjects(placed, true);
    if (placedHits.length > 0) {
      let obj = placedHits[0].object;
      while (obj.parent && !obj.userData.isPlaced) obj = obj.parent;
      const entry = placedRef.current.find(p => p.mesh === obj);
      if (entry) {
        selectedRef.current = entry;
        if (transformRef.current) transformRef.current.attach(obj);
        onObjectsChange([...placedRef.current]);
        return;
      }
    }
    // Deselect if clicked empty space
    if (transformRef.current) transformRef.current.detach();
    selectedRef.current = null;
    onObjectsChange([...placedRef.current]);
  }, [getRaycast, onObjectsChange]);

  // Double click — open station popup
  const handleCanvasDblClick = useCallback((e) => {
    const res = getRaycast(e);
    if (!res) return;
    const { ray, scene } = res;
    const allHits = ray.intersectObjects(scene.children, true);
    for (const hit of allHits) {
      let obj = hit.object;
      while (obj && obj !== scene) {
        if (obj.userData.stationId) {
          onStationClick && onStationClick(obj.userData.stationId);
          return;
        }
        obj = obj.parent;
      }
    }
  }, [getRaycast, onStationClick]);

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
    if (layoutIdRef.current) z3dDel(`${layoutIdRef.current}_${id}`);
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

  // Set uniform scale multiplier — if object is in a line group, applies to all group members
  const setObjectScale = useCallback((id, multiplier) => {
    const entry = placedRef.current.find(p => p.id === id);
    if (!entry) return;
    const targets = entry.lineGroupId
      ? placedRef.current.filter(p => p.lineGroupId === entry.lineGroupId)
      : [entry];
    targets.forEach(t => {
      const base = t.mesh.userData.baseScale || 1;
      t.mesh.scale.setScalar(base * multiplier);
      if (layoutIdRef.current) {
        z3dPut({
          key: `${layoutIdRef.current}_${t.id}`,
          layoutId: layoutIdRef.current,
          id: t.id, name: t.name,
          ext: t.mesh.userData.objExt || 'glb',
          fileBlob: blobCacheRef.current[t.id] || undefined,
          lineGroupId: t.lineGroupId || null,
          px: t.mesh.position.x, py: t.mesh.position.y, pz: t.mesh.position.z,
          rx: t.mesh.rotation.x, ry: t.mesh.rotation.y, rz: t.mesh.rotation.z,
          sx: t.mesh.scale.x,    sy: t.mesh.scale.y,    sz: t.mesh.scale.z,
        });
      }
    });
  }, []);

  // Set rotation (degrees) on a placed object — if in a line group, applies to all group members
  const setGroupRotation = useCallback((id, rx, ry, rz) => {
    const entry = placedRef.current.find(p => p.id === id);
    if (!entry) return;
    const targets = entry.lineGroupId
      ? placedRef.current.filter(p => p.lineGroupId === entry.lineGroupId)
      : [entry];
    targets.forEach(t => {
      t.mesh.rotation.set(
        (rx * Math.PI) / 180,
        (ry * Math.PI) / 180,
        (rz * Math.PI) / 180
      );
      if (layoutIdRef.current) {
        z3dPut({
          key: `${layoutIdRef.current}_${t.id}`,
          layoutId: layoutIdRef.current,
          id: t.id, name: t.name,
          ext: t.mesh.userData.objExt || 'glb',
          fileBlob: blobCacheRef.current[t.id] || undefined,
          lineGroupId: t.lineGroupId || null,
          px: t.mesh.position.x, py: t.mesh.position.y, pz: t.mesh.position.z,
          rx: t.mesh.rotation.x, ry: t.mesh.rotation.y, rz: t.mesh.rotation.z,
          sx: t.mesh.scale.x,    sy: t.mesh.scale.y,    sz: t.mesh.scale.z,
        });
      }
    });
  }, []);

  // Place one file at every station in the given stationIds array (line placement).
  // Loads the file once then deep-clones the resulting object per station — same
  // code path as placeObject so it's proven to work.
  const placeObjectForLine = useCallback((file, name, layoutId, stationIds) => {
    const scene = sceneRef.current;
    if (!scene || !stationIds?.length) return;
    const ext  = file.name.split('.').pop().toLowerCase();
    const groupId = `line_${Date.now()}`;
    const url  = URL.createObjectURL(file);

    const onTemplateLoaded = (template) => {
      URL.revokeObjectURL(url);

      // Measure auto-scale from a clean template at origin
      template.position.set(0, 0, 0);
      template.rotation.set(0, 0, 0);
      template.scale.set(1, 1, 1);
      const bbox0 = new THREE.Box3().setFromObject(template);
      const size0 = new THREE.Vector3();
      bbox0.getSize(size0);
      const maxDim = Math.max(size0.x, size0.y, size0.z);
      const autoScale = maxDim > 0 ? 2.0 / maxDim : 1;
      template.scale.setScalar(autoScale);

      // Floor-snap offset (computed once, same for every clone)
      const bboxScaled = new THREE.Box3().setFromObject(template);
      const floorY = -bboxScaled.min.y;

      const posMap = stationPosRef.current;
      const newEntries = [];

      stationIds.forEach((stationId, idx) => {
        const stnPos = posMap[stationId];
        if (!stnPos) return; // station not in this scene yet

        // Clone for every station — sharedClone shares geometry/material buffers
        // so GPU memory stays ~1× instead of N× for a 70 MB model
        const obj = idx === 0 ? template : sharedClone(template);

        obj.position.set(stnPos.x, floorY, stnPos.z);
        obj.userData.baseScale        = autoScale;
        obj.userData.isPlaced         = true;
        obj.userData.objId            = `${groupId}_${idx}`;
        obj.userData.objName          = name;
        obj.userData.objExt           = ext;
        obj.userData.assignedStation  = stationId;
        obj.userData.lineGroupId      = groupId;

        scene.add(obj);
        newEntries.push({
          id: obj.userData.objId, mesh: obj,
          label: null, name, stationId, lineGroupId: groupId,
        });
      });

      if (newEntries.length === 0) {
        alert(
          `Line Placement: no 3D positions found.\n` +
          `Tried stations: ${stationIds.slice(0,5).join(', ')}${stationIds.length>5?'…':''}\n` +
          `Scene has ${Object.keys(posMap).length} station(s) mapped.`
        );
        return;
      }

      placedRef.current = [...placedRef.current, ...newEntries];
      onObjectsChange([...placedRef.current]);

      // Persist each clone to IDB with its file blob cached
      if (layoutId) {
        file.arrayBuffer().then(buf => {
          const fileBlob = new Blob([buf], { type: file.type || 'application/octet-stream' });
          newEntries.forEach((entry) => {
            blobCacheRef.current[entry.id] = fileBlob;
            z3dPut({
              key: `${layoutId}_${entry.id}`,
              layoutId, id: entry.id, name, ext,
              fileBlob,
              lineGroupId: groupId,
              px: entry.mesh.position.x, py: entry.mesh.position.y, pz: entry.mesh.position.z,
              rx: entry.mesh.rotation.x, ry: entry.mesh.rotation.y, rz: entry.mesh.rotation.z,
              sx: entry.mesh.scale.x,    sy: entry.mesh.scale.y,    sz: entry.mesh.scale.z,
            });
          });
        }).catch(() => {});
      }
    };

    if (ext === 'glb' || ext === 'gltf') {
      makeGLTFLoader().load(url, (gltf) => onTemplateLoaded(gltf.scene), undefined, (err) => console.error('[Z3D] GLB line-load failed:', err));
    } else if (ext === 'obj') {
      new OBJLoader().load(url, onTemplateLoaded);
    } else if (ext === 'stl') {
      new STLLoader().load(url, (geometry) => {
        geometry.computeVertexNormals();
        const mesh = new THREE.Mesh(geometry, new THREE.MeshLambertMaterial({ color: 0x90a4ae }));
        onTemplateLoaded(mesh);
      });
    }
  }, [onObjectsChange]); // eslint-disable-line

  const animateAlongPath = useCallback((id, waypointIds, durationSec, onComplete) => {
    const entry = placedRef.current.find(p => p.id === id);
    if (!entry) return;

    animationsRef.current = animationsRef.current.filter(a => a.id !== id);

    const posMap = stationPosRef.current;
    const pts = waypointIds.map(sid => posMap[sid]).filter(Boolean);
    if (pts.length < 2) return;

    // Travel center of From station → center of To station, stop there
    const startPt = pts[0];
    const endPt   = pts[pts.length - 1];

    const segments = [
      { fromX: startPt.x, fromZ: startPt.z, toX: endPt.x, toZ: endPt.z, durationMs: durationSec * 1000 },
    ];

    let segIdx = 0;
    const runSegment = () => {
      if (segIdx >= segments.length) { onComplete && onComplete(); return; }
      const seg = segments[segIdx];
      animationsRef.current = animationsRef.current.filter(a => a.id !== id);
      animationsRef.current.push({
        id,
        mesh:       entry.mesh,
        fromX:      seg.fromX,
        fromZ:      seg.fromZ,
        toX:        seg.toX,
        toZ:        seg.toZ,
        startTime:  performance.now(),
        durationMs: seg.durationMs,
        onComplete: () => { segIdx++; runSegment(); },
      });
    };
    runSegment();
  }, []);

  const stopAnimation = useCallback((id, resetToStart) => {
    animationsRef.current = animationsRef.current.filter(a => a.id !== id);
    if (resetToStart) {
      const entry = placedRef.current.find(p => p.id === id);
      if (!entry) return;
      const stn = entry.mesh.userData.assignedStation || entry.stationId;
      if (stn && stationPosRef.current[stn]) {
        entry.mesh.position.x = stationPosRef.current[stn].x;
        entry.mesh.position.z = stationPosRef.current[stn].z;
      }
    }
  }, []);

  // Label follows mesh position — reuse cached height offset to avoid
  // expensive Box3.setFromObject() calls every 50 ms per object
  useEffect(() => {
    const labelHeightCache = new Map();
    const tid = setInterval(() => {
      placedRef.current.forEach(({ mesh, label }) => {
        if (!mesh || !label) return;
        if (!labelHeightCache.has(mesh.uuid)) {
          const box = new THREE.Box3().setFromObject(mesh);
          labelHeightCache.set(mesh.uuid, box.max.y + 0.6);
        }
        const labelY = labelHeightCache.get(mesh.uuid);
        label.position.set(mesh.position.x, labelY, mesh.position.z);
      });
    }, 50);
    return () => clearInterval(tid);
  }, []);

  return { snapView, setTransformMode, placeObject, placeObjectForLine, handleCanvasClick, handleCanvasDblClick, selectById, deleteById, renameById, setObjectScale, setGroupRotation, animateAlongPath, stopAnimation };
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

// ── IndexedDB helpers for placed-object persistence ───────────────────────────
const Z3D_DB   = 'z3d_placed_v1';
const Z3D_STORE = 'objects';

function z3dOpen() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(Z3D_DB, 1);
    req.onupgradeneeded = (e) => e.target.result.createObjectStore(Z3D_STORE, { keyPath: 'key' });
    req.onsuccess = (e) => resolve(e.target.result);
    req.onerror   = (e) => reject(e.target.error);
  });
}
async function z3dGetAll(layoutId) {
  try {
    const db  = await z3dOpen();
    const all = await new Promise((res) => {
      const req = db.transaction(Z3D_STORE, 'readonly').objectStore(Z3D_STORE).getAll();
      req.onsuccess = () => res(req.result || []);
      req.onerror   = () => res([]);
    });
    db.close();
    return all.filter(r => r.layoutId === layoutId);
  } catch { return []; }
}
async function z3dPut(record) {
  try {
    const db = await z3dOpen();
    await new Promise((res, rej) => {
      const tx = db.transaction(Z3D_STORE, 'readwrite');
      tx.objectStore(Z3D_STORE).put(record);
      tx.oncomplete = res; tx.onerror = () => rej(tx.error);
    });
    db.close();
  } catch {}
}
async function z3dDel(key) {
  try {
    const db = await z3dOpen();
    await new Promise((res) => {
      const tx = db.transaction(Z3D_STORE, 'readwrite');
      tx.objectStore(Z3D_STORE).delete(key);
      tx.oncomplete = res; tx.onerror = res;
    });
    db.close();
  } catch {}
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
  const [converting,    setConverting]    = useState(false);
  const [convertProgress, setConvertProgress] = useState(0);
  const [popupStation,      setPopupStation]      = useState(null);
  const [records,           setRecords]           = useState([]);
  const [auditRecords,      setAuditRecords]      = useState([]);
  const [adherenceRecords,  setAdherenceRecords]  = useState([]);
  const [sceneReady,        setSceneReady]        = useState(false);
  const [refreshing,        setRefreshing]        = useState(false);
  // Upload modal
  const [showUploadModal,   setShowUploadModal]   = useState(false);
  const [pendingFile,       setPendingFile]       = useState(null);
  const [uploadMode,        setUploadMode]        = useState('free');
  const [uploadShop,        setUploadShop]        = useState('');
  const [uploadStation,     setUploadStation]     = useState('');
  const [uploadLine,        setUploadLine]        = useState('');
  // Per-object scale and rotation
  const [scaleVal,          setScaleVal]          = useState(1.0);
  const [rotX,              setRotX]              = useState(0);
  const [rotY,              setRotY]              = useState(0);
  const [rotZ,              setRotZ]              = useState(0);
  // Animation panel (toolbar dropdown)
  const [showAnimPanel,     setShowAnimPanel]     = useState(false);
  const [animObjId,         setAnimObjId]         = useState('');
  const [animShop,          setAnimShop]          = useState('');
  const [animFromStation,   setAnimFromStation]   = useState('');
  const [animToStation,     setAnimToStation]     = useState('');
  const [animDuration,      setAnimDuration]      = useState(6);
  const [animPlaying,       setAnimPlaying]       = useState(false);
  const [animPresets,       setAnimPresets]       = useState([]);
  const [playingAll,        setPlayingAll]        = useState(false);

  useEffect(() => {
    if (activeLayoutId && !selectedLayoutId) setSelectedLayoutId(activeLayoutId);
  }, [activeLayoutId]); // eslint-disable-line

  // Load animation presets when layout changes
  useEffect(() => {
    if (!selectedLayoutId) { setAnimPresets([]); return; }
    try {
      const stored = localStorage.getItem(`z3d_anim_presets_${selectedLayoutId}`);
      setAnimPresets(stored ? JSON.parse(stored) : []);
    } catch (_) { setAnimPresets([]); }
  }, [selectedLayoutId]);

  // Save animation presets whenever they change
  useEffect(() => {
    if (!selectedLayoutId) return;
    try {
      localStorage.setItem(`z3d_anim_presets_${selectedLayoutId}`, JSON.stringify(animPresets));
    } catch (_) {}
  }, [animPresets, selectedLayoutId]);

  useEffect(() => {
    if (!selectedLayoutId) return;
    setSceneReady(false);
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
      Promise.all([
        inputApi.getRecords(userId, layout.id),
        layeredAuditApi.getAuditRecords(userId, layout.id),
        layeredAuditApi.getAdherenceRecords(userId, layout.id),
      ])
        .then(([recRes, auditRes, adherenceRes]) => {
          const recs = Array.isArray(recRes.data) ? recRes.data : [];
          setRecords(recs);
          setZeMap(computeZeMap(recs));
          setAuditRecords(Array.isArray(auditRes.data) ? auditRes.data : []);
          setAdherenceRecords(Array.isArray(adherenceRes.data) ? adherenceRes.data : []);
        })
        .catch(() => { setZeMap({}); setRecords([]); setAuditRecords([]); setAdherenceRecords([]); });
    }
  }, [layout, userId]);

  const onObjectsChange = useCallback((objs) => {
    setPlacedObjects(objs);
  }, []);

  const onConvertStart = useCallback((pct) => {
    setConverting(true);
    if (pct !== undefined) setConvertProgress(Math.round(pct));
  }, []);
  const onConvertEnd = useCallback(() => {
    setConvertProgress(100);
    setTimeout(() => { setConverting(false); setConvertProgress(0); }, 800);
  }, []);

  const allMonths = React.useMemo(() => {
    const set = new Set(MONTHLY_KEYS);
    records.forEach((rec) => {
      if (rec.monthly_data) {
        try { Object.keys(JSON.parse(rec.monthly_data)).forEach((k) => set.add(k)); } catch {}
      }
    });
    return Array.from(set).sort();
  }, [records]);

  // Flat ordered list of all station IDs in the layout (sorted numerically within each shop)
  const stationList = React.useMemo(() => {
    if (!layout) return [];
    const result = [];
    (layout.station_boxes || []).forEach(box => {
      const ids = (box.station_ids || '').split(',').map(s => s.trim()).filter(Boolean);
      ids.forEach(id => result.push({ id, shop: box.name || '' }));
    });
    // Sort numerically by the number embedded in the station ID
    result.sort((a, b) => {
      const na = parseInt((a.id.match(/\d+/) || ['0'])[0], 10);
      const nb = parseInt((b.id.match(/\d+/) || ['0'])[0], 10);
      return na - nb;
    });
    return result;
  }, [layout]);

  const shopList = React.useMemo(() => {
    const set = new Set();
    stationList.forEach(s => { if (s.shop) set.add(s.shop); });
    return Array.from(set);
  }, [stationList]);

  const handleRecordSaved = useCallback((recordId, updatedRecord) => {
    setRecords((prev) => prev.map((r) => (r.id === recordId ? updatedRecord : r)));
  }, []);

  const handleRecordAdded = useCallback((tabType, newRec) => {
    if (tabType === 'master') setRecords((prev) => [...prev, newRec]);
    else if (tabType === 'layered-audit') setAuditRecords((prev) => [...prev, newRec]);
    else if (tabType === 'audit-adherence') setAdherenceRecords((prev) => [...prev, newRec]);
  }, []);

  const handleRefresh = useCallback(() => {
    if (!selectedLayoutId) return;
    setRefreshing(true);
    setSceneReady(false);
    Promise.allSettled([
      layoutApi.getLayout(selectedLayoutId).then(res => setLayout(res.data)),
      inputApi.getRecords(userId, selectedLayoutId).then(r => {
        const recs = Array.isArray(r.data) ? r.data : [];
        setRecords(recs);
        setZeMap(computeZeMap(recs));
      }),
      layeredAuditApi.getAuditRecords(userId, selectedLayoutId).then(r => setAuditRecords(Array.isArray(r.data) ? r.data : [])),
      layeredAuditApi.getAdherenceRecords(userId, selectedLayoutId).then(r => setAdherenceRecords(Array.isArray(r.data) ? r.data : [])),
    ]).finally(() => setRefreshing(false));
  }, [selectedLayoutId, userId]);

  const handleStationClick = useCallback((stationId) => {
    setPopupStation(stationId);
  }, []);

  const handleSceneReady = useCallback(() => {
    setSceneReady(true);
  }, []);

  const { snapView, setTransformMode, placeObject, placeObjectForLine, handleCanvasClick, handleCanvasDblClick, selectById, deleteById, renameById, setObjectScale, setGroupRotation, animateAlongPath, stopAnimation } =
    useThreeScene(canvasRef, layout, statusMap, zeMap, walkMode, onObjectsChange, onConvertStart, onConvertEnd, handleStationClick, isActive, handleSceneReady);

  const runPreset = useCallback((preset) => {
    // Resolve current object ID by name (objId changes after page refresh)
    const obj = placedObjects.find(o => o.name === preset.objName) || placedObjects.find(o => o.id === preset.objId);
    if (!obj) return;
    const fromNum  = parseInt((preset.fromStation.match(/\d+/) || ['0'])[0], 10);
    const toNum    = parseInt((preset.toStation.match(/\d+/)   || ['0'])[0], 10);
    const filtered = stationList.filter(s => !preset.shop || s.shop === preset.shop);
    const dir      = fromNum <= toNum ? 1 : -1;
    const waypoints = filtered
      .filter(s => {
        const n = parseInt((s.id.match(/\d+/) || ['0'])[0], 10);
        return dir === 1 ? n >= fromNum && n <= toNum : n <= fromNum && n >= toNum;
      })
      .sort((a, b) => {
        const na = parseInt((a.id.match(/\d+/) || ['0'])[0], 10);
        const nb = parseInt((b.id.match(/\d+/) || ['0'])[0], 10);
        return dir === 1 ? na - nb : nb - na;
      })
      .map(s => s.id);
    if (waypoints.length < 2) return;
    animateAlongPath(obj.id, waypoints, preset.duration, () => {});
  }, [stationList, animateAlongPath, placedObjects]);

  const handleLayoutChange = useCallback((e) => {
    setSelectedLayoutId(Number(e.target.value) || null);
    setLayout(null); setWalkMode(false); setPlacedObjects([]); setSelectedId(null);
  }, []);

  const handleFileUpload = useCallback((e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPendingFile(file);
    setUploadMode('free');
    setUploadShop('');
    setUploadStation('');
    setShowUploadModal(true);
    e.target.value = '';
  }, []);

  const handleUploadConfirm = useCallback(() => {
    if (!pendingFile) return;
    const name = pendingFile.name.replace(/\.[^/.]+$/, '');
    if (uploadMode === 'line' && uploadLine) {
      const lineStations = stationList.filter(s => s.shop === uploadLine).map(s => s.id);
      console.log('[Upload] line mode, line=', uploadLine, 'stations=', lineStations);
      if (lineStations.length === 0) {
        alert(`No stations found for line "${uploadLine}". Please check the layout.`);
        return;
      }
      placeObjectForLine(pendingFile, name, selectedLayoutId, lineStations);
    } else {
      const opts = uploadMode === 'station' && uploadStation ? { stationId: uploadStation } : {};
      placeObject(pendingFile, name, selectedLayoutId, opts);
    }
    setShowObjPanel(true);
    setScaleVal(1.0);
    setRotX(0); setRotY(0); setRotZ(0);
    setAnimFromStation('');
    setAnimToStation('');
    setAnimPlaying(false);
    setShowUploadModal(false);
    setPendingFile(null);
  }, [pendingFile, uploadMode, uploadStation, uploadLine, stationList, placeObject, placeObjectForLine, selectedLayoutId]);

  const handleModeChange = useCallback((mode) => {
    setTransformModeState(mode);
    setTransformMode(mode);
  }, [setTransformMode]);

  const handleSelect = useCallback((id) => {
    setSelectedId(id);
    setRenameVal(placedObjects.find(o => o.id === id)?.name || '');
    setScaleVal(1.0);
    setRotX(0); setRotY(0); setRotZ(0);
    setAnimFromStation('');
    setAnimToStation('');
    setAnimPlaying(false);
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
                <button key={v} type="button" className="z3d-view-btn" onClick={() => snapView(v.toLowerCase())}>{v}</button>
              ))}
            </div>

            {/* Upload object */}
            <button type="button" className="z3d-upload-btn" onClick={() => fileInputRef.current?.click()} title="Upload GLB, OBJ or STL file">
              ⬆ Upload Object
            </button>
            <input ref={fileInputRef} type="file" accept=".glb,.gltf,.obj,.stl,.wrl,.stp,.step" style={{ display: 'none' }} onChange={handleFileUpload} />

            {/* Object list toggle */}
            <button type="button" className={`z3d-walk-btn${showObjPanel ? ' z3d-walk-btn--active' : ''}`} onClick={() => setShowObjPanel(v => !v)}>
              📦 Objects {placedObjects.length > 0 && `(${placedObjects.length})`}
            </button>

            {/* Walk mode */}
            <button type="button" className={`z3d-walk-btn${walkMode ? ' z3d-walk-btn--active' : ''}`} onClick={() => setWalkMode(v => !v)}>
              {walkMode ? '🧍 Exit Walk' : '🚶 Walk Mode'}
            </button>

            {/* Play All / Stop All presets */}
            {!playingAll ? (
              <button type="button"
                className="z3d-walk-btn z3d-play-all-btn"
                disabled={animPresets.length === 0}
                onClick={() => {
                  setPlayingAll(true);
                  animPresets.forEach(p => runPreset(p));
                  // Stop All clears flag; use a short delay as a safety net
                  setTimeout(() => setPlayingAll(false), Math.max(...animPresets.map(p => p.duration), 6) * 1000 + 500);
                }}
              >▶ Play All</button>
            ) : (
              <button type="button"
                className="z3d-walk-btn z3d-play-all-btn z3d-walk-btn--playing"
                onClick={() => {
                  animPresets.forEach(p => stopAnimation(p.objId, true));
                  setPlayingAll(false);
                }}
              >■ Stop All</button>
            )}

            {/* Animate dropdown trigger */}
            <div className="z3d-anim-dropdown-wrapper">
              <button type="button"
                className={`z3d-walk-btn${showAnimPanel ? ' z3d-walk-btn--active' : ''}${animPlaying ? ' z3d-walk-btn--playing' : ''}`}
                onClick={() => setShowAnimPanel(v => !v)}
              >
                🎬 Animate{animPlaying ? ' ●' : ''}
              </button>

              {showAnimPanel && (
                <div className="z3d-anim-dropdown">
                  <div className="z3d-anim-dropdown-title">Animate Object Along Path</div>

                  <label className="z3d-anim-field-label">Object</label>
                  <select
                    className="z3d-anim-select"
                    value={animObjId}
                    onChange={e => setAnimObjId(e.target.value)}
                    disabled={animPlaying}
                  >
                    <option value="">— Select object —</option>
                    {placedObjects.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
                  </select>

                  <label className="z3d-anim-field-label">Site / Shop</label>
                  <select
                    className="z3d-anim-select"
                    value={animShop}
                    onChange={e => { setAnimShop(e.target.value); setAnimFromStation(''); setAnimToStation(''); }}
                    disabled={animPlaying}
                  >
                    <option value="">— All shops —</option>
                    {shopList.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>

                  <label className="z3d-anim-field-label">From Station</label>
                  <select
                    className="z3d-anim-select"
                    value={animFromStation}
                    onChange={e => setAnimFromStation(e.target.value)}
                    disabled={animPlaying}
                  >
                    <option value="">— Start —</option>
                    {stationList
                      .filter(s => !animShop || s.shop === animShop)
                      .map(s => <option key={s.id} value={s.id}>{s.id}{s.shop ? ` · ${s.shop}` : ''}</option>)}
                  </select>

                  <label className="z3d-anim-field-label">To Station</label>
                  <select
                    className="z3d-anim-select"
                    value={animToStation}
                    onChange={e => setAnimToStation(e.target.value)}
                    disabled={animPlaying}
                  >
                    <option value="">— End —</option>
                    {stationList
                      .filter(s => !animShop || s.shop === animShop)
                      .map(s => <option key={s.id} value={s.id}>{s.id}{s.shop ? ` · ${s.shop}` : ''}</option>)}
                  </select>

                  <div className="z3d-anim-dur-row">
                    <span className="z3d-anim-field-label">Duration</span>
                    <input
                      type="range" min="2" max="20" step="1"
                      value={animDuration}
                      className="z3d-scale-slider"
                      onChange={e => setAnimDuration(parseInt(e.target.value, 10))}
                      disabled={animPlaying}
                    />
                    <span className="z3d-scale-value">{animDuration}s</span>
                  </div>

                  <div className="z3d-anim-btns">
                    {!animPlaying ? (
                      <button type="button"
                        className="z3d-anim-play-btn"
                        disabled={!animObjId || !animFromStation || !animToStation || animFromStation === animToStation}
                        onClick={() => {
                          const fromNum  = parseInt((animFromStation.match(/\d+/) || ['0'])[0], 10);
                          const toNum    = parseInt((animToStation.match(/\d+/)   || ['0'])[0], 10);
                          const filtered = stationList.filter(s => !animShop || s.shop === animShop);
                          const dir      = fromNum <= toNum ? 1 : -1;
                          const waypoints = filtered
                            .filter(s => {
                              const n = parseInt((s.id.match(/\d+/) || ['0'])[0], 10);
                              return dir === 1 ? n >= fromNum && n <= toNum : n <= fromNum && n >= toNum;
                            })
                            .sort((a, b) => {
                              const na = parseInt((a.id.match(/\d+/) || ['0'])[0], 10);
                              const nb = parseInt((b.id.match(/\d+/) || ['0'])[0], 10);
                              return dir === 1 ? na - nb : nb - na;
                            })
                            .map(s => s.id);
                          if (waypoints.length < 2) return;
                          setAnimPlaying(true);
                          animateAlongPath(animObjId, waypoints, animDuration, () => setAnimPlaying(false));
                        }}
                      >▶ Animate</button>
                    ) : (
                      <button type="button"
                        className="z3d-anim-stop-btn"
                        onClick={() => { stopAnimation(animObjId, true); setAnimPlaying(false); }}
                      >■ Stop</button>
                    )}
                    {animPlaying && <span className="z3d-anim-playing">Animating…</span>}
                  </div>

                  {/* Save Preset */}
                  <button
                    type="button"
                    className="z3d-anim-play-btn"
                    style={{ marginTop: 6 }}
                    disabled={!animObjId || !animFromStation || !animToStation}
                    onClick={() => {
                      const label = `${animFromStation} → ${animToStation}`;
                      const objEntry = placedObjects.find(o => o.id === animObjId);
                      const newPreset = {
                        id: `${Date.now()}`,
                        label,
                        objId:   animObjId,
                        objName: objEntry ? objEntry.name : '',
                        shop: animShop,
                        fromStation: animFromStation,
                        toStation: animToStation,
                        duration: animDuration,
                      };
                      setAnimPresets(prev => [...prev, newPreset]);
                    }}
                  >💾 Save Preset</button>

                  {/* Saved presets list */}
                  {animPresets.length > 0 && (
                    <div className="z3d-preset-list">
                      {animPresets.map(preset => (
                        <div key={preset.id} className="z3d-preset-item">
                          <span className="z3d-preset-label">{preset.label}</span>
                          <button
                            type="button"
                            className="z3d-preset-play-btn"
                            onClick={() => runPreset(preset)}
                          >▶</button>
                          <button
                            type="button"
                            className="z3d-preset-del-btn"
                            onClick={() => setAnimPresets(prev => prev.filter(p => p.id !== preset.id))}
                          >×</button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </>
        )}

        <div className="dash-legend" style={{ marginLeft: 'auto' }}>
          <span className="dash-legend-chip dash-legend-chip--red">Z</span>
          <span className="dash-legend-text">Active issues</span>
          <span className="dash-legend-chip dash-legend-chip--green">Z</span>
          <span className="dash-legend-text">No issues</span>
          <span className="dash-legend-sep" />
          <span className="dash-legend-chip dash-legend-chip--m">M</span>
          <span className="dash-legend-text">Manufacturing</span>
          <span className="dash-legend-chip dash-legend-chip--p">P</span>
          <span className="dash-legend-text">Part Quality</span>
          <span className="dash-legend-chip dash-legend-chip--d">D</span>
          <span className="dash-legend-text">Design</span>
          <span className="dash-legend-chip dash-legend-chip--u">U</span>
          <span className="dash-legend-text">Under Analysis</span>
        </div>

        <button type="button" className="dash-refresh-btn" onClick={handleRefresh} disabled={refreshing} title="Refresh layout and records">
          <RefreshCw size={13} className={refreshing ? 'dash-spin' : ''} />
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </button>
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
                  <button type="button"
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
                <button type="button" className="z3d-rename-btn" onClick={handleRename}>✓</button>
              </div>
            )}

            {/* Scale */}
            {currentSelected && (
              <div className="z3d-scale-row">
                <span className="z3d-scale-label">Scale{currentSelected.lineGroupId ? ' (all)' : ''}</span>
                <input
                  type="range" min="0.1" max="5" step="0.1"
                  value={scaleVal}
                  className="z3d-scale-slider"
                  onChange={e => {
                    const v = parseFloat(e.target.value);
                    setScaleVal(v);
                    setObjectScale(selectedId, v);
                  }}
                />
                <span className="z3d-scale-value">{scaleVal.toFixed(1)}×</span>
                <button type="button" className="z3d-scale-reset" title="Reset scale" onClick={() => { setScaleVal(1.0); setObjectScale(selectedId, 1.0); }}>↺</button>
              </div>
            )}

            {/* Rotation (applies to all in group) */}
            {currentSelected && (
              <div className="z3d-rotation-panel">
                <div className="z3d-rotation-title">Rotation{currentSelected.lineGroupId ? ' (all)' : ''} °</div>
                {[['X', rotX, setRotX], ['Y', rotY, setRotY], ['Z', rotZ, setRotZ]].map(([axis, val, setter]) => (
                  <div key={axis} className="z3d-rot-row">
                    <span className="z3d-rot-label">{axis}</span>
                    <input
                      type="range" min="0" max="360" step="1"
                      value={val}
                      className="z3d-scale-slider"
                      onChange={e => {
                        const v = parseInt(e.target.value, 10);
                        setter(v);
                        const newX = axis === 'X' ? v : rotX;
                        const newY = axis === 'Y' ? v : rotY;
                        const newZ = axis === 'Z' ? v : rotZ;
                        setGroupRotation(selectedId, newX, newY, newZ);
                      }}
                    />
                    <input
                      type="number" min="0" max="360"
                      value={val}
                      className="z3d-rot-input"
                      onChange={e => {
                        const v = Math.max(0, Math.min(360, parseInt(e.target.value, 10) || 0));
                        setter(v);
                        const newX = axis === 'X' ? v : rotX;
                        const newY = axis === 'Y' ? v : rotY;
                        const newZ = axis === 'Z' ? v : rotZ;
                        setGroupRotation(selectedId, newX, newY, newZ);
                      }}
                    />
                  </div>
                ))}
                <button
                  type="button" className="z3d-scale-reset"
                  title="Reset rotation"
                  onClick={() => { setRotX(0); setRotY(0); setRotZ(0); setGroupRotation(selectedId, 0, 0, 0); }}
                >↺ Reset</button>
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
                  <span className="z3d-obj-icon">{obj.lineGroupId ? '🔗' : '📦'}</span>
                  <span className="z3d-obj-name">
                    {obj.name}
                    {obj.stationId && <span className="z3d-obj-station-tag">{obj.stationId}</span>}
                  </span>
                  <button type="button"
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
              <canvas ref={canvasRef} className="z3d-canvas" onClick={handleCanvasClick} onDoubleClick={handleCanvasDblClick} />
              {!sceneReady && (
                <div className="z3d-scene-loading">
                  <div className="z3d-scene-loading-box">
                    <div className="z3d-scene-loading-spinner" />
                    <div className="z3d-scene-loading-text">Building 3D scene…</div>
                    <div className="z3d-scene-loading-bar-track">
                      <div className="z3d-scene-loading-bar-fill" />
                    </div>
                  </div>
                </div>
              )}
              {converting && (
                <div className="z3d-convert-overlay">
                  <div className="z3d-convert-box">
                    <div className="z3d-convert-title">Converting file…</div>
                    <div className="z3d-convert-sub">Server is simplifying the model for browser rendering</div>
                    <div className="z3d-convert-bar-track">
                      <div className="z3d-convert-bar-fill" style={{ width: `${convertProgress}%` }} />
                    </div>
                    <div className="z3d-convert-pct">{convertProgress}%</div>
                  </div>
                </div>
              )}
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

      {showUploadModal && (
        <div className="z3d-modal-overlay" onClick={() => { setShowUploadModal(false); setPendingFile(null); }}>
          <div className="z3d-modal-box" onClick={e => e.stopPropagation()}>
            <div className="z3d-modal-title">Upload 3D Object</div>
            <div className="z3d-modal-filename">{pendingFile?.name}</div>

            <div className="z3d-upload-mode-tabs">
              <button type="button"
                className={`z3d-upload-mode-tab${uploadMode === 'free' ? ' active' : ''}`}
                onClick={() => setUploadMode('free')}
              >Free Placement</button>
              <button type="button"
                className={`z3d-upload-mode-tab${uploadMode === 'station' ? ' active' : ''}`}
                onClick={() => setUploadMode('station')}
              >Station Placement</button>
              <button type="button"
                className={`z3d-upload-mode-tab${uploadMode === 'line' ? ' active' : ''}`}
                onClick={() => { setUploadMode('line'); setUploadLine(''); }}
              >Line Placement</button>
            </div>

            {uploadMode === 'free' && (
              <div className="z3d-modal-hint">Object will be placed at scene centre. Drag it anywhere using the transform handles.</div>
            )}

            {uploadMode === 'station' && (
              <div className="z3d-modal-station-fields">
                <label className="z3d-modal-label">Shop / Line</label>
                <select
                  className="z3d-modal-select"
                  value={uploadShop}
                  onChange={e => { setUploadShop(e.target.value); setUploadStation(''); }}
                >
                  <option value="">— All shops —</option>
                  {shopList.map(s => <option key={s} value={s}>{s}</option>)}
                </select>

                <label className="z3d-modal-label">Station ID</label>
                <select
                  className="z3d-modal-select"
                  value={uploadStation}
                  onChange={e => setUploadStation(e.target.value)}
                >
                  <option value="">— Select station —</option>
                  {stationList
                    .filter(s => !uploadShop || s.shop === uploadShop)
                    .map(s => <option key={s.id} value={s.id}>{s.id}{s.shop ? ` (${s.shop})` : ''}</option>)}
                </select>
              </div>
            )}

            {uploadMode === 'line' && (
              <div className="z3d-modal-station-fields">
                <div className="z3d-modal-hint z3d-modal-hint--line">
                  One copy of the model will be placed at <strong>every station</strong> in the selected line.
                  Scale &amp; rotation can be adjusted for all at once from the Objects panel.
                </div>
                <label className="z3d-modal-label">Line / Shop</label>
                <select
                  className="z3d-modal-select"
                  value={uploadLine}
                  onChange={e => setUploadLine(e.target.value)}
                >
                  <option value="">— Select line —</option>
                  {shopList.map(s => (
                    <option key={s} value={s}>
                      {s} ({stationList.filter(st => st.shop === s).length} stations)
                    </option>
                  ))}
                </select>
                {uploadLine && (
                  <div className="z3d-modal-line-preview">
                    {stationList.filter(s => s.shop === uploadLine).map(s => (
                      <span key={s.id} className="z3d-modal-stn-chip">{s.id}</span>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="z3d-modal-actions">
              <button type="button" className="z3d-modal-cancel" onClick={() => { setShowUploadModal(false); setPendingFile(null); }}>Cancel</button>
              <button type="button"
                className="z3d-modal-confirm"
                disabled={(uploadMode === 'station' && !uploadStation) || (uploadMode === 'line' && !uploadLine)}
                onClick={handleUploadConfirm}
              >Upload</button>
            </div>
          </div>
        </div>
      )}

      {popupStation && (
        <StationDetailModal
          stationId={popupStation}
          records={records}
          allMonths={allMonths}
          onSaved={handleRecordSaved}
          onClose={() => setPopupStation(null)}
          auditRecords={auditRecords}
          adherenceRecords={adherenceRecords}
          userId={userId}
          layoutId={selectedLayoutId}
          onRecordAdded={handleRecordAdded}
          stationIds={(layout?.station_boxes || []).flatMap(b =>
            (b.station_ids || '').split(',').map(s => s.trim()).filter(Boolean)
          )}
        />
      )}
    </div>
  );
}

// ── Error boundary so a crash in the 3D scene doesn't take down the whole page ──
class ZStage3DErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(err) { return { error: err }; }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 32, color: '#e6edf3', background: '#161b22', height: '100%', display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ fontSize: 32 }}>⚠️</div>
          <div style={{ fontSize: 15, fontWeight: 700 }}>3D Layout encountered an error</div>
          <div style={{ fontSize: 12, color: '#8b949e', maxWidth: 400, textAlign: 'center' }}>{this.state.error?.message}</div>
          <button type="button" style={{ marginTop: 8, padding: '7px 18px', borderRadius: 6, border: 'none', background: '#238636', color: '#fff', cursor: 'pointer', fontWeight: 600 }}
            onClick={() => this.setState({ error: null })}>Retry</button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function ZStage3DLayoutWithBoundary(props) {
  return (
    <ZStage3DErrorBoundary>
      <ZStage3DLayout {...props} />
    </ZStage3DErrorBoundary>
  );
}
