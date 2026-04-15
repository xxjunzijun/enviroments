<template>
  <div style="overflow-x: auto">

    <!-- Toolbar -->
    <div class="toolbar">
      <el-input
        v-model="searchQuery"
        placeholder="搜索 IP / 标签 / 系统版本 / 备注…"
        style="width: 260px"
        clearable
        :prefix-icon="Search"
        autocomplete="off"
      />
      <el-button type="primary" @click="openAdd">
        <el-icon><Plus /></el-icon> 添加服务器
      </el-button>
      <el-button @click="checkAllStatus" :loading="checkingAll">
        <el-icon><Refresh /></el-icon> 检测全部状态
      </el-button>
    </div>

    <!-- Server Table -->
    <el-table :data="filteredServers" stripe border v-loading="loading" class="server-table" style="width: 100%; table-layout: fixed; overflow-x: auto">
      <el-table-column label="状态" min-width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_online ? 'success' : 'danger'" size="small">
            {{ row.is_online ? '在线' : '离线' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="ip" label="IP 地址" min-width="160" />
      <el-table-column prop="os_type" label="系统" min-width="100">
        <template #default="{ row }">
          <el-tag size="small">{{ row.os_type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="cached_os_version" label="系统版本" min-width="160" show-overflow-tooltip />
      <el-table-column prop="cached_cpu_model" label="CPU 型号" min-width="180" show-overflow-tooltip />
      <el-table-column prop="tags" label="标签" min-width="160">
        <template #default="{ row }">
          <template v-if="editingTagsId === row.id">
            <el-input
              v-model="editingTagsValue"
              size="small"
              style="width: 140px"
              @keyup.enter="saveTags(row.id)"
              @blur="saveTags(row.id)"
              ref="tagsInputRef"
              placeholder="多个标签用逗号分隔" autocomplete="off"
            />
          </template>
          <template v-else>
            <span class="tags-cell" @mousedown.prevent="startEditTags(row)" title="点击编辑标签">{{ row.tags || '—' }}</span>
          </template>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="备注" min-width="120">
        <template #default="{ row }">
          <template v-if="editingDescId === row.id">
            <el-input
              v-model="editingDescValue"
              size="small"
              style="width: 100px"
              @keyup.enter="saveDesc(row.id)"
              @blur="saveDesc(row.id)"
              placeholder="备注" autocomplete="off"
            />
          </template>
          <template v-else>
            <span class="tags-cell" @mousedown.prevent="startEditDesc(row)" title="点击编辑备注">{{ row.description || '—' }}</span>
          </template>
        </template>
      </el-table-column>
      <el-table-column label="BMC IP" min-width="140">
        <template #default="{ row }">
          <template v-if="editingBmcId === row.id && editingBmcField === 'bmc_ip'">
            <el-input v-model="editingBmcValue" size="small" style="width: 120px" @keyup.enter="saveBmc(row.id)" @blur="saveBmc(row.id)" placeholder="BMC IP" autocomplete="off" />
          </template>
          <template v-else>
            <span class="tags-cell" @mousedown.prevent="startEditBmc($event, row, 'bmc_ip')" title="点击编辑BMC">{{ row.bmc_ip || '—' }}</span>
          </template>
        </template>
      </el-table-column>
      <el-table-column label="BMC 账号" min-width="120">
        <template #default="{ row }">
          <template v-if="editingBmcId === row.id && editingBmcField === 'bmc_username'">
            <el-input v-model="editingBmcValue" size="small" style="width: 100px" @keyup.enter="saveBmc(row.id)" @blur="saveBmc(row.id)" placeholder="用户名" autocomplete="off" />
          </template>
          <template v-else>
            <span class="tags-cell" @mousedown.prevent="startEditBmc($event, row, 'bmc_username')">{{ row.bmc_username || '—' }}</span>
          </template>
        </template>
      </el-table-column>
      <el-table-column label="BMC 密码" min-width="120">
        <template #default="{ row }">
          <template v-if="editingBmcId === row.id && editingBmcField === 'bmc_password'">
            <el-input v-model="editingBmcValue" size="small" style="width: 100px" @keyup.enter="saveBmc(row.id)" @blur="saveBmc(row.id)" placeholder="密码" autocomplete="off" />
          </template>
          <template v-else>
            <span class="tags-cell" @mousedown.prevent="startEditBmc($event, row, 'bmc_password')">{{ row.bmc_password || '—' }}</span>
          </template>
        </template>
      </el-table-column>
      <el-table-column label="使用人" min-width="120" align="center">
        <template #default="{ row }">
          <span v-if="row.occupied_by" class="occupied-by" @click="handleRelease(row)">
            {{ row.occupied_by }}
          </span>
          <el-link v-else type="primary" @click="handleOccupy(row)">占用</el-link>
        </template>
      </el-table-column>
      <el-table-column label="关联交换机" min-width="120" align="center">
        <template #default="{ row }">
          <el-link type="primary" @click="openAssocDialog(row)">{{ row.assoc_switch_count ?? '—' }}</el-link>
        </template>
      </el-table-column>
      <el-table-column label="操作" min-width="240" align="center">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="openDetail(row)">查看详情</el-button>
          <el-button size="small" @click="openTerminal(row)">Web SSH</el-button>
          <el-button size="small" @click="openTerminalNewWindow(row)">新窗口</el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Add/Edit Dialog -->
    <el-dialog v-model="showAddDialog" :title="editing ? '编辑服务器' : '添加服务器'" width="520px">
      <el-form :model="form" label-width="100" ref="formRef">
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
        <el-form-item label="BMC IP">
          <el-input v-model="form.bmc_ip" placeholder="e.g. 192.168.5.1" />
        </el-form-item>
        <el-form-item label="BMC 用户名">
          <el-input v-model="form.bmc_username" placeholder="e.g. admin" />
        </el-form-item>
        <el-form-item label="BMC 密码">
          <el-input v-model="form.bmc_password" placeholder="BMC 密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="saveServer" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- Detail Drawer -->
    <ServerDetail :serverId="activeServerId" @close="activeServerId = null" @server-updated="loadServers" @open-edit="openEditById" />

    <!-- Assoc Dialog -->
    <el-dialog v-model="showAssocDialog" :title="`关联交换机 — ${assocTargetServer?.ip}`" width="480px">
      <el-select v-model="selectedSwitchIds" multiple placeholder="选择关联的交换机" style="width: 100%">
        <el-option v-for="sw in allSwitches" :key="sw.id" :label="`${sw.name} (${sw.ip})`" :value="sw.id" />
      </el-select>
      <template #footer>
        <el-button @click="showAssocDialog = false">取消</el-button>
        <el-button type="primary" @click="saveAssoc" :loading="savingAssoc">保存</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'
import { servers as serverApi, switches as switchApi, serverSwitchAssoc } from '../api/index.js'
import ServerDetail from '../components/ServerDetail.vue'

const loading = ref(false)
const showAssocDialog = ref(false)
const savingAssoc = ref(false)
const assocTargetServer = ref(null)
const selectedSwitchIds = ref([])
const allSwitches = ref([])
const checkingAll = ref(false)
const showAddDialog = ref(false)
const servers = ref([])
const editing = ref(null)
const saving = ref(false)
const activeServerId = ref(null)
const searchQuery = ref('')

const filteredServers = computed(() => {
  if (!searchQuery.value.trim()) return servers.value
  const q = searchQuery.value.trim().toLowerCase()
  return servers.value.filter(s =>
    s.ip?.toLowerCase().includes(q) ||
    s.tags?.toLowerCase().includes(q) ||
    s.cached_os_version?.toLowerCase().includes(q) ||
    s.cached_cpu_model?.toLowerCase().includes(q) ||
    s.description?.toLowerCase().includes(q)
  )
})

const defaultForm = () => ({
  ip: '',
  port: 22,
  os_type: 'linux',
  ssh_username: '',
  ssh_password: '',
  ssh_key_file: null,
  description: '',
  tags: '',
  bmc_ip: '',
  bmc_username: '',
  bmc_password: '',
})

const form = ref(defaultForm())
const formRef = ref(null)
const editingTagsId = ref(null)
const editingTagsValue = ref('')
const tagsInputRef = ref(null)
const editingDescId = ref(null)
const editingDescValue = ref('')
const descInputRef = ref(null)
const editingBmcId = ref(null)
const editingBmcValue = ref('')
const editingBmcField = ref(null)

const bmcInputRef = ref(null)

function startEditDesc(row) {
  editingDescId.value = row.id
  editingDescValue.value = row.description || ''
  nextTick(() => descInputRef.value?.focus())
}

async function saveDesc(id) {
  if (editingDescId.value !== id) return
  const idx = servers.value.findIndex(s => s.id === id)
  if (idx === -1) return
  try {
    await serverApi.update(id, { description: editingDescValue.value })
    servers.value[idx] = { ...servers.value[idx], description: editingDescValue.value }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存备注失败')
  } finally {
    editingDescId.value = null
  }
}

function startEditBmc(event, row, field) {
  editingBmcId.value = row.id
  editingBmcField.value = field
  editingBmcValue.value = row[field] || ''
  nextTick(() => {
    // 通过事件 target 往上找到该行 tr，再聚焦对应列的输入框
    const tr = event.target.closest('.el-table__body tr')
    if (!tr) return
    const ph = field === 'bmc_ip' ? 'BMC IP' : field === 'bmc_username' ? '用户名' : '密码'
    tr.querySelector(`[placeholder="${ph}"]`)?.focus()
  })
}

async function saveBmc(id) {
  if (editingBmcId.value !== id) return
  const idx = servers.value.findIndex(s => s.id === id)
  if (idx === -1) return
  const field = editingBmcField.value
  if (!field) return
  try {
    await serverApi.update(id, { [field]: editingBmcValue.value })
    // 只更新对应字段，确保响应式
    servers.value[idx] = { ...servers.value[idx], [field]: editingBmcValue.value }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存BMC信息失败')
  } finally {
    editingBmcId.value = null
    editingBmcField.value = null
  }
}

function startEditTags(row) {
  editingTagsId.value = row.id
  editingTagsValue.value = row.tags || ''
  nextTick(() => tagsInputRef.value?.focus())
}

async function saveTags(id) {
  if (editingTagsId.value !== id) return
  const server = servers.value.find(s => s.id === id)
  if (!server) return
  try {
    await serverApi.update(id, { tags: editingTagsValue.value })
    server.tags = editingTagsValue.value
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存标签失败')
  } finally {
    editingTagsId.value = null
  }
}

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

function openDetail(row) {
  activeServerId.value = row.id
}

function openTerminal(row) {
  const label = encodeURIComponent(row.ip)
  window.open(`/#/ssh/server/${row.id}/${label}`, '_blank')
}

function openAdd() {
  editing.value = null
  form.value = defaultForm()
  showAddDialog.value = true
}

function openEditById(id) {
  openEdit(servers.value.find(s => s.id === id))
}

function openEdit(row) {
  editing.value = row.id
  form.value = {
    ip: row.ip,
    port: row.port,
    os_type: row.os_type,
    ssh_username: row.ssh_username,
    ssh_password: row.ssh_password,
    ssh_key_file: row.ssh_key_file,
    description: row.description || '',
    tags: row.tags || '',
    bmc_ip: row.bmc_ip || '',
    bmc_username: row.bmc_username || '',
    bmc_password: row.bmc_password || '',
  }
  showAddDialog.value = true
}

async function saveServer() {
  saving.value = true
  try {
    if (editing.value) {
      await serverApi.update(editing.value, form.value)
      ElMessage.success('更新成功')
      showAddDialog.value = false
      editing.value = null
      form.value = defaultForm()
      await loadServers()
    } else {
      const created = await serverApi.create(form.value)
      ElMessage.success('添加成功')
      showAddDialog.value = false
      form.value = defaultForm()
      await loadServers()
      openDetail({ id: created.id })
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      `删除服务器 "${row.ip}"？`,
      '确认删除',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    await serverApi.delete(row.id)
    ElMessage.success('已删除')
    if (activeServerId.value === row.id) activeServerId.value = null
    await loadServers()
  } catch {}
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

async function handleOccupy(row) {
  try {
    const updated = await serverApi.occupy(row.id)
    const idx = servers.value.findIndex(s => s.id === row.id)
    if (idx !== -1) servers.value[idx] = { ...servers.value[idx], occupied_by: updated.occupied_by }
    ElMessage.success(`已占用 ${row.ip}`)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '占用失败')
  }
}

async function handleRelease(row) {
  try {
    await ElMessageBox.confirm(`确定释放服务器 "${row.ip}" 吗？`, '确认释放', { type: 'warning' })
    const updated = await serverApi.release(row.id)
    const idx = servers.value.findIndex(s => s.id === row.id)
    if (idx !== -1) servers.value[idx] = { ...servers.value[idx], occupied_by: updated.occupied_by }
    ElMessage.success('已释放')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '释放失败')
  }
}

async function openAssocDialog(row) {
  assocTargetServer.value = row
  selectedSwitchIds.value = []
  showAssocDialog.value = true
  try {
    const [assocData, allSwitchData] = await Promise.all([
      serverSwitchAssoc.get(row.id),
      switchApi.list(),
    ])
    selectedSwitchIds.value = (assocData.switches || []).map(s => s.id)
    allSwitches.value = allSwitchData.switches || []
  } catch (e) {
    ElMessage.error('加载交换机列表失败')
  }
}

async function saveAssoc() {
  if (!assocTargetServer.value) return
  savingAssoc.value = true
  try {
    await serverSwitchAssoc.set(assocTargetServer.value.id, selectedSwitchIds.value)
    const idx = servers.value.findIndex(s => s.id === assocTargetServer.value.id)
    if (idx !== -1) {
      servers.value[idx] = { ...servers.value[idx], assoc_switch_count: selectedSwitchIds.value.length }
    }
    ElMessage.success('关联已保存')
    showAssocDialog.value = false
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存关联失败')
  } finally {
    savingAssoc.value = false
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

.tags-cell {
  cursor: pointer;
  color: #606266;
  padding: 2px 6px;
  border-radius: 4px;
  transition: background 0.2s;
}
.tags-cell:hover {
  background: #f0f9eb;
  color: #67c23a;
}

.occupied-by {
  color: #e6a23c;
  font-weight: 500;
  cursor: pointer;
}
.occupied-by:hover { text-decoration: underline; }
</style>