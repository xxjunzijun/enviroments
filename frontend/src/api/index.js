import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
})

export const servers = {
  list: () => api.get('/servers').then(r => r.data),

  get: (id) => api.get(`/servers/${id}`).then(r => r.data),

  create: (data) => api.post('/servers', data).then(r => r.data),

  update: (id, data) => api.put(`/servers/${id}`, data).then(r => r.data),

  delete: (id) => api.delete(`/servers/${id}`),

  checkStatus: (id) => api.get(`/servers/${id}/status`).then(r => r.data),

  fetchDetail: (id) => api.get(`/servers/${id}/detail`).then(r => r.data),
}

export const files = {
  list: (serverId, path) => api.get(`/servers/${serverId}/files`, { params: { path } }).then(r => r.data),

  downloadUrl: (serverId, path) => `/api/v1/servers/${serverId}/files/download?path=${encodeURIComponent(path)}`,

  upload: (serverId, path, base64Content) =>
    api.post(`/servers/${serverId}/files`, { path, content: base64Content }).then(r => r.data),
}

export const logs = {
  list: (serverId, limit = 100, offset = 0) =>
    api.get(`/servers/${serverId}/logs`, { params: { limit, offset } }).then(r => r.data),

  clear: (serverId) => api.delete(`/servers/${serverId}/logs/clear`),
}
