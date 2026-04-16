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
  targetType: { type: String, required: true },
  targetLabel: { type: String, default: '' },
  fullScreen: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'closed'])

// Expose connect so parent can call it
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

// ── Terminal init ──────────────────────────────────────────────────────────────
function initTerminal() {
  if (term) return
  console.log('[WS SSH] initTerminal: creating Terminal instance')
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

  term.onData((data) => {
    console.log('[WS SSH] onData:', JSON.stringify(data))
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'input', data }))
    }
  })

  term.onResize(({ cols, rows }) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'resize', width: cols, height: rows }))
    }
  })
  console.log('[WS SSH] initTerminal: done')
}

function openTerminal() {
  console.log('[WS SSH] openTerminal: termExists=', !!term, 'refExists=', !!terminalRef.value, 'fullScreen=', props.fullScreen)
  if (!term || !terminalRef.value) {
    console.warn('[WS SSH] openTerminal: skipped — term or ref missing')
    return
  }
  console.log('[WS SSH] openTerminal: calling term.open()')
  term.open(terminalRef.value)
  term.focus()

  // Ensure valid dimensions before resize. proposeDimensions() may return null
  // if the container hasn't been laid out yet (0×0), so use fallback values.
  const fallback = { cols: 200, rows: 40 }
  const proposed = fitAddon?.proposeDimensions()
  const dims = (proposed && proposed.cols > 0 && proposed.rows > 0) ? proposed : fallback
  console.log('[WS SSH] openTerminal: resize to', dims, '(proposed=', proposed, ', fallback=', fallback, ')')
  term.resize(dims.cols, dims.rows)
  fitAddon?.fit()
  console.log('[WS SSH] openTerminal: success, cols=', dims.cols, 'rows=', dims.rows)

  resizeObserver = new ResizeObserver(() => {
    try { fitAddon?.fit() } catch {}
    sendResize()
  })
  resizeObserver.observe(terminalRef.value)
}

// ── WebSocket connect ──────────────────────────────────────────────────────────
function connect() {
  console.log('[WS SSH] connect() called, already connected?', connected)
  if (connected) return

  const token = localStorage.getItem('token')
  if (!token) {
    statusText.value = '未登录'
    statusClass.value = 'status-error'
    return
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const url = `${protocol}//${host}/ws/ssh?token=${encodeURIComponent(token)}&target_type=${props.targetType}&target_id=${props.targetId}`
  console.log('[WS SSH] connecting to:', url)

  ws = new WebSocket(url)

  ws.onopen = () => {
    console.log('[WS SSH] ws.onopen fired')
    statusText.value = '已连接'
    statusClass.value = 'status-connected'
    connected = true
    sendResize()
    pingInterval = setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30000)
  }

  ws.onmessage = (event) => {
    console.log('[WS SSH] ws.onmessage raw:', JSON.stringify(event.data).substring(0, 80))
    let msg
    try {
      msg = JSON.parse(event.data)
      console.log('[WS SSH] ws.onmessage parsed:', msg)
    } catch {
      // Raw string — write directly (shouldn't happen with our JSON protocol)
      console.warn('[WS SSH] ws.onmessage: non-JSON, writing directly to term')
      term?.write(event.data)
      return
    }

    if (msg.type === 'data') {
      console.log('[WS SSH] ws.onmessage: writing', JSON.stringify(msg.data).substring(0, 60), 'to xterm')
      try {
        term?.write(msg.data)
      } catch (e) {
        console.error('[WS SSH] xterm write error:', e)
      }
    } else if (msg.type === 'connected') {
      console.log('[WS SSH] ws.onmessage: connected received')
      statusText.value = 'SSH 已连接'
      statusClass.value = 'status-connected'
    } else if (msg.type === 'error') {
      statusText.value = `错误: ${msg.data}`
      statusClass.value = 'status-error'
      ElMessage.error(`SSH 连接错误: ${msg.data}`)
    } else if (msg.type === 'pong') {
      // heartbeat response — ignore
    }
  }

  ws.onclose = () => {
    console.log('[WS SSH] ws.onclose')
    statusText.value = '连接已关闭'
    statusClass.value = 'status-disconnected'
    connected = false
    clearInterval(pingInterval)
    term?.write('\r\n\x1b[33m[连接已关闭]\x1b[0m\r\n')
  }

  ws.onerror = (err) => {
    console.error('[WS SSH] ws.onerror:', err)
    statusText.value = '连接失败'
    statusClass.value = 'status-error'
    connected = false
  }
}

// ── Resize ─────────────────────────────────────────────────────────────────────
function sendResize() {
  if (!term || !ws || ws.readyState !== WebSocket.OPEN) return
  try {
    const { cols, rows } = term
    ws.send(JSON.stringify({ type: 'resize', width: cols, height: rows }))
  } catch {}
}

// ── Cleanup ────────────────────────────────────────────────────────────────────
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
  console.log('[WS SSH] cleanup done')
}

function onClosed() {
  cleanup()
  emit('closed')
}

// ── Visibility watch ───────────────────────────────────────────────────────────
// For dialog mode: opens terminal + connects when dialog becomes visible
// For full-screen mode (StandaloneSSH): also fires on mount via immediate:true
watch(() => props.modelValue, async (val) => {
  console.log('[WS SSH] modelValue watch:', val, 'fullScreen=', props.fullScreen)
  visible.value = val
  if (!val) {
    cleanup()
    return
  }

  // Wait for DOM to be ready (dialog body to mount)
  await nextTick()
  await nextTick()  // two ticks to be safe for el-dialog
  console.log('[WS SSH] modelValue watch: DOM ready, ref=', !!terminalRef.value)

  initTerminal()
  openTerminal()
  connect()
}, { immediate: true })

watch(visible, (val) => {
  emit('update:modelValue', val)
})

onMounted(() => {
  console.log('[WS SSH] onMounted: fullScreen=', props.fullScreen, 'modelValue=', props.modelValue)
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
