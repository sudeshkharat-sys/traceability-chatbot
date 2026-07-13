import axios from 'axios';
import { backend_url } from "./config";

const BASE_URL = `${backend_url}/z-stage`;

const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

export const layoutApi = {
  getLayouts: (userId) => api.get('/layouts/', { params: userId != null ? { user_id: userId } : {} }),
  getLayout: (id) => api.get(`/layouts/${id}`),
  createLayout: (data, userId) => api.post('/layouts', data, { params: userId != null ? { user_id: userId } : {} }),
  updateLayout: (id, data) => api.put(`/layouts/${id}`, data),
  deleteLayout: (id) => api.delete(`/layouts/${id}`),
  // Snapshot: full canvas save in one request
  createSnapshot: (data, userId) => api.post('/layouts/snapshot', data, { params: userId != null ? { user_id: userId } : {} }),
  updateSnapshot: (id, data) => api.put(`/layouts/${id}/snapshot`, data),
};

export const stationBoxApi = {
  getBoxesByLayout: (layoutId) => api.get(`/layouts/${layoutId}/boxes`),
  createBox: (layoutId, data) => api.post(`/layouts/${layoutId}/boxes`, data),
  updateBox: (boxId, data) => api.put(`/boxes/${boxId}`, data),
  deleteBox: (boxId) => api.delete(`/boxes/${boxId}`),
};

export const buyoffIconApi = {
  getBuyoffIcons: (layoutId) => api.get(`/layouts/${layoutId}/buyoff-icons`),
  createBuyoffIcon: (layoutId, data) => api.post(`/layouts/${layoutId}/buyoff-icons`, data),
  updateBuyoffIcon: (iconId, data) => api.put(`/buyoff-icons/${iconId}`, data),
  deleteBuyoffIcon: (iconId) => api.delete(`/buyoff-icons/${iconId}`),
};

// Backward-compat alias
export const bypassIconApi = buyoffIconApi;

export const inputApi = {
  uploadExcel: (file, userId, layoutId, mode = 'replace') => {
    const formData = new FormData();
    formData.append('file', file);
    if (userId != null) formData.append('user_id', userId);
    if (layoutId != null) formData.append('layout_id', layoutId);
    formData.append('mode', mode);
    return axios.post(`${BASE_URL}/input/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  getRecords: (userId, layoutId) => {
    const params = {};
    if (userId != null) params.user_id = userId;
    if (layoutId != null) params.layout_id = layoutId;
    return api.get('/input/records', { params });
  },
  updateRecord: (id, data) => api.put(`/input/records/${id}`, data),
  deleteRecord: (id) => api.delete(`/input/records/${id}`),
  createRecord: (data, userId, layoutId) => {
    const params = {};
    if (userId != null) params.user_id = userId;
    if (layoutId != null) params.layout_id = layoutId;
    return api.post('/input/records', data, { params });
  },
  downloadExcel: (userId, layoutId) => {
    const params = {};
    if (userId != null) params.user_id = userId;
    if (layoutId != null) params.layout_id = layoutId;
    return axios.get(`${BASE_URL}/input/download`, { params, responseType: 'blob' });
  },
};

export const layeredAuditApi = {
  uploadAudit: (file, userId, layoutId, mode = 'replace') => {
    const formData = new FormData();
    formData.append('file', file);
    if (userId != null) formData.append('user_id', userId);
    if (layoutId != null) formData.append('layout_id', layoutId);
    formData.append('mode', mode);
    return axios.post(`${BASE_URL}/layered-audit/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  getAuditRecords: (userId, layoutId) => {
    const params = {};
    if (userId != null) params.user_id = userId;
    if (layoutId != null) params.layout_id = layoutId;
    return api.get('/layered-audit/records', { params });
  },
  uploadAdherence: (file, userId, layoutId, mode = 'replace') => {
    const formData = new FormData();
    formData.append('file', file);
    if (userId != null) formData.append('user_id', userId);
    if (layoutId != null) formData.append('layout_id', layoutId);
    formData.append('mode', mode);
    return axios.post(`${BASE_URL}/layered-audit/adherence/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  getAdherenceRecords: (userId, layoutId) => {
    const params = {};
    if (userId != null) params.user_id = userId;
    if (layoutId != null) params.layout_id = layoutId;
    return api.get('/layered-audit/adherence/records', { params });
  },
  updateAuditRecord:       (id, data) => api.put(`/layered-audit/records/${id}`, data),
  deleteAuditRecord:       (id) => api.delete(`/layered-audit/records/${id}`),
  downloadAudit: (userId, layoutId) => {
    const params = {};
    if (userId != null) params.user_id = userId;
    if (layoutId != null) params.layout_id = layoutId;
    return axios.get(`${BASE_URL}/layered-audit/download`, { params, responseType: 'blob' });
  },
  updateAdherenceRecord:   (id, data) => api.put(`/layered-audit/adherence/records/${id}`, data),
  deleteAdherenceRecord:   (id) => api.delete(`/layered-audit/adherence/records/${id}`),
  downloadAdherence: (userId, layoutId) => {
    const params = {};
    if (userId != null) params.user_id = userId;
    if (layoutId != null) params.layout_id = layoutId;
    return axios.get(`${BASE_URL}/layered-audit/adherence/download`, { params, responseType: 'blob' });
  },
  createAuditRecord: (data, userId, layoutId) => {
    const params = {};
    if (userId != null) params.user_id = userId;
    if (layoutId != null) params.layout_id = layoutId;
    return api.post('/layered-audit/records', data, { params });
  },
  createAdherenceRecord: (data, userId, layoutId) => {
    const params = {};
    if (userId != null) params.user_id = userId;
    if (layoutId != null) params.layout_id = layoutId;
    return api.post('/layered-audit/adherence/records', data, { params });
  },
};

export const docApi = {
  uploadDoc: (file, userId, layoutId, stationId, concernId, docType) => {
    const formData = new FormData();
    formData.append('file', file);
    if (userId != null) formData.append('user_id', userId);
    if (layoutId != null) formData.append('layout_id', layoutId);
    formData.append('station_id', stationId);
    if (concernId != null) formData.append('concern_id', concernId);
    formData.append('doc_type', docType);
    return axios.post(`${BASE_URL}/docs/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  listDocs: (stationId, userId, layoutId) => {
    const params = { station_id: stationId };
    if (userId != null) params.user_id = userId;
    if (layoutId != null) params.layout_id = layoutId;
    return api.get('/docs/list', { params });
  },
  getDownloadUrl: (docId) => `${BASE_URL}/docs/${docId}/download`,
  deleteDoc: (docId) => api.delete(`/docs/${docId}`),
};
export const z3dModelApi = {
  // ── Global library ──────────────────────────────────────────────────────────
  listLibrary: () => api.get('/3d-models/library'),

  getLibraryModel: (name) => api.get(`/3d-models/library/${encodeURIComponent(name)}`),

  uploadToLibrary: (file, { name, defaultSx = 1, defaultSy = 1, defaultSz = 1, defaultRx = 0, defaultRy = 0, defaultRz = 0 }) => {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('name', name);
    fd.append('default_sx', defaultSx); fd.append('default_sy', defaultSy); fd.append('default_sz', defaultSz);
    fd.append('default_rx', defaultRx); fd.append('default_ry', defaultRy); fd.append('default_rz', defaultRz);
    return axios.post(`${BASE_URL}/3d-models/library/upload`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
  },

  saveDefaults: (name, { px = 0, py = 0, pz = 0, sx = 1, sy = 1, sz = 1, rx = 0, ry = 0, rz = 0 }) =>
    api.put(`/3d-models/library/${encodeURIComponent(name)}/defaults`, { px, py, pz, sx, sy, sz, rx, ry, rz }),

  deleteLibraryModel: (name) => api.delete(`/3d-models/library/${encodeURIComponent(name)}`),

  getDownloadUrl: (name) => `${BASE_URL}/3d-models/library/${encodeURIComponent(name)}/download`,

  // ── Per-layout placements ───────────────────────────────────────────────────
  listPlacements: (layoutId) => api.get(`/3d-models/placements/layout/${layoutId}`),
  listAllLineGroups: () => api.get('/3d-models/placements/line-groups'),
  getPlacementsByModelName: (modelName) => api.get(`/3d-models/placements/by-model-name/${encodeURIComponent(modelName)}`),
  getPlacementsByLineGroup: (lineGroupId) => api.get(`/3d-models/placements/by-line-group/${encodeURIComponent(lineGroupId)}`),

  createPlacement: ({ layoutId, modelName, lineGroupId, stationId, px, py, pz, rx, ry, rz, sx, sy, sz, posIsOffset }) => {
    // FormData.append() silently stringifies a missing value into the literal
    // text "undefined"/"null", which then gets saved to the DB as if it were
    // a real model name — fail loudly here instead of writing garbage data.
    if (!modelName) {
      return Promise.reject(new Error('createPlacement: modelName is required'));
    }
    const fd = new FormData();
    fd.append('layout_id', layoutId);
    fd.append('model_name', modelName);
    if (lineGroupId) fd.append('line_group_id', lineGroupId);
    if (stationId)   fd.append('station_id', stationId);
    fd.append('px', px ?? 0); fd.append('py', py ?? 0); fd.append('pz', pz ?? 0);
    fd.append('rx', rx ?? 0); fd.append('ry', ry ?? 0); fd.append('rz', rz ?? 0);
    fd.append('sx', sx ?? 1); fd.append('sy', sy ?? 1); fd.append('sz', sz ?? 1);
    fd.append('pos_is_offset', posIsOffset ? 'true' : 'false');
    return axios.post(`${BASE_URL}/3d-models/placements`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
  },

  updateTransform: (placementId, transform) =>
    api.put(`/3d-models/placements/${placementId}/transform`, transform),

  deletePlacement: (placementId) => api.delete(`/3d-models/placements/${placementId}`),

  deleteGroup: (layoutId, lineGroupId) =>
    api.delete(`/3d-models/placements/group/${layoutId}/${encodeURIComponent(lineGroupId)}`),
};

export const carModelApi = {
  list: () => api.get('/car-models'),
  create: ({ name, code }) => api.post('/car-models', { name, code }),
  update: (carModelId, { name, code }) => api.put(`/car-models/${carModelId}`, { name, code }),
  delete: (carModelId) => api.delete(`/car-models/${carModelId}`),
};

// Per-layout mappings: line name (+ optional car model) -> library model.
// Each layout has its own set — the object's transform (position/rotation/
// scale) is what's shared globally, via the library model's own defaults.
export const lineModelMappingApi = {
  listByLayout: (layoutId) => api.get(`/line-model-mappings/layout/${layoutId}`),
  create: ({ layoutId, lineGroupId, carModelId, modelName }) =>
    api.post('/line-model-mappings', {
      layout_id: layoutId, line_group_id: lineGroupId,
      car_model_id: carModelId ?? null, model_name: modelName,
    }),
  delete: (mappingId) => api.delete(`/line-model-mappings/${mappingId}`),
};
