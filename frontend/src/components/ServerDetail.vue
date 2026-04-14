<template>
  <el-drawer v-model="drawerVisible" :title="`服务器 ${serverIp}`" size="560px" direction="rtl">

    <!-- Tabs: 详情 / 文件管理 / 日志 -->
    <el-tabs v-model="activeTab" class="server-tabs">

      <!-- ── 详情 ─────────────────────────────────────────────────────────── -->
      <el-tab-pane label="详情" name="detail">
        <template v-if="detail">
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="IP">{{ detail.ip }}</el-descriptions-item>
            <el-descriptions-item label="系统">{{ detail.os_type }} — {{ detail.os_version || '—' }}</el-descriptions-item>
            <el-descriptions-item label="CPU">{{ detail.cpu ?? '—' }} 核{{ detail.cpu_model ? ' / ' + detail.cpu_model : '' }}</el-descriptions-item>
            <el-descriptions-item label="内存">{{ detail.mem ? detail.mem + ' MB' : '—' }}</el-descriptions-item>
            <el-descriptions-item label="标签">{{ detail.tags || '—' }}</el-descriptions-item>
            <el-descriptions-item label="备注">{{ detail.description || '—' }}</el-descriptions-item>
            <el-descriptions-item label="采集时间">{{ detail.cached_at || '—' }}</el-descriptions-item>
          </el-descriptions>

          <el-divider>网卡</el-divider>
          <el-table v-if="detail.interfaces?.length" :data="detail.interfaces" size="small" max-height="200">
            <el-table-column prop="name" label="网卡" width="90" />
            <el-table-column prop="ip" label="IP" min-width="120" />
            <el-table-column prop="mac" label="MAC" width="140" />
            <el-table-column prop="pci_addr" label="PCI 地址" width="110" show-overflow-tooltip />
            <el-table-column prop="pci_desc" label="PCI 设备" min-width="180" show-overflow-tooltip />
            <el-table-column prop="speed" label="速率" width="80" />
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
        <el-empty v-else-if="loadingDetail" description="加载中…" />
        <el-empty v-else description="暂无数据，请点击" />
      </el-tab-pane>

      <!-- ── 文件管理 ──────────────────────────────────────────────────────── -->
      <el-tab-pane label="文件管理" name="files">
        <!-- Path bar: breadcrumb -->
        <div class="path-bar">
          <el-button size="small" text @click="navigateRoot" title="回到根目录">
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
          @row-dblclick="onRowDblClick"
          @row-click="onRowClick"
          highlight-current-row
        >
          <el-table-column width="40">
            <template #default="{ row }">
              <el-icon :color="row.type === 'directory' ? '#409eff' : '#909399'" size="18">
                <FolderOpened v-if="row.type === 'directory'" />
                <Document v-else />
              </el-icon>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="名称" min-width="240">
            <template #default="{ row }">
              <span :class="row.type === 'directory' ? 'dir-name' : 'file-name'">{{ row.name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="大小" width="90" align="right">
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

      <!-- ── 日志 ───────────────────────────────────────────────────────────── -->
      <el-tab-pane label="日志" name="logs">
        <div class="log-toolbar">
          <el-button size="small" @click="loadLogs" :loading="loadingLogs">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
          <el-button size="small" type="danger" @click="clearLogs">
            清空日志
          </el-button>
        </div>

        <div class="log-container" v-loading="loadingLogs">
          <div v-if="logs.length === 0" class="log-empty">暂无日志记录</div>
          <div v-else class="log-list">
            <div v-for="(log, i) in logs" :key="i" class="log-line" :class="logClass(log)">
              <span class="log-time">{{ log.time || '—' }}</span>
              <span class="log-type">{{ log.type === 'status_check' ? '状态' : '详情' }}</span>
              <span class="log-status" :class="log.online ? 'online' : 'offline'">
                {{ log.online === true ? '在线' : log.online === false ? '离线' : '—' }}
              </span>
              <span v-if="log.cpu" class="log-info">CPU {{ log.cpu }}核</span>
              <span v-if="log.mem" class="log-info">内存 {{ log.mem }}MB</span>
              <span v-if="log.os_version" class="log-info">{{ log.os_version }}</span>
              <span v-if="log.error" class="log-error">{{ log.error }}</span>
            </div>
          </div>
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
const loadingDetail = ref(false)
const fetchingDetail = ref(false)
const entries = ref([])
const loading = ref(false)
const currentPath = ref('/')
const selectedFile = ref(null)
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

// ── Detail load ─────────────────────────────────────────────────────────────────

// 模块级缓存：serverId -> { detail, timestamp }
const detailCache = new Map()
const CACHE_TTL = 60_000  // 60 秒

watch(() => props.serverId, async (id) => {
  if (!id) return
  entries.value = []
  currentPath.value = '/'
  selectedFile.value = null
  activeTab.value = 'detail'

  // 优先用缓存（不等待）
  const cached = detailCache.get(id)
  if (cached) {
    detail.value = cached.detail
    serverIp.value = cached.detail.ip
  }

  // 静默后台刷新
  try {
    const data = await serverApi.fetchDetail(id)
    detail.value = data
    serverIp.value = data.ip
    detailCache.set(id, { detail: data, timestamp: Date.now() })
  } catch {
    if (!cached) {
      ElMessage.error('加载失败')
    }
  }
}, { immediate: true })

async function loadDetail() {
  loadingDetail.value = true
  try {
    detail.value = await serverApi.fetchDetail(props.serverId)
    serverIp.value = detail.value.ip
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loadingDetail.value = false
  }
}

async function fetchDetail() {
  fetchingDetail.value = true
  try {
    detail.value = await serverApi.fetchDetail(props.serverId)
    detailCache.set(props.serverId, { detail: detail.value, timestamp: Date.now() })
    ElMessage.success('采集成功')
    if (activeTab.value === 'logs') {
      await loadLogs()
    }
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
    detailCache.set(props.serverId, { detail: detail.value, timestamp: Date.now() })
    emit('server-updated')
    ElMessage.success(`${detail.value.ip}: ${result.online ? '在线' : '离线'}`)
    if (activeTab.value === 'logs') {
      await loadLogs()
    }
  } catch {
    ElMessage.error('检测失败')
  }
}

function openEdit() {
  emit('close')
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

// ── File Browser ─────────────────────────────────────────────────────────────────

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

const pathSegments = computed(() => {
  if (!currentPath.value || currentPath.value === '/') return []
  return currentPath.value.split('/').filter(Boolean)
})

function navigateRoot() { loadDir('/') }
function goUp() {
  if (currentPath.value === '/') return
  const parts = currentPath.value.split('/').filter(Boolean)
  parts.pop()
  loadDir(parts.length ? '/' + parts.join('/') : '/')
}
function navigateToSeg(idx) {
  if (currentPath.value === '/') return
  const parts = currentPath.value.split('/').filter(Boolean)
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

// ── Logs ─────────────────────────────────────────────────────────────────────────

async function loadLogs() {
  if (!props.serverId) return
  loadingLogs.value = true
  logOffset.value = 0
  logs.value = []
  try {
    const data = await logsApi.list(props.serverId, 200, 0)
    logs.value = data.logs
    logTotal.value = data.total
  } catch (e) {
    ElMessage.error('加载日志失败')
  } finally {
    loadingLogs.value = false
  }
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

function logClass(log) {
  if (log.error) return 'log-error-row'
  if (log.online === false) return 'log-offline-row'
  return ''
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
.breadcrumb-sep { color: #999; margin: 0 2px; user-select: none; }
.breadcrumb-seg {
  color: #409eff; cursor: pointer; padding: 2px 4px;
  border-radius: 4px; white-space: nowrap; max-width: 120px;
  overflow: hidden; text-overflow: ellipsis;
}
.breadcrumb-seg:hover { background: #ecf5ff; text-decoration: underline; }
.breadcrumb-seg.last { color: #333; cursor: default; font-weight: 500; }
.breadcrumb-seg.last:hover { background: none; text-decoration: none; }
.file-table { cursor: pointer; }
.dir-name { color: #409eff; font-weight: 500; }
.file-name { color: #333; }
.file-size { color: #999; font-size: 12px; }
.file-toolbar { display: flex; gap: 8px; margin-top: 10px; }
.detail-actions { display: flex; gap: 8px; margin-top: 16px; }

/* Log tab */
.log-toolbar { display: flex; gap: 8px; margin-bottom: 10px; }
.log-container {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  max-height: 400px;
  overflow-y: auto;
}
.log-empty { padding: 24px; text-align: center; color: #999; }
.log-list { font-family: 'Consolas', monospace; font-size: 12px; }
.log-line {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 10px;
  border-bottom: 1px solid #f0f0f0;
  flex-wrap: wrap;
}
.log-line:last-child { border-bottom: none; }
.log-offline-row { background: #fff5f5; }
.log-error-row { background: #fff0f0; }
.log-time { color: #999; white-space: nowrap; }
.log-type { color: #409eff; font-weight: 500; }
.log-status { font-size: 12px; }
.log-status.online { color: #67c23a; }
.log-status.offline { color: #f56c6c; }
.log-info { color: #666; }
.log-error { color: #f56c6c; }
</style>