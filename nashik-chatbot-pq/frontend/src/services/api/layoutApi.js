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
  list: (layoutId) => api.get(`/3d-models/layout/${layoutId}`),

  upload: (file, { layoutId, userId, name, lineGroupId, stationId, isGroupLeader, px, py, pz, rx, ry, rz, sx, sy, sz }) => {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('layout_id', layoutId);
    if (userId != null) fd.append('user_id', userId);
    fd.append('name', name);
    if (lineGroupId) fd.append('line_group_id', lineGroupId);
    if (stationId) fd.append('station_id', stationId);
    fd.append('is_group_leader', isGroupLeader ? 'true' : 'false');
    fd.append('px', px ?? 0); fd.append('py', py ?? 0); fd.append('pz', pz ?? 0);
    fd.append('rx', rx ?? 0); fd.append('ry', ry ?? 0); fd.append('rz', rz ?? 0);
    fd.append('sx', sx ?? 1); fd.append('sy', sy ?? 1); fd.append('sz', sz ?? 1);
    return axios.post(`${BASE_URL}/3d-models/upload`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
  },

  getDownloadUrl: (modelId) => `${BASE_URL}/3d-models/${modelId}/download`,

  updateTransform: (modelId, transform) => api.put(`/3d-models/${modelId}/transform`, transform),

  delete: (modelId) => api.delete(`/3d-models/${modelId}`),
};
