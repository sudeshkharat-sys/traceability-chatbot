import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { TransformControls } from 'three/examples/jsm/controls/TransformControls';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader';
import { VRMLLoader } from 'three/examples/jsm/loaders/VRMLLoader';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader';

// Shared DracoLoader — reused across all GLTFLoader instances
const dracoLoader = new DRACOLoader();
dracoLoader.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.7/');

function makeGLTFLoader() {
  const loader = new GLTFLoader();
  loader.setDRACOLoader(dracoLoader);
  return loader;
}
import { RefreshCw } from 'lucide-react';
import { layoutApi, inputApi } from '../../../services/api/layoutApi';
import { layeredAuditApi } from '../../../services/api/layoutApi';
import { StationDetailModal, MONTHLY_KEYS } from '../ZStageDashboard/ZStageDashboard';
import '../ZStageDashboard/ZStageDashboard.css';
import { backend_url } from '../../../services/api/config';
import './ZStage3DLayout.css';

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
function useThreeScene(canvasRef, layout, statusMap, zeMap, walkMode, onObjectsChange, onConvertStart, onConvertEnd, onStationClick, isActive, onSceneReady, onPlaceStart, onPlaceEnd) {
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
  const walkModeRef     = useRef(walkMode);
  const layoutIdRef     = useRef(null);   // kept in sync by the scene effect
  const stationCellsRef = useRef({});     // { stationId: { x, z } } — centre of each station cell
  const linesRef        = useRef({});     // { lineName: [{stationId, x, z}] } — stations per line
  const blobsRef        = useRef({});     // { 'tmpl_<id>': Blob } — template blobs
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

    layoutBoxes.forEach(box => buildStationShell(box, statusMap, zeMap, scene));

    // Populate station cell centres and line→stations map
    stationCellsRef.current = {};
    linesRef.current = {};
    layoutBoxes.forEach(box => {
      const sids     = (box.station_ids || '').split(',').map(s => s.trim()).filter(Boolean);
      const lineName = box.name || `Box-${box.id}`;
      linesRef.current[lineName] = sids.map((sid, i) => ({
        stationId: sid,
        x: box._x3d + i * CELL_W + CELL_W / 2,
        z: box._z3d + DEPTH / 2,
      }));
      sids.forEach((sid, i) => {
        stationCellsRef.current[sid] = {
          x: box._x3d + i * CELL_W + CELL_W / 2,
          z: box._z3d + DEPTH / 2,
        };
      });
    });

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
      // Drag finished — persist updated transform to IDB
      if (!e.value && selectedRef.current && layoutIdRef.current) {
        const { mesh, id, name } = selectedRef.current;
        z3dPut({
          key: `${layoutIdRef.current}_${id}`,
          layoutId: layoutIdRef.current,
          id, name,
          ext:        mesh.userData.objExt      || 'glb',
          templateId: mesh.userData.templateId  || null,
          stationId:  mesh.userData.stationId   || null,
          lineName:   mesh.userData.lineName    || null,
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

    // Reload previously saved placed objects from IDB
    // Template blob is stored once; each station clone references it by templateId.
    Promise.all([z3dGetAll(layout.id), z3dGetAllTemplates(layout.id)]).then(([saved, templates]) => {
      const tmplMap = {};
      templates.forEach(t => { tmplMap[t.templateId] = t; });

      // Group object records by templateId (fallback: use id as group key for legacy records)
      const groups = {};
      saved.forEach(record => {
        const gKey = record.templateId || record.id;
        if (!groups[gKey]) groups[gKey] = [];
        groups[gKey].push(record);
      });

      Object.entries(groups).forEach(([templateId, records]) => {
        const tmpl      = tmplMap[templateId];
        const firstRec  = records[0];
        const blob      = tmpl?.fileBlob || firstRec?.fileBlob;
        if (!blob) return;

        const ext = (tmpl?.ext || firstRec?.ext || 'glb').toLowerCase();
        const url = URL.createObjectURL(new Blob([blob], { type: blob.type || 'model/gltf-binary' }));

        if (tmpl) blobsRef.current[`tmpl_${templateId}`] = tmpl.fileBlob;

        const onBaseLoaded = (baseObj) => {
          URL.revokeObjectURL(url);
          records.forEach((record, idx) => {
            const obj = idx === 0 ? baseObj : baseObj.clone(true);
            obj.traverse(child => {
              if (child.isSprite || (child.material && child.material.map === null && child.isLine)) child.visible = false;
            });
            obj.position.set(record.px ?? 0, record.py ?? 0, record.pz ?? 0);
            obj.rotation.set(record.rx ?? 0, record.ry ?? 0, record.rz ?? 0);
            obj.scale.set(record.sx ?? 1, record.sy ?? 1, record.sz ?? 1);
            obj.userData.isPlaced   = true;
            obj.userData.objId      = record.id;
            obj.userData.objName    = record.name;
            obj.userData.objExt     = ext;
            obj.userData.stationId  = record.stationId  || null;
            obj.userData.templateId = record.templateId || null;
            obj.userData.lineName   = record.lineName   || null;
            scene.add(obj);
            const entry = {
              id: record.id, mesh: obj, label: null, name: record.name,
              stationId:  record.stationId  || null,
              lineName:   record.lineName   || null,
              templateId: record.templateId || null,
            };
            placedRef.current = [...placedRef.current, entry];
            onObjectsChange([...placedRef.current]);
          });
        };

        try {
          if (ext === 'glb' || ext === 'gltf') makeGLTFLoader().load(url, g => onBaseLoaded(g.scene));
          else if (ext === 'obj') new OBJLoader().load(url, onBaseLoaded);
          else if (ext === 'stl') new STLLoader().load(url, geo => {
            geo.computeVertexNormals();
            onBaseLoaded(new THREE.Mesh(geo, new THREE.MeshLambertMaterial({ color: 0x90a4ae })));
          });
        } catch {}
      });
    });

    // Signal that the scene is built and ready to display
    onSceneReady && onSceneReady();

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

  // Load and place a 3D object file — cloned to every station on lineName
  const placeObject = useCallback((file, name, layoutId, lineName = null) => {
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
          placeObject(glbFile, name, layoutId, lineName);
        })
        .catch(err => {
          clearInterval(ticker);
          onConvertEnd && onConvertEnd(false);
          alert(`Conversion failed: ${err.message}`);
        });
      return;
    }

    const url = URL.createObjectURL(file);
    onPlaceStart && onPlaceStart();

    const onLoadError = (err) => {
      URL.revokeObjectURL(url);
      onPlaceEnd && onPlaceEnd();
      alert(`Failed to load model: ${err?.message || 'Unknown error'}`);
    };

    const onLoaded = (baseObj) => {
      URL.revokeObjectURL(url);
      onPlaceEnd && onPlaceEnd();

      // Strip text/label helpers from the loaded model
      baseObj.traverse(child => {
        if (child.isSprite || (child.material && child.material.map === null && child.isLine))
          child.visible = false;
      });

      // Auto-scale to ~2m on base object
      baseObj.position.set(0, 0, 0);
      baseObj.rotation.set(0, 0, 0);
      const bbox = new THREE.Box3().setFromObject(baseObj);
      const size = new THREE.Vector3();
      bbox.getSize(size);
      const maxDim = Math.max(size.x, size.y, size.z);
      if (maxDim > 0) baseObj.scale.setScalar(2.0 / maxDim);
      const bbox2 = new THREE.Box3().setFromObject(baseObj);
      const bottomY = -bbox2.min.y;

      // Determine target stations (all stations on the chosen line, or scene centre)
      const lineStations = lineName && linesRef.current[lineName];
      const stations = lineStations && lineStations.length > 0
        ? lineStations
        : [{ stationId: null, x: sceneCenterRef.current.x, z: sceneCenterRef.current.z }];

      const templateId  = Date.now().toString();
      const newEntries  = [];

      stations.forEach((station, idx) => {
        const obj = idx === 0 ? baseObj : baseObj.clone(true);
        obj.position.set(station.x, bottomY, station.z);
        obj.rotation.set(0, 0, 0);

        const objId = `${templateId}_${idx}`;
        obj.userData.isPlaced   = true;
        obj.userData.objId      = objId;
        obj.userData.objName    = name;
        obj.userData.objExt     = ext;
        obj.userData.stationId  = station.stationId || null;
        obj.userData.templateId = templateId;
        obj.userData.lineName   = lineName || null;

        scene.add(obj);
        newEntries.push({
          id: objId, mesh: obj, label: null, name,
          stationId: station.stationId || null,
          lineName:  lineName || null,
          templateId,
        });
      });

      placedRef.current = [...placedRef.current, ...newEntries];

      // Persist: one template record (with blob) + one lightweight record per station clone
      if (layoutId) {
        file.arrayBuffer().then(buf => {
          const blob = new Blob([buf], { type: file.type || 'application/octet-stream' });
          blobsRef.current[`tmpl_${templateId}`] = blob;
          z3dPutTemplate({
            key: `${layoutId}_tmpl_${templateId}`,
            layoutId, templateId, name, ext,
            fileBlob: blob,
            lineName: lineName || null,
          });
          newEntries.forEach(entry => {
            z3dPut({
              key: `${layoutId}_${entry.id}`,
              layoutId, id: entry.id, name, ext,
              templateId,
              stationId: entry.stationId || null,
              lineName:  entry.lineName  || null,
              px: entry.mesh.position.x, py: entry.mesh.position.y, pz: entry.mesh.position.z,
              rx: 0, ry: 0, rz: 0,
              sx: entry.mesh.scale.x, sy: entry.mesh.scale.y, sz: entry.mesh.scale.z,
            });
          });
        }).catch(() => {});
      }

      // Select first clone
      const first = newEntries[0];
      if (first && transformRef.current) {
        transformRef.current.setMode('translate');
        transformRef.current.attach(first.mesh);
        selectedRef.current = first;
      }

      onObjectsChange([...placedRef.current]);
    };

    if (ext === 'glb' || ext === 'gltf') {
      makeGLTFLoader().load(url, (gltf) => onLoaded(gltf.scene), undefined, onLoadError);
    } else if (ext === 'obj') {
      new OBJLoader().load(url, onLoaded, undefined, onLoadError);
    } else if (ext === 'wrl') {
      new VRMLLoader().load(url, onLoaded, undefined, onLoadError);
    } else if (ext === 'stl') {
      new STLLoader().load(url, (geometry) => {
        geometry.computeVertexNormals();
        onLoaded(new THREE.Mesh(geometry, new THREE.MeshLambertMaterial({ color: 0x90a4ae })));
      }, undefined, onLoadError);
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

  // Delete object by id (and template if it was the last clone)
  const deleteById = useCallback((id) => {
    const scene = sceneRef.current;
    const entry = placedRef.current.find(p => p.id === id);
    if (!entry || !scene) return;
    if (transformRef.current && selectedRef.current?.id === id) transformRef.current.detach();
    scene.remove(entry.mesh);
    if (entry.label) scene.remove(entry.label);
    placedRef.current = placedRef.current.filter(p => p.id !== id);
    if (selectedRef.current?.id === id) selectedRef.current = null;
    if (layoutIdRef.current) {
      z3dDel(`${layoutIdRef.current}_${id}`);
      if (entry.templateId) {
        const remaining = placedRef.current.filter(p => p.templateId === entry.templateId);
        if (remaining.length === 0) {
          z3dDelTemplate(`${layoutIdRef.current}_tmpl_${entry.templateId}`);
          delete blobsRef.current[`tmpl_${entry.templateId}`];
        }
      }
    }
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

  // Apply value-based rotation (degrees) or scale to selected object
  const updateTransformVals = useCallback((id, vals) => {
    const entry = placedRef.current.find(p => p.id === id);
    if (!entry) return;
    const m = entry.mesh;
    if (vals.rx !== undefined) m.rotation.x = vals.rx * Math.PI / 180;
    if (vals.ry !== undefined) m.rotation.y = vals.ry * Math.PI / 180;
    if (vals.rz !== undefined) m.rotation.z = vals.rz * Math.PI / 180;
    if (vals.sx !== undefined) m.scale.x = vals.sx;
    if (vals.sy !== undefined) m.scale.y = vals.sy;
    if (vals.sz !== undefined) m.scale.z = vals.sz;
    if (layoutIdRef.current) {
      z3dPut({
        key: `${layoutIdRef.current}_${id}`,
        layoutId: layoutIdRef.current,
        id, name: entry.name,
        ext:        m.userData.objExt      || 'glb',
        templateId: m.userData.templateId  || null,
        stationId:  m.userData.stationId   || null,
        lineName:   m.userData.lineName    || null,
        px: m.position.x, py: m.position.y, pz: m.position.z,
        rx: m.rotation.x, ry: m.rotation.y, rz: m.rotation.z,
        sx: m.scale.x, sy: m.scale.y, sz: m.scale.z,
      });
    }
  }, []);

  return { snapView, setTransformMode, placeObject, handleCanvasClick, handleCanvasDblClick, selectById, deleteById, renameById, updateTransformVals, stationCellsRef };
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
const Z3D_DB    = 'z3d_placed_v1';
const Z3D_STORE = 'objects';
const Z3D_TMPL  = 'templates';

function z3dOpen() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(Z3D_DB, 2);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(Z3D_STORE))
        db.createObjectStore(Z3D_STORE, { keyPath: 'key' });
      if (!db.objectStoreNames.contains(Z3D_TMPL))
        db.createObjectStore(Z3D_TMPL, { keyPath: 'key' });
    };
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
async function z3dPutTemplate(record) {
  try {
    const db = await z3dOpen();
    await new Promise((res, rej) => {
      const tx = db.transaction(Z3D_TMPL, 'readwrite');
      tx.objectStore(Z3D_TMPL).put(record);
      tx.oncomplete = res; tx.onerror = () => rej(tx.error);
    });
    db.close();
  } catch {}
}
async function z3dGetAllTemplates(layoutId) {
  try {
    const db  = await z3dOpen();
    const all = await new Promise(res => {
      const req = db.transaction(Z3D_TMPL, 'readonly').objectStore(Z3D_TMPL).getAll();
      req.onsuccess = () => res(req.result || []);
      req.onerror   = () => res([]);
    });
    db.close();
    return all.filter(r => r.layoutId === layoutId);
  } catch { return []; }
}
async function z3dDelTemplate(key) {
  try {
    const db = await z3dOpen();
    await new Promise(res => {
      const tx = db.transaction(Z3D_TMPL, 'readwrite');
      tx.objectStore(Z3D_TMPL).delete(key);
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
  const [pendingFile,       setPendingFile]       = useState(null);
  const [pendingName,       setPendingName]       = useState('');
  const [showLinePicker,    setShowLinePicker]    = useState(false);
  const [pickerLine,        setPickerLine]        = useState('');
  const [transformVals,     setTransformVals]     = useState({ rx: 0, ry: 0, rz: 0, sx: 1, sy: 1, sz: 1 });
  const [placingObject,     setPlacingObject]     = useState(false);

  useEffect(() => {
    if (activeLayoutId && !selectedLayoutId) setSelectedLayoutId(activeLayoutId);
  }, [activeLayoutId]); // eslint-disable-line

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

  const allLines = React.useMemo(() => {
    if (!layout) return [];
    return (layout.station_boxes || [])
      .filter(b => b.name)
      .map(b => ({
        name: b.name,
        count: (b.station_ids || '').split(',').filter(s => s.trim()).length,
      }));
  }, [layout]);

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

  const onPlaceStart = useCallback(() => setPlacingObject(true),  []);
  const onPlaceEnd   = useCallback(() => setPlacingObject(false), []);

  const { snapView, setTransformMode, placeObject, handleCanvasClick, handleCanvasDblClick, selectById, deleteById, renameById, updateTransformVals } =
    useThreeScene(canvasRef, layout, statusMap, zeMap, walkMode, onObjectsChange, onConvertStart, onConvertEnd, handleStationClick, isActive, handleSceneReady, onPlaceStart, onPlaceEnd);

  const handleLayoutChange = useCallback((e) => {
    setSelectedLayoutId(Number(e.target.value) || null);
    setLayout(null); setWalkMode(false); setPlacedObjects([]); setSelectedId(null);
  }, []);

  const handleFileUpload = useCallback((e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const name = file.name.replace(/\.[^/.]+$/, '');
    setPendingFile(file);
    setPendingName(name);
    setPickerLine('');
    setShowLinePicker(true);
    e.target.value = '';
  }, []);

  const handlePickerConfirm = useCallback(() => {
    if (!pendingFile) return;
    placeObject(pendingFile, pendingName, selectedLayoutId, pickerLine || null);
    setShowLinePicker(false);
    setPendingFile(null);
    setShowObjPanel(true);
  }, [pendingFile, pendingName, selectedLayoutId, pickerLine, placeObject]);

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

  // Sync transform values when selected object changes
  useEffect(() => {
    if (!selectedId) return;
    const sel = placedObjects.find(o => o.id === selectedId);
    if (!sel?.mesh) return;
    const m = sel.mesh;
    setTransformVals({
      rx: +(m.rotation.x * 180 / Math.PI).toFixed(1),
      ry: +(m.rotation.y * 180 / Math.PI).toFixed(1),
      rz: +(m.rotation.z * 180 / Math.PI).toFixed(1),
      sx: +m.scale.x.toFixed(3),
      sy: +m.scale.y.toFixed(3),
      sz: +m.scale.z.toFixed(3),
    });
  }, [selectedId]); // eslint-disable-line

  const handleTransformInput = useCallback((key, value) => {
    setTransformVals(prev => ({ ...prev, [key]: value }));
    const v = parseFloat(value);
    if (!isNaN(v) && selectedId) updateTransformVals(selectedId, { [key]: v });
  }, [selectedId, updateTransformVals]);

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
            <button className="z3d-upload-btn" onClick={() => fileInputRef.current?.click()} title="Upload GLB, OBJ or STL file">
              ⬆ Upload Object
            </button>
            <input ref={fileInputRef} type="file" accept=".glb,.gltf,.obj,.stl,.wrl,.stp,.step" style={{ display: 'none' }} onChange={handleFileUpload} />

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

        <button className="dash-refresh-btn" onClick={handleRefresh} disabled={refreshing} title="Refresh layout and records">
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
                  <button
                    key={m}
                    className={`z3d-transform-btn${transformMode === m ? ' z3d-transform-btn--active' : ''}`}
                    onClick={() => handleModeChange(m)}
                  >{lbl}</button>
                ))}
              </div>
            )}

            {/* Value-based rotation inputs */}
            {currentSelected && transformMode === 'rotate' && (
              <div className="z3d-transform-inputs">
                <div className="z3d-transform-input-label">Rotation (degrees)</div>
                {[['rx','X'],['ry','Y'],['rz','Z']].map(([key, axis]) => (
                  <div key={key} className="z3d-transform-input-row">
                    <span className="z3d-transform-axis">{axis}</span>
                    <input
                      type="number"
                      className="z3d-transform-val-input"
                      value={transformVals[key]}
                      onChange={e => handleTransformInput(key, e.target.value)}
                      step="1"
                    />
                    <span className="z3d-transform-unit">°</span>
                  </div>
                ))}
              </div>
            )}

            {/* Value-based scale inputs */}
            {currentSelected && transformMode === 'scale' && (
              <div className="z3d-transform-inputs">
                <div className="z3d-transform-input-label">Scale</div>
                {[['sx','X'],['sy','Y'],['sz','Z']].map(([key, axis]) => (
                  <div key={key} className="z3d-transform-input-row">
                    <span className="z3d-transform-axis">{axis}</span>
                    <input
                      type="number"
                      className="z3d-transform-val-input"
                      value={transformVals[key]}
                      onChange={e => handleTransformInput(key, e.target.value)}
                      step="0.01"
                      min="0.001"
                    />
                  </div>
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
                  <div className="z3d-obj-info">
                    <span className="z3d-obj-name">{obj.name}</span>
                    <div className="z3d-obj-tags">
                      {obj.lineName  && <span className="z3d-obj-line-tag">{obj.lineName}</span>}
                      {obj.stationId && <span className="z3d-obj-station-tag">{obj.stationId}</span>}
                    </div>
                  </div>
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
              {placingObject && (
                <div className="z3d-convert-overlay">
                  <div className="z3d-convert-box">
                    <div className="z3d-convert-spinner" />
                    <div className="z3d-convert-title">Loading model…</div>
                    <div className="z3d-convert-sub">Parsing and placing the 3D object — large files may take a moment</div>
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

      {/* Line picker modal */}
      {showLinePicker && (
        <div className="z3d-picker-overlay">
          <div className="z3d-picker-box">
            <div className="z3d-picker-title">Select Line</div>
            <div className="z3d-picker-sub">
              The object is uploaded <strong>once</strong> and automatically cloned to every station on the chosen line.
            </div>
            <select
              className="z3d-picker-select"
              value={pickerLine}
              onChange={e => setPickerLine(e.target.value)}
            >
              <option value="">— Free placement (no line) —</option>
              {allLines.map(line => (
                <option key={line.name} value={line.name}>
                  {line.name}  ({line.count} station{line.count !== 1 ? 's' : ''})
                </option>
              ))}
            </select>
            <div className="z3d-picker-actions">
              <button className="z3d-picker-cancel" onClick={() => { setShowLinePicker(false); setPendingFile(null); }}>Cancel</button>
              <button className="z3d-picker-confirm" onClick={handlePickerConfirm}>Place Object</button>
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

export default ZStage3DLayout;
