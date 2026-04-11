<template>
  <el-container class="layout">
    <el-header class="header">
      <h2>🖥️ Enviroments — 服务器管理</h2>
    </el-header>
    <el-main>
      <ServerList />
    </el-main>
  </el-container>
</template>

<script setup>
import ServerList from './views/ServerList.vue'
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
}

.header h2 { font-size: 20px; font-weight: 600; }

.el-main { padding: 24px; }
</style>
