# Enviroments

机房服务器与交换机管理工具。

## 架构

```
frontend/          Vue 3 + Element Plus + Axios
backend/           Python + FastAPI
  app/             API 路由、业务逻辑、数据库模型
  infrastructure/  paramiko SSH（纯函数，与 FastAPI 解耦）
```

## 快速启动

### 后端

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API 地址：`http://localhost:8000`
文档：`http://localhost:8000/docs`

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问：`http://localhost:3000`

（前端已配置代理 `/api` → `localhost:8000`，开发环境无需 CORS 配置。）

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/servers | 列出所有服务器 |
| POST | /api/v1/servers | 添加服务器 |
| GET | /api/v1/servers/:id | 获取服务器信息 |
| PUT | /api/v1/servers/:id | 更新服务器 |
| DELETE | /api/v1/servers/:id | 删除服务器 |
| GET | /api/v1/servers/:id/status | 检测在线状态 |
| GET | /api/v1/servers/:id/detail | 通过 SSH 采集详细信息 |

## 数据模型

```
Server
├── hostname        主机名
├── ip              IP 地址
├── port            SSH 端口
├── os_type         linux | windows
├── ssh_username    SSH 用户名
├── ssh_password    SSH 密码（可选）
├── ssh_key_file    SSH 密钥路径（可选）
├── tags            标签（逗号分隔）
├── description     备注
├── cached_*        最近采集的系统信息
└── is_online       在线状态
```

## MVP 功能

- ✅ 服务器列表（增删改查）
- ✅ 在线状态检测（TCP 连接）
- ✅ 详细信息采集（CPU、内存、网卡 — Linux/Windows）
- ✅ 标签管理
