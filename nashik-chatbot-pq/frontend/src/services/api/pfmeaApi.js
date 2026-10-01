import axios from 'axios';
import { backend_url } from "./config";

const BASE_URL = `${backend_url}/pfmea`;

export const pfmeaApi = {
  listSheets: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return axios.post(`${BASE_URL}/sheets`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  // Starts the review as a background job and returns { token } right
  // away - poll getProgress(token) for live status, then getResult(token)
  // once it reports done/cancelled. Replaces the old single long-lived
  // request, which had no way to show real progress and could only be
  // "cancelled" by dropping the connection.
  // Converts non-Nashik sheets to Nashik format (no AI calls) and returns a
  // before/after preview + convert_token to confirm and then run on.
  convertToNashik: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return axios.post(`${BASE_URL}/convert`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  convertedUrl: (token) => `${BASE_URL}/converted/${token}`,
  startAnalysis: (file, sheetNames, repeat = 3, convertToken = null) => {
    const formData = new FormData();
    formData.append('file', file);
    if (sheetNames && sheetNames.length) {
      formData.append('sheet_names', sheetNames.join(','));
    }
    formData.append('repeat', repeat);
    if (convertToken) formData.append('convert_token', convertToken);
    return axios.post(`${BASE_URL}/analyze`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  getProgress: (token) => axios.get(`${BASE_URL}/progress/${token}`),
  getResult: (token) => axios.get(`${BASE_URL}/result/${token}`),
  cancelRun: (token) => axios.post(`${BASE_URL}/cancel/${token}`),
  downloadUrl: (token) => `${BASE_URL}/download/${token}`,
};
