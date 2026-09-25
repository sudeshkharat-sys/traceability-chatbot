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
  analyze: (file, sheetNames, repeat = 3) => {
    const formData = new FormData();
    formData.append('file', file);
    if (sheetNames && sheetNames.length) {
      formData.append('sheet_names', sheetNames.join(','));
    }
    formData.append('repeat', repeat);
    return axios.post(`${BASE_URL}/analyze`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      // Row-by-row LLM scoring on a real sheet can take several minutes -
      // axios's default timeout would cut the request off well before the
      // pipeline finishes.
      timeout: 15 * 60 * 1000,
    });
  },
  downloadUrl: (token) => `${BASE_URL}/download/${token}`,
};
