<template>
  <!-- Standalone SSH terminal (full-screen, hash routed) -->
  <StandaloneSSH
    v-if="sshRoute"
    :target-id="sshRoute.id"
    :target-type="sshRoute.type"
    :target-label="sshRoute.label"
  />
  <!-- Normal app layout -->
  <div v-else class="app-shell">

    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-logo">
        <span class="logo-icon">🖥</span>
        <span class="logo-text">Enviroments</span>
      </div>

      <nav class="sidebar-nav">
        <button
          class="nav-item"
          :class="{ active: activeTab === 'servers' }"
          @click="activeTab = 'servers'"
        >
          <span class="nav-icon">🖧</span>
          <span>服务器</span>
          <span v-if="serverOnlineCount" class="nav-badge">{{ serverOnlineCount }}</span>
        </button>

        <button
          class="nav-item"
          :class="{ active: activeTab === 'switches' }"
          @click="activeTab = 'switches'"
        >
          <span class="nav-icon">🔌</span>
          <span>交换机</span>
          <span v-if="switchOnlineCount" class="nav-badge">{{ switchOnlineCount }}</span>
        </button>
      </nav>

      <div class="sidebar-footer">
        <div class="user-block">
          <span class="user-avatar">👤</span>
          <div class="user-info">
            <span class="user-name">{{ username }}</span>
            <span class="user-role">管理员</span>
          </div>
          <button class="logout-btn" @click="logout" title="退出登录">⚐</button>
        </div>
      </div>
    </aside>

    <!-- Main -->
    <div class="main-area">
      <!-- Top bar -->
      <header class="topbar">
        <div class="topbar-title">
          <h1>{{ activeTab === 'servers' ? '服务器列表' : '交换机列表' }}</h1>
          <span class="topbar-sub">{{ activeTab === 'servers' ? `共 ${serverTotal} 台` : `共 ${switchTotal} 台` }}</span>
        </div>

        <!-- Stats -->
        <div class="stats-row">
          <div class="stat-chip stat-online">
            <span class="stat-dot"></span>
            <span>在线</span>
            <strong>{{ activeTab === 'servers' ? serverOnlineCount : switchOnlineCount }}</strong>
          </div>
          <div class="stat-chip stat-offline">
            <span class="stat-dot"></span>
            <span>离线</span>
            <strong>{{ activeTab === 'servers' ? serverOfflineCount : switchOfflineCount }}</strong>
          </div>
          <button class="theme-toggle" @click="toggleTheme" :title="isDark ? '切换亮色主题' : '切换暗色主题'">
            {{ isDark ? '☀️' : '🌙' }}
          </button>
        </div>
      </header>

      <!-- Content -->
      <main class="content">
        <div class="fade-in">
          <ServerList
            v-if="activeTab === 'servers'"
            @stats="onServerStats"
          />
          <SwitchList
            v-else-if="activeTab === 'switches'"
            @stats="onSwitchStats"
          />
        </div>
      </main>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import ServerList from './views/ServerList.vue'
import SwitchList from './views/SwitchList.vue'
import StandaloneSSH from './views/StandaloneSSH.vue'

const activeTab = ref('servers')
const username = ref(localStorage.getItem('username') || '')
const sshRoute = ref(null)
const isDark = ref(localStorage.getItem('theme') !== 'light')

// Stats
const serverTotal = ref(0)
const serverOnlineCount = ref(0)
const serverOfflineCount = ref(0)
const switchTotal = ref(0)
const switchOnlineCount = ref(0)
const switchOfflineCount = ref(0)

function onServerStats(stats) {
  serverTotal.value = stats.total || 0
  serverOnlineCount.value = stats.online || 0
  serverOfflineCount.value = stats.offline || 0
}

function onSwitchStats(stats) {
  switchTotal.value = stats.total || 0
  switchOnlineCount.value = stats.online || 0
  switchOfflineCount.value = stats.offline || 0
}

function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('username')
  localStorage.removeItem('user_id')
  window.location.reload()
}

function toggleTheme() {
  isDark.value = !isDark.value
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
  document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
}

function parseHash() {
  const hash = window.location.hash
  const match = hash.match(/^#\/ssh\/([a-z]+)\/(\d+)(?:\/(.+))?$/)
  if (match) {
    return {
      type: match[1],
      id: Number(match[2]),
      label: decodeURIComponent(match[3] || `${match[1]} #${match[2]}`),
    }
  }
  return null
}

sshRoute.value = parseHash()
window.addEventListener('hashchange', () => { sshRoute.value = parseHash() })
</script>

<style>
/* ─── Shell Layout ─────────────────────────────────────────────────────────── */

.app-shell {
  display: flex;
  min-height: 100vh;
  background: var(--bg-base);
}

/* ─── Sidebar ──────────────────────────────────────────────────────────────── */

.sidebar {
  width: 220px;
  min-height: 100vh;
  background: var(--bg-surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 10;
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 18px;
  border-bottom: 1px solid var(--border);
}

.logo-icon { font-size: 22px; }

.logo-text {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.02em;
}

/* Nav */
.sidebar-nav {
  flex: 1;
  padding: 12px 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 14px;
  font-family: inherit;
  transition: var(--transition);
  width: 100%;
  text-align: left;
  position: relative;
}

.nav-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--accent-glow);
  color: var(--accent);
  font-weight: 600;
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: var(--accent);
  border-radius: 0 2px 2px 0;
}

.nav-icon { font-size: 16px; }

.nav-badge {
  margin-left: auto;
  background: var(--accent);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  padding: 1px 7px;
  border-radius: 20px;
}

/* Footer */
.sidebar-footer {
  border-top: 1px solid var(--border);
  padding: 14px;
}

.user-block {
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-avatar { font-size: 22px; }

.user-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.user-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-role {
  font-size: 11px;
  color: var(--text-muted);
}

.logout-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 14px;
  padding: 4px;
  border-radius: 4px;
  transition: var(--transition);
}

.logout-btn:hover { color: var(--offline); background: var(--bg-hover); }

/* ─── Main Area ────────────────────────────────────────────────────────────── */

.main-area {
  margin-left: 220px;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

/* Top bar */
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 28px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-surface);
  position: sticky;
  top: 0;
  z-index: 5;
}

.topbar-title {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.topbar-title h1 {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.topbar-sub {
  font-size: 13px;
  color: var(--text-muted);
}

.stats-row {
  display: flex;
  gap: 10px;
}

.stat-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 20px;
  font-size: 13px;
  color: var(--text-secondary);
  background: var(--bg-card);
  border: 1px solid var(--border);
}

.stat-chip strong { color: var(--text-primary); font-weight: 600; }

.stat-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.stat-online .stat-dot { background: var(--online); box-shadow: 0 0 6px var(--online); }
.stat-offline .stat-dot { background: var(--offline); }

.theme-toggle {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 5px 12px;
  font-size: 16px;
  cursor: pointer;
  transition: var(--transition);
  display: flex;
  align-items: center;
}
.theme-toggle:hover { background: var(--bg-hover); transform: scale(1.05); }

/* Content */
.content {
  padding: 24px 28px;
  overflow-x: hidden;
}
</style>