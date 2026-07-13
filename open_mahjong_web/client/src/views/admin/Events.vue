<template>
  <div>
    <h2 class="page-title">赛事管理</h2>

    <el-card>
      <template #header>创建赛事</template>
      <p class="hint">创建后为「已注册」状态，需赛事主管理员自行开启后方可建房。</p>
      <el-form inline class="admin-inline-form" @submit.prevent="createEvent">
        <el-form-item label="赛事名称">
          <el-input v-model="createForm.name" clearable style="width: 220px" placeholder="如 2026春季赛" />
        </el-form-item>
        <el-form-item label="主管理员 ID">
          <el-input
            v-model="createForm.owner_user_id"
            clearable
            style="width: 160px"
            placeholder="可选，稍后指定"
          />
        </el-form-item>
        <el-form-item label="操作原因">
          <el-input v-model="createForm.reason" clearable style="width: 180px" placeholder="审计必填" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="creating" @click="createEvent">创建</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card style="margin-top: 16px">
      <template #header>
        <div class="list-header">
          <span>赛事列表</span>
          <el-radio-group v-model="statusFilter" size="small" @change="load">
            <el-radio-button value="">全部</el-radio-button>
            <el-radio-button value="registered">已注册</el-radio-button>
            <el-radio-button value="active">已开启</el-radio-button>
            <el-radio-button value="closed">已关闭</el-radio-button>
            <el-radio-button value="reopen">待审再开</el-radio-button>
          </el-radio-group>
        </div>
      </template>

      <el-table :data="items" v-loading="loading" size="small">
        <el-table-column prop="name" label="赛事名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="event_id" label="赛事 ID" min-width="140" />
        <el-table-column label="状态" width="140">
          <template #default="{ row }">
            <el-tag :type="eventStatusTagType(row.status)" size="small">
              {{ eventStatusLabel(row.status) }}
            </el-tag>
            <el-tag v-if="row.reopen_requested" type="warning" size="small" style="margin-left: 4px">
              待再开
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="赛事主管理员" min-width="140">
          <template #default="{ row }">
            <template v-if="row.owner_user_id">
              {{ row.owner_username || '-' }}
              <span class="uid">({{ row.owner_user_id }})</span>
            </template>
            <span v-else class="muted">未指定</span>
          </template>
        </el-table-column>
        <el-table-column prop="admin_count" label="子管理员" width="90" />
        <el-table-column prop="record_count" label="牌谱数" width="80" />
        <el-table-column label="创建时间" min-width="160">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="$router.push(`/admin/events/${row.event_id}`)">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import adminApi from '@/api/adminClient'
import { eventStatusLabel, eventStatusTagType } from '@/utils/eventMeta'

const router = useRouter()
const items = ref([])
const loading = ref(false)
const creating = ref(false)
const statusFilter = ref('')
const createForm = reactive({
  name: '',
  owner_user_id: '',
  reason: '',
})

function formatDate(v) {
  return v ? new Date(v).toLocaleString('zh-CN') : '-'
}

async function load() {
  loading.value = true
  try {
    const params = {}
    if (statusFilter.value === 'reopen') {
      params.reopen_requested = '1'
      params.status = 'closed'
    } else if (statusFilter.value) {
      params.status = statusFilter.value
    }
    const res = await adminApi.get('/events', { params })
    items.value = res.data.data.items
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function createEvent() {
  if (!createForm.name.trim()) {
    ElMessage.warning('请填写赛事名称')
    return
  }
  if (!createForm.reason.trim()) {
    ElMessage.warning('请填写操作原因')
    return
  }
  creating.value = true
  try {
    const body = {
      name: createForm.name.trim(),
      reason: createForm.reason.trim(),
    }
    if (createForm.owner_user_id.trim()) {
      body.owner_user_id = createForm.owner_user_id.trim()
    }
    const res = await adminApi.post('/events', body)
    ElMessage.success('赛事已创建（已注册，待开启）')
    createForm.name = ''
    createForm.owner_user_id = ''
    createForm.reason = ''
    const id = res.data.data.event_id
    if (id) {
      router.push(`/admin/events/${id}`)
    } else {
      await load()
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '创建失败')
  } finally {
    creating.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: #909399;
}
.uid {
  color: #909399;
  font-size: 12px;
}
.muted {
  color: #909399;
}
</style>
