<template>
  <div>
    <!-- Toolbar -->
    <div class="toolbar">
      <el-button type="primary" @click="showAddDialog = true">
        <el-icon><Plus /></el-icon> 添加服务器
      </el-button>
      <el-button @click="checkAllStatus" :loading="checkingAll">
        <el-icon><Refresh /></el-icon> 检测全部状态
      </el-button>
    </div>

    <!-- Server Table -->
    <el-table :data="servers" stripe v-loading="loading" class="server-table">
      <el-table-column label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_online ? 'success' : 'danger'" size="small">
            {{ row.is_online ? '在线' : '离线' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="hostname" label="主机名" min-width="160" />
      <el-table-column prop="ip" label="IP 地址" width="160" />
      <el-table-column prop="os_type" label="系统" width="100">
        <template #default="{ row }">
          <el-tag size="small">{{ row.os_type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="cached_os_version" label="系统版本" min-width="160" show-overflow-tooltip />
      <el-table-column prop="tags" label="标签" width="160" show-overflow-tooltip />
      <el-table-column label="操作" width="200" align="center">
        <template #default="{ row }">
          <el-button size="small" @click="checkStatus(row)">检测</el-button>
          <el-button size="small" @click="viewDetail(row)">详情</el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Add/Edit Dialog -->
    <el-dialog v-model="showAddDialog" :title="editing ? '编辑服务器' : '添加服务器'" width="520px">
      <el-form :model="form" label-width="100" ref="formRef">
        <el-form-item label="主机名" required>
          <el-input v-model="form.hostname" placeholder="e.g. web-prod-01" />
        </el-form-item>
        <el-form-item label="IP 地址" required>
          <el-input v-model="form.ip" placeholder="e.g. 192.168.1.10" />
        </el-form-item>
        <el-form-item label="SSH 端口" required>
          <el-input-number v-model="form.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="系统类型" required>
          <el-radio-group v-model="form.os_type">
            <el-radio value="linux">Linux</el-radio>
            <el-radio value="windows">Windows</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="SSH 用户名" required>
          <el-input v-model="form.ssh_username" placeholder="e.g. root" />
        </el-form-item>
        <el-form-item label="SSH 密码">
          <el-input v-model="form.ssh_password" show-password placeholder="留空则使用密钥" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="form.tags" placeholder="e.g. 生产,Web,北京" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.description" type="textarea" rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="saveServer" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- Detail Drawer -->
    <el-drawer v-model="showDetail" title="服务器详情" size="480px" direction="rtl">
      <template v-if="detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="主机名">{{ detail.hostname }}</el-descriptions-item>
          <el-descriptions-item label="IP">{{ detail.ip }}</el-descriptions-item>
          <el-descriptions-item label="系统">{{ detail.os_type }} — {{ detail.os_version }}</el-descriptions-item>
          <el-descriptions-item label="CPU 核心">{{ detail.cpu_count ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="内存">{{ detail.memory_total ? `${detail.memory_total} MB` : '—' }}</el-descriptions-item>
          <el-descriptions-item label="标签">{{ detail.tags || '—' }}</el-descriptions-item>
          <el-descriptions-item label="备注">{{ detail.description || '—' }}</el-descriptions-item>
          <el-descriptions-item label="在线状态">
            <el-tag :type="detail.is_online ? 'success' : 'danger'">
              {{ detail.is_online ? '在线' : '离线' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="最后采集">{{ detail.cached_at || '从未' }}</el-descriptions-item>
        </el-descriptions>

        <el-divider>网卡信息</el-divider>
        <el-table v-if="detail.interfaces?.length" :data="detail.interfaces" size="small">
          <el-table-column prop="name" label="网卡" width="120" />
          <el-table-column prop="ip" label="IP" min-width="140" />
          <el-table-column prop="mac" label="MAC" width="160" />
        </el-table>
        <el-empty v-else description="暂无网卡信息" />

        <div class="detail-actions">
          <el-button type="primary" @click="fetchDetailAgain" :loading="fetchingDetail">
            <el-icon><Refresh /></el-icon> 重新采集
          </el-button>
          <el-button @click="checkStatus(detail)">检测状态</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { servers as serverApi } from '../api/index.js'

const loading = ref(false)
const checkingAll = ref(false)
const showAddDialog = ref(false)
const showDetail = ref(false)
const saving = ref(false)
const fetchingDetail = ref(false)
const servers = ref([])
const detail = ref(null)
const formRef = ref(null)
const editing = ref(null)

const defaultForm = () => ({
  hostname: '',
  ip: '',
  port: 22,
  os_type: 'linux',
  ssh_username: '',
  ssh_password: '',
  ssh_key_file: null,
  description: '',
  tags: '',
})

const form = ref(defaultForm())

async function loadServers() {
  loading.value = true
  try {
    const data = await serverApi.list()
    servers.value = data.servers
  } catch {
    ElMessage.error('加载服务器列表失败')
  } finally {
    loading.value = false
  }
}

async function saveServer() {
  saving.value = true
  try {
    if (editing.value) {
      await serverApi.update(editing.value, form.value)
      ElMessage.success('更新成功')
    } else {
      await serverApi.create(form.value)
      ElMessage.success('添加成功')
    }
    showAddDialog.value = false
    editing.value = null
    form.value = defaultForm()
    await loadServers()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`删除服务器 "${row.hostname}" (${row.ip})？`, '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await serverApi.delete(row.id)
    ElMessage.success('已删除')
    await loadServers()
  } catch {}
}

async function checkStatus(row) {
  try {
    const result = await serverApi.checkStatus(row.id)
    const s = servers.value.find(s => s.id === row.id)
    if (s) {
      s.is_online = result.online
      s.online_checked_at = new Date().toISOString()
    }
    if (detail.value?.id === row.id) {
      detail.value.is_online = result.online
    }
    ElMessage.success(`${row.ip}: ${result.online ? '在线' : '离线'}`)
  } catch (e) {
    ElMessage.error('检测失败')
  }
}

async function checkAllStatus() {
  checkingAll.value = true
  const promises = servers.value.map(s => serverApi.checkStatus(s.id).catch(() => null))
  const results = await Promise.all(promises)
  await loadServers()
  checkingAll.value = false
  const online = results.filter(r => r?.online).length
  ElMessage.info(`检测完成：${online}/${results.length} 在线`)
}

async function viewDetail(row) {
  detail.value = { ...row }
  showDetail.value = true
  await fetchDetailAgain(row.id)
}

async function fetchDetailAgain(id = detail.value?.id) {
  if (!id) return
  fetchingDetail.value = true
  try {
    detail.value = await serverApi.fetchDetail(id)
    const s = servers.value.find(s => s.id === id)
    if (s) Object.assign(s, detail.value)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '采集详情失败')
  } finally {
    fetchingDetail.value = false
  }
}

onMounted(loadServers)
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.server-table {
  border-radius: 8px;
  overflow: hidden;
}

.detail-actions {
  margin-top: 24px;
  display: flex;
  gap: 12px;
}
</style>
