import axios from 'axios'

const TOKEN_KEY = 'admin_token'

export function getAdminToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setAdminToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }
}

const adminApi = axios.create({
  baseURL: '/api/admin',
  timeout: 30000,
})

adminApi.interceptors.request.use((config) => {
  const token = getAdminToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

adminApi.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      setAdminToken(null)
      try {
        const { useAdminAuthStore } = require('@/stores/adminAuth')
        const store = useAdminAuthStore()
        if (store.token) {
          store.token = ''
          store.userId = null
          store.username = ''
        }
      } catch (_) {
        /* pinia may not be ready */
      }
      const path = window.location.pathname
      if (path.startsWith('/admin') && !path.startsWith('/admin/login')) {
        window.location.href = '/admin/login?redirect=/admin'
      }
    }
    return Promise.reject(err)
  }
)

export default adminApi
