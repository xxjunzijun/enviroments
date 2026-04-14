# Enviroments

机房服务器与交换机管理工具。

## 技术架构

```
frontend/          Vue 3 + Element Plus + Axios（内置于 exe）
backend/            Python + FastAPI + paramiko + APScheduler
infrastructure/     纯函数 SSH/SFTP 调用，无 FastAPI 依赖
log/                backend/log/{server_id}.log  JSON 行日志
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

**服务器管理**
- 添加/编辑/删除服务器（IP、端口、系统类型、SSH 凭证、标签、备注）
- 在线状态检测（每 5 分钟自动检测，可配置间隔）
- SSH 信息采集（OS 版本、CPU、内存、网卡 — Linux/Windows 双支持）
- 每 30 分钟自动采集详情（可配置间隔）
- cached_info 存最新完整快照（JSON 结构，易扩展新字段）

**文件管理器**
- 通过 SFTP 浏览服务器目录
- 支持上传/下载文件
- breadcrumb 路径导航（点击跳转任意目录）
- 双击目录进入/文件下载

**日志系统**
- JSON 行格式存储在 `backend/log/{server_id}.log`
- 每行格式：`{"time":"2026-04-13 17:00:00","type":"status_check","online":true,"cpu":8,"mem":32768,...}`
- 前端直接展示 JSON 行，无需数据库表结构扩展
- 扩展新采集字段只需改 SSH 采集代码，日志自动容纳

**背景任务调度**
- APScheduler 每 5 分钟检测状态
- APScheduler 每 30 分钟采集详情
- 写入日志文件，不依赖数据库表

**Windows exe 构建**
- GitHub Actions workflow 自动构建
- 下载即用，无需安装 Python

### ❌ 待做

- 交换机管理（Phase 2）
- 拓扑图（谁接哪台交换机哪个端口）

---

## 目录结构

```
enviroments/
├── backend/
│   ├── app/
│   │   ├── api/v1/routers/  servers.py  files.py  logs.py
│   │   ├── core/            database.py  scheduler.py
│   │   ├── models/          server.py
│   │   └── main.py
│   ├── infrastructure/       ssh_client.py  sftp_client.py
│   ├── log/                 JSON-line 日志文件
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── views/   ServerList.vue
│   │   ├── components/  ServerDetail.vue  FileBrowser.vue
│   │   ├── api/    index.js
│   │   └── App.vue
│   └── dist/    已打包静态文件
├── .github/workflows/   build.yml
├── Enviroments.spec     PyInstaller 配置
├── build.bat / build.sh
└── README.md
```

## GitHub

https://github.com/xxjunzijun/enviroments

## 版本标签

| 标签 | 说明 |
|------|------|
| v0.1.0 | MVP：服务器管理 + 文件浏览器 + SSH 信息采集 |
| v0.2.0 | 修复日志路径bug，新增标签行内编辑、搜索栏、detail_fetch日志记录 |
| v0.3.0 | 新增CPU型号列、网卡PCI信息采集（地址/设备描述/速率） |
| v0.4.0 | 新增备注主界面可编辑、BMC IP/账号/密码字段 |

## 开发记录

### v0.4.0 (2026-04-14)
- `Server` 模型新增 `bmc_ip`、`bmc_username`、`bmc_password` 三个字段
- `ServerResponse` 和 `ServerUpdate` schema 同步更新
- 主界面新增"备注"列（直接可编辑）、"BMC IP"、"BMC账号"、"BMC密码"三列（点击行内编辑）
- 添加/编辑服务器弹窗新增 BMC 信息表单
- 数据库通过 `ALTER TABLE` 完成迁移

### v0.3.0 (2026-04-14)
- 新增 `_cpu_model_linux()` 多平台CPU型号采集（device-tree → lscpu → dmidecode → cpuinfo）
- 新增 `_pci_of_interface()` 通过 `lspci -nnk` + sysfs 采集网卡PCI地址、设备描述、速率
- 主界面新增"CPU型号"列，搜索支持CPU型号关键字过滤
- 详情页CPU行显示"核数 / 型号"，网卡表格新增PCI地址/设备/速率三列
- `ServerResponse` 和 `ServerDetailResponse` 新增 `cpu_model` 字段
- `detail_fetch` 日志snapshot同步包含 `cpu_model` 和网卡PCI信息

### v0.2.0 (2026-04-13)
- **Bug修复**：`servers.py` 和 `logs.py` 的日志路径计算错误（3层/4层dirname），统一改为从 `scheduler.py` 导入 `LOG_DIR`
- **Bug修复**：`ServerResponse` 新增 `cached_os_version` 字段，解决主界面系统版本列不显示
- **Bug修复**：日志API分页offset语义错误，前端loadLogs每次重新拉取不再追加
- **功能**：`fetchDetail` 和 `checkStatus` 成功后自动刷新日志tab
- **功能**：标签列改为点击行内编辑（回车或失焦自动保存）
- **功能**：新增搜索栏，支持IP/标签/系统版本/备注关键字实时过滤
- **Bug修复**：`ServerList.vue` 的 `onMounted` import 遗漏导致页面无法渲染