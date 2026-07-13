import { defineStore } from 'pinia'
import eventAdminApi, { getEventAdminToken, setEventAdminToken } from '@/api/eventAdminClient'

export const useEventAdminAuthStore = defineStore('eventAdminAuth', {
  state: () => ({
    userId: null,
    username: '',
    events: [],
    loaded: false,
  }),
  getters: {
    isLoggedIn: (s) => !!getEventAdminToken() && s.userId != null,
  },
  actions: {
    async login(username, password) {
      const res = await eventAdminApi.post('/auth/login', { username, password })
      const { token, user_id, username: name, events } = res.data.data
      setEventAdminToken(token)
      this.userId = user_id
      this.username = name
      this.events = events || []
      this.loaded = true
    },
    logout() {
      setEventAdminToken(null)
      this.userId = null
      this.username = ''
      this.events = []
      this.loaded = false
    },
    async fetchMe() {
      if (!getEventAdminToken()) {
        this.loaded = true
        return false
      }
      try {
        const res = await eventAdminApi.get('/auth/me')
        this.userId = res.data.data.user_id
        this.username = res.data.data.username
        this.events = res.data.data.events || []
        this.loaded = true
        return true
      } catch {
        this.logout()
        this.loaded = true
        return false
      }
    },
  },
})
