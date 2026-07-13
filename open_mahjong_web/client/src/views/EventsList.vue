<template>
  <div class="events-page">
    <div class="sec-h">■ 比赛列表</div>
    <div v-if="loading" class="tip">加载中…</div>
    <div v-else-if="!items.length" class="tip">暂无赛事</div>
    <div v-else class="list">
      <router-link
        v-for="ev in items"
        :key="ev.event_id"
        class="item"
        :to="`/events/${ev.event_id}`"
      >
        <div class="name">{{ ev.name }}</div>
        <div class="meta">
          <span :class="['st', ev.status]">{{ eventStatusLabel(ev.status) }}</span>
          <span>{{ formatDate(ev.created_at) }}</span>
        </div>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import axios from 'axios'
import { eventStatusLabel } from '@/utils/eventMeta'

const items = ref([])
const loading = ref(true)

function formatDate(v) {
  if (!v) return ''
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return String(v)
  return d.toLocaleString('zh-CN', { hour12: false })
}

onMounted(async () => {
  loading.value = true
  try {
    const res = await axios.get('/api/player/events')
    items.value = res.data?.data?.items || []
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.sec-h {
  background: rgba(0, 0, 0, 0.75);
  color: #fff;
  padding: 6px 12px;
  font-size: 13px;
  margin-bottom: 12px;
}
.tip { color: #999; font-size: 13px; }
.list { display: flex; flex-direction: column; gap: 8px; }
.item {
  display: block;
  background: #fff;
  border: 1px solid #e0e0e0;
  padding: 14px 16px;
  text-decoration: none;
  color: inherit;
}
.item:hover { border-color: #409eff; }
.name { font-weight: 700; margin-bottom: 6px; }
.meta { display: flex; gap: 12px; font-size: 12px; color: #888; }
.st.active { color: #067a3a; font-weight: 600; }
.st.registered { color: #606266; }
.st.closed { color: #c45656; }
</style>
