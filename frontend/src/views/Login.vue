<template>
  <div class="login-page">
    <div class="login-card">
      <h1 class="title">🖥️ Enviroments</h1>
      <p class="subtitle">服务器与交换机管理平台</p>

      <el-tabs v-model="activeTab" class="auth-tabs">
        <el-tab-pane label="登录" name="login">
          <el-form :model="loginForm" label-width="60" @submit.prevent="doLogin">
            <el-form-item label="用户名">
              <el-input v-model="loginForm.username" placeholder="输入用户名" autocomplete="username" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input v-model="loginForm.password" type="password" placeholder="输入密码" show-password autocomplete="current-password" @keyup.enter="doLogin" />
            </el-form-item>
            <el-button type="primary" style="width:100%" :loading="loading" @click="doLogin">登录</el-button>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="注册" name="register">
          <el-form :model="regForm" label-width="60" @submit.prevent="doRegister">
            <el-form-item label="用户名">
              <el-input v-model="regForm.username" placeholder="输入用户名（2-50字符）" autocomplete="username" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input v-model="regForm.password" type="password" placeholder="输入密码（至少6位）" show-password autocomplete="new-password" @keyup.enter="doRegister" />
            </el-form-item>
            <el-button type="primary" style="width:100%" :loading="loading" @click="doRegister">注册</el-button>
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
  background: #1a1a2e;
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-card {
  background: #fff;
  border-radius: 12px;
  padding: 40px 36px;
  width: 380px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
}

.title {
  text-align: center;
  font-size: 24px;
  margin-bottom: 4px;
  color: #1a1a2e;
}

.subtitle {
  text-align: center;
  color: #999;
  font-size: 13px;
  margin-bottom: 24px;
}

.auth-tabs { margin-top: 8px; }
</style>
