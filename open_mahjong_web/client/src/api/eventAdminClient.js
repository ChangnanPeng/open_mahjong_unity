import axios from 'axios'

const TOKEN_KEY = 'event_admin_token'

export function getEventAdminToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setEventAdminToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }
}

const eventAdminApi = axios.create({
  baseURL: '/api/event-admin',
  timeout: 30000,
})

eventAdminApi.interceptors.request.use((config) => {
  const token = getEventAdminToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

eventAdminApi.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      setEventAdminToken(null)
      const path = window.location.pathname
      if (path.startsWith('/event-admin') && !path.startsWith('/event-admin/login')) {
        window.location.href = `/login?redirect=${encodeURIComponent(path)}`
      }
    }
    return Promise.reject(err)
  }
)

export default eventAdminApi
