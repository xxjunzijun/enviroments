# Enviroments

机房服务器与交换机管理工具。

## 技术架构

```
frontend/          Vue 3 + Element Plus + Axios（内置于 exe）
backend/            Python + FastAPI + paramiko + APScheduler
infrastructure/     纯函数 SSH/SFTP 调用，无 FastAPI 依赖
log/                backend/log/{server_id}.log  JSON 行日志
                    backend/log/switch_{id}.log  交换机日志
```

## 快速启动

### 后端（开发）

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 前端（开发）

```bash
cd frontend
pnpm install
pnpm run dev
```

访问：`http://localhost:8000`（前端已内置，无需另开）

---

## 功能清单

### ✅ 已完成

**多用户认证**
- JWT 注册/登录（30天有效），注册开放无限制
- 所有 API 接口 Bearer Token 鉴权
- 前端 Axios interceptor 自动附加 Token，401 自动跳转登录页
- 右上角用户名 + 退出登录，数据共享（所有用户共同编辑同一套服务器/交换机）

**服务器管理**
- 添加/编辑/删除服务器（IP、端口、系统类型、SSH 凭证、BMC 信息、标签、备注）
- 在线状态检测（每 5 分钟自动检测）
- SSH 信息采集（OS 版本、CPU 型号/核数、内存、网卡含 PCI 信息 — Linux/Windows 双支持）
- 每 30 分钟自动采集详情，cached_info 存最新完整快照（JSON 结构，易扩展新字段）
- **使用人占用/释放**：多人协同时标识谁在操作，防重复占用
- 详情页默认读缓存毫秒响应，"重新采集"才走 SSH
- 主界面标签/备注/BMC 三字段独立行内编辑（互不干扰），点击自动聚焦

**交换机管理**
- 交换机 CRUD（名称、IP、端口、用户名、密码、标签、备注）
- 顶部 Tab 切换：服务器列表 / 交换机列表
- **display version 采集**：华为 VRP / H3C Comware / Cisco IOS 自动识别，解析设备型号/运行时间/补丁版本
- SSH 登录后若遇密码变更提示自动回答 N 跳过
- 交换机"关联服务器"弹窗多选
- 服务器列表"关联交换机"列，点击弹窗多选关联

**文件管理器**
- 通过 SFTP 浏览服务器目录
- 支持上传/下载文件
- breadcrumb 路径导航（点击跳转任意目录）
- 双击目录进入/文件下载

**日志系统**
- JSON 行格式存储在 `backend/log/{server_id}.log` 和 `backend/log/switch_{id}.log`
- 前端详情页 Tab 展示，每行显示时间/类型/状态/关键信息
- 支持刷新和清空

**Windows exe 构建**
- GitHub Actions workflow 自动构建
- 下载即用，无需安装 Python

### ❌ 待做

- 拓扑图（服务器网口 ↔ 交换机 ↔ 端口 映射）
- Web SSH 功能（xterm.js + WebSocket，浏览器内嵌终端）

---

## 目录结构

```
enviroments/
├── backend/
│   ├── app/
│   │   ├── api/v1/routers/  servers.py  files.py  logs.py  switches.py  auth.py
│   │   ├── core/             database.py  scheduler.py  auth.py
│   │   ├── models/          server.py  switch.py  user.py
│   │   └── main.py
│   ├── infrastructure/       ssh_client.py  sftp_client.py
│   ├── log/                  JSON-line 日志文件
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── views/            ServerList.vue  SwitchList.vue  Login.vue
│   │   ├── components/       ServerDetail.vue  SwitchDetail.vue
│   │   ├── api/              index.js
│   │   └── App.vue
│   └── dist/                 已打包静态文件
├── .github/workflows/        build.yml
├── Enviroments.spec           PyInstaller 配置
├── build.bat / build.sh
└── README.md
```

## GitHub

https://github.com/xxjunzijun/enviroments

## 版本标签

| 标签 | 说明 |
|------|------|
| v0.7.0 | 多用户JWT认证、使用人占用/释放、BMC三字段独立编辑、display version采集、华为/H3C/Cisco自动识别、SSH密码变更提示自动跳过 |
| v0.6.0 | 交换机管理模块：switches表、server_switches关联表、Tab切换、关联服务器/交换机多选弹窗 |
| v0.5.x | 详情页60秒缓存、表格列宽策略、Chrome自动填充修复、Vue响应式修复 |
| v0.4.0 | 备注主界面可编辑、BMC IP/账号/密码字段 |
| v0.3.0 | CPU型号列、网卡PCI信息采集（地址/设备描述/速率） |
| v0.2.0 | 修复日志路径bug、标签行内编辑、搜索栏 |
| v0.1.0 | MVP：服务器管理 + 文件浏览器 + SSH 信息采集 |

## 开发记录

### v0.7.0 (2026-04-15)
- **多用户认证**：新增 User 模型 + JWT（python-jose + bcrypt），注册登录开放，30天有效
- **服务器使用人**：occupied_by 字段，占用/释放 API，防重复占用
- **BMC 字段**：三列独立编辑互不干扰，点击自动聚焦，密码明文显示
- **交换机 SSH 采集**：新增 `get_switch_info_via_ssh()`，交互式 shell 执行 `display version`
- **华为 VRP 解析**：正确提取 VRP 版本/补丁版本/设备型号/运行时间/主机名（CE6860 等型号）
- **SSH 兼容性**：登录后遇密码变更提示自动发送 N 跳过
- **详情页优化**：默认读 cached_info 毫秒响应，`?refresh=true` 才走 SSH 重新采集
- `SwitchDetail.vue`：与 ServerDetail.vue 结构对齐（详情/日志 Tab）
- 交换机详情页关联服务器显示 IP 列表
- 数据库 ALTER TABLE：switches 加 cached_info/is_online 等列

### v0.6.0 (2026-04-15)
- 新增 `Switch` 模型和 `server_switches` 多对多关联表
- 新增 `switches` API 路由：CRUD + 关联管理
- 顶部 Tab 切换：服务器列表 / 交换机列表
- `SwitchList.vue`：交换机管理完整页面
- 服务器列表新增"关联交换机"列，`el-select` 多选交换机
