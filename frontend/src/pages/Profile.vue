<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NButton, NSpin } from 'naive-ui'
import { useRouter } from 'vue-router'
import { api } from '../api'
import ChildNav from '../components/ChildNav.vue'
import EmptyState from '../components/EmptyState.vue'
import { useAuthStore } from '../stores/auth'
import type { ChildHome } from '../types'

const router = useRouter()
const auth = useAuthStore()
const home = ref<ChildHome | null>(null)
const loading = ref(true)

const levelBadges = computed(
  () => home.value?.badges.filter((badge) => badge.kind === 'level') ?? [],
)
const achievementBadges = computed(
  () => home.value?.badges.filter((badge) => badge.kind === 'achievement') ?? [],
)

onMounted(async () => {
  try {
    home.value = await api.childHome()
  } finally {
    loading.value = false
  }
})

async function logout() {
  await auth.logout()
  await router.replace('/login')
}
</script>

<template>
  <div v-if="loading" class="loading-state">
    <n-spin size="large" />
  </div>

  <main v-else class="child-shell page-enter">
    <header class="child-header">
      <div>
        <p class="eyebrow">MY LITTLE CORNER</p>
        <h1 class="display-title">我的</h1>
        <p class="muted">这里是你的心愿罐小角落。</p>
      </div>
    </header>

    <div v-if="!home">
      <EmptyState emoji="🫙" title="暂时打不开" text="请稍后刷新页面。" />
    </div>

    <template v-else>
      <section class="profile-card">
        <div class="profile-face">{{ home.member.avatar }}</div>
        <h1>{{ home.member.name }}</h1>
        <p>
          {{ home.family_name }} · Lv.{{ home.level }}
          <template v-if="home.next_level_points > 0">
            · 再攒 {{ home.next_level_points }} 分升级
          </template>
        </p>
        <div class="profile-stats">
          <div>
            <strong>{{ home.balance }}</strong>
            <span>总积分</span>
          </div>
          <div>
            <strong>{{ home.available }}</strong>
            <span>可用</span>
          </div>
          <div>
            <strong>{{ home.streak_days }}</strong>
            <span>连续打卡</span>
          </div>
        </div>
      </section>

      <section class="detail-card">
        <div class="panel-head">
          <div>
            <h2>我的徽章</h2>
            <p class="hint">升级和完成目标会留下徽章</p>
          </div>
          <span class="pill amber">{{ home.badges.length }} 枚</span>
        </div>
        <div v-if="home.badges.length === 0" class="muted" style="font-size: 13px">
          还没有徽章。完成目标或攒够积分升级，就会得到第一枚。
        </div>
        <template v-else>
          <div v-if="levelBadges.length" class="badge-group">
            <p class="badge-group-title">等级徽章</p>
            <div class="badge-wall">
              <div v-for="badge in levelBadges" :key="badge.id" class="badge-item">
                <img v-if="badge.image_url" :src="badge.image_url" alt="" />
                <span v-else class="badge-emoji">{{ badge.emoji }}</span>
                <span>{{ badge.name }}</span>
              </div>
            </div>
          </div>
          <div v-if="achievementBadges.length" class="badge-group">
            <p class="badge-group-title">成就徽章</p>
            <div class="badge-wall">
              <div v-for="badge in achievementBadges" :key="badge.id" class="badge-item">
                <img v-if="badge.image_url" :src="badge.image_url" alt="" />
                <span v-else class="badge-emoji">{{ badge.emoji }}</span>
                <span>{{ badge.name }}</span>
              </div>
            </div>
          </div>
        </template>
      </section>

      <section class="detail-card">
        <h2>我的足迹</h2>
        <div class="profile-links">
          <router-link to="/wishes" class="profile-link">
            <span>💌</span>
            <div>
              <strong>我的心愿</strong>
              <small>写下想要的事，等家长看看</small>
            </div>
          </router-link>
          <router-link to="/stats" class="profile-link">
            <span>📊</span>
            <div>
              <strong>成长统计</strong>
              <small>看看这段时间攒下的进步</small>
            </div>
          </router-link>
          <router-link to="/rewards" class="profile-link">
            <span>🎁</span>
            <div>
              <strong>心愿商店</strong>
              <small>挑一个想靠近的愿望</small>
            </div>
          </router-link>
        </div>
      </section>

      <section class="detail-card">
        <h2>关于这个罐子</h2>
        <p class="muted" style="font-size: 13px">
          积分来自完成任务和家长的鼓励。锁定储蓄会先把一部分积分留给长期心愿，但不会让总积分变少。
        </p>
        <div class="wish-meta" style="margin-top: 12px">
          <span class="pill teal">累计获得 {{ home.lifetime_earned }}</span>
          <span class="pill amber">锁定 {{ home.locked }}</span>
          <span class="pill">等级 {{ home.level }}</span>
        </div>
      </section>

      <section class="detail-card">
        <n-button block size="large" @click="logout">退出登录 / 切换账号</n-button>
      </section>
    </template>

    <ChildNav />
  </main>
</template>
