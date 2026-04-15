<template>
  <!-- Standalone SSH terminal (full-screen, hash routed) -->
  <StandaloneSSH
    v-if="sshRoute"
    :target-id="sshRoute.id"
    :target-type="sshRoute.type"
    :target-label="sshRoute.label"
  />
  <!-- Normal app layout -->
  <el-container v-else class="layout">
    <el-header class="header">
      <h2>🖥️ Enviroments</h2>
      <el-tabs v-model="activeTab" class="main-tabs" @tab-change="onTabChange">
        <el-tab-pane label="服务器列表" name="servers" />
        <el-tab-pane label="交换机列表" name="switches" />
      </el-tabs>
      <div class="header-right">
        <el-dropdown trigger="click" @command="handleCommand">
          <span class="user-name">
            👤 {{ username }}
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>
    <el-main>
      <ServerList v-if="activeTab === 'servers'" />
      <SwitchList v-else-if="activeTab === 'switches'" />
    </el-main>
  </el-container>
</template>

<script setup>
import { ref } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import ServerList from './views/ServerList.vue'
import SwitchList from './views/SwitchList.vue'
import StandaloneSSH from './views/StandaloneSSH.vue'

const activeTab = ref('servers')
const username = ref(localStorage.getItem('username') || '')
const sshRoute = ref(null)

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

function onTabChange(tab) {
  activeTab.value = tab
}

function handleCommand(cmd) {
  if (cmd === 'logout') {
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    localStorage.removeItem('user_id')
    window.location.reload()
  }
}

// Init
sshRoute.value = parseHash()
window.addEventListener('hashchange', () => { sshRoute.value = parseHash() })
</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: #f5f7fa;
}

.layout { min-height: 100vh; }

.header {
  background: #1a1a2e;
  color: #eaeaea;
  display: flex;
  align-items: center;
  padding: 0 24px;
  height: 60px;
  gap: 24px;
}

.header h2 { font-size: 20px; font-weight: 600; white-space: nowrap; }

.el-tabs.main-tabs {
  flex: 1;
  --el-color-primary: #409eff;
}
.el-tabs.main-tabs .el-tabs__header { margin: 0; }
.el-tabs.main-tabs .el-tabs__nav-wrap::after { display: none; }
.el-tabs.main-tabs .el-tabs__item {
  color: #8b8b9e !important;
  font-size: 15px;
  height: 60px;
  line-height: 60px;
  padding: 0 16px;
}
.el-tabs.main-tabs :deep(.el-tabs__item.is-active) {
  color: #ffffff !important;
  font-weight: 500;
}
.el-tabs.main-tabs .el-tabs__active-bar {
  background-color: #409eff;
  height: 3px;
}
.el-tabs.main-tabs .el-tabs__nav { height: 60px; }

.header-right { margin-left: auto; }
.user-name {
  color: #aaa;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 4px;
}
.user-name:hover { color: #fff; background: rgba(255,255,255,0.1); }

.el-main { padding: 24px; }
</style>
