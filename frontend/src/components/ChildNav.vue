<template>
  <Teleport to="body">
    <nav class="bottom-nav" aria-label="孩子端导航">
      <router-link to="/" class="nav-item">
        <span class="nav-icon">🏠</span>
        <span>今天</span>
      </router-link>
      <router-link to="/rewards" class="nav-item">
        <span class="nav-icon">🎁</span>
        <span>心愿</span>
      </router-link>
      <router-link to="/history" class="nav-item">
        <span class="nav-icon">✨</span>
        <span>足迹</span>
      </router-link>
      <router-link to="/me" class="nav-item">
        <span class="nav-icon">🌱</span>
        <span>我的</span>
      </router-link>
    </nav>
  </Teleport>
</template>
