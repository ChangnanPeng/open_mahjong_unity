<template>
  <el-container class="event-admin-layout">
    <el-aside width="220px" class="event-aside">
      <div class="event-brand">赛事管理</div>
      <el-menu :default-active="activeMenu" router class="event-menu">
        <el-menu-item index="/account">返回账户面板</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="event-header">
        <span class="event-user">{{ auth.username }} ({{ auth.userId }})</span>
        <el-button type="danger" link @click="onLogout">退出</el-button>
      </el-header>
      <el-main class="event-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useEventAdminAuthStore } from '@/stores/eventAdminAuth'
import { usePlayerAuthStore } from '@/stores/playerAuth'

const router = useRouter()
const auth = useEventAdminAuthStore()
const playerAuth = usePlayerAuthStore()

const activeMenu = computed(() => '/account')

function onLogout() {
  auth.logout()
  playerAuth.logout()
  router.push('/login?redirect=/account')
}
</script>

<style scoped>
.event-admin-layout {
  min-height: 100vh;
  background: #f5f7fa;
}
.event-aside {
  background: #ffffff;
  color: #303133;
  border-right: 1px solid #e4e7ed;
}
.event-brand {
  padding: 20px 16px;
  font-weight: 600;
  font-size: 16px;
  color: #303133;
  border-bottom: 1px solid #e4e7ed;
}
.event-aside :deep(.event-menu.el-menu) {
  border-right: none;
  background: #ffffff;
}
.event-aside :deep(.el-menu-item) {
  color: #303133;
}
.event-aside :deep(.el-menu-item.is-active) {
  color: #409eff;
  background-color: #ecf5ff;
}
.event-aside :deep(.el-menu-item:hover) {
  color: #409eff;
  background-color: #f5f7fa;
}
.event-header {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
}
.event-user {
  color: #606266;
  font-size: 14px;
}
.event-main {
  padding: 20px;
}
</style>
