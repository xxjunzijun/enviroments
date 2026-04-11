# Enviroments

机房服务器与交换机管理工具。

## 快速启动（开发模式）

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
pnpm install
pnpm run dev
```

访问：`http://localhost:3000`

---

## Windows 一键构建（生成 .exe）

### 前置条件

1. **Python 3.10+** — [python.org/downloads](https://python.org/downloads)
2. **Node.js** — [nodejs.org](https://nodejs.org)（仅构建前端时需要）
3. 安装构建工具：

```bash
pip install pyinstaller
npm install -g pnpm
```

### 构建

双击运行 `build.bat`，或命令行：

```cmd
build.bat
```

输出：`dist/Enviroments/Enviroments.exe`

### 使用

直接双击 `Enviroments.exe`，自动打开浏览器访问 `http://localhost:8000`。

---

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

## MVP 功能

- ✅ 服务器列表（增删改查）
- ✅ 在线状态检测（TCP 连接）
- ✅ 详细信息采集（CPU、内存、网卡 — Linux/Windows）
- ✅ 标签管理
- ❌ 交换机管理（后续版本）
