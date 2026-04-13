<template>
  <el-drawer v-model="drawerVisible" :title="`📁 ${serverIp}`" size="560px" direction="rtl">

    <!-- Tabs: 详情 / 文件管理 -->
    <el-tabs v-model="activeTab" class="server-tabs">
      <el-tab-pane label="详情" name="detail">
        <template v-if="detail">
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="IP">{{ detail.ip }}</el-descriptions-item>
            <el-descriptions-item label="系统">{{ detail.os_type }} — {{ detail.os_version || '—' }}</el-descriptions-item>
            <el-descriptions-item label="CPU">{{ detail.cpu_count ?? '—' }} 核</el-descriptions-item>
            <el-descriptions-item label="内存">{{ detail.memory_total ? detail.memory_total + ' MB' : '—' }}</el-descriptions-item>
            <el-descriptions-item label="标签">{{ detail.tags || '—' }}</el-descriptions-item>
            <el-descriptions-item label="备注">{{ detail.description || '—' }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="detail.is_online ? 'success' : 'danger'" size="small">
                {{ detail.is_online ? '在线' : '离线' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="采集时间">{{ detail.cached_at || '从未' }}</el-descriptions-item>
          </el-descriptions>

          <el-divider>网卡</el-divider>
          <el-table v-if="detail.interfaces?.length" :data="detail.interfaces" size="small" max-height="200">
            <el-table-column prop="name" label="网卡" width="100" />
            <el-table-column prop="ip" label="IP" min-width="130" />
            <el-table-column prop="mac" label="MAC" width="150" />
          </el-table>
          <el-empty v-else description="暂无网卡信息" />

          <div class="detail-actions">
            <el-button type="primary" size="small" @click="fetchDetail" :loading="fetchingDetail">
              <el-icon><Refresh /></el-icon> 重新采集
            </el-button>
            <el-button size="small" @click="checkStatus">检测状态</el-button>
            <el-button size="small" @click="openEdit">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteServer">删除</el-button>
          </div>
        </template>
        <el-empty v-else description="加载中…" />
      </el-tab-pane>

      <el-tab-pane label="日志" name="logs">
        <div class="log-toolbar">
          <el-button size="small" @click="loadLogs" :loading="loadingLogs">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
          <el-button size="small" type="danger" @click="clearLogs" :disabled="logs.length === 0">
            清空日志
          </el-button>
        </div>

        <el-table :data="logs" size="small" max-height="400" v-loading="loadingLogs">
          <el-table-column label="时间" width="160">
            <template #default="{ row }">
              {{ formatTime(row.logged_at) }}
            </template>
          </el-table-column>
          <el-table-column label="事件" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="row.event_type === 'status_check' ? 'info' : 'primary'">
                {{ row.event_type === 'status_check' ? '状态' : '详情采集' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="70">
            <template #default="{ row }">
              <el-tag v-if="row.is_online !== null" :type="row.is_online ? 'success' : 'danger'" size="small">
                {{ row.is_online ? '在线' : '离线' }}
              </el-tag>
              <span v-else-if="row.error_message" style="color:#f56c6c;font-size:12px">失败</span>
              <span v-else>—</span>
            </template>
          </el-table-column>
          <el-table-column prop="error_message" label="备注" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.error_message" style="color:#f56c6c">{{ row.error_message }}</span>
              <span v-else-if="row.os_version">{{ row.os_version }}</span>
              <span v-else>—</span>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="logTotal > logs.length" style="text-align:center;margin-top:8px">
          <el-button size="small" @click="loadMoreLogs" :loading="loadingLogs">加载更多</el-button>
        </div>
      </el-tab-pane>

      <el-tab-pane label="文件管理" name="files">
        <!-- Path bar: breadcrumb — click any segment to navigate there -->
        <div class="path-bar">
          <el-button size="small" text @click="navigateRoot" title="回到根目录" class="home-btn">
            <el-icon><House /></el-icon>
          </el-button>
          <el-button size="small" text :disabled="currentPath === '/'" @click="goUp" title="上一级">
            <el-icon><Top /></el-icon>
          </el-button>
          <span class="breadcrumb-sep">/</span>
          <span
            v-for="(seg, i) in pathSegments"
            :key="i"
            class="breadcrumb-seg"
            :class="{ 'last': i === pathSegments.length - 1 }"
            @click="navigateToSeg(i)"
          >{{ seg }}</span>
        </div>

        <!-- File list: double-click to enter/download -->
        <el-table
          :data="entries"
          v-loading="loading"
          size="small"
          class="file-table"
          row-class-name="file-row"
          @row-dblclick="onRowDblClick"
          @row-click="onRowClick"
          @header-dragend="onColumnResize"
          highlight-current-row
          :resizable="true"
        >
          <el-table-column :width="colWidths.icon || 40" min-width="40" label="">
            <template #default="{ row }">
              <el-icon :color="row.type === 'directory' ? '#409eff' : '#909399'" size="18">
                <FolderOpened v-if="row.type === 'directory'" />
                <Document v-else />
              </el-icon>
            </template>
          </el-table-column>
          <el-table-column prop="name" :width="colWidths.name || 260" min-width="120" label="名称">
            <template #default="{ row }">
              <span :class="row.type === 'directory' ? 'dir-name' : 'file-name'">{{ row.name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="大小" :width="colWidths.size || 90" min-width="80" align="right">
            <template #default="{ row }">
              <span v-if="row.type === 'file'" class="file-size">{{ formatSize(row.size) }}</span>
              <span v-else>—</span>
            </template>
          </el-table-column>
        </el-table>

        <!-- Toolbar -->
        <div class="file-toolbar">
          <el-button size="small" @click="refresh">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
          <el-button size="small" type="primary" @click="showUploadDialog">
            <el-icon><Upload /></el-icon> 上传文件
          </el-button>
          <el-button size="small" @click="downloadSelected" :disabled="!selectedFile">
            <el-icon><Download /></el-icon> 下载
          </el-button>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- Upload Dialog -->
    <el-dialog v-model="uploadDialogVisible" title="上传文件" width="440px">
      <el-form>
        <el-form-item label="目标路径">
          <el-input v-model="uploadRemotePath" placeholder="例: /home/user/" />
        </el-form-item>
        <el-form-item label="选择文件">
          <input type="file" @change="onFileSelected" style="width:100%" />
        </el-form-item>
        <el-form-item v-if="uploadFileName" label="文件名">
          <el-tag>{{ uploadFileName }}</el-tag>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="doUpload" :loading="uploading">上传</el-button>
      </template>
    </el-dialog>
  </el-drawer>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  FolderOpened, Document, Refresh, Top, House, Upload, Download
} from '@element-plus/icons-vue'
import { servers as serverApi, files as filesApi, logs as logsApi } from '../api/index.js'

const props = defineProps({ serverId: { type: Number, default: null } })

const drawerVisible = computed({
  get: () => !!props.serverId,
  set: () => emit('close'),
})
const emit = defineEmits(['close', 'server-updated'])

const activeTab = ref('detail')
const detail = ref(null)
const fetchingDetail = ref(false)
const entries = ref([])
const loading = ref(false)
const currentPath = ref('/')
const selectedFile = ref(null)

const pathSegments = computed(() => {
  // "/home/user/dir" → ["home", "user", "dir"] for breadcrumb rendering
  if (!currentPath.value || currentPath.value === '/') return []
  return currentPath.value.split('/').filter(Boolean)
})
const colWidths = ref(loadColWidths())

function loadColWidths() {
  try {
    return JSON.parse(localStorage.getItem('enviroments_file_col_widths') || '{}')
  } catch { return {} }
}

function saveColWidths(w) {
  localStorage.setItem('enviroments_file_col_widths', JSON.stringify(w))
  colWidths.value = w
}

function onColumnResize(nw, col) {
  const key = col.property === null ? 'icon' : col.property
  if (key === 'label' || !key) return
  const widths = { ...colWidths.value }
  if (col.property === 'name') widths.name = nw
  else if (col.property === null) widths.icon = nw
  else if (col.label === '大小') widths.size = nw
  saveColWidths(widths)
}
const uploadDialogVisible = ref(false)
const uploadRemotePath = ref('')
const uploadFileBase64 = ref(null)
const uploadFileName = ref('')
const uploading = ref(false)
const serverIp = ref('')
const logs = ref([])
const loadingLogs = ref(false)
const logOffset = ref(0)
const logTotal = ref(0)

// Load data when serverId changes
watch(() => props.serverId, async (id) => {
  if (!id) return
  detail.value = null
  entries.value = []
  currentPath.value = '/'
  selectedFile.value = null
  activeTab.value = 'detail'
  await loadDetail()
}, { immediate: true })

async function loadDetail() {
  // Use cached data — fast, no SSH. Background scheduler keeps it fresh.
  try {
    const data = await serverApi.get(props.serverId)
    detail.value = data
    serverIp.value = data.hostname || data.ip
  } catch (e) {
    ElMessage.error('加载失败')
  }
}

async function fetchDetail() {
  fetchingDetail.value = true
  try {
    detail.value = await serverApi.fetchDetail(props.serverId)
    ElMessage.success('采集成功')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '采集失败')
  } finally {
    fetchingDetail.value = false
  }
}

async function checkStatus() {
  try {
    const result = await serverApi.checkStatus(props.serverId)
    detail.value.is_online = result.online
    emit('server-updated')
    ElMessage.success(`${detail.value.ip}: ${result.online ? '在线' : '离线'}`)
  } catch {
    ElMessage.error('检测失败')
  }
}

function openEdit() {
  emit('close')
  // Emit event to parent to open edit dialog
  emit('open-edit', props.serverId)
}

async function deleteServer() {
  try {
    await ElMessageBox.confirm('删除该服务器？此操作不可恢复。', '确认删除', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
    await serverApi.delete(props.serverId)
    ElMessage.success('已删除')
    emit('close')
    emit('server-updated')
  } catch {}
}

// ── File Browser ────────────────────────────────────────────────────────────────

async function loadDir(path) {
  if (!props.serverId) return
  loading.value = true
  entries.value = []
  try {
    const data = await filesApi.list(props.serverId, path)
    entries.value = data.entries
    currentPath.value = data.path
    selectedFile.value = null
  } catch (e) {
    ElMessage.error('读取目录失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

function navigateRoot() { loadDir('/') }
function goUp() {
  if (currentPath.value === '/') return
  const parts = currentPath.value.split('/').filter(Boolean)
  parts.pop()
  loadDir(parts.length ? '/' + parts.join('/') : '/')
}

// Click on breadcrumb segment: navigate to that depth (0 = root /)
function navigateToSeg(idx) {
  if (currentPath.value === '/') return
  const parts = currentPath.value.split('/').filter(Boolean)
  // idx 0 = first segment = root child, idx 1 = second segment, etc.
  const target = '/' + parts.slice(0, idx + 1).join('/')
  loadDir(target)
}

function refresh() { loadDir(currentPath.value) }

function onRowClick(row) {
  selectedFile.value = row.type === 'file' ? row : null
}

function onRowDblClick(row) {
  if (row.type === 'directory') {
    loadDir(row.path)
  } else {
    downloadFile(row.path)
  }
}

function downloadFile(path) {
  const url = filesApi.downloadUrl(props.serverId, path)
  const a = document.createElement('a')
  a.href = url
  a.download = path.split('/').pop()
  a.click()
}

function downloadSelected() {
  if (selectedFile.value) downloadFile(selectedFile.value)
}

// Auto-load files tab content when switching to files tab
watch(activeTab, (tab) => {
  if (tab === 'files' && entries.value.length === 0) {
    loadDir('/')
  }
  if (tab === 'logs') {
    logOffset.value = 0
    logs.value = []
    loadLogs()
  }
})

async function loadLogs() {
  if (!props.serverId) return
  loadingLogs.value = true
  try {
    const data = await logsApi.list(props.serverId, 100, logOffset.value)
    if (logOffset.value === 0) {
      logs.value = data.logs
    } else {
      logs.value.push(...data.logs)
    }
    logTotal.value = data.total
    logOffset.value += data.logs.length
  } catch (e) {
    ElMessage.error('加载日志失败')
  } finally {
    loadingLogs.value = false
  }
}

async function loadMoreLogs() {
  await loadLogs()
}

async function clearLogs() {
  try {
    await ElMessageBox.confirm('确定清空该服务器的所有日志？', '确认', { type: 'warning' })
    await logsApi.clear(props.serverId)
    logs.value = []
    logTotal.value = 0
    ElMessage.success('已清空')
  } catch {}
}

function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

function showUploadDialog() {
  uploadRemotePath.value = currentPath.value === '/' ? '/' : currentPath.value + '/'
  uploadFileBase64.value = null
  uploadFileName.value = ''
  uploadDialogVisible.value = true
}

function onFileSelected(e) {
  const file = e.target.files[0]
  if (!file) return
  uploadFileName.value = file.name
  const baseName = file.name.replace(/\\/g, '/').split('/').pop()
  uploadRemotePath.value = (currentPath.value === '/' ? '' : currentPath.value) + '/' + baseName
  const reader = new FileReader()
  reader.onload = (ev) => {
    uploadFileBase64.value = ev.target.result.split(',')[1]
  }
  reader.readAsDataURL(file)
}

async function doUpload() {
  if (!uploadFileBase64.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  uploading.value = true
  try {
    await filesApi.upload(props.serverId, uploadRemotePath.value, uploadFileBase64.value)
    ElMessage.success('上传成功')
    uploadDialogVisible.value = false
    refresh()
  } catch (e) {
    ElMessage.error('上传失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    uploading.value = false
  }
}

function formatSize(bytes) {
  if (bytes == null) return '—'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}
</script>

<style scoped>
.path-bar {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-bottom: 10px;
  padding: 6px 10px;
  background: #f5f7fa;
  border-radius: 6px;
  font-size: 13px;
  flex-wrap: nowrap;
  overflow: hidden;
}
.home-btn { padding: 0 4px; }
.breadcrumb-sep {
  color: #999;
  margin: 0 2px;
  user-select: none;
}
.breadcrumb-seg {
  color: #409eff;
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 4px;
  white-space: nowrap;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.breadcrumb-seg:hover { background: #ecf5ff; text-decoration: underline; }
.breadcrumb-seg.last { color: #333; cursor: default; font-weight: 500; }
.breadcrumb-seg.last:hover { background: none; text-decoration: none; }
.file-table { cursor: pointer; }
.dir-name { color: #409eff; font-weight: 500; }
.file-name { color: #333; }
.file-size { color: #999; font-size: 12px; }
.file-toolbar {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}
.detail-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}
</style>
