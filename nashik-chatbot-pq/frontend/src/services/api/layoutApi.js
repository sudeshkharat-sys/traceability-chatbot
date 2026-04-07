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
  uploadExcel: (file, userId, layoutId) => {
    const formData = new FormData();
    formData.append('file', file);
    if (userId != null) formData.append('user_id', userId);
    if (layoutId != null) formData.append('layout_id', layoutId);
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
};

export const layeredAuditApi = {
  uploadAudit: (file, userId, layoutId) => {
    const formData = new FormData();
    formData.append('file', file);
    if (userId != null) formData.append('user_id', userId);
    if (layoutId != null) formData.append('layout_id', layoutId);
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
  uploadAdherence: (file, userId, layoutId) => {
    const formData = new FormData();
    formData.append('file', file);
    if (userId != null) formData.append('user_id', userId);
    if (layoutId != null) formData.append('layout_id', layoutId);
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
};
