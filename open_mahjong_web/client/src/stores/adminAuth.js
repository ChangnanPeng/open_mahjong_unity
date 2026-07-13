import { defineStore } from 'pinia'
import adminApi, { getAdminToken, setAdminToken } from '@/api/adminClient'

export const useAdminAuthStore = defineStore('adminAuth', {
  state: () => ({
    token: getAdminToken() || '',
    userId: null,
    username: '',
    loaded: false,
  }),
  getters: {
    isLoggedIn: (s) => !!s.token && s.userId != null && s.userId !== '',
  },
  actions: {
    _setSession({ token, userId, username }) {
      if (token) {
        setAdminToken(token)
        this.token = token
      }
      if (userId != null) this.userId = Number(userId) || userId
      if (username != null) this.username = username
      this.loaded = true
    },
    async login(username, password) {
      const res = await adminApi.post('/auth/login', { username, password })
      const { token, user_id, username: name } = res.data.data
      this._setSession({ token, userId: user_id, username: name })
    },
    logout() {
      setAdminToken(null)
      this.token = ''
      this.userId = null
      this.username = ''
      this.loaded = false
    },
    async fetchMe() {
      if (!getAdminToken()) {
        this.token = ''
        this.userId = null
        this.username = ''
        this.loaded = true
        return false
      }
      try {
        const res = await adminApi.get('/auth/me')
        this._setSession({
          token: getAdminToken(),
          userId: res.data.data.user_id,
          username: res.data.data.username,
        })
        return true
      } catch {
        this.logout()
        this.loaded = true
        return false
      }
    },
  },
})
