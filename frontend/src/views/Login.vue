<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-logo">🖥</div>
      <h1 class="login-title">Enviroments</h1>
      <p class="login-sub">服务器与交换机管理平台</p>

      <el-tabs v-model="activeTab" class="auth-tabs">
        <el-tab-pane label="登录" name="login">
          <el-form :model="loginForm" label-width="0" @submit.prevent="doLogin" class="auth-form">
            <el-form-item>
              <el-input v-model="loginForm.username" placeholder="用户名" autocomplete="username" size="large" />
            </el-form-item>
            <el-form-item>
              <el-input v-model="loginForm.password" type="password" placeholder="密码" show-password autocomplete="current-password" size="large" @keyup.enter="doLogin" />
            </el-form-item>
            <el-button type="primary" class="auth-submit" :loading="loading" @click="doLogin">登录</el-button>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="注册" name="register">
          <el-form :model="regForm" label-width="0" @submit.prevent="doRegister" class="auth-form">
            <el-form-item>
              <el-input v-model="regForm.username" placeholder="用户名（2-50字符）" autocomplete="username" size="large" />
            </el-form-item>
            <el-form-item>
              <el-input v-model="regForm.password" type="password" placeholder="密码（至少6位）" show-password autocomplete="new-password" size="large" @keyup.enter="doRegister" />
            </el-form-item>
            <el-button type="primary" class="auth-submit" :loading="loading" @click="doRegister">注册</el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="true" @close="errorMsg=''" style="margin-top:16px" />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const activeTab = ref('login')
const loading = ref(false)
const errorMsg = ref('')

const loginForm = reactive({ username: '', password: '' })
const regForm = reactive({ username: '', password: '' })

async function doLogin() {
  if (!loginForm.username || !loginForm.password) {
    errorMsg.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await axios.post('/api/v1/auth/login', {
      username: loginForm.username,
      password: loginForm.password,
    })
    localStorage.setItem('token', res.data.access_token)
    localStorage.setItem('username', res.data.username)
    localStorage.setItem('user_id', res.data.user_id)
    ElMessage.success(`欢迎，${res.data.username}`)
    window.location.reload()
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || '登录失败'
  } finally {
    loading.value = false
  }
}

async function doRegister() {
  if (!regForm.username || !regForm.password) {
    errorMsg.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await axios.post('/api/v1/auth/register', {
      username: regForm.username,
      password: regForm.password,
    })
    localStorage.setItem('token', res.data.access_token)
    localStorage.setItem('username', res.data.username)
    localStorage.setItem('user_id', res.data.user_id)
    ElMessage.success(`注册成功，欢迎 ${res.data.username}`)
    window.location.reload()
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || '注册失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  background: var(--bg-base);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

.login-page::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -20%;
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, rgba(0, 180, 42, 0.08) 0%, transparent 70%);
  border-radius: 50%;
}

.login-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 40px 36px;
  width: 380px;
  box-shadow: var(--shadow-lg);
  position: relative;
  z-index: 1;
  animation: fadeIn 0.4s ease;
}

.login-logo {
  text-align: center;
  font-size: 36px;
  margin-bottom: 8px;
}

.login-title {
  text-align: center;
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 4px;
  letter-spacing: -0.02em;
}

.login-sub {
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  margin-bottom: 28px;
}

.auth-tabs { margin-top: 8px; }

.auth-form :deep(.el-form-item) { margin-bottom: 14px; }

.auth-form :deep(.el-input__wrapper) {
  border-radius: var(--radius-md) !important;
  padding: 12px 16px !important;
}

.auth-submit {
  width: 100%;
  height: 42px;
  font-size: 15px;
  border-radius: var(--radius-md) !important;
  margin-top: 4px;
}
</style>