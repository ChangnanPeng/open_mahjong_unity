<template>
  <el-container class="default-layout">
    <el-header class="layout-header">
      <nav-bar />
    </el-header>

    <el-main class="layout-main">
      <router-view />
    </el-main>

    <el-footer class="layout-footer">
      <app-footer />
    </el-footer>
  </el-container>
</template>

<script setup>
import NavBar from '@/components/NavBar.vue'
import AppFooter from '@/components/AppFooter.vue'
</script>

<style scoped>
.default-layout {
  min-height: 100vh;
  background: #f5f5f5;
}

.layout-header {
  padding: 0;
  height: auto;
  background: transparent;
  position: sticky;
  top: 0;
  z-index: 1000;
}

.layout-main {
  padding: 20px 16px 48px;
  flex: 1;
  max-width: 1100px;
  width: 100%;
  margin: 0 auto;
  box-sizing: border-box;
}

.layout-footer {
  padding: 0;
  height: auto;
}
</style>
