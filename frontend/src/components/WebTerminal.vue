<template>
  <el-dialog
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
import { Terminal } from 'xterm'
import { FitAddon } from '@xterm/addon-fit'
import { ElMessage } from 'element-plus'
import 'xterm/css/xterm.css'

const props = defineProps({
  modelValue: Boolean,
  targetId: { type: Number, required: true },
  targetType: { type: String, required: true }, // 'server' or 'switch'
  targetLabel: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'closed'])

const terminalRef = ref(null)
const statusText = ref('连接中…')
const statusClass = ref('status-connecting')
const visible = ref(props.modelValue)

let term = null
let fitAddon = null
let ws = null
let pingInterval = null
let resizeObserver = null

watch(() => props.modelValue, async (val) => {
  visible.value = val
  if (val) {
    await nextTick()
    initTerminal()
    connect()
  }
})

watch(visible, (val) => {
  emit('update:modelValue', val)
})

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
  term.open(terminalRef.value)
  fitAddon.fit()

  // Resize on window changes
  resizeObserver = new ResizeObserver(() => {
    if (fitAddon) {
      fitAddon.fit()
      sendResize()
    }
  })
  resizeObserver.observe(terminalRef.value)

  term.onData((data) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'input', data }))
    }
  })

  term.onResize(({ cols, rows }) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'resize', width: cols, height: rows }))
    }
  })
}

function connect() {
  const token = localStorage.getItem('token')
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const url = `${protocol}//${host}/ws/ssh?token=${encodeURIComponent(token)}&target_type=${props.targetType}&target_id=${props.targetId}`

  ws = new WebSocket(url)

  ws.onopen = () => {
    statusText.value = '已连接'
    statusClass.value = 'status-connected'
    // Send initial resize
    sendResize()
    // Heartbeat
    pingInterval = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30000)
  }

  ws.onmessage = (event) => {
    let msg
    try {
      msg = JSON.parse(event.data)
    } catch {
      // Plain text (old servers may send raw)
      term.write(event.data)
      return
    }

    if (msg.type === 'data') {
      term.write(msg.data)
    } else if (msg.type === 'connected') {
      statusText.value = 'SSH 已连接'
      statusClass.value = 'status-connected'
    } else if (msg.type === 'error') {
      statusText.value = `错误: ${msg.data}`
      statusClass.value = 'status-error'
      ElMessage.error(`SSH 连接错误: ${msg.data}`)
    } else if (msg.type === 'pong') {
      // heartbeat ack
    }
  }

  ws.onclose = () => {
    statusText.value = '连接已关闭'
    statusClass.value = 'status-disconnected'
    clearInterval(pingInterval)
    term.write('\r\n\x1b[33m[连接已关闭]\x1b[0m\r\n')
  }

  ws.onerror = (err) => {
    statusText.value = '连接失败'
    statusClass.value = 'status-error'
    console.error('WebSocket error', err)
  }
}

function sendResize() {
  if (!term || !ws) return
  const { cols, rows } = term
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'resize', width: cols, height: rows }))
  }
}

function cleanup() {
  clearInterval(pingInterval)
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
}

function onClosed() {
  cleanup()
  emit('closed')
}

onBeforeUnmount(cleanup)
</script>

<style scoped>
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
/* Global override for terminal dialog width */
.terminal-dialog .el-dialog {
  max-width: 1200px;
  width: 90%;
}
.terminal-dialog .el-dialog__body {
  padding: 12px 20px;
}
</style>
