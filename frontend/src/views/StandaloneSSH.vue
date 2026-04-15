<template>
  <div class="standalone-ssh">
    <div class="ssh-header">
      <span class="target-label">🖥️ {{ targetLabel }}</span>
      <el-button size="small" @click="goBack">← 返回</el-button>
    </div>
    <WebTerminal
      :target-id="targetId"
      :target-type="targetType"
      :target-label="targetLabel"
      :full-screen="true"
      :model-value="true"
    />
  </div>
</template>

<script setup>
import WebTerminal from '../components/WebTerminal.vue'

defineProps({
  targetId: { type: Number, required: true },
  targetType: { type: String, required: true },
  targetLabel: { type: String, default: '' },
})

function goBack() {
  window.location.hash = ''
  window.location.href = '/'
}
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
</style>
