<template>
  <el-container class="layout">
    <el-header class="header">
      <h2>🖥️ Enviroments — 服务器管理</h2>
      <el-tabs v-model="activeTab" class="main-tabs" @tab-change="onTabChange">
        <el-tab-pane label="服务器列表" name="servers" />
        <el-tab-pane label="交换机列表" name="switches" />
      </el-tabs>
    </el-header>
    <el-main>
      <ServerList v-if="activeTab === 'servers'" />
      <SwitchList v-else-if="activeTab === 'switches'" />
    </el-main>
  </el-container>
</template>

<script setup>
import { ref } from 'vue'
import ServerList from './views/ServerList.vue'
import SwitchList from './views/SwitchList.vue'

const activeTab = ref('servers')

function onTabChange(tab) {
  activeTab.value = tab
}
</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: #f5f7fa;
}

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

.main-tabs { flex: 1; }
.main-tabs :deep(.el-tabs__header) { margin: 0; }
.main-tabs :deep(.el-tabs__nav-wrap::after) { display: none; }
.main-tabs :deep(.el-tabs__item) { color: #aaa; font-size: 15px; height: 60px; line-height: 60px; padding: 0 16px; }
.main-tabs :deep(.el-tabs__item.is-active) { color: #fff; font-weight: 500; }
.main-tabs :deep(.el-tabs__active-bar) { background-color: #409eff; height: 3px; }
.main-tabs :deep(.el-tabs__nav) { height: 60px; }

.el-main { padding: 24px; }
</style>
