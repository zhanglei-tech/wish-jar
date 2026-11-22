<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

async function logout() {
  await auth.logout()
  await router.replace({ name: 'login' })
}
</script>

<template>
  <header class="parent-nav">
    <router-link to="/parent" class="brand">
      心愿罐
      <span>家长台</span>
    </router-link>
    <nav class="parent-nav-links" aria-label="家长端导航">
      <router-link to="/parent">看板</router-link>
      <router-link to="/parent/wishes">心愿</router-link>
      <router-link to="/stats">统计</router-link>
      <router-link to="/parent/manage">管理</router-link>
      <span class="nav-logout-group">
        <span class="nav-separator" aria-hidden="true"></span>
        <button type="button" @click="logout">退出</button>
      </span>
    </nav>
  </header>
</template>
