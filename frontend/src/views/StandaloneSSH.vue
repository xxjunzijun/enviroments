<template>
  <div class="standalone-ssh">
    <div class="ssh-header">
      <span class="target-label">🖥️ {{ targetLabel }}</span>
      <el-button size="small" @click="goBack">← 返回</el-button>
    </div>
    <WebTerminal
      v-if="ready"
      :target-id="targetId"
      :target-type="targetType"
      :target-label="targetLabel"
      :full-screen="true"
      :model-value="true"
      :host="credentials.host"
      :port="credentials.port"
      :username="credentials.username"
      :password="credentials.password"
    />
    <div v-else class="loading">加载中…</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import WebTerminal from '../components/WebTerminal.vue'

const ready = ref(false)
const credentials = ref({ host: '', port: 22, username: '', password: '' })

// Parse query params from hash URL like #/ssh/server/123/Label
function parseSshRoute() {
  const hash = window.location.hash
  const match = hash.match(/^#\/ssh\/([a-z]+)\/(\d+)(?:\/(.+))?$/)
  if (match) {
    return {
      type: match[1],
      id: Number(match[2]),
      label: decodeURIComponent(match[3] || `${match[1]} #${match[2]}`),
    }
  }
  return { type: 'server', id: 0, label: 'SSH 终端' }
}

const { type: targetType, id: targetId, label: targetLabel } = parseSshRoute()

async function fetchCredentials() {
  const token = localStorage.getItem('token')
  if (!token) return

  const apiBase = `${window.location.protocol}//${window.location.host}`
  const endpoint = targetType === 'switch'
    ? `/api/v1/switches/${targetId}`
    : `/api/v1/servers/${targetId}`

  try {
    const res = await fetch(`${apiBase}${endpoint}`, {
      headers: { 'Authorization': `Bearer ${token}` },
    })
    if (!res.ok) return
    const data = await res.json()
    if (targetType === 'switch') {
      credentials.value = {
        host: data.ip,
        port: data.port || 22,
        username: data.username,
        password: data.password,
      }
    } else {
      credentials.value = {
        host: data.ip,
        port: data.port || 22,
        username: data.ssh_username,
        password: data.ssh_password,
      }
    }
  } catch (e) {
    console.error('Failed to fetch credentials:', e)
  }
  ready.value = true
}

function goBack() {
  window.location.hash = ''
  window.location.href = '/'
}

onMounted(fetchCredentials)
</script>

<style scoped>
.standalone-ssh {
  width: 100vw;
  height: 100vh;
  background: #1e1e1e;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.ssh-header {
  background: #1a1a2e;
  color: #eaeaea;
  padding: 8px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
  height: 44px;
  box-sizing: border-box;
}
.target-label { font-size: 14px; font-weight: 500; }
.loading {
  color: #eaeaea;
  padding: 20px;
  font-size: 14px;
}
</style>
