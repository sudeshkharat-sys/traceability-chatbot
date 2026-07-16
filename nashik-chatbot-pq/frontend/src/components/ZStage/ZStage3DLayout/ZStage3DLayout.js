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
import { layoutApi, inputApi, z3dModelApi, lineModelMappingApi } from '../../../services/api/layoutApi';
import { layeredAuditApi } from '../../../services/api/layoutApi';
import { StationDetailModal, MONTHLY_KEYS } from '../ZStageDashboard/ZStageDashboard';
import '../ZStageDashboard/ZStageDashboard.css';
import { backend_url } from '../../../services/api/config';
import authService from '../../../services/api/authService';
import './ZStage3DLayout.css';

// ── Model Presets (localStorage) ─────────────────────────────────────────────
// Keyed by normalised model name. Stores { scale, rotX, rotY, rotZ }.
const MODEL_PRESETS_KEY = 'z3d_model_presets_v1';
function loadModelPresets() {
  try { return JSON.parse(localStorage.getItem(MODEL_PRESETS_KEY) || '{}'); } catch { return {}; }
}
function saveModelPreset(modelName, preset) {
  const all = loadModelPresets();
  all[modelName.toLowerCase().trim()] = preset;
  localStorage.setItem(MODEL_PRESETS_KEY, JSON.stringify(all));
}
function getModelPreset(modelName) {
  return loadModelPresets()[modelName.toLowerCase().trim()] || null;
}

// ── Environment presets ────────────────────────────────────────────────────
// Swatch-style background/lighting moods, like picking a render environment
// in Revit/AutoCAD — no external HDR/asset downloads, just background color,
// fog and light color/intensity, so switching is instant and offline-safe.
const ENV_PRESETS = [
  {
    key: 'studio', label: 'Studio Grey', swatch: '#f0f2f5',
    bg: 0xf0f2f5, fogNear: 80, fogFar: 250,
    ambientColor: 0xffffff, ambientIntensity: 0.7,
    sunColor: 0xffffff, sunIntensity: 0.85,
    fillColor: 0xdce8ff, fillIntensity: 0.4,
  },
  {
    key: 'warm', label: 'Warm Factory', swatch: '#e8dcc8',
    bg: 0xe8dcc8, fogNear: 80, fogFar: 250,
    ambientColor: 0xfff2df, ambientIntensity: 0.75,
    sunColor: 0xfff1d6, sunIntensity: 0.9,
    fillColor: 0xcfe0ff, fillIntensity: 0.35,
  },
  {
    key: 'cool', label: 'Cool Warehouse', swatch: '#dfe6ec',
    bg: 0xdfe6ec, fogNear: 80, fogFar: 250,
    ambientColor: 0xdfe9ff, ambientIntensity: 0.65,
    sunColor: 0xffffff, sunIntensity: 0.8,
    fillColor: 0xb8c9e0, fillIntensity: 0.45,
  },
  {
    key: 'outdoor', label: 'Outdoor Daylight', swatch: '#bfe0f5',
    bg: 0xbfe0f5, fogNear: 100, fogFar: 300,
    ambientColor: 0xffffff, ambientIntensity: 0.85,
    sunColor: 0xfff6e0, sunIntensity: 1.1,
    fillColor: 0xcfe8ff, fillIntensity: 0.5,
  },
  {
    key: 'night', label: 'Night Mode', swatch: '#12151a',
    bg: 0x12151a, fogNear: 60, fogFar: 200,
    ambientColor: 0x8899aa, ambientIntensity: 0.35,
    sunColor: 0x88aaff, sunIntensity: 0.5,
    fillColor: 0x445566, fillIntensity: 0.25,
  },
];
const DEFAULT_ENV_KEY = ENV_PRESETS[0].key;
const ENV_PRESET_KEY_LS = 'z3d_env_preset_v1'; // layoutId → preset key
function loadEnvPresetMap() {
  try { return JSON.parse(localStorage.getItem(ENV_PRESET_KEY_LS) || '{}'); } catch { return {}; }
}
function getEnvPreset(layoutId) {
  const key = loadEnvPresetMap()[layoutId];
  return ENV_PRESETS.find(p => p.key === key) || ENV_PRESETS[0];
}
function saveEnvPreset(layoutId, key) {
  const all = loadEnvPresetMap();
  all[layoutId] = key;
  localStorage.setItem(ENV_PRESET_KEY_LS, JSON.stringify(all));
}

// ── Line name fuzzy matcher ────────────────────────────────────────────────────
// Handles variations like "Trim 1" / "Trim Line" / "trim", "U/B" / "Under Break Line"
function _normLine(name) {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]/g, ' ')          // non-alphanumeric → space
    .replace(/\b(line|lines|no|num|number|the)\b/g, '') // strip noise words
    .replace(/\b\d+\b/g, '')             // strip lone numbers (1, 2, 3…)
    .replace(/\s+/g, ' ')
    .trim();
}
function _abbrev(normalized) {
  // First letter of each word, eg. "under break" → "ub"
  return normalized.split(' ').filter(Boolean).map(w => w[0]).join('');
}
function lineNamesMatch(a, b) {
  if (!a || !b) return false;
  const na = _normLine(a);
  const nb = _normLine(b);
  if (!na || !nb) return false;
  if (na === nb) return true;
  if (na.includes(nb) || nb.includes(na)) return true;
  // abbreviation: "U/B" → "ub" matches "under break" → "ub"
  const abba = _abbrev(na);
  const abbb = _abbrev(nb);
  if (abba && abba === nb) return true;
  if (abbb && abbb === na) return true;
  if (abba && abbb && abba === abbb) return true;
  return false;
}

// A real model name, not missing/empty and not the literal string "undefined"
// or "null" — FormData.append() silently stringifies a JS undefined/null
// value passed to it into that exact text, so a genuinely-missing model_name
// can end up stored as a real (garbage) 4-9 character string, not a falsy one.
function isValidModelName(name) {
  return !!name && name !== 'undefined' && name !== 'null';
}
function formatFileSize(bytes) {
  if (!bytes && bytes !== 0) return '';
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// Module-level GLB template cache — keyed by model name (lowercase).
// Once a model is loaded this session, subsequent layouts skip the download
// entirely and clone directly from the cached Three.js scene.
const _modelTemplateCache = new Map(); // name → THREE.Object3D

function getCachedTemplate(name) {
  if (!isValidModelName(name)) return null;
  return _modelTemplateCache.get(name.toLowerCase()) || null;
}
function setCachedTemplate(name, template) {
  if (!isValidModelName(name)) return;
  _modelTemplateCache.set(name.toLowerCase(), template);
}

// Bounding-box measurements (autoScale, floor offset, centering offset,
// footprint) only depend on a model's geometry + its rotation/scale — not on
// where it's placed. Box3().setFromObject() traverses every vertex, so doing
// it 3x per station adds up fast on a line with many stations sharing the
// same model/rotation/scale (the common auto-seeded case). Cache it once per
// (model, scale, rotation) combo instead of recomputing per station.
const _placementGeoCache = new Map();

// Bounding-box measurements are only valid for the geometry they were
// measured from. A re-upload (same name, new file) changes the geometry
// without changing scale/rotation, so the geoKey stays identical — evict
// every cached entry for this model name whenever its template is
// (re)loaded, or stale offsets get applied to the new mesh in other layouts.
function invalidateGeoCache(name) {
  if (!isValidModelName(name)) return;
  const prefix = `${name}::`;
  for (const key of _placementGeoCache.keys()) {
    if (key.startsWith(prefix)) _placementGeoCache.delete(key);
  }
}

// Single shared DRACOLoader — decoder is downloaded and initialised once,
// then reused for every upload. Saves 1-3 s per upload vs creating a new one each time.
const _sharedDraco = new DRACOLoader();
_sharedDraco.setDecoderPath('/draco/');
_sharedDraco.preload(); // start downloading decoder immediately on page load

function makeGLTFLoader() {
  const loader = new GLTFLoader();
  loader.setDRACOLoader(_sharedDraco);
  return loader;
}

// Bumped whenever the placement persistence logic changes — logged on every
// scene build so "is the browser actually running the new bundle" can be
// answered from a console screenshot instead of guessing.
const Z3D_BUILD_TAG = 'offset-persistence-v2';

// A transform save that fails leaves the object looking correct on screen but
// silently reverts it on the next refresh — the single most confusing failure
// mode this component has. Alert the first time it happens (console-only for
// repeats) so it's diagnosed at drag-time, not discovered a day later.
let _transformSaveErrorAlerted = false;
function reportTransformSaveError(err) {
  const status = err?.response?.status;
  const detail = err?.response?.data?.detail || err?.message || 'unknown error';
  console.error('[Z3D] Transform save FAILED — changes will revert on refresh:', status, detail);
  if (!_transformSaveErrorAlerted) {
    _transformSaveErrorAlerted = true;
    alert(
      `Saving the object's position/rotation to the server FAILED (${status ?? ''} ${detail}).\n` +
      `The change you just made will revert when the page is refreshed.\n` +
      `Check that the backend is running the latest code and was restarted.`
    );
  }
}

// Build the transform payload to persist for a placed entry. Station-bound
// entries (baseX/baseZ set) save px/pz as an OFFSET from their station anchor
// with pos_is_offset=true — the loader adds it back on top of the station's
// current position, so a sideways drag survives refresh AND still follows the
// station if its 2D box is moved. Free objects save absolute coords; px gets
// the same xOff compensation the loader applies in reverse (geoXOff), so a
// save/reload round-trip lands exactly where the object was left.
function buildTransformPayload(entry) {
  const mesh = entry.mesh;
  const stationBound = entry.baseX != null && entry.baseZ != null;
  const common = {
    py: mesh.position.y,
    rx: mesh.rotation.x, ry: mesh.rotation.y, rz: mesh.rotation.z,
    sx: mesh.scale.x, sy: mesh.scale.y, sz: mesh.scale.z,
  };
  if (stationBound) {
    return {
      ...common,
      px: mesh.position.x - entry.baseX,
      pz: mesh.position.z - entry.baseZ,
      pos_is_offset: true,
    };
  }
  return {
    ...common,
    px: mesh.position.x + (mesh.userData.geoXOff || 0),
    pz: mesh.position.z,
    pos_is_offset: false,
  };
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
// Real extruded I/H-beam profile (flanges + web) instead of a solid box — a
// plain rectangular block reads as a placeholder, not structural steel.
// "vertical"     — square post along Y
// "horizontal-x" — beam along X
// "horizontal-z" — beam along Z
const COL_W = 0.35;  // column / beam cross-section width
const COL_H = 0.22;  // beam cross-section height (thinner for horizontal)

// 12-point outline of a standard I/H profile, centered at origin, in the
// shape's local XY plane. Extruded along local Z to make the beam's length.
function buildIProfileShape(width, height) {
  const flangeT = Math.min(height * 0.24, height / 2 - 0.01);
  const webT    = Math.min(width * 0.34, width / 2 - 0.01);
  const w2 = width / 2, h2 = height / 2, wt2 = webT / 2;
  const shape = new THREE.Shape();
  shape.moveTo(-w2, -h2);
  shape.lineTo(w2, -h2);
  shape.lineTo(w2, -h2 + flangeT);
  shape.lineTo(wt2, -h2 + flangeT);
  shape.lineTo(wt2, h2 - flangeT);
  shape.lineTo(w2, h2 - flangeT);
  shape.lineTo(w2, h2);
  shape.lineTo(-w2, h2);
  shape.lineTo(-w2, h2 - flangeT);
  shape.lineTo(-wt2, h2 - flangeT);
  shape.lineTo(-wt2, -h2 + flangeT);
  shape.lineTo(-w2, -h2 + flangeT);
  shape.closePath();
  return shape;
}
function makeIBeamGeometry(width, height, length) {
  const geo = new THREE.ExtrudeGeometry(buildIProfileShape(width, height), {
    depth: length, bevelEnabled: false, curveSegments: 1,
  });
  // Extrude's default UV generator scales V by actual world-unit depth
  // (not 0..1 like BoxGeometry) — normalize so the streak texture's repeat
  // count stays consistent instead of getting finer on longer beams.
  const uv = geo.getAttribute('uv');
  for (let i = 0; i < uv.count; i++) uv.setY(i, uv.getY(i) / length);
  uv.needsUpdate = true;
  geo.translate(0, 0, -length / 2); // center along the extrusion (length) axis
  return geo;
}
function makeIBeam(length, mat, orientation) {
  let geo, rotX = 0, rotY = 0;
  if (orientation === 'vertical') {
    geo = makeIBeamGeometry(COL_W, COL_W, length);
    rotX = -Math.PI / 2; // extrusion (local Z) axis -> world Y
  } else if (orientation === 'horizontal-x') {
    geo = makeIBeamGeometry(COL_W, COL_H, length);
    rotY = -Math.PI / 2; // extrusion (local Z) axis -> world X
  } else {
    geo = makeIBeamGeometry(COL_W, COL_H, length); // extrusion axis already world Z
  }
  const mesh = new THREE.Mesh(geo, mat);
  mesh.rotation.set(rotX, rotY, 0);
  return mesh;
}

// ── Hanger support bar ─────────────────────────────────────────────────────────
// Stations whose placed model is a "hanger" get an extra horizontal beam
// 1 m below the top of the structure — like the rail inside a cupboard —
// so the hanger has a bar to hang from / be height-adjusted against. Bars
// are kept on scene.userData so they survive the cached-scene reuse path
// and are added/removed automatically as hanger models are placed or deleted.
const HANGER_NAME_RE = /hanger/i;
const HANGER_BAR_DROP = 1.0; // metres below the top beam
function syncHangerBars(scene, placedEntries, posMap) {
  if (!scene) return;
  if (!scene.userData.hangerBars) scene.userData.hangerBars = new Map(); // stationId → mesh
  const bars = scene.userData.hangerBars;
  const wanted = new Set();
  placedEntries.forEach(p => {
    if (p.stationId && HANGER_NAME_RE.test(p.name || '')) wanted.add(p.stationId);
  });
  for (const [sid, mesh] of [...bars]) {
    if (!wanted.has(sid)) { scene.remove(mesh); bars.delete(sid); }
  }
  wanted.forEach(sid => {
    if (bars.has(sid)) return;
    const pos = posMap[sid];
    if (!pos) return;
    const bar = makeIBeam(CELL_W, getStructMaterial(), 'horizontal-x');
    bar.position.set(pos.x, HEIGHT - HANGER_BAR_DROP, pos.z);
    scene.add(bar);
    bars.set(sid, bar);
  });
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

// ── Streak texture generator for the structural frame ───────────────────────────
// Horizontal streak variation baked into one small texture, tiled — reads as
// brushed metal instead of a flat plastic color, no extra material cost.
function makeStreakTexture(baseColor) {
  const w = 32, h = 128;
  const canvas = document.createElement('canvas');
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = baseColor;
  ctx.fillRect(0, 0, w, h);
  for (let y = 0; y < h; y++) {
    const delta = (Math.random() - 0.5) * 40;
    ctx.fillStyle = delta >= 0 ? `rgba(255,255,255,${delta / 255})` : `rgba(0,0,0,${-delta / 255})`;
    ctx.fillRect(0, y, w, 1);
  }
  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(1, 4);
  return tex;
}
let _steelTex = null;
function getSteelTexture() {
  // Neutral mill/galvanized-steel grey — dark charcoal read as flat black
  // plastic once combined with the real I-beam profile; a mid grey lets the
  // PBR metal shading actually show a highlight gradient.
  if (!_steelTex) _steelTex = makeStreakTexture('#9aa1a6');
  return _steelTex;
}
let _steelStructMat = null;
function getStructMaterial() {
  // Real metalness/roughness PBR instead of Phong — Phong's specular is a
  // fixed highlight color with no sense of reflectivity, which is why the
  // beams read as flat plastic. Needs an envMap (assigned alongside the
  // renderer, directly on this material — not scene.environment, which
  // would also dull every uploaded model's PBR material) to actually show
  // a metal-like reflection gradient.
  if (!_steelStructMat) {
    _steelStructMat = new THREE.MeshStandardMaterial({ map: getSteelTexture(), metalness: 0.85, roughness: 0.4 });
  }
  return _steelStructMat;
}

// ── Lightweight procedural environment for PBR metal reflections ───────────────
// A metalness/roughness material with no envMap has nothing to reflect and
// renders almost black except for direct specular highlights — this builds
// a tiny "room" (walls + a couple of bright panels) purely from core THREE
// primitives, no external HDR asset, just enough variation for
// PMREMGenerator to bake into a believable metal reflection.
function buildEnvScene() {
  const envScene = new THREE.Scene();
  const boxGeo = new THREE.BoxGeometry();
  boxGeo.deleteAttribute('uv');
  const room = new THREE.Mesh(boxGeo, new THREE.MeshStandardMaterial({ side: THREE.BackSide, color: 0x888888 }));
  room.scale.set(20, 20, 20);
  envScene.add(room);
  const panel1 = new THREE.Mesh(boxGeo, new THREE.MeshBasicMaterial({ color: 0xffffff }));
  panel1.scale.set(4, 0.1, 1); panel1.position.set(-3, 6, -3);
  envScene.add(panel1);
  const panel2 = new THREE.Mesh(boxGeo, new THREE.MeshBasicMaterial({ color: 0xffe4b5 }));
  panel2.scale.set(0.1, 4, 1); panel2.position.set(6, 2, -3);
  envScene.add(panel2);
  return envScene;
}

// ── Shared hazard-stripe texture + base sleeve for column feet ─────────────────
// Classic yellow/black caution striping, baked once and tiled on a short box
// mesh mounted at the base of every column — a cheap, instantly-readable
// factory-floor safety cue.
let _hazardTex = null;
function getHazardStripeTexture() {
  if (_hazardTex) return _hazardTex;
  const size = 64;
  const canvas = document.createElement('canvas');
  canvas.width = size; canvas.height = size;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#f5c400';
  ctx.fillRect(0, 0, size, size);
  ctx.fillStyle = '#1a1a1a';
  ctx.save();
  ctx.translate(size / 2, size / 2);
  ctx.rotate(Math.PI / 4);
  const stripeW = size / 4;
  for (let x = -size * 1.5; x < size * 1.5; x += stripeW * 2) {
    ctx.fillRect(x, -size * 1.5, stripeW, size * 3);
  }
  ctx.restore();
  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(1, 1.5);
  _hazardTex = tex;
  return tex;
}
const HAZARD_H = 0.12; // matches floor slab thickness so the base sits flush, no visible step
const _hazardGeo = new THREE.BoxGeometry(COL_W + 0.02, HAZARD_H, COL_W + 0.02);
const _hazardMat = new THREE.MeshBasicMaterial({ map: getHazardStripeTexture() });
function makeHazardBase() {
  const mesh = new THREE.Mesh(_hazardGeo, _hazardMat);
  mesh.position.y = HAZARD_H / 2;
  return mesh;
}

// One flat hazard-stripe segment used to build the line-perimeter border —
// same diagonal yellow/black texture as the column-base stripe, but each
// segment gets its own cloned texture so its repeat can be scaled to its own
// length (the shared _hazardTex/_hazardMat repeat is tuned for the tiny
// column base and would look wrong stretched across a long station edge).
const BORDER_T = 0.12; // border ribbon thickness (footprint)
const BORDER_H = 0.05; // border ribbon height above floor
const _borderGeoCache = new Map(); // "alongX:length" -> BoxGeometry
function makeHazardBorderSegment(length, alongX) {
  const key = `${alongX}:${length}`;
  let geo = _borderGeoCache.get(key);
  if (!geo) {
    geo = alongX
      ? new THREE.BoxGeometry(length, BORDER_H, BORDER_T)
      : new THREE.BoxGeometry(BORDER_T, BORDER_H, length);
    _borderGeoCache.set(key, geo);
  }
  const tex = getHazardStripeTexture().clone();
  tex.needsUpdate = true;
  const period = 0.5; // world units per stripe repeat cycle
  tex.repeat.set(Math.max(1, Math.round(length / period)), 1);
  const mesh = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ map: tex }));
  return mesh;
}

// ── Shared floor texture — baked concrete speckle + soft AO vignette ───────────
// Faking ambient occlusion in the texture itself costs nothing at render time
// (no shadow maps), and one texture instance is shared across every station floor.
let _floorTex = null;
let _floorRoughTex = null;
function buildFloorTextures() {
  const size = 512; // doubled from 256 — floor tile covers a 6x6 unit area, low-res read blurry/flat up close
  const colorCanvas = document.createElement('canvas');
  colorCanvas.width = size; colorCanvas.height = size;
  const ctx = colorCanvas.getContext('2d');
  // Warm sand/beige base — most placed equipment models are grey, and both
  // the previous blue and off-white shades ended up reading too close to
  // that grey on screen. A warm tan (common warehouse epoxy-floor color)
  // gives clear hue contrast against grey models instead of blending in.
  ctx.fillStyle = '#c9b48c';
  ctx.fillRect(0, 0, size, size);

  // Roughness variation painted in parallel (dark = glossier/sealed epoxy,
  // light = duller/worn) so the PBR material picks up real sheen variation
  // instead of a uniform plastic-flat shine across the whole floor.
  const roughCanvas = document.createElement('canvas');
  roughCanvas.width = size; roughCanvas.height = size;
  const rctx = roughCanvas.getContext('2d');
  rctx.fillStyle = '#8c8c8c'; // mid roughness base
  rctx.fillRect(0, 0, size, size);

  // Two-tone aggregate speckle — darker flecks + lighter flecks, reads more
  // like a real terrazzo/epoxy floor than single-tone noise.
  const speckleCount = size * size * 0.014;
  for (let i = 0; i < speckleCount; i++) {
    const x = Math.random() * size, y = Math.random() * size;
    const dark = Math.random() < 0.5;
    const shade = (dark ? -1 : 1) * (10 + Math.random() * 16);
    ctx.fillStyle = `rgba(${201 + shade},${180 + shade},${140 + shade},0.45)`;
    const s = 1 + Math.random() * 2;
    ctx.fillRect(x, y, s, s);
    rctx.fillStyle = dark ? 'rgba(40,40,40,0.35)' : 'rgba(220,220,220,0.3)';
    rctx.fillRect(x, y, s, s);
  }
  // Soft warm-brown veining — a few faint curved strokes, not a repeating pattern
  ctx.strokeStyle = 'rgba(150,125,90,0.25)';
  ctx.lineWidth = 2.5;
  for (let i = 0; i < 5; i++) {
    const x0 = Math.random() * size, y0 = Math.random() * size;
    const x1 = x0 + (Math.random() - 0.5) * size, y1 = y0 + (Math.random() - 0.5) * size;
    const cx = (x0 + x1) / 2 + (Math.random() - 0.5) * size * 0.4;
    const cy = (y0 + y1) / 2 + (Math.random() - 0.5) * size * 0.4;
    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.quadraticCurveTo(cx, cy, x1, y1);
    ctx.stroke();
  }

  _floorTex = new THREE.CanvasTexture(colorCanvas);
  _floorRoughTex = new THREE.CanvasTexture(roughCanvas);
}
function getFloorTexture() {
  if (!_floorTex) buildFloorTextures();
  return _floorTex;
}
function getFloorRoughnessTexture() {
  if (!_floorRoughTex) buildFloorTextures();
  return _floorRoughTex;
}
let _floorMat = null;
function getFloorMaterial() {
  // PBR instead of Phong, same reasoning as the column/beam rework — Phong's
  // fixed specular highlight reads as flat plastic. Floor isn't metal
  // (metalness 0) but a sealed epoxy coating does pick up soft environment
  // reflections, which is what roughness + an envMap (assigned directly on
  // this material, see the renderer-setup effect) gives it.
  if (!_floorMat) {
    _floorMat = new THREE.MeshStandardMaterial({
      map: getFloorTexture(), roughnessMap: getFloorRoughnessTexture(),
      roughness: 0.6, metalness: 0,
    });
  }
  return _floorMat;
}

// ── Station shell ──────────────────────────────────────────────────────────────
function buildStationShell(box, statusMap, zeMap, scene) {
  const group   = new THREE.Group();
  const count   = box.station_count || 1;
  const totalW  = count * CELL_W;
  const originX = box._x3d ?? (box.position_x || 0) * SCALE;
  const originZ = box._z3d ?? (box.position_y || 0) * SCALE;
  const structMat = getStructMaterial();

  // ── 4 corner columns (+ hazard-stripe base) ──
  [[originX, originZ], [originX + totalW, originZ],
   [originX, originZ + DEPTH], [originX + totalW, originZ + DEPTH]]
    .forEach(([cx, cz]) => {
      const col = makeIBeam(HEIGHT, structMat, 'vertical');
      col.position.set(cx, HEIGHT / 2, cz);
      group.add(col);
      const hazard = makeHazardBase();
      hazard.position.set(cx, 0, cz);
      group.add(hazard);
    });

  // ── Middle columns on FRONT and BACK faces only (door-frame look) ──
  // One middle column per cell boundary on front (Z=originZ) and back (Z=originZ+DEPTH)
  for (let i = 1; i < count; i++) {
    const mx = originX + i * CELL_W;
    [originZ, originZ + DEPTH].forEach(cz => {
      const col = makeIBeam(HEIGHT, structMat, 'vertical');
      col.position.set(mx, HEIGHT / 2, cz);
      group.add(col);
      const hazard = makeHazardBase();
      hazard.position.set(mx, 0, cz);
      group.add(hazard);
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

    // Concrete-look floor (baked texture, shared across all stations) with blue border line
    const floorW = CELL_W - 0.05, floorD = DEPTH - 0.05;
    const floor  = new THREE.Mesh(
      new THREE.BoxGeometry(floorW, 0.12, floorD),
      getFloorMaterial()
    );
    floor.position.set(cellCX, 0.06, cellCZ);
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

  // ── Yellow/black hazard-stripe border around the entire line ──────────────────
  // Same stripe treatment as the column-base safety markers, run around the
  // whole line perimeter instead of a plain blue line.
  const borderY = 0.03;
  const frontBorder = makeHazardBorderSegment(totalW, true);
  frontBorder.position.set(originX + totalW / 2, borderY, originZ);
  group.add(frontBorder);
  const backBorder = makeHazardBorderSegment(totalW, true);
  backBorder.position.set(originX + totalW / 2, borderY, originZ + DEPTH);
  group.add(backBorder);
  const leftBorder = makeHazardBorderSegment(DEPTH, false);
  leftBorder.position.set(originX, borderY, originZ + DEPTH / 2);
  group.add(leftBorder);
  const rightBorder = makeHazardBorderSegment(DEPTH, false);
  rightBorder.position.set(originX + totalW, borderY, originZ + DEPTH / 2);
  group.add(rightBorder);

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
  bc.fillStyle = '#1a237e';
  bc.textAlign = 'center'; bc.textBaseline = 'middle';
  // Auto-shrink font so long line names stay inside the board instead of overflowing
  const maxTextW = bW - 40; // padding on both sides
  let boxFontSize = 68;
  bc.font = `bold ${boxFontSize}px Arial`;
  while (bc.measureText(boxLabel).width > maxTextW && boxFontSize > 20) {
    boxFontSize -= 2;
    bc.font = `bold ${boxFontSize}px Arial`;
  }
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
function useThreeScene(canvasRef, layout, statusMapProp, zeMapProp, walkMode, onObjectsChange, onConvertStart, onConvertEnd, onStationClick, isActive, onSceneReady, onModelProgress, canEdit = true) {
  // Model editing (move/rotate/scale gizmo) is admin-only — kept in a ref so
  // the click handlers below read the current value without re-running the
  // whole scene effect.
  const canEditRef = useRef(canEdit);
  useEffect(() => { canEditRef.current = canEdit; }, [canEdit]);
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
  const ambientLightRef = useRef(null);
  const sunLightRef     = useRef(null);
  const fillLightRef    = useRef(null);
  const envPresetKeyRef = useRef(DEFAULT_ENV_KEY);
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
  const dirtyRef       = useRef(true);   // render dirty flag — set true whenever scene changes
  // Last-2 built scenes, keyed by layout id — lets switching back to a
  // recently-viewed layout skip the full structure-build + model-download
  // pipeline entirely. Invalidated per-entry whenever the layout's station
  // boxes/connections/Z-E data actually differ from what's cached, so a real
  // edit is never hidden behind a stale cached scene. Renderer/camera/controls
  // are still created fresh every time (untouched, same as before this
  // change) — only the expensive scene *content* is what gets reused.
  const layoutSceneCacheRef = useRef(new Map()); // layoutId → { scene, signature, stationPosMap, center, span, placedEntries }
  useEffect(() => { walkModeRef.current = walkMode; }, [walkMode]);

  // Applies a background/lighting preset to the live renderer + scene +
  // lights. Pure state tweak — no geometry rebuild — so it's safe to call
  // both once on scene mount and on-demand when the user picks a swatch.
  const applyEnvPresetInternal = useCallback((key) => {
    const preset  = ENV_PRESETS.find(p => p.key === key) || ENV_PRESETS[0];
    const renderer = rendererRef.current;
    const scene     = sceneRef.current;
    if (!renderer || !scene) return;
    renderer.setClearColor(preset.bg);
    if (scene.fog) {
      scene.fog.color.set(preset.bg);
      scene.fog.near = preset.fogNear;
      scene.fog.far  = preset.fogFar;
    }
    if (ambientLightRef.current) {
      ambientLightRef.current.color.set(preset.ambientColor);
      ambientLightRef.current.intensity = preset.ambientIntensity;
    }
    if (sunLightRef.current) {
      sunLightRef.current.color.set(preset.sunColor);
      sunLightRef.current.intensity = preset.sunIntensity;
    }
    if (fillLightRef.current) {
      fillLightRef.current.color.set(preset.fillColor);
      fillLightRef.current.intensity = preset.fillIntensity;
    }
    envPresetKeyRef.current = preset.key;
    dirtyRef.current = true;
  }, []);

  // Public entry point — also persists the choice per-layout so it's
  // remembered next time this layout is opened.
  const setEnvironment = useCallback((key) => {
    if (layoutIdRef.current != null) saveEnvPreset(layoutIdRef.current, key);
    applyEnvPresetInternal(key);
  }, [applyEnvPresetInternal]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !layout) return;

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
    // Cap pixel ratio at 1.5 — full devicePixelRatio (2-3×) multiplies GPU work by 4-9× for no visible benefit
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    // Guard against 0×0 when tab is hidden — ResizeObserver will correct once visible
    renderer.setSize(Math.max(1, canvas.clientWidth), Math.max(1, canvas.clientHeight));
    renderer.setClearColor(0xf0f2f5);
    rendererRef.current = renderer;

    // Try to reuse a previously-built scene for this exact layout instead of
    // redoing the full structure-build + model-download pipeline. Invalidated
    // whenever the layout's boxes/connections/Z-E data actually differ from
    // what's cached, so a real edit always gets a fresh, correct rebuild
    // rather than a stale cached view.
    const sceneSignature = JSON.stringify({
      boxes: (layout.station_boxes || []).map(b => ({
        id: b.id, name: b.name, count: b.station_count,
        ids: b.station_ids, x: b.position_x, y: b.position_y, data: b.station_data,
      })),
      conns: (layout.connections || []).map(c => [c.from_box_id, c.to_box_id]),
      ze: zeMapRef.current,
    });
    const cachedScene   = layoutSceneCacheRef.current.get(layout.id);
    const canReuseScene = !!cachedScene && cachedScene.signature === sceneSignature;

    let scene, camera;
    if (canReuseScene) {
      scene = cachedScene.scene;
      sceneRef.current = scene;
      stationPosRef.current = cachedScene.stationPosMap;
      placedRef.current = cachedScene.placedEntries;
      sceneCenterRef.current.copy(cachedScene.center);
      sceneSpanRef.current = cachedScene.span;

      const aspect = canvas.clientWidth && canvas.clientHeight
        ? canvas.clientWidth / canvas.clientHeight : 1;
      camera = new THREE.PerspectiveCamera(60, aspect, 0.1, 300);
      cameraRef.current = camera;
      const c = cachedScene.center, span = cachedScene.span;
      camera.position.set(c.x, span * 0.8, c.z + span * 0.9);
      camera.lookAt(c.x, 0, c.z);

      // Lights live on the reused scene's userData (stashed when it was
      // first built below) — grab them so environment-preset changes can
      // still reach them without rebuilding the whole scene.
      const cachedLights = scene.userData.lights || {};
      ambientLightRef.current = cachedLights.ambient || null;
      sunLightRef.current     = cachedLights.sun || null;
      fillLightRef.current    = cachedLights.fill || null;

      onObjectsChange([...placedRef.current]);
    } else {
      scene = new THREE.Scene();
      scene.fog = new THREE.Fog(0xf0f2f5, 80, 250);
      sceneRef.current = scene;

      const aspect = canvas.clientWidth && canvas.clientHeight
        ? canvas.clientWidth / canvas.clientHeight : 1;
      camera = new THREE.PerspectiveCamera(60, aspect, 0.1, 300);
      cameraRef.current = camera;

      const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
      scene.add(ambientLight);
      // "Sun" — no shadow casting, just directional highlight/modeling light.
      const dir = new THREE.DirectionalLight(0xffffff, 0.85);
      dir.position.set(20, 40, 25); scene.add(dir);
      scene.add(dir.target);
      // Fill light from opposite side to soften the sun's highlight
      const fill = new THREE.DirectionalLight(0xdce8ff, 0.4);
      fill.position.set(-20, 10, -20); scene.add(fill);
      scene.add(new THREE.GridHelper(200, 100, 0xb0bec5, 0xdde1e7));

      ambientLightRef.current = ambientLight;
      sunLightRef.current     = dir;
      fillLightRef.current    = fill;
      // Stashed on the scene itself so a later cache-reuse pass (the branch
      // above) can find these same light instances instead of losing them.
      scene.userData.lights = { ambient: ambientLight, sun: dir, fill };

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

      // Within a row, boxes were placed left-to-right using their raw 2D
      // position_x with no minimum-gap enforcement (unlike between rows,
      // where MIN_GAP is already enforced above). Two boxes sitting at
      // similar/identical position_x in the SAME row therefore could
      // compute to the exact same 3D X — confirmed via a real report where
      // two different boxes' stations landed on the identical (x, z)
      // coordinate, hiding one model inside/behind the other. Fix: within
      // each row, walk boxes left-to-right (by their original position_x,
      // so relative order is preserved) and push any box whose raw X would
      // overlap the previous box's footprint out past it + MIN_GAP.
      const boxesByBand = {};
      boxes.forEach(b => {
        const band = rowBand(b.position_y);
        if (!boxesByBand[band]) boxesByBand[band] = [];
        boxesByBand[band].push(b);
      });
      const xById = new Map(); // box.id -> resolved _x3d
      Object.values(boxesByBand).forEach(rowBoxes => {
        const sorted = [...rowBoxes].sort((a, b) => (a.position_x || 0) - (b.position_x || 0));
        let cursorX = null;
        sorted.forEach(b => {
          const rawX = (b.position_x || 0) * scaleX;
          const width = (b.station_count || 1) * CELL_W;
          const x = cursorX === null ? rawX : Math.max(rawX, cursorX);
          xById.set(b.id, x);
          cursorX = x + width + MIN_GAP;
        });
      });

      const layoutBoxes = boxes.map(b => ({
        ...b,
        _x3d: xById.get(b.id) ?? (b.position_x || 0) * scaleX,
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
      let sunCX = 0, sunCZ = 0, sunSpan = 20;
      if (boxes.length) {
        const cx = (minX + maxX) / 2, cz = (minZ + maxZ) / 2;
        const span = Math.max(maxX - minX, maxZ - minZ, 10);
        sceneCenterRef.current.set(cx, 0, cz);
        sceneSpanRef.current = span;
        camera.position.set(cx, span * 0.8, cz + span * 0.9);
        camera.lookAt(cx, 0, cz);
        sunCX = cx; sunCZ = cz; sunSpan = span;
      } else {
        camera.position.set(0, 20, 30); camera.lookAt(0, 0, 0);
      }

      const sunDist = sunSpan * 1.2;
      dir.position.set(sunCX + sunDist * 0.5, sunDist * 0.9, sunCZ + sunDist * 0.4);
      dir.target.position.set(sunCX, 0, sunCZ);
      dir.target.updateMatrixWorld();
    }

    // Environment map is tied to the WebGL context of the renderer that
    // baked it — same issue as the shadow-map dispose fix above. Regenerate
    // it against the current renderer every time (cheap, tiny scene) rather
    // than trusting a texture potentially baked by a since-disposed renderer.
    //
    // Assigned directly to the structure/floor materials' .envMap instead of
    // scene.environment — scene.environment applies to EVERY PBR material in
    // the scene with no opt-out, which was silently dulling/greying out
    // uploaded models (most GLB exports use MeshStandardMaterial too, so
    // they picked up this same flat grey room reflection). Per-material
    // envMap keeps the reflection scoped to only the meshes it was built for.
    const structMatForEnv = getStructMaterial();
    const floorMatForEnv  = getFloorMaterial();
    if (structMatForEnv.envMap) structMatForEnv.envMap.dispose();
    const pmrem = new THREE.PMREMGenerator(renderer);
    const envTex = pmrem.fromScene(buildEnvScene(), 0.04).texture;
    structMatForEnv.envMap = envTex;
    structMatForEnv.needsUpdate = true;
    floorMatForEnv.envMap = envTex;
    floorMatForEnv.needsUpdate = true;
    pmrem.dispose();

    // Apply whichever environment/background preset was last picked for this
    // layout (defaults to Studio Grey) — same on a fresh build or a reused
    // cached scene, since it only touches renderer/fog/light state, not geometry.
    applyEnvPresetInternal(getEnvPreset(layout.id).key);

    const orbit = new OrbitControls(camera, renderer.domElement);
    orbit.enableDamping = true; orbit.dampingFactor = 0.08;
    orbit.minDistance = 2; orbit.maxDistance = 200;
    orbitRef.current = orbit;

    // TransformControls
    const tc = new TransformControls(camera, renderer.domElement);

    // Absolute-delta approach: record leader start pos + each member start pos at drag begin.
    // During drag, apply (leaderCurrent - leaderStart) to each member's start pos.
    // More reliable than incremental deltas which can drift or miss the first frame.
    let leaderDragStart = null;
    const memberDragStarts = new Map(); // id → Vector3

    tc.addEventListener('objectChange', () => {
      const sel = selectedRef.current;
      if (!sel?.lineGroupId || !leaderDragStart) return;
      const leader = sel.mesh;
      const dx = leader.position.x - leaderDragStart.x;
      const dy = leader.position.y - leaderDragStart.y;
      const dz = leader.position.z - leaderDragStart.z;
      // Only sync the property the active gizmo actually changes — a plain
      // translate drag must never touch siblings' rotation/scale. Previously
      // this unconditionally copied the leader's rotation+scale onto every
      // other station on the line on EVERY drag (including pure moves), so
      // moving one station's object silently reset every other station's
      // rotation/scale to match the leader's, even though the user never
      // touched rotate/scale.
      placedRef.current
        .filter(p => p.lineGroupId === sel.lineGroupId && p.id !== sel.id)
        .forEach(m => {
          if (tc.mode === 'translate') {
            const start = memberDragStarts.get(m.id);
            if (start) m.mesh.position.set(start.x + dx, start.y + dy, start.z + dz);
          } else if (tc.mode === 'rotate') {
            m.mesh.rotation.copy(leader.rotation);
          } else if (tc.mode === 'scale') {
            m.mesh.scale.copy(leader.scale);
          }
        });
      dirtyRef.current = true;
    });

    tc.addEventListener('dragging-changed', (e) => {
      orbit.enabled = !e.value;
      if (e.value && selectedRef.current?.lineGroupId) {
        // Drag started — snapshot positions of leader and all group members
        leaderDragStart = selectedRef.current.mesh.position.clone();
        memberDragStarts.clear();
        placedRef.current
          .filter(p => p.lineGroupId === selectedRef.current.lineGroupId && p.id !== selectedRef.current.id)
          .forEach(m => memberDragStarts.set(m.id, m.mesh.position.clone()));
      } else if (!e.value) {
        leaderDragStart = null;
        memberDragStarts.clear();
        // Drag finished — persist updated transforms to server
        if (selectedRef.current) {
          const sel = selectedRef.current;
          const targets = sel.lineGroupId
            ? placedRef.current.filter(p => p.lineGroupId === sel.lineGroupId)
            : [sel];
          targets.forEach(t => {
            const sid = t.mesh.userData.serverModelId;
            if (!sid) return;
            z3dModelApi.updateTransform(sid, buildTransformPayload(t))
              .catch(reportTransformSaveError);
          });
        }
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

    // Reload previously saved placed objects from server — skipped entirely
    // when a cached scene was reused above, since its placements are already
    // in placedRef.current and nothing needs downloading again.
    // Group records by line_group_id so each unique GLB file is downloaded
    // only ONCE, then shallow-cloned per station — one download even for a
    // 20-station line placement.
    // Restore placed models: fetch placements for this layout, then download
    // each unique model from the global library (one download per model name,
    // even if it's placed at 20 stations).
    if (canReuseScene) {
      onSceneReady && onSceneReady();
    } else {
    console.info(`[Z3D] bundle: ${Z3D_BUILD_TAG} — loading placements for layout ${layout.id}`);
    Promise.all([
      z3dModelApi.listPlacements(layout.id),
      // This layout's own explicit line->car model->object assignments (set
      // via the Layout Preparation 🎯 popup). A line with an explicit
      // mapping here must NEVER fall through to the fuzzy cross-line
      // auto-seed matcher below — lineNamesMatch() deliberately treats
      // "Trim"/"Trim 1"/"Trim Line" as the SAME logical line (it strips
      // trailing numbers), which is right for the old "one shared model,
      // copied across layouts" use case but wrong the moment two DIFFERENT
      // physical lines in the SAME layout ("Trim" and "Trim 1") are each
      // explicitly assigned a DIFFERENT model — the fuzzy matcher would
      // otherwise seed a missing station on one from whichever line's
      // placement happens to be "most recently updated", silently swapping
      // one line's object for the other's on the very next reload.
      lineModelMappingApi.listByLayout(layout.id).catch(() => ({ data: [] })),
    ]).then(([placementsRes, mappingsRes]) => {
      const placements = placementsRes.data || [];
      const explicitMappings = mappingsRes.data || [];
      // Prefer a mapping with no car model (single-model line) since it's
      // unambiguous; otherwise fall back to whichever car-model mapping was
      // saved most recently. No "active car model" selector exists yet to
      // pick deliberately — this only matters for FILLING IN a station that
      // has no placement at all, not for lines that are already fully seeded.
      const mappingByLine = new Map();
      explicitMappings.forEach(m => {
        const existing = mappingByLine.get(m.line_group_id);
        if (!existing) { mappingByLine.set(m.line_group_id, m); return; }
        const existingIsGeneric = existing.car_model_id == null;
        const thisIsGeneric = m.car_model_id == null;
        if (existingIsGeneric) return; // generic mapping already wins
        if (thisIsGeneric || new Date(m.updated_at) > new Date(existing.updated_at)) {
          mappingByLine.set(m.line_group_id, m);
        }
      });

      // Auto-seed any station that has NO placement yet — per STATION, not
      // per line. Only count placements with a real, loadable model_name
      // here — an orphaned row (invalid model_name, e.g. left over from a
      // bug in an earlier session) would otherwise mark the station as
      // "already placed" forever, permanently blocking auto-seeding even
      // though nothing actually renders for it (loadAndPlace below deletes
      // those rows, but only AFTER this seeding decision has already been
      // made this run).
      const validPlacements = placements.filter(p => isValidModelName(p.model_name));
      const placedStationIds = new Set(validPlacements.map(p => p.station_id).filter(Boolean));

      // Build a local station-id → 3D-position map for THIS layout
      // (stationPosRef is already populated by the box-building loop above)
      const localPosMap = stationPosRef.current;

      // Per-line list of stations that still need a model. This used to be
      // an all-or-nothing check per LINE — if even one station in a line
      // already had ANY placement row (including a stale/broken leftover
      // from earlier testing), the entire line was skipped, leaving its
      // genuinely-empty siblings blank forever ("sometimes one station gets
      // it, sometimes all, one stays empty" — that flakiness was exactly
      // this: which stations happened to carry leftover rows varied between
      // test runs). Now every station is judged independently.
      // Accumulate (push), don't overwrite — two boxes can legitimately share
      // the exact same name (e.g. two boxes both named "Trim Line"). Keying
      // by name with a plain assignment would let the second box's station
      // IDs silently replace the first's, so only one of the two ever got
      // auto-seeded. Merging into one array covers every box with that name.
      const missingStationsByLine = {}; // lineGroupId -> [stationId, ...]
      (layout.station_boxes || []).forEach(box => {
        if (!box.name) return;
        const ids = (box.station_ids || '').split(',').map(s => s.trim()).filter(Boolean);
        const missing = ids.filter(sid => !placedStationIds.has(sid));
        if (missing.length === 0) return;
        if (!missingStationsByLine[box.name]) missingStationsByLine[box.name] = [];
        missingStationsByLine[box.name].push(...missing);
      });
      const unseededLines = Object.keys(missingStationsByLine);

      // Helper: given a template record + line name, place at every station
      // of that line still missing one. Returns the new records instead of
      // mutating a shared array, so each seeded line's models can start
      // downloading the moment its own seed data resolves — not gated
      // behind every other line finishing.
      const seedFromTemplate = (tmpl, lineGroupId) => {
        const modelName = tmpl.model_name;
        // Don't propagate a broken template — copying an already-invalid
        // model_name (e.g. the literal string "undefined") just creates more
        // of the same garbage on the new line instead of fixing anything.
        if (!isValidModelName(modelName)) return Promise.resolve([]);
        const lineStationIds = missingStationsByLine[lineGroupId] || [];
        if (lineStationIds.length === 0) return Promise.resolve([]);
        // Prefer the model's saved LIBRARY default scale/rotation (the one
        // set via "Save Preset -> All layouts") over this specific
        // placement row's own numbers. `tmpl` is just whichever single
        // placement happened to have the most recent updated_at across every
        // layout — a one-off drag/rotate on a lone station (never meant to
        // be broadcast) would otherwise become "the latest" and get copied
        // onto every brand-new empty line, tilt and all. The library default
        // is the deliberate, confirmed value; fall back to tmpl's own
        // numbers only if the model has no library entry yet.
        return z3dModelApi.getLibraryModel(modelName).then(res => res.data).catch(() => null).then(lib => {
          const sx = lib?.default_sx ?? tmpl.sx ?? 1, sy = lib?.default_sy ?? tmpl.sy ?? 1, sz = lib?.default_sz ?? tmpl.sz ?? 1;
          const rx = lib?.default_rx ?? tmpl.rx ?? 0, ry = lib?.default_ry ?? tmpl.ry ?? 0, rz = lib?.default_rz ?? tmpl.rz ?? 0;
          // Position: library default_px/pz are station-relative offsets (the
          // model's saved "movement" preset); py is an absolute height.
          const px = lib?.default_px ?? 0, pz = lib?.default_pz ?? 0;
          const py = lib?.default_py ?? tmpl.py ?? 0;
          return Promise.all(lineStationIds.map(stationId => {
            return z3dModelApi.createPlacement({
              layoutId: layout.id, modelName, lineGroupId, stationId,
              px, py, pz, rx, ry, rz, sx, sy, sz, posIsOffset: true,
            }).then(cr => ({
              id: cr.data.id, layout_id: layout.id,
              model_name: modelName, line_group_id: lineGroupId, station_id: stationId,
              px, py, pz, rx, ry, rz, sx, sy, sz, pos_is_offset: true,
            }));
          }));
        });
      };

      // Places one loaded template at every record that shares its model_name.
      // Defined once outside the per-model-name loop since it doesn't close
      // over anything model-specific.
      const applyRecord = (template, record) => {
        // Always clone — `template` is the same object held in the
        // module-level _modelTemplateCache. Placing it directly would parent
        // it into THIS scene; Object3D.add() silently detaches an object
        // from its previous parent, so the next layout/session that reuses
        // this cached template for its own placement would rip the mesh out
        // of whichever scene currently shows it, leaving that station's box
        // empty even though its entry survives.
        const obj = sharedClone(template);
        obj.traverse(child => {
          if (child.isSprite || (child.material && child.material.map === null && child.isLine)) child.visible = false;
        });

        const sx = record.sx ?? 1;
        const rx = record.rx ?? 0, ry = record.ry ?? 0, rz = record.rz ?? 0;
        // autoScale/floor-offset/centering only depend on model+scale+rotation,
        // not on which station it ends up at — cache per unique combo so a
        // 20-station line measures geometry once instead of 20 times.
        const geoKey = `${record.model_name}::${sx}::${rx}::${ry}::${rz}`;
        let geo = _placementGeoCache.get(geoKey);

        if (!geo) {
          // Auto-scale the raw template to ~2m so baseScale is correct
          obj.position.set(0, 0, 0);
          obj.rotation.set(0, 0, 0);
          obj.scale.set(1, 1, 1);
          const _bbox = new THREE.Box3().setFromObject(obj);
          const _size = new THREE.Vector3(); _bbox.getSize(_size);
          const _maxDim = Math.max(_size.x, _size.y, _size.z);
          const autoScale = _maxDim > 0 ? 2.0 / _maxDim : 1;

          // Floor-snap: compute AFTER rotation so bbox accounts for rotated shape
          obj.scale.setScalar(sx);
          obj.rotation.set(rx, ry, rz);
          const _bbox2 = new THREE.Box3().setFromObject(obj);
          const floorY = -_bbox2.min.y;

          // Centering offsets — compensates for mesh origin offset from its bbox center
          obj.position.set(0, floorY, 0);
          const _bboxXZ = new THREE.Box3().setFromObject(obj);

          geo = {
            autoScale,
            floorOffsetAtBase: floorY / sx,
            xOff: (_bboxXZ.min.x + _bboxXZ.max.x) / 2,
            zOff: (_bboxXZ.min.z + _bboxXZ.max.z) / 2,
            footprintW: _bboxXZ.max.x - _bboxXZ.min.x,
            footprintD: _bboxXZ.max.z - _bboxXZ.min.z,
          };
          _placementGeoCache.set(geoKey, geo);
        } else {
          obj.scale.setScalar(sx);
          obj.rotation.set(rx, ry, rz);
        }
        obj.userData.baseScale = geo.autoScale;
        obj.userData.floorOffsetAtBase = geo.floorOffsetAtBase;
        obj.userData.geoXOff = geo.xOff;

        // Use the saved height if one was ever explicitly set — ABOVE or
        // BELOW the auto floor-snap — and only fall back to the computed
        // floor-snap for a never-touched row (py still at its 0 default).
        // Previously this only ever let a saved height win if it was HIGHER
        // than the auto-snap, treating the auto-snap as a hard floor no
        // saved value could go below — so dragging an object down and
        // saving it (e.g. to fix a model whose bounding box makes it look
        // like it's floating) always got silently overridden back up on
        // the next load, no matter how many times it was re-saved.
        const floorY = geo.floorOffsetAtBase * sx;
        const savedPy = record.py ?? 0;
        const finalY = savedPy !== 0 ? savedPy : floorY;

        // Station-bound placements anchor to their station's center (so they
        // follow the station if the 2D box is moved). Rows saved with
        // pos_is_offset carry the user's drag as an offset from that anchor —
        // legacy rows (flag false) stored absolute world coords the renderer
        // never used, so they keep the old snap-to-center behaviour. Free
        // placements use absolute px/pz as always.
        const stnPos = record.station_id ? localPosMap[record.station_id] : null;
        const baseX = stnPos ? stnPos.x - geo.xOff : null;
        const baseZ = stnPos ? stnPos.z : null;
        let finalX, finalZ;
        if (stnPos) {
          const offX = record.pos_is_offset ? (record.px ?? 0) : 0;
          const offZ = record.pos_is_offset ? (record.pz ?? 0) : 0;
          finalX = baseX + offX;
          finalZ = baseZ + offZ;
        } else {
          finalX = (record.px ?? sceneCenterRef.current.x) - geo.xOff;
          finalZ = record.pz ?? sceneCenterRef.current.z;
        }
        obj.position.set(finalX, finalY, finalZ);

        obj.userData.isPlaced          = true;
        obj.userData.objId             = String(record.id);
        obj.userData.serverModelId     = record.id;
        obj.userData.objName           = record.model_name;
        obj.userData.objExt            = record.model_name.split('.').pop() || 'glb';
        scene.add(obj);
        dirtyRef.current = true;
        const entry = {
          id: String(record.id), mesh: obj, label: null, name: record.model_name,
          stationId: record.station_id || null,
          lineGroupId: record.line_group_id || null,
          // Station anchor (already xOff-compensated) — persist code uses it
          // to convert the mesh's world position back into a saveable offset.
          baseX, baseZ,
          posIsOffset: !!record.pos_is_offset,
        };
        placedRef.current = [...placedRef.current, entry];
        syncHangerBars(scene, placedRef.current, localPosMap);
        onObjectsChange([...placedRef.current]);
      };

      // Overall progress tracking across every batch (the initial placements
      // batch plus one batch per seeded line) — "ready" only fires once every
      // batch has resolved AND every model within them has finished loading.
      let totalModels = 0, loadedModels = 0, batchesResolved = 0;
      const totalBatches = 1 + unseededLines.length;
      const checkDone = () => {
        if (batchesResolved >= totalBatches && loadedModels >= totalModels) {
          // Diagnostic: a placement can exist and be counted (shows up in the
          // Objects panel) but render nowhere visible if its 3D position is
          // wrong — e.g. two stations landing on the exact same coordinate
          // (one hides behind/inside the other) or a station whose position
          // fell back to a default like (0,0) because it wasn't found in
          // this layout's station map at seed time. Logging every placed
          // object's station + rounded position makes either case obvious
          // at a glance instead of having to guess which one is "missing".
          const posByStation = new Map();
          const dupes = [];
          placedRef.current.forEach(p => {
            const x = Math.round(p.mesh.position.x * 10) / 10;
            const z = Math.round(p.mesh.position.z * 10) / 10;
            const key = `${x},${z}`;
            if (posByStation.has(key)) dupes.push([posByStation.get(key), p.stationId, key]);
            posByStation.set(key, p.stationId);
          });
          console.info(
            `[Z3D] Scene ready (${Z3D_BUILD_TAG}): ${placedRef.current.length} object(s) placed.`,
            placedRef.current.map(p => ({
              station: p.stationId, name: p.name,
              x: Math.round(p.mesh.position.x * 10) / 10,
              y: Math.round(p.mesh.position.y * 100) / 100,
              z: Math.round(p.mesh.position.z * 10) / 10,
              ryDeg: Math.round((p.mesh.rotation.y * 180) / Math.PI),
              offsetMode: !!p.posIsOffset,
            }))
          );
          if (dupes.length > 0) {
            console.warn(`[Z3D] Scene ready: ${dupes.length} pair(s) of objects share the exact same position (one is likely hidden behind/inside the other):`, dupes);
          }
          // Cache this freshly-built scene so switching away and back to this
          // exact layout (same structure/Z-E signature) can skip straight to
          // reuse next time, instead of redoing this whole pipeline. Capped
          // at 2 entries (LRU) to bound GPU memory — evicted entries are just
          // dropped, not explicitly disposed, since their placed-model
          // geometry is shared with the module-level template cache and must
          // not be destroyed out from under it.
          const cache = layoutSceneCacheRef.current;
          cache.delete(layout.id); // re-insert at the end → most-recently-used
          cache.set(layout.id, {
            scene, signature: sceneSignature,
            stationPosMap: { ...stationPosRef.current },
            placedEntries: [...placedRef.current],
            center: sceneCenterRef.current.clone(),
            span: sceneSpanRef.current,
          });
          while (cache.size > 2) cache.delete(cache.keys().next().value);

          onSceneReady && onSceneReady();
        }
      };

      // Byte-level download progress per in-flight model (0..1), so the
      // loading bar moves continuously instead of sitting frozen at "0 of 2"
      // for however long the biggest file takes to transfer.
      const downloadFractions = new Map(); // modelName → 0..1
      const reportProgress = () => {
        let inFlight = 0;
        downloadFractions.forEach(f => { inFlight += f; });
        onModelProgress && onModelProgress(loadedModels + inFlight, totalModels, loadedModels);
      };

      // Downloads+places one batch of records, grouped by model_name so each
      // unique GLB is only fetched once regardless of station count. Called
      // once immediately for the placements we already know about, and again
      // for each line as soon as ITS seed data resolves — no batch waits on
      // any other batch to start downloading.
      const loadAndPlace = (records) => {
        // Keyed by LOWERCASED model_name — the library's name-uniqueness
        // check turned out to be case-sensitive, so "Trim Line" and
        // "trim line" ended up as two separate rows/files in the database
        // instead of one. Grouping by exact-case model_name here treated
        // those as two different models: both got downloaded and placed,
        // landing two objects on the exact same station (one hiding the
        // other). Grouping case-insensitively merges them back into one.
        const byName = new Map(); // lowercase name -> { modelName (first-seen casing), recs }
        records.forEach(p => {
          // A placement with no model_name has nothing to download — skip it
          // instead of crashing later trying to fetch/cache an undefined name.
          // Also delete it server-side: a dead placement like this makes the
          // station look "already seeded", which permanently blocks the
          // auto-copy-from-another-layout feature from ever running for this
          // line. Removing it lets that line self-heal on the next page load.
          if (!isValidModelName(p.model_name)) {
            console.error('[Z3D] Removing placement with invalid model_name:', p);
            if (p.id) z3dModelApi.deletePlacement(p.id).catch(() => {});
            return;
          }
          const key = p.model_name.toLowerCase();
          if (!byName.has(key)) byName.set(key, { modelName: p.model_name, recs: [] });
          byName.get(key).recs.push(p);
        });
        totalModels += byName.size;
        reportProgress();

        byName.forEach(({ modelName, recs }) => {
          const downloadUrl = z3dModelApi.getDownloadUrl(modelName);
          // Extension comes straight from the filename — avoids an extra
          // getLibraryModel round-trip per unique model before download starts.
          const ext = (recs[0].model_name || 'glb').split('.').pop().toLowerCase();

          const onDownloadProgress = (evt) => {
            if (evt.total > 0) {
              downloadFractions.set(modelName, evt.loaded / evt.total);
              reportProgress();
            }
          };

          const onTemplate = (template) => {
            setCachedTemplate(modelName, template);
            downloadFractions.delete(modelName);
            // Deduplicate: skip any record whose station_id is already placed in the scene
            const renderedStations = new Set(placedRef.current.map(p => p.stationId).filter(Boolean));
            const dedupedRecords = recs.filter(r => {
              if (!r.station_id) return true; // free-placed, no station, always show
              if (renderedStations.has(r.station_id)) return false; // already in scene
              renderedStations.add(r.station_id); // mark as handled
              return true;
            });
            dedupedRecords.forEach((record) => applyRecord(template, record));
            loadedModels += 1;
            reportProgress();
            checkDone();
          };

          // If already loaded this session → skip download entirely
          const cached = getCachedTemplate(modelName);
          if (cached) { onTemplate(cached); return; }

          // A failed/hanging model must not freeze the loading overlay forever —
          // count it toward loadedModels so the rest of the scene still becomes
          // ready even if this one file is broken, missing, or blocked.
          const onError = (err) => {
            console.error('[Z3D] Model load failed:', modelName, err);
            downloadFractions.delete(modelName);
            // Same reasoning as the invalid-model_name cleanup above: a
            // placement whose file 404s (deleted from disk, library entry
            // removed, etc.) renders nothing, but the row still exists — so
            // the auto-seed check keeps treating that station/line as
            // "already has a model" forever, even though it visually looks
            // completely empty. Deleting it lets the line self-heal and
            // become eligible for auto-fill again on the next load.
            recs.forEach(r => { if (r.id) z3dModelApi.deletePlacement(r.id).catch(() => {}); });
            loadedModels += 1;
            reportProgress();
            checkDone();
          };

          try {
            if (ext === 'obj') {
              new OBJLoader().load(downloadUrl, onTemplate, onDownloadProgress, onError);
            } else if (ext === 'stl') {
              new STLLoader().load(downloadUrl, geo => {
                geo.computeVertexNormals();
                onTemplate(new THREE.Mesh(geo, new THREE.MeshLambertMaterial({ color: 0x90a4ae })));
              }, onDownloadProgress, onError);
            } else {
              // glb/gltf, or unrecognized extension — GLTFLoader is the common case
              makeGLTFLoader().load(downloadUrl, g => onTemplate(g.scene), onDownloadProgress, onError);
            }
          } catch (err) {
            onError(err);
          }
        });
      };

      // Batch 1: whatever is already placed in this layout — starts downloading
      // immediately, doesn't wait on the seeding lookups below.
      batchesResolved += 1;
      loadAndPlace(placements);
      checkDone();

      // Remaining batches: one per unseeded line. All unseeded lines share a
      // single listAllLineGroups/listLibrary fetch (only made at all if there's
      // something to seed), but each line's own seed lookup + download proceeds
      // independently as soon as it resolves.
      if (unseededLines.length > 0) {
        const lineGroupsAndLibrary = Promise.all([
          z3dModelApi.listAllLineGroups().catch(() => ({ data: [] })),
          z3dModelApi.listLibrary().catch(() => ({ data: [] })),
        ]);

        unseededLines.forEach(lineGroupId => {
          // This exact line has an explicit assignment in THIS layout —
          // trust it completely and skip fuzzy cross-line matching, so a
          // missing station on "Trim" can never get seeded from "Trim 1"'s
          // (or any other layout's) model just because the names are similar.
          const explicitMapping = mappingByLine.get(lineGroupId);
          if (explicitMapping) {
            z3dModelApi.getLibraryModel(explicitMapping.model_name).then(res => res.data).then(lib => {
              console.info(`[Z3D] Auto-seed: line "${lineGroupId}" seeded from its own explicit mapping (model "${explicitMapping.model_name}"), no fuzzy matching used.`);
              return seedFromTemplate({
                model_name: explicitMapping.model_name,
                sx: lib?.default_sx, sy: lib?.default_sy, sz: lib?.default_sz,
                rx: lib?.default_rx, ry: lib?.default_ry, rz: lib?.default_rz,
                py: lib?.default_py,
              }, lineGroupId);
            }).catch(err => {
              console.error(`[Z3D] Auto-seed: explicit mapping for "${lineGroupId}" references missing model "${explicitMapping.model_name}" —`, err?.message);
              return [];
            }).then(newRecords => {
              batchesResolved += 1;
              if (newRecords.length > 0) loadAndPlace(newRecords);
              checkDone();
            });
            return;
          }

          lineGroupsAndLibrary.then(([lgRes, libRes]) => {
            const knownLineGroups = lgRes.data || [];
            const libraryModels = libRes.data || [];  // [{name, ext, ...}]

            // Gather EVERY plausible source instead of taking the first fuzzy
            // match: every line_group_id in the DB that loosely resembles
            // this line's name, plus every library model whose file name
            // does. lineNamesMatch is a loose matcher (substrings,
            // abbreviations) with no notion of "best" match, and
            // knownLineGroups/libraryModels are NOT ordered by recency — so
            // picking just the first match (old behavior) could silently
            // grab a stale naming variant instead of the one that's actually
            // current. Instead: fetch placements from every matching source,
            // then pick the single most-recently-updated record across all
            // of them — recency, not array order, decides the winner.
            const matchingLineGroups = knownLineGroups.filter(kg => lineNamesMatch(kg, lineGroupId));
            const matchingModels = libraryModels.filter(m => lineNamesMatch(m.name, lineGroupId));

            const lookups = [
              ...matchingLineGroups.map(kg => z3dModelApi.getPlacementsByLineGroup(kg).then(r => r.data || []).catch(() => [])),
              ...matchingModels.map(m => z3dModelApi.getPlacementsByModelName(m.name).then(r => r.data || []).catch(() => [])),
            ];
            if (lookups.length === 0) {
              // Nothing to seed this line from — surface WHY in the console
              // instead of silently leaving it blank, so a "why didn't this
              // line get a model" report can be diagnosed from a screenshot
              // of devtools instead of guessing blind.
              console.warn(
                `[Z3D] Auto-seed: no source found for line "${lineGroupId}". ` +
                `Checked ${knownLineGroups.length} known line group(s) and ${libraryModels.length} library model(s), 0 matched.`
              );
              return Promise.resolve([]);
            }

            return Promise.all(lookups).then(resultsArr => {
              const allRecsRaw = resultsArr.flat();
              // Drop candidates with a broken model_name (e.g. the literal
              // string "undefined") BEFORE picking "latest" — otherwise one
              // stray garbage row with a recent timestamp can permanently
              // win the "most recently updated" contest over real, valid
              // records, leaving the line seeded with nothing (or blocked
              // entirely) even though good data exists among the candidates.
              const brokenRecs = allRecsRaw.filter(r => !isValidModelName(r.model_name));
              if (brokenRecs.length > 0) {
                console.warn(
                  `[Z3D] Auto-seed: ignoring ${brokenRecs.length} broken candidate record(s) for "${lineGroupId}" ` +
                  `(model_name: ${[...new Set(brokenRecs.map(r => r.model_name))].join(', ')}) — deleting them.`
                );
                brokenRecs.forEach(r => { if (r.id) z3dModelApi.deletePlacement(r.id).catch(() => {}); });
              }
              const allRecs = allRecsRaw.filter(r => isValidModelName(r.model_name));
              if (allRecs.length === 0) {
                console.warn(
                  `[Z3D] Auto-seed: matched ${matchingLineGroups.length} line group(s)/${matchingModels.length} ` +
                  `library model(s) for "${lineGroupId}", but they returned 0 usable placement records.`
                );
                return [];
              }
              const latest = allRecs.reduce((best, r) =>
                (!best || new Date(r.updated_at) > new Date(best.updated_at)) ? r : best
              , null);
              console.info(`[Z3D] Auto-seed: line "${lineGroupId}" seeded from model "${latest.model_name}" (${allRecs.length} usable candidate record(s), ${brokenRecs.length} broken skipped).`);
              return seedFromTemplate(latest, lineGroupId);
            });
          }).then(newRecords => {
            batchesResolved += 1;
            if (newRecords.length > 0) loadAndPlace(newRecords);
            checkDone();
          });
        });
      }
    }).catch(err => {
      console.error('[Z3D] Failed to load saved models:', err);
      onSceneReady && onSceneReady(); // unblock overlay on error
    });
    }

    // Only re-render when something changes — saves GPU when user is idle
    dirtyRef.current = true;
    orbit.addEventListener('change', () => { dirtyRef.current = true; });
    tc.addEventListener('change',    () => { dirtyRef.current = true; });

    const animate = () => {
      rafRef.current = requestAnimationFrame(animate);
      try {
        if (walkModeRef.current) { walk.update(); dirtyRef.current = true; orbit.enabled = false; }
        else { if (!tc.dragging) orbit.enabled = true; orbit.update(); }

        // Process active tweens
        const now = performance.now();
        const done = [];
        if (animationsRef.current.length > 0) {
          dirtyRef.current = true;
          animationsRef.current = animationsRef.current.filter(anim => {
            const raw  = Math.min((now - anim.startTime) / anim.durationMs, 1);
            const ease = raw < 0.5 ? 2 * raw * raw : -1 + (4 - 2 * raw) * raw;
            anim.mesh.position.x = anim.fromX + (anim.toX - anim.fromX) * ease;
            anim.mesh.position.z = anim.fromZ + (anim.toZ - anim.fromZ) * ease;
            if (raw >= 1) { done.push(anim); return false; }
            return true;
          });
        }
        done.forEach(anim => anim.onComplete && anim.onComplete());

        if (dirtyRef.current) {
          renderer.render(scene, camera);
          dirtyRef.current = false;
        }
      } catch (err) {
        console.error('[Z3D animate error]', err);
      }
    };
    animate();

    return () => {
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
      walk.destroy();
      // A cached scene can outlive this effect run (reused on a later layout
      // switch) — tc.dispose() alone doesn't remove it from the scene graph,
      // so without this it would silently accumulate one orphaned
      // TransformControls per revisit instead of being thrown away with a
      // fresh scene like before.
      scene.remove(tc);
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

    // Fake progress ticker — blob URLs have no Content-Length so xhr.total is always 0.
    // This keeps the progress bar moving so the user knows something is happening.
    let _pct = 10;
    onConvertStart && onConvertStart(_pct);
    const _ticker = setInterval(() => {
      _pct = Math.min(_pct + (_pct < 60 ? 4 : _pct < 85 ? 1.5 : 0.4), 92);
      onConvertStart && onConvertStart(Math.round(_pct));
    }, 300);

    const onLoaded = (obj) => {
      clearInterval(_ticker);
      onConvertEnd && onConvertEnd();
      URL.revokeObjectURL(url);

      // Cache this template so other layouts can clone it without re-downloading
      setCachedTemplate(name, obj);
      // Any OTHER layout's cached scene (layoutSceneCacheRef, below) may have
      // already baked in the OLD version of this model — that fast-path
      // reuse skips the whole download pipeline, so it would otherwise never
      // notice this upload. Clear it so switching to another layout rebuilds
      // and picks up the new file instead of showing stale meshes.
      layoutSceneCacheRef.current.clear();
      // A re-upload keeps the same scale/rotation, so the geo cache key is
      // unchanged even though the geometry (and its bbox) is new — evict it
      // too, or other layouts apply the OLD file's offsets to the NEW mesh.
      invalidateGeoCache(name);

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
      // Store ratio so setObjectScale can re-snap without recomputing bbox
      obj.userData.floorOffsetAtBase = obj.position.y / autoScale;

      // Apply saved model preset (scale + rotation) if one exists
      const _preset = getModelPreset(name);
      if (_preset) {
        const presetScale = (obj.userData.baseScale || 1) * (_preset.scale || 1);
        obj.scale.setScalar(presetScale);
        obj.position.y = (obj.userData.floorOffsetAtBase || 0) * presetScale;
        obj.rotation.set(
          ((_preset.rotX || 0) * Math.PI) / 180,
          ((_preset.rotY || 0) * Math.PI) / 180,
          ((_preset.rotZ || 0) * Math.PI) / 180
        );
      }

      // Place at station centre or scene centre, compensating for mesh origin offset
      const stnPos = options.stationId ? stationPosRef.current[options.stationId] : null;
      const c = sceneCenterRef.current;
      const targetX = stnPos ? stnPos.x : c.x;
      const targetZ = stnPos ? stnPos.z : c.z;
      // Compute X/Z bbox center at rotation=0 so origin-offset is cancelled out
      obj.rotation.set(0, 0, 0);
      const _bboxC = new THREE.Box3().setFromObject(obj);
      const xOff = (_bboxC.min.x + _bboxC.max.x) / 2;
      obj.position.x = targetX - xOff;
      obj.position.z = targetZ; // Z: station center directly, no offset
      // Restore preset rotation after centering
      if (_preset) obj.rotation.set(
        ((_preset.rotX || 0) * Math.PI) / 180,
        ((_preset.rotY || 0) * Math.PI) / 180,
        ((_preset.rotZ || 0) * Math.PI) / 180
      );

      const objId = Date.now().toString();
      obj.userData.isPlaced       = true;
      obj.userData.objId          = objId;
      obj.userData.objName        = name;
      obj.userData.objExt         = ext;
      obj.userData.assignedStation = options.stationId || null;
      obj.userData.geoXOff        = xOff;

      scene.add(obj); dirtyRef.current = true;

      const entry = {
        id: objId, mesh: obj, label: null, name,
        stationId: options.stationId || null, lineGroupId: options.lineGroupId || null,
        // Station anchor for offset-based persistence — the object currently
        // sits exactly on it (offset 0) since it was just snapped there.
        baseX: stnPos ? obj.position.x : null,
        baseZ: stnPos ? obj.position.z : null,
      };
      placedRef.current = [...placedRef.current, entry];
      syncHangerBars(scene, placedRef.current, stationPosRef.current);
      // A newly-placed model makes any cached scene snapshot for this layout
      // stale (its placedEntries wouldn't include this new one) — drop it.
      layoutSceneCacheRef.current.delete(layoutIdRef.current);

      // Save to server: upload file to global library (reuses if name exists),
      // then create a per-layout placement record with the transform.
      if (layoutId) {
        z3dModelApi.uploadToLibrary(file, { name }).then(() =>
          z3dModelApi.createPlacement({
            layoutId, modelName: name,
            lineGroupId: options.lineGroupId || null, stationId: options.stationId || null,
            ...(() => {
              const p = buildTransformPayload(entry);
              return { px: p.px, py: p.py, pz: p.pz, posIsOffset: p.pos_is_offset };
            })(),
            rx: obj.rotation.x, ry: obj.rotation.y, rz: obj.rotation.z,
            sx: obj.scale.x,    sy: obj.scale.y,    sz: obj.scale.z,
          })
        ).then(res => {
          obj.userData.serverModelId = res.data.id;
          const entry = placedRef.current.find(p => p.id === objId);
          if (entry) entry.serverModelId = res.data.id;
        }).catch(err => {
          console.error('[Z3D] Failed to save model to server:', err);
          const status = err?.response?.status;
          const reason = status === 413
            ? 'File is too large for the server to accept.'
            : (err?.message || 'Unknown error');
          alert(
            `"${name}" is visible now, but failed to save to the server (${reason}).\n` +
            `It will disappear on refresh and won't be available in other layouts.`
          );
        });
      }

      // Select immediately and set mode to translate
      if (transformRef.current && canEditRef.current) {
        transformRef.current.setMode('translate');
        transformRef.current.attach(obj);
        selectedRef.current = entry;
      }

      onObjectsChange([...placedRef.current]);
    };

    if (ext === 'glb' || ext === 'gltf') {
      makeGLTFLoader().load(
        url,
        (gltf) => onLoaded(gltf.scene),
        (xhr) => { if (xhr.total) onConvertStart && onConvertStart(Math.round(xhr.loaded / xhr.total * 90)); },
        (err) => {
          clearInterval(_ticker);
          onConvertEnd && onConvertEnd();
          console.error('[Z3D] GLB upload failed:', err);
          alert('Failed to load GLB: ' + (err?.message || err));
        }
      );
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
        if (transformRef.current && canEditRef.current) transformRef.current.attach(obj);
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
    if (transformRef.current && canEditRef.current) {
      transformRef.current.attach(entry.mesh);
    }
    onObjectsChange([...placedRef.current]);
  }, [onObjectsChange]);

  // Delete object by id — if the object belongs to a line group, deletes all group members
  const deleteById = useCallback((id) => {
    const scene = sceneRef.current;
    const entry = placedRef.current.find(p => p.id === id);
    if (!entry || !scene) return;
    const targets = entry.lineGroupId
      ? placedRef.current.filter(p => p.lineGroupId === entry.lineGroupId)
      : [entry];
    targets.forEach(t => {
      if (transformRef.current && selectedRef.current?.id === t.id) transformRef.current.detach();
      scene.remove(t.mesh);
      if (t.label) scene.remove(t.label);
      if (selectedRef.current?.id === t.id) selectedRef.current = null;
    });
    const deleteIds = new Set(targets.map(t => t.id));
    placedRef.current = placedRef.current.filter(p => !deleteIds.has(p.id));
    syncHangerBars(scene, placedRef.current, stationPosRef.current);
    // Delete from server using server-assigned IDs
    targets.forEach(t => {
      const sid = t.mesh.userData.serverModelId;
      if (sid) z3dModelApi.deletePlacement(sid).catch(() => {});
    });
    onObjectsChange([...placedRef.current]);
    // The cached scene's placedEntries snapshot is now stale — drop it so the
    // next visit to this layout rebuilds fresh instead of showing a deleted
    // model back in the side list.
    layoutSceneCacheRef.current.delete(layoutIdRef.current);
    dirtyRef.current = true;
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
    dirtyRef.current = true;
  }, [onObjectsChange]);

  // Set uniform scale multiplier — if object is in a line group, applies to all group members.
  // Auto-saves as default for the model name so other layouts inherit the same scale.
  // applyGlobally: false (default) — only this layout's placement(s) are
  // updated, exactly like every other drag/edit. true is opt-in, only ever
  // passed from the explicit "Save Preset" confirm popup — that's what
  // pushes the value into the shared model default other layouts inherit.
  const setObjectScale = useCallback((id, multiplier, applyGlobally = false) => {
    const entry = placedRef.current.find(p => p.id === id);
    if (!entry) return;
    const targets = entry.lineGroupId
      ? placedRef.current.filter(p => p.lineGroupId === entry.lineGroupId)
      : [entry];
    targets.forEach(t => {
      const base = t.mesh.userData.baseScale || 1;
      const newScale = base * multiplier;
      t.mesh.scale.setScalar(newScale);
      // Re-snap floor: keep ratio constant so model stays planted on floor
      if (t.mesh.userData.floorOffsetAtBase !== undefined) {
        t.mesh.position.y = t.mesh.userData.floorOffsetAtBase * newScale;
      }
      const sid = t.mesh.userData.serverModelId;
      if (sid) {
        z3dModelApi.updateTransform(sid, buildTransformPayload(t)).catch(reportTransformSaveError);
      }
    });
    // Only pushed to the shared model default (which every OTHER layout's
    // future placements/new-layout auto-seed inherit) when the user
    // explicitly confirmed "All Layouts" in the save-scope popup.
    if (applyGlobally) {
      const modelName = entry.mesh.userData.objName || entry.name;
      if (modelName) {
        // Preserve current position/rotation — this only changes scale, so
        // hardcoding rotation to 0 or omitting position would silently wipe
        // out whatever was previously saved for this model. Position is the
        // station-relative offset (what default_px/pz mean), not world coords.
        const rotXDeg = (entry.mesh.rotation.x * 180) / Math.PI;
        const rotYDeg = (entry.mesh.rotation.y * 180) / Math.PI;
        const rotZDeg = (entry.mesh.rotation.z * 180) / Math.PI;
        const p = buildTransformPayload(entry);
        saveModelPreset(modelName, { scale: multiplier, rotX: rotXDeg, rotY: rotYDeg, rotZ: rotZDeg });
        z3dModelApi.saveDefaults(modelName, {
          px: p.pos_is_offset ? p.px : 0, py: p.py, pz: p.pos_is_offset ? p.pz : 0,
          sx: multiplier, sy: multiplier, sz: multiplier,
          rx: entry.mesh.rotation.x, ry: entry.mesh.rotation.y, rz: entry.mesh.rotation.z,
        }).catch(() => {});
      }
    }
    // The render loop only redraws when this flag is set — without it, the
    // mesh's scale changes internally but stays on screen until some
    // unrelated interaction (e.g. clicking the canvas) happens to mark the
    // scene dirty for another reason.
    dirtyRef.current = true;
  }, []);

  // Set rotation (degrees) on a placed object — if in a line group, applies to all group members.
  // applyGlobally: see setObjectScale above — same opt-in-only rule.
  const setGroupRotation = useCallback((id, rx, ry, rz, applyGlobally = false) => {
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
      const sid = t.mesh.userData.serverModelId;
      if (sid) {
        z3dModelApi.updateTransform(sid, buildTransformPayload(t)).catch(reportTransformSaveError);
      }
    });
    if (applyGlobally) {
      const modelName = entry.mesh.userData.objName || entry.name;
      if (modelName) {
        const currentScale = entry.mesh.userData.baseScale
          ? entry.mesh.scale.x / entry.mesh.userData.baseScale
          : 1;
        saveModelPreset(modelName, { scale: currentScale, rotX: rx, rotY: ry, rotZ: rz });
        // rx/ry/rz here are the slider's DEGREES (0-360) — the server/renderer
        // expects radians (same convention as t.mesh.rotation, set above via
        // `* Math.PI / 180`). Sending raw degrees as radians is what made
        // "Save Preset -> All Layouts" show other layouts' copies wildly
        // tilted, as if freshly uploaded with garbage rotation.
        const p = buildTransformPayload(entry);
        z3dModelApi.saveDefaults(modelName, {
          px: p.pos_is_offset ? p.px : 0, py: p.py, pz: p.pos_is_offset ? p.pz : 0,
          sx: currentScale, sy: currentScale, sz: currentScale,
          rx: (rx * Math.PI) / 180, ry: (ry * Math.PI) / 180, rz: (rz * Math.PI) / 180,
        }).catch(() => {});
      }
    }
    // Same reasoning as setObjectScale — force a redraw instead of waiting
    // for an unrelated interaction to mark the scene dirty.
    dirtyRef.current = true;
  }, []);

  // Place one file at every station in the given stationEntries array (line placement).
  // Loads the file once then deep-clones the resulting object per station — same
  // code path as placeObject so it's proven to work.
  // stationEntries: [{ stationId, lineGroupId }] — lineGroupId is each STATION's
  // own box name, which can differ from `lineName` (the line picked in the
  // upload dropdown) when the upload was fanned out to fuzzy-matching sibling
  // boxes ("Trim 1"/"Trim 2"/"Trim Line" etc. all count as one logical line
  // for seeding, but each keeps its own box name as line_group_id in the DB —
  // otherwise DELETE_BY_GROUP/getPlacementsByLineGroup for a sibling box's
  // real name would no longer find rows created under the dropdown's name).
  const placeObjectForLine = useCallback((file, name, layoutId, stationEntries, lineName) => {
    const scene = sceneRef.current;
    if (!scene || !stationEntries?.length) return;
    const ext  = file.name.split('.').pop().toLowerCase();
    // Use line name as group ID so the same line across layouts shares the same key.
    // Fall back to a timestamp-based ID only if no line name is provided.
    const groupId = lineName ? lineName : `line_${Date.now()}`;
    const url  = URL.createObjectURL(file);

    let _lpct = 10;
    onConvertStart && onConvertStart(_lpct);
    const _lticker = setInterval(() => {
      _lpct = Math.min(_lpct + (_lpct < 60 ? 4 : _lpct < 85 ? 1.5 : 0.4), 92);
      onConvertStart && onConvertStart(Math.round(_lpct));
    }, 300);

    const onTemplateLoaded = (template) => {
      clearInterval(_lticker);
      onConvertEnd && onConvertEnd();
      URL.revokeObjectURL(url);

      // Cache so other layouts (or reuse-from-library) skip the download
      setCachedTemplate(name, template);
      // See the matching comment in placeObject — an already-cached OTHER
      // layout's scene could still be showing the OLD version of this model.
      layoutSceneCacheRef.current.clear();
      invalidateGeoCache(name);

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
      const floorOffsetAtBase = floorY / autoScale;

      // Apply saved model preset if one exists
      const _linePreset = getModelPreset(name);
      if (_linePreset) {
        const ps = autoScale * (_linePreset.scale || 1);
        template.scale.setScalar(ps);
        template.rotation.set(
          ((_linePreset.rotX || 0) * Math.PI) / 180,
          ((_linePreset.rotY || 0) * Math.PI) / 180,
          ((_linePreset.rotZ || 0) * Math.PI) / 180
        );
        // recompute floorY after scale change
        const bboxPreset = new THREE.Box3().setFromObject(template);
        // override floorY for this preset
        Object.defineProperty(template, '_presetFloorY', { value: -bboxPreset.min.y, writable: true, configurable: true });
      }
      const effectiveFloorY = template._presetFloorY !== undefined ? template._presetFloorY : floorY;
      const effectiveScale  = _linePreset ? autoScale * (_linePreset.scale || 1) : autoScale;

      const posMap = stationPosRef.current;
      const newEntries = [];

      stationEntries.forEach((se, idx) => {
        const stationId = se.stationId;
        const entryGroupId = se.lineGroupId || groupId;
        const stnPos = posMap[stationId];
        if (!stnPos) return; // station not in this scene yet

        // Clone for every station — sharedClone shares geometry/material buffers
        // so GPU memory stays ~1× instead of N× for a 70 MB model. Always
        // clone (never place `template` itself): it's the same object held
        // in _modelTemplateCache, and Object3D.add() silently detaches an
        // object from its previous parent — placing the cached template
        // directly would rip it out of whichever scene last displayed it
        // the next time this line/model is loaded, leaving that station empty.
        const obj = sharedClone(template);

        // Center model's bounding box visual center at station center (X/Z)
        obj.position.set(0, effectiveFloorY, 0);
        const _bboxLine = new THREE.Box3().setFromObject(obj);
        const _xOff = (_bboxLine.min.x + _bboxLine.max.x) / 2;
        obj.position.set(stnPos.x - _xOff, effectiveFloorY, stnPos.z); // Z: station center directly
        obj.userData.baseScale           = effectiveScale;
        obj.userData.floorOffsetAtBase   = effectiveFloorY / effectiveScale;
        obj.userData.geoXOff          = _xOff;
        obj.userData.isPlaced         = true;
        obj.userData.objId            = `${groupId}_${idx}`;
        obj.userData.objName          = name;
        obj.userData.objExt           = ext;
        obj.userData.assignedStation  = stationId;
        obj.userData.lineGroupId      = entryGroupId;

        scene.add(obj); dirtyRef.current = true;
        newEntries.push({
          id: obj.userData.objId, mesh: obj,
          label: null, name, stationId, lineGroupId: entryGroupId,
          // Station anchor for offset persistence — object starts at offset 0.
          baseX: obj.position.x, baseZ: obj.position.z,
        });
      });

      if (newEntries.length === 0) {
        alert(
          `Line Placement: no 3D positions found.\n` +
          `Tried stations: ${stationEntries.slice(0,5).map(se => se.stationId).join(', ')}${stationEntries.length>5?'…':''}\n` +
          `Scene has ${Object.keys(posMap).length} station(s) mapped.`
        );
        return;
      }

      placedRef.current = [...placedRef.current, ...newEntries];
      syncHangerBars(scene, placedRef.current, posMap);
      onObjectsChange([...placedRef.current]);
      // Same reasoning as the single-object placement path — new entries mean
      // any cached scene snapshot for this layout is now out of date.
      layoutSceneCacheRef.current.delete(layoutIdRef.current);

      // Upload file once to global library, then create one placement per station.
      if (layoutId) {
        z3dModelApi.uploadToLibrary(file, { name }).then(() =>
          Promise.all(newEntries.map(entry =>
            z3dModelApi.createPlacement({
              layoutId, modelName: name,
              lineGroupId: entry.lineGroupId, stationId: entry.stationId || null,
              ...(() => {
                const p = buildTransformPayload(entry);
                return { px: p.px, py: p.py, pz: p.pz, posIsOffset: p.pos_is_offset };
              })(),
              rx: entry.mesh.rotation.x, ry: entry.mesh.rotation.y, rz: entry.mesh.rotation.z,
              sx: entry.mesh.scale.x,    sy: entry.mesh.scale.y,    sz: entry.mesh.scale.z,
            }).then(res => {
              entry.mesh.userData.serverModelId = res.data.id;
              entry.serverModelId = res.data.id;
            })
          ))
        ).catch(err => {
          console.error('[Z3D] Failed to save line model to server:', err);
          const status = err?.response?.status;
          const reason = status === 413
            ? 'File is too large for the server to accept.'
            : (err?.message || 'Unknown error');
          alert(
            `"${name}" is visible now, but failed to save to the server (${reason}).\n` +
            `It will disappear on refresh and won't be available in other layouts.`
          );
        });
      }
    };

    if (ext === 'glb' || ext === 'gltf') {
      makeGLTFLoader().load(url, (gltf) => onTemplateLoaded(gltf.scene), undefined, (err) => {
        clearInterval(_lticker);
        URL.revokeObjectURL(url);
        onConvertEnd && onConvertEnd(false);
        console.error('[Z3D] GLB line-load failed:', err);
        alert('Failed to load GLB: ' + (err?.message || err));
      });
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

  // Drops every cached scene so the next visit to ANY layout re-fetches
  // placements from the server instead of reusing stale in-memory meshes.
  // Needed after any change that edits placement rows OUTSIDE this hook's
  // own mutation functions (which already clear their own layout's cache
  // entry) — e.g. a retroactive "apply to all layouts" bulk update that
  // touches other layouts' rows directly via the API.
  const clearSceneCache = useCallback(() => {
    layoutSceneCacheRef.current.clear();
  }, []);

  return { snapView, setTransformMode, placeObject, placeObjectForLine, handleCanvasClick, handleCanvasDblClick, selectById, deleteById, renameById, setObjectScale, setGroupRotation, animateAlongPath, stopAnimation, setEnvironment, previewEnvironment: applyEnvPresetInternal, clearSceneCache };
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

// (IndexedDB removed — models are now persisted server-side via z3dModelApi)

// ── Main component ─────────────────────────────────────────────────────────────
function ZStage3DLayout({ userId, savedLayouts = [], activeLayoutId, isActive }) {
  // Model editing (upload, move/rotate/scale, rename, delete, presets) will
  // become admin-only; everyone else keeps the viewing features (layout/view
  // selection, environment swatches, walk mode, animations, station popups).
  // Enforcement is OFF for now so the whole flow can be tested as a normal
  // user — flip ENFORCE_ADMIN_EDIT to true once the exact set of options to
  // restrict is confirmed.
  const ENFORCE_ADMIN_EDIT = false;
  const isAdmin = !ENFORCE_ADMIN_EDIT || authService.isAdmin();
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
  const [modelLoadCount,    setModelLoadCount]    = useState({ loaded: 0, total: 0 });
  // Upload modal
  const [showUploadModal,   setShowUploadModal]   = useState(false);
  const [pendingFile,       setPendingFile]       = useState(null);
  const [uploadMode,        setUploadMode]        = useState('free');
  const [uploadShop,        setUploadShop]        = useState('');
  const [uploadStation,     setUploadStation]     = useState('');
  const [uploadLine,        setUploadLine]        = useState('');
  const [libraryModels,     setLibraryModels]     = useState([]);   // global library list
  const [selectedLibraryModel, setSelectedLibraryModel] = useState(null); // reuse-from-library
  const [existingNameMatch, setExistingNameMatch] = useState(null); // library entry that the pending upload's name would overwrite
  // Replace-confirmation popup — shown instead of uploading straight away when
  // the picked name collides with an existing library model.
  const [showReplaceModal,  setShowReplaceModal]  = useState(false);
  const [replaceInfo,       setReplaceInfo]       = useState(null); // { file, name, existingMatch }
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
    setModelLoadCount({ loaded: 0, total: 0, completed: 0 });
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

  const handleModelProgress = useCallback((loaded, total, completed) => {
    setModelLoadCount({ loaded, total, completed });
  }, []);

  const { snapView, setTransformMode, placeObject, placeObjectForLine, handleCanvasClick, handleCanvasDblClick, selectById, deleteById, renameById, setObjectScale, setGroupRotation, animateAlongPath, stopAnimation, setEnvironment, previewEnvironment, clearSceneCache } =
    useThreeScene(canvasRef, layout, statusMap, zeMap, walkMode, onObjectsChange, onConvertStart, onConvertEnd, handleStationClick, isActive, handleSceneReady, handleModelProgress, isAdmin);

  // Environment/background swatch — remembered per layout (localStorage),
  // re-read whenever the selected layout changes.
  const [envKey, setEnvKey] = useState(DEFAULT_ENV_KEY);
  useEffect(() => {
    if (!selectedLayoutId) return;
    setEnvKey(getEnvPreset(selectedLayoutId).key);
  }, [selectedLayoutId]);
  const handleEnvChange = useCallback((key) => {
    setEnvKey(key);
    setEnvironment(key);
  }, [setEnvironment]);

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

    // Auto-detect line from filename — fuzzy match against shopList
    const modelName = file.name.replace(/\.[^/.]+$/, '');
    const baseName = modelName.toLowerCase().replace(/[-_\s]+/g, ' ');
    const matched = shopList.find(shop => {
      const s = shop.toLowerCase().replace(/[-_\s]+/g, ' ');
      return baseName.includes(s) || s.includes(baseName);
    });
    if (matched) {
      setUploadMode('line');
      setUploadLine(matched);
    } else {
      setUploadMode('free');
      setUploadLine('');
    }
    setUploadShop('');
    setUploadStation('');

    // Check server library for saved defaults — apply if found. Also drives
    // the "this will replace an existing model" warning in the modal, since
    // uploading under a name that already exists in the library silently
    // overwrites that model's file for every layout/line that uses it.
    setExistingNameMatch(null);
    z3dModelApi.getLibraryModel(modelName).then(res => {
      const lib = res.data;
      if (lib) {
        const scale = lib.default_sx || 1;
        // lib.default_rx/ry/rz are stored in RADIANS (same convention as
        // every placement's rx/ry/rz); the local preset cache and the
        // rotation sliders are in DEGREES — convert or the modal/slider
        // shows a bogus angle and re-saves it back out just as wrong.
        const toDeg = (r) => ((r || 0) * 180) / Math.PI;
        saveModelPreset(modelName, { scale, rotX: toDeg(lib.default_rx), rotY: toDeg(lib.default_ry), rotZ: toDeg(lib.default_rz) });
        setExistingNameMatch(lib);
      }
    }).catch(() => {}); // not in library yet — that's fine

    // Fetch global library so modal can show "Recent Uploads"
    setSelectedLibraryModel(null);
    z3dModelApi.listLibrary().then(res => setLibraryModels(res.data || [])).catch(() => {});

    setShowUploadModal(true);
    e.target.value = '';
  }, [shopList]);

  // Places a file (real upload or blob fetched from the library) using
  // whichever upload-mode tab (free / station / line) is currently selected.
  // Shared by the normal upload path and both branches of the replace-confirm popup.
  const doPlaceUpload = useCallback((file, name) => {
    if (uploadMode === 'line' && uploadLine) {
      // Fan out to every box whose name fuzzy-matches the selected line
      // ("Trim 1" / "Trim 2" / "Trim Line" all count as the same logical
      // line per lineNamesMatch), not just boxes with a byte-identical
      // name. Each station keeps its OWN box name as lineGroupId. Without
      // this, only the exactly-matching box got filled immediately and the
      // rest stayed empty until the next full layout reload happened to
      // trigger the separate cross-layout auto-seed fallback.
      //
      // Guard: lineNamesMatch is deliberately loose (substring + abbreviation
      // matching) so it can equate "Trim 1"/"Trim Line", but that looseness
      // can also false-positive-match two genuinely unrelated lines that
      // happen to share a word. Never blast this upload onto a station that
      // already holds a DIFFERENT model — only fan out into stations that
      // are empty or already show this same model. Otherwise an edit to one
      // model could silently overwrite/rescale an unrelated model sitting in
      // a fuzzy-matched-but-different box.
      const modelAtStation = new Map(placedObjects.filter(o => o.stationId).map(o => [o.stationId, o.name]));
      const lineStations = stationList
        .filter(s => s.shop === uploadLine || lineNamesMatch(s.shop, uploadLine))
        .filter(s => {
          const existing = modelAtStation.get(s.id);
          return !existing || existing === name;
        })
        .map(s => ({ stationId: s.id, lineGroupId: s.shop }));
      if (lineStations.length === 0) { alert(`No stations found for line "${uploadLine}".`); return; }
      placeObjectForLine(file, name, selectedLayoutId, lineStations, uploadLine);
    } else {
      // Pass the shop/line as lineGroupId so cross-layout seeding can find this model
      const opts = uploadMode === 'station' && uploadStation
        ? { stationId: uploadStation, lineGroupId: uploadShop || null }
        : {};
      placeObject(file, name, selectedLayoutId, opts);
    }
    const _p = getModelPreset(name);
    setShowObjPanel(true);
    setScaleVal(_p ? (_p.scale || 1.0) : 1.0);
    setRotX(_p ? (_p.rotX || 0) : 0);
    setRotY(_p ? (_p.rotY || 0) : 0);
    setRotZ(_p ? (_p.rotZ || 0) : 0);
    setAnimFromStation(''); setAnimToStation(''); setAnimPlaying(false);
    setShowUploadModal(false); setPendingFile(null); setSelectedLibraryModel(null); setExistingNameMatch(null);
  }, [uploadMode, uploadStation, uploadLine, uploadShop, stationList, placeObject, placeObjectForLine, selectedLayoutId, placedObjects]);

  const handleUploadConfirm = useCallback(() => {
    // Reuse an existing library model — if already cached this session, still need a
    // File blob for placeObject (it creates a blob URL internally), so fetch from server.
    // The template cache inside placeObject/placeObjectForLine will then skip re-parsing.
    if (selectedLibraryModel) {
      const libName = selectedLibraryModel.name;
      const ext = selectedLibraryModel.ext || 'glb';
      const url = z3dModelApi.getDownloadUrl(libName);
      fetch(url)
        .then(r => { if (!r.ok) throw new Error('Download failed'); return r.blob(); })
        .then(blob => {
          const file = new File([blob], `${libName}.${ext}`, { type: blob.type || 'model/gltf-binary' });
          doPlaceUpload(file, libName);
        })
        .catch(err => alert('Failed to load library model: ' + err.message));
      return;
    }

    if (!pendingFile) return;
    const name = pendingFile.name.replace(/\.[^/.]+$/, '');
    // Uploading under a name that already exists in the library would silently
    // replace that model's file for every layout/line that references it —
    // ask which behaviour is wanted before doing something that hard to notice.
    if (existingNameMatch && existingNameMatch.name.toLowerCase() === name.toLowerCase()) {
      setReplaceInfo({ file: pendingFile, name, existingMatch: existingNameMatch });
      setShowReplaceModal(true);
      return;
    }
    doPlaceUpload(pendingFile, name);
  }, [pendingFile, selectedLibraryModel, existingNameMatch, doPlaceUpload]);

  // "Yes" — overwrite the shared library file so every layout/line using this
  // model name (old presets included, since presets are keyed by name) picks
  // up the new file.
  const confirmReplaceEverywhere = useCallback(() => {
    if (!replaceInfo) return;
    const { file, name, existingMatch } = replaceInfo;
    setShowReplaceModal(false); setReplaceInfo(null);
    // Use the EXISTING library entry's exact casing, not whatever case the
    // new file happened to be named — the library's name-uniqueness check
    // is case-sensitive, so uploading "Trim Line" when the library already
    // has "trim line" would otherwise create a brand-new second row/file
    // instead of updating the one everything already points to, silently
    // leaving old placements (and old layouts) referencing the old entry.
    doPlaceUpload(file, existingMatch?.name || name);
  }, [replaceInfo, doPlaceUpload]);

  // "No" — keep the existing shared model untouched (every other layout keeps
  // rendering the old file) and save the new upload under its own distinct
  // library name so only the current placement uses it.
  const confirmReplaceThisLayoutOnly = useCallback(() => {
    if (!replaceInfo) return;
    const { file, name } = replaceInfo;
    setShowReplaceModal(false); setReplaceInfo(null);
    const uniqueName = `${name}_${Date.now().toString(36)}`;
    doPlaceUpload(file, uniqueName);
  }, [replaceInfo, doPlaceUpload]);

  const cancelReplaceModal = useCallback(() => {
    setShowReplaceModal(false); setReplaceInfo(null);
  }, []);

  const currentSelected = placedObjects.find(o => o.id === selectedId);

  // Keep the scale/rotation sliders in sync with whatever is ACTUALLY
  // selected. Without this, the sliders only ever get set when a NEW object
  // is first placed (or explicitly dragged) — selecting a different,
  // already-placed object (click in the canvas, or the Objects list) left
  // them showing whatever was left over from the PREVIOUS selection. Clicking
  // "Save Preset" then broadcast that stale, wrong value onto every
  // placement of the newly-selected model, silently reverting its real saved
  // rotation/scale back to whatever the sliders happened to still show.
  useEffect(() => {
    if (!currentSelected?.mesh) return;
    const mesh = currentSelected.mesh;
    const base = mesh.userData.baseScale || 1;
    setScaleVal(base ? mesh.scale.x / base : 1);
    setRotX(Math.round((mesh.rotation.x * 180) / Math.PI));
    setRotY(Math.round((mesh.rotation.y * 180) / Math.PI));
    setRotZ(Math.round((mesh.rotation.z * 180) / Math.PI));
  }, [selectedId, currentSelected]);

  // ── Scope-confirm popup ─────────────────────────────────────────────────
  // Same "this layout only, or every layout" question, reused for two things:
  // saving a scale/rotation as the model's default, and picking an
  // environment swatch. `pending` carries whatever the confirm/cancel
  // handlers need: { kind: 'transform', modelName, scale, rotX, rotY, rotZ }
  // or { kind: 'environment', key }.
  const [scopeConfirm, setScopeConfirm] = useState(null);

  const openSavePresetConfirm = useCallback(() => {
    if (!currentSelected) return;
    const modelName = currentSelected.mesh?.userData?.objName || currentSelected.name;
    if (!modelName) return;
    // Capture position as the station-relative offset (what the library's
    // default_px/pz mean) so the preset makes sense on any station/line.
    // Free objects have no station anchor — save a zero offset for them.
    const p = buildTransformPayload(currentSelected);
    setScopeConfirm({
      kind: 'transform', modelName,
      // scale here is the SLIDER MULTIPLIER (e.g. 1.0 = "100%", shown as
      // "1.0×") — baseScale is the model's own auto-fit scale. Both saved
      // placements and library defaults store an ABSOLUTE scale
      // (baseScale * multiplier), same convention as every drag/rotate save
      // elsewhere — baseScale must travel with scale so the confirm handler
      // can convert back to absolute instead of saving the bare multiplier.
      scale: scaleVal, baseScale: currentSelected.mesh?.userData?.baseScale || 1,
      rotX, rotY, rotZ,
      px: p.pos_is_offset ? p.px : 0, py: p.py, pz: p.pos_is_offset ? p.pz : 0,
    });
  }, [currentSelected, scaleVal, rotX, rotY, rotZ]);

  // Clicking a swatch shows the change immediately (so you can see it before
  // deciding anything) but doesn't save anywhere yet — only Cancel/Confirm
  // in the popup decides whether it sticks, and where.
  const openEnvScopeConfirm = useCallback((key) => {
    const prevKey = envKey;
    previewEnvironment(key);
    setEnvKey(key);
    setScopeConfirm({ kind: 'environment', key, prevKey });
  }, [envKey, previewEnvironment]);

  const cancelScopeConfirm = useCallback(() => {
    if (scopeConfirm?.kind === 'environment') {
      // Undo the preview — restore whatever was showing before the swatch was clicked.
      previewEnvironment(scopeConfirm.prevKey);
      setEnvKey(scopeConfirm.prevKey);
    }
    setScopeConfirm(null);
  }, [scopeConfirm, previewEnvironment]);

  const confirmScopeThisLayout = useCallback(() => {
    if (!scopeConfirm) return;
    if (scopeConfirm.kind === 'transform') {
      // Values are already live-saved to this layout's placement(s) as the
      // user dragged the slider — nothing further to do.
    } else if (scopeConfirm.kind === 'environment') {
      handleEnvChange(scopeConfirm.key);
    }
    setScopeConfirm(null);
  }, [scopeConfirm, handleEnvChange]);

  const confirmScopeAllLayouts = useCallback(() => {
    if (!scopeConfirm) return;
    if (scopeConfirm.kind === 'transform') {
      const { modelName, scale, baseScale, rotX: rx, rotY: ry, rotZ: rz, px, py, pz } = scopeConfirm;
      // rx/ry/rz are the slider's DEGREES (0-360) — every placement's stored
      // rotation, and the renderer's obj.rotation.set(), are in RADIANS.
      // The live per-layout drag handler (setGroupRotation) converts before
      // saving; this "apply to all" push must do the same conversion or
      // every OTHER layout's copy ends up with a huge bogus radian value
      // (e.g. 90° sent as 90 rad), which renders as a wild, "tilted"
      // rotation that looks like an untouched fresh upload.
      const rxRad = (rx * Math.PI) / 180, ryRad = (ry * Math.PI) / 180, rzRad = (rz * Math.PI) / 180;
      // `scale` is the slider's MULTIPLIER (1.0 = "100%") — every stored sx/
      // sy/sz (placements AND library defaults) is an ABSOLUTE scale
      // (baseScale * multiplier), same convention the loader/renderer use
      // everywhere else. Sending the bare multiplier as sx directly shrank
      // or grew the object on the very next reload (autoScale is typically
      // well under 1, e.g. 0.1-0.5, so a "1.0×" save could 2-10x the visible
      // size) — and since floor-snap height is scale-dependent, the object
      // visibly jumped upward at the same time as it changed size.
      const absScale = (baseScale || 1) * scale;
      // Sets the default for FUTURE placements/new layouts... position must
      // be included too — the defaults endpoint accepts px/py/pz and
      // defaults any missing one to 0, so omitting them here would silently
      // reset this model's saved position to the origin every time someone
      // saves a rotation/scale preset.
      saveModelPreset(modelName, { scale, rotX: rx, rotY: ry, rotZ: rz });
      z3dModelApi.saveDefaults(modelName, { px, py, pz, sx: absScale, sy: absScale, sz: absScale, rx: rxRad, ry: ryRad, rz: rzRad })
        .catch(err => console.error('[Z3D] Save Preset: saveDefaults failed —', err?.response?.status, err?.response?.data || err?.message));
      // ...AND retroactively pushes the same scale/rotation onto every
      // already-placed copy of this model in every other layout, so "All
      // layouts" actually means all layouts — not just ones created later.
      // Uses the rotation/scale-ONLY endpoint — it never reads or rewrites
      // position, so it can't race a concurrent drag/move on the same
      // placement (the old approach fetched each row's "current" px/py/pz
      // and wrote it straight back "unchanged", but if that fetch ran before
      // an in-flight drag's own save had committed, it silently wrote back
      // the stale pre-drag position, undoing the move).
      z3dModelApi.getPlacementsByModelName(modelName).then(res => {
        const rows = res.data || [];
        console.info(`[Z3D] Save Preset (All layouts): found ${rows.length} existing placement(s) of "${modelName}" to update.`);
        return Promise.all(rows.map(p =>
          z3dModelApi.updateRotationScale(p.id, {
            rx: rxRad, ry: ryRad, rz: rzRad, sx: absScale, sy: absScale, sz: absScale,
          }).then(
            () => ({ id: p.id, ok: true }),
            err => {
              console.error(`[Z3D] Save Preset: updateTransform failed for placement ${p.id} —`, err?.response?.status, err?.response?.data || err?.message);
              return { id: p.id, ok: false };
            }
          )
        ));
      }).then(results => {
        const failed = results.filter(r => !r.ok);
        if (failed.length > 0) {
          console.error(`[Z3D] Save Preset (All layouts): ${failed.length} of ${results.length} placement(s) FAILED to update — see errors above. IDs:`, failed.map(f => f.id));
        } else {
          console.info(`[Z3D] Save Preset (All layouts): all ${results.length} placement(s) updated successfully.`);
        }
        // Without this, switching back to a layout you edited moments ago
        // (or any other layout using this model) can show the OLD in-memory
        // scene from before this update — the retroactive fix landed in the
        // database, but the cached scene never got told to refresh, so it
        // looked like nothing happened (or reverted back to the old tilt).
        clearSceneCache();
      }).catch(err => console.error('[Z3D] Save Preset (All layouts): getPlacementsByModelName failed —', err?.response?.status, err?.response?.data || err?.message));
    } else if (scopeConfirm.kind === 'environment') {
      const { key } = scopeConfirm;
      setEnvKey(key);
      setEnvironment(key);
      savedLayouts.forEach(l => { if (l.id !== selectedLayoutId) saveEnvPreset(l.id, key); });
    }
    setScopeConfirm(null);
  }, [scopeConfirm, savedLayouts, selectedLayoutId, setEnvironment, clearSceneCache]);

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
    // deleteById removes entire group — clear selection if any group member was selected
    const obj = placedObjects.find(o => o.id === id);
    const groupIds = obj?.lineGroupId
      ? placedObjects.filter(o => o.lineGroupId === obj.lineGroupId).map(o => o.id)
      : [id];
    const scopeMsg = obj?.lineGroupId
      ? `Remove "${obj?.name}" from all ${groupIds.length} station(s) of line "${obj.lineGroupId}"?`
      : `Remove "${obj?.name}" from this layout?`;
    if (!window.confirm(
      `${scopeMsg}\n\nThe uploaded file stays in the model library — it can be ` +
      `assigned again from Layout Preparation without re-uploading.`
    )) return;
    deleteById(id);
    if (groupIds.includes(selectedId)) setSelectedId(null);
  }, [deleteById, selectedId, placedObjects]);

  const handleRename = useCallback(() => {
    if (!renameVal.trim() || !selectedId) return;
    renameById(selectedId, renameVal.trim());
  }, [renameVal, renameById, selectedId]);

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

            {/* Environment / background swatches */}
            <div className="z3d-env-group" title="Environment">
              {ENV_PRESETS.map(p => (
                <button
                  key={p.key}
                  type="button"
                  className={`z3d-env-swatch${envKey === p.key ? ' active' : ''}`}
                  style={{ backgroundColor: p.swatch }}
                  title={p.label}
                  onClick={() => openEnvScopeConfirm(p.key)}
                />
              ))}
            </div>

            {/* Upload object — admin only */}
            {isAdmin && (
              <>
                <button type="button" className="z3d-upload-btn" onClick={() => fileInputRef.current?.click()} title="Upload GLB, OBJ or STL file">
                  ⬆ Upload Object
                </button>
                <input ref={fileInputRef} type="file" accept=".glb,.gltf,.obj,.stl,.wrl,.stp,.step" style={{ display: 'none' }} onChange={handleFileUpload} />
              </>
            )}

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

            {/* Transform mode — admin only */}
            {isAdmin && currentSelected && (
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

            {/* Rename — admin only */}
            {isAdmin && currentSelected && (
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

            {/* Scale — admin only */}
            {isAdmin && currentSelected && (
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

            {/* Rotation (applies to all in group) — admin only */}
            {isAdmin && currentSelected && (
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
                      onFocus={e => e.target.select()}
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
                <button
                  type="button" className="z3d-save-preset-btn"
                  title="Save this scale/rotation as the model's preset"
                  onClick={openSavePresetConfirm}
                >💾 Save Preset…</button>
                <div className="z3d-autosave-notice">Changes apply to this layout only until you save a preset</div>
              </div>
            )}

            {/* Object list — line groups collapsed into one row */}
            <div className="z3d-obj-list">
              {placedObjects.length === 0 && <div className="z3d-obj-empty">No objects placed yet</div>}
              {(() => {
                const seen = new Set();
                return placedObjects.map(obj => {
                  const key = obj.lineGroupId || obj.id;
                  if (seen.has(key)) return null;
                  seen.add(key);
                  const groupMembers = obj.lineGroupId
                    ? placedObjects.filter(o => o.lineGroupId === obj.lineGroupId)
                    : [obj];
                  const isGroupSelected = groupMembers.some(o => o.id === selectedId);
                  return (
                    <div
                      key={key}
                      className={`z3d-obj-item${isGroupSelected ? ' z3d-obj-item--active' : ''}`}
                      onClick={() => handleSelect(obj.id)}
                    >
                      <span className="z3d-obj-icon">{obj.lineGroupId ? '🔗' : '📦'}</span>
                      <span className="z3d-obj-name">
                        {obj.name}
                        {obj.lineGroupId
                          ? <span className="z3d-obj-station-tag">{groupMembers.length} stations</span>
                          : obj.stationId && <span className="z3d-obj-station-tag">{obj.stationId}</span>
                        }
                      </span>
                      {isAdmin && (
                        <button type="button"
                          className="z3d-obj-del"
                          title={obj.lineGroupId ? 'Delete all in line' : 'Delete'}
                          onClick={e => { e.stopPropagation(); handleDelete(obj.id); }}
                        >✕</button>
                      )}
                    </div>
                  );
                });
              })()}
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
              {!sceneReady && (() => {
                const pct = modelLoadCount.total > 0
                  ? Math.min(100, Math.round((modelLoadCount.loaded / modelLoadCount.total) * 100))
                  : 0;
                const completed = modelLoadCount.completed ?? 0;
                return (
                <div className="z3d-scene-loading">
                  <div className="z3d-scene-loading-box">
                    <div className="z3d-scene-loading-spinner" />
                    <div className="z3d-scene-loading-text">
                      {modelLoadCount.total === 0
                        ? 'Preparing scene…'
                        : completed < modelLoadCount.total
                          ? `Downloading models… (${completed} of ${modelLoadCount.total} done)`
                          : 'Placing models…'}
                    </div>
                    <div className="z3d-scene-loading-bar-track">
                      {modelLoadCount.total > 0 ? (
                        <div
                          className="z3d-scene-loading-bar-fill z3d-scene-loading-bar-fill--progress"
                          style={{ width: `${pct}%` }}
                        />
                      ) : (
                        <div className="z3d-scene-loading-bar-fill" />
                      )}
                    </div>
                    {modelLoadCount.total > 0 && (
                      <div className="z3d-scene-loading-pct">
                        {pct}%
                      </div>
                    )}
                  </div>
                </div>
                );
              })()}
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
        <div className="z3d-modal-overlay" onClick={() => { setShowUploadModal(false); setPendingFile(null); setSelectedLibraryModel(null); setExistingNameMatch(null); }}>
          <div className="z3d-modal-box" onClick={e => e.stopPropagation()}>
            <div className="z3d-modal-title">Upload 3D Object</div>

            {/* ── Library picks: reuse an already-uploaded model ── */}
            {libraryModels.length > 0 && (
              <div className="z3d-library-section">
                <div className="z3d-library-section-title">Recent Uploads (click to reuse)</div>
                <div className="z3d-library-picks">
                  {libraryModels.map(m => (
                    <button
                      key={m.name}
                      type="button"
                      className={`z3d-library-chip${selectedLibraryModel?.name === m.name ? ' selected' : ''}`}
                      onClick={() => setSelectedLibraryModel(selectedLibraryModel?.name === m.name ? null : m)}
                      title={`Reuse "${m.name}" from library`}
                    >
                      {m.name}
                    </button>
                  ))}
                </div>
                {selectedLibraryModel && (
                  <div className="z3d-library-notice">
                    Using saved model: <strong>{selectedLibraryModel.name}</strong>
                    <span className="z3d-library-or"> — or upload a new file below</span>
                  </div>
                )}
                <div className="z3d-library-divider"><span>— or upload new file —</span></div>
              </div>
            )}

            {!selectedLibraryModel && (
              <div className="z3d-modal-filename">{pendingFile?.name}</div>
            )}
            {!selectedLibraryModel && existingNameMatch &&
              existingNameMatch.name.toLowerCase() === pendingFile?.name.replace(/\.[^/.]+$/, '').toLowerCase() && (
              <div className="z3d-library-notice z3d-library-notice--warning">
                ⚠ A model named "{existingNameMatch.name}"
                {existingNameMatch.file_size ? ` (${formatFileSize(existingNameMatch.file_size)})` : ''} already
                exists — uploading will replace it everywhere it's used.
              </div>
            )}

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
              <button type="button" className="z3d-modal-cancel" onClick={() => { setShowUploadModal(false); setPendingFile(null); setSelectedLibraryModel(null); setExistingNameMatch(null); }}>Cancel</button>
              <button type="button"
                className="z3d-modal-confirm"
                disabled={
                  (!selectedLibraryModel && !pendingFile) ||
                  (uploadMode === 'station' && !uploadStation) ||
                  (uploadMode === 'line' && !uploadLine)
                }
                onClick={handleUploadConfirm}
              >{selectedLibraryModel ? 'Place' : 'Upload'}</button>
            </div>
          </div>
        </div>
      )}

      {showReplaceModal && replaceInfo && (
        <div className="z3d-modal-overlay" onClick={cancelReplaceModal}>
          <div className="z3d-modal-box" onClick={e => e.stopPropagation()}>
            <div className="z3d-modal-title">Replace "{replaceInfo.name}"?</div>
            <div className="z3d-modal-hint">
              A model named "{replaceInfo.name}"
              {replaceInfo.existingMatch?.file_size ? ` (${formatFileSize(replaceInfo.existingMatch.file_size)})` : ''} already
              exists in the library.
            </div>
            <div className="z3d-modal-hint" style={{ marginTop: 8 }}>
              <strong>Replace all layouts</strong> — every layout/line currently using this model will
              switch to the new file, keeping the same scale/rotation preset.<br />
              <strong>Keep old layouts as-is</strong> — only this upload uses the new file; every other
              layout keeps showing the old model untouched.
            </div>
            <div className="z3d-modal-actions">
              <button type="button" className="z3d-modal-cancel" onClick={cancelReplaceModal}>Cancel</button>
              <button type="button" className="z3d-modal-cancel" onClick={confirmReplaceThisLayoutOnly}>Keep old layouts as-is</button>
              <button type="button" className="z3d-modal-confirm" onClick={confirmReplaceEverywhere}>Replace all layouts</button>
            </div>
          </div>
        </div>
      )}

      {scopeConfirm && (
        <div className="z3d-modal-overlay" onClick={cancelScopeConfirm}>
          <div className="z3d-modal-box" onClick={e => e.stopPropagation()}>
            {scopeConfirm.kind === 'transform' ? (
              <>
                <div className="z3d-modal-title">Save preset for "{scopeConfirm.modelName}"?</div>
                <div className="z3d-modal-hint">
                  <strong>This layout only</strong> — keep this scale/rotation just for the copy you're
                  editing now; every other layout keeps its own values.<br />
                  <strong>All layouts</strong> — save this as the default for "{scopeConfirm.modelName}", so
                  new placements and newly-created layouts use it too.
                </div>
              </>
            ) : (
              <>
                <div className="z3d-modal-title">Apply this environment everywhere?</div>
                <div className="z3d-modal-hint">
                  <strong>This layout only</strong> — just the layout you're viewing now switches to this
                  background/lighting.<br />
                  <strong>All layouts</strong> — every saved layout switches to it too.
                </div>
              </>
            )}
            <div className="z3d-modal-actions">
              <button type="button" className="z3d-modal-cancel" onClick={cancelScopeConfirm}>Cancel</button>
              <button type="button" className="z3d-modal-cancel" onClick={confirmScopeThisLayout}>This layout only</button>
              <button type="button" className="z3d-modal-confirm" onClick={confirmScopeAllLayouts}>All layouts</button>
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
