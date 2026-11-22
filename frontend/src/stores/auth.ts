import { defineStore } from 'pinia'
import { api } from '../api'
import type { AuthMe, MemberOut } from '../types'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    member: null as MemberOut | null,
    familyName: '',
    needsSetup: false,
    checked: false,
    loading: false,
  }),
  getters: {
    isParent: (state) => state.member?.role === 'parent',
    isChild: (state) => state.member?.role === 'child',
  },
  actions: {
    setSession(data: AuthMe) {
      this.member = data.member
      this.familyName = data.family_name
    },
    clearSession() {
      this.member = null
      this.familyName = ''
    },
    async fetchSetupStatus() {
      const status = await api.setupStatus()
      this.needsSetup = status.needs_setup
      if (status.family_name) this.familyName = status.family_name
    },
    async fetchMe() {
      try {
        const data = await api.me()
        this.setSession(data)
      } catch {
        this.clearSession()
      }
    },
    async bootstrap() {
      if (this.checked) return
      this.loading = true
      try {
        await this.fetchSetupStatus()
        if (!this.needsSetup) await this.fetchMe()
      } finally {
        this.checked = true
        this.loading = false
      }
    },
    async login(memberId: number, pin: string) {
      const data = await api.login(memberId, pin)
      this.setSession(data)
      this.needsSetup = false
      this.checked = true
    },
    async logout() {
      try {
        await api.logout()
      } finally {
        this.clearSession()
        this.checked = true
      }
    },
  },
})
