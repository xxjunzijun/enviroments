<template>
  <!-- Full-screen mode (StandaloneSSH passes :full-screen="true") -->
  <div v-if="fullScreen" ref="terminalRef" class="terminal-fullscreen" tabindex="0"></div>

  <!-- Dialog mode (default) -->
  <el-dialog
    v-else
    v-model="visible"
    :title="`🖥️ Web SSH — ${targetLabel}`"
    width="80%"
    :close-on-click-modal="false"
    destroy-on-close
    class="terminal-dialog"
    @closed="onClosed"
  >
    <div ref="terminalRef" class="terminal-container" />
    <template #footer>
      <span class="connection-status" :class="statusClass">{{ statusText }}</span>
      <el-button @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { ElMessage } from 'element-plus'
import '@xterm/xterm/css/xterm.css'

const props = defineProps({
  modelValue: Boolean,
  targetId: { type: Number, required: true },
  targetType: { type: String, required: true },  // 'server' or 'switch'
  targetLabel: { type: String, default: '' },
  fullScreen: { type: Boolean, default: false },
  // SSH credentials — if not passed, fetched from server list
  host: { type: String, default: '' },
  port: { type: Number, default: 22 },
  username: { type: String, default: '' },
  password: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'closed'])

defineExpose({ connect, cleanup })

const terminalRef = ref(null)
const statusText = ref('连接中…')
const statusClass = ref('status-connecting')
const visible = ref(false)

let term = null
let fitAddon = null
let ws = null
let pingInterval = null
let resizeObserver = null
let connected = false
let workerId = null
let encoding = 'utf-8'

// ── Terminal init ──────────────────────────────────────────────────────────────
function initTerminal() {
  if (term) return
  term = new Terminal({
    cursorBlink: true,
    fontSize: 14,
    fontFamily: '"Cascadia Code", "Fira Code", "Consolas", monospace',
    theme: {
      background: '#1e1e1e',
      foreground: '#d4d4d4',
      cursor: '#ffffff',
      selection: { background: '#264f78' },
    },
    rows: 40,
    cols: 200,
  })
  fitAddon = new FitAddon()
  term.loadAddon(fitAddon)

  // WebSocket input -> SSH
  term.onData((data) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ data }))
    }
  })

  // Terminal resize -> SSH pty resize
  term.onResize(({ cols, rows }) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ resize: [cols, rows] }))
    }
  })
}

function openTerminal() {
  if (!term || !terminalRef.value) return
  term.open(terminalRef.value)
  term.focus()

  const fallback = { cols: 200, rows: 40 }
  const proposed = fitAddon?.proposeDimensions()
  const dims = (proposed && proposed.cols > 0 && proposed.rows > 0) ? proposed : fallback
  term.resize(dims.cols, dims.rows)
  fitAddon?.fit()

  resizeObserver = new ResizeObserver(() => {
    try { fitAddon?.fit() } catch {}
    sendResize()
  })
  resizeObserver.observe(terminalRef.value)
}

function sendResize() {
  if (!term || !ws || ws.readyState !== WebSocket.OPEN) return
  try {
    ws.send(JSON.stringify({ resize: [term.cols, term.rows] }))
  } catch {}
}

// ── Step 1: POST /api/v1/terminal/connect ──────────────────────────────────────
async function createSession() {
  const token = localStorage.getItem('token')
  if (!token) throw new Error('未登录')

  const apiBase = getApiBase()
  const params = new URLSearchParams({
    host: props.host,
    port: props.port,
    username: props.username,
    password: props.password || '',
    term: 'xterm',
  })

  const res = await fetch(`${apiBase}/api/v1/terminal/connect?${params}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: '',
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || '连接失败')
  }

  const data = await res.json()
  return data  // { id, encoding }
}

function getApiBase() {
  return `${window.location.protocol}//${window.location.host}`
}

// ── Step 2: WebSocket /api/v1/terminal/ws?id=<id> ─────────────────────────────
function connectWs(id) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const url = `${protocol}//${host}/api/v1/terminal/ws?id=${encodeURIComponent(id)}`
  ws = new WebSocket(url)

  ws.onopen = () => {
    statusText.value = 'SSH 已连接'
    statusClass.value = 'status-connected'
    connected = true
    sendResize()
    pingInterval = setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ data: '' }))  // keep-alive (or use ping if supported)
      }
    }, 30000)
  }

  // xterm.js accepts Uint8Array, ArrayBuffer, and strings
  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      if (msg.data) {
        // msg.data is raw bytes from SSH — write directly
        if (typeof msg.data === 'string') {
          term?.write(msg.data)
        } else {
          // Could be base64 or ArrayBuffer — if string base64 decode
          term?.write(msg.data)
        }
      }
      if (msg.type === 'error') {
        statusText.value = `错误: ${msg.data}`
        statusClass.value = 'status-error'
        ElMessage.error(`SSH 错误: ${msg.data}`)
      }
    } catch {
      // Binary frame — write as-is
      term?.write(event.data)
    }
  }

  ws.onclose = (e) => {
    statusText.value = '连接已关闭'
    statusClass.value = 'status-disconnected'
    connected = false
    clearInterval(pingInterval)
    term?.write('\r\n\x1b[33m[连接已关闭]\x1b[0m\r\n')
  }

  ws.onerror = () => {
    statusText.value = '连接失败'
    statusClass.value = 'status-error'
    connected = false
  }
}

// ── Combined connect ────────────────────────────────────────────────────────────
async function connect() {
  if (connected) return
  statusText.value = '连接中…'
  statusClass.value = 'status-connecting'

  try {
    // Step 1: Create session
    const { id, encoding: enc } = await createSession()
    workerId = id
    encoding = enc || 'utf-8'

    // Step 2: Open WebSocket
    connectWs(workerId)
  } catch (e) {
    statusText.value = `连接失败: ${e.message}`
    statusClass.value = 'status-error'
    ElMessage.error(e.message)
  }
}

// ── Cleanup ─────────────────────────────────────────────────────────────────────
function cleanup() {
  clearInterval(pingInterval)
  pingInterval = null
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (ws) {
    ws.close()
    ws = null
  }
  if (term) {
    term.dispose()
    term = null
  }
  connected = false
  workerId = null
}

function onClosed() {
  cleanup()
  emit('closed')
}

// ── Visibility watch ───────────────────────────────────────────────────────────
watch(() => props.modelValue, async (val) => {
  visible.value = val
  if (!val) {
    cleanup()
    return
  }

  await nextTick()
  await nextTick()

  initTerminal()
  openTerminal()
  connect()
}, { immediate: true })

watch(visible, (val) => {
  emit('update:modelValue', val)
})

onMounted(() => {
  // full-screen mode: connect immediately on mount
  if (props.fullScreen && props.modelValue) {
    nextTick(() => {
      initTerminal()
      openTerminal()
      connect()
    })
  }
})

onBeforeUnmount(cleanup)
</script>

<style scoped>
.terminal-fullscreen {
  width: 100%;
  height: 100%;
  background: #1e1e1e;
  padding: 8px;
  box-sizing: border-box;
}

.terminal-container {
  background: #1e1e1e;
  height: 60vh;
  min-height: 400px;
  padding: 8px;
  border-radius: 6px;
  overflow: hidden;
}

.connection-status {
  font-size: 13px;
  margin-right: auto;
}
.status-connecting { color: #e6a23c; }
.status-connected { color: #67c23a; }
.status-error { color: #f56c6c; }
.status-disconnected { color: #909399; }
</style>

<style>
.terminal-dialog .el-dialog {
  max-width: 1200px;
  width: 90%;
}
.terminal-dialog .el-dialog__body {
  padding: 12px 20px;
}
</style>
