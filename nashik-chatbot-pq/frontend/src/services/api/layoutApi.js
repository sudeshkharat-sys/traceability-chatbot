import axios from 'axios';

const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

export const layoutApi = {
  getLayouts: () => api.get('/layouts'),
  getLayout: (id) => api.get(`/layouts/${id}`),
  createLayout: (data) => api.post('/layouts', data),
  updateLayout: (id, data) => api.put(`/layouts/${id}`, data),
  deleteLayout: (id) => api.delete(`/layouts/${id}`),
  // Snapshot: full canvas save in one request
  createSnapshot: (data) => api.post('/layouts/snapshot', data),
  updateSnapshot: (id, data) => api.put(`/layouts/${id}/snapshot`, data),
};

export const stationBoxApi = {
  getBoxesByLayout: (layoutId) => api.get(`/layouts/${layoutId}/boxes`),
  createBox: (layoutId, data) => api.post(`/layouts/${layoutId}/boxes`, data),
  updateBox: (boxId, data) => api.put(`/boxes/${boxId}`, data),
  deleteBox: (boxId) => api.delete(`/boxes/${boxId}`),
};

export const bypassIconApi = {
  getBypassIcons: (layoutId) => api.get(`/layouts/${layoutId}/bypass-icons`),
  createBypassIcon: (layoutId, data) => api.post(`/layouts/${layoutId}/bypass-icons`, data),
  updateBypassIcon: (iconId, data) => api.put(`/bypass-icons/${iconId}`, data),
  deleteBypassIcon: (iconId) => api.delete(`/bypass-icons/${iconId}`),
};

export const inputApi = {
  uploadExcel: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return axios.post(`${BASE_URL}/input/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  getRecords: () => api.get('/input/records'),
  updateRecord: (id, data) => api.put(`/input/records/${id}`, data),
};
