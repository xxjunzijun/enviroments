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
