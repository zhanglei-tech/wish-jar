import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from './stores/auth'
import type { MemberOut } from './types'
import ChildHome from './pages/ChildHome.vue'
import ChildWishes from './pages/ChildWishes.vue'
import History from './pages/History.vue'
import Login from './pages/Login.vue'
import ParentDashboard from './pages/ParentDashboard.vue'
import ParentManage from './pages/ParentManage.vue'
import ParentWishes from './pages/ParentWishes.vue'
import Profile from './pages/Profile.vue'
import RewardDetail from './pages/RewardDetail.vue'
import Rewards from './pages/Rewards.vue'
import Setup from './pages/Setup.vue'
import Stats from './pages/Stats.vue'

function homeFor(member: MemberOut) {
  return member.role === 'parent'
    ? { name: 'parent-dashboard' }
    : { name: 'child-home' }
}

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    { path: '/setup', name: 'setup', component: Setup, meta: { public: true } },
    { path: '/login', name: 'login', component: Login, meta: { public: true } },
    { path: '/', name: 'child-home', component: ChildHome },
    { path: '/rewards', name: 'rewards', component: Rewards },
    { path: '/rewards/:id', name: 'reward-detail', component: RewardDetail },
    { path: '/wishes', name: 'child-wishes', component: ChildWishes },
    { path: '/history', name: 'history', component: History },
    { path: '/stats', name: 'stats', component: Stats },
    { path: '/me', name: 'profile', component: Profile },
    {
      path: '/parent',
      name: 'parent-dashboard',
      component: ParentDashboard,
      meta: { parent: true },
    },
    {
      path: '/parent/wishes',
      name: 'parent-wishes',
      component: ParentWishes,
      meta: { parent: true },
    },
    {
      path: '/parent/manage',
      name: 'parent-manage',
      component: ParentManage,
      meta: { parent: true },
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.checked) await auth.bootstrap()

  if (auth.needsSetup && to.name !== 'setup') return { name: 'setup' }
  if (!auth.needsSetup && to.name === 'setup') {
    return auth.member ? homeFor(auth.member) : { name: 'login' }
  }
  if (to.meta.public) return true
  if (!auth.member) return { name: 'login' }
  if (to.meta.parent && auth.member.role !== 'parent') {
    return { name: 'child-home' }
  }
  if (
    auth.member.role === 'parent' &&
    [
      'child-home',
      'rewards',
      'reward-detail',
      'child-wishes',
      'history',
      'profile',
    ].includes(String(to.name))
  ) {
    return { name: 'parent-dashboard' }
  }
  return true
})

export default router
