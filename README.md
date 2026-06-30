# 🐹 A股模拟短线交易训练器

一个基于 AI 的 A 股模拟短线交易系统。设定初始资金后，系统自动完成选股、买卖、仓位管理和风险控制，你只需要打开浏览器查看交易情况。

> ⚠️ 本项目仅用于学习和模拟交易训练，不构成任何投资建议。

## ✨ 功能特性

- **🤖 AI 自动交易** — 基于大模型（DeepSeek/阿里百炼/小米Mimo等）的综合决策引擎，一次调用同时判断持仓操作和新股开仓
- **📊 实时行情** — 使用 akshare 获取 A 股实时数据，支持技术指标分析
- **🎯 智能选股** — 多维度评分系统（量价、均线、趋势等），自动筛选最优标的
- **🛡️ 风险控制** — 自动止盈止损、移动止损、单笔风险控制、最大持仓限制
- **🐹 交易宠物** — 可爱的仓鼠宠物，根据交易盈亏变换心情和台词
- **📈 完整记录** — 交易历史、决策日志、净值曲线、实时运行日志
- **⏰ 交易时间感知** — 非交易时间自动跳过 AI 调用，节省 token

## 🚀 快速开始

### 环境要求

- Python 3.9+
- 一个兼容 OpenAI 格式的 API Key（DeepSeek、阿里百炼、小米Mimo、OpenAI 等）

### 1. 克隆项目

```bash
git clone https://github.com/yourname/a-share-sim-trader.git
cd a-share-sim-trader
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置 API Key

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 API Key：

```env
# DeepSeek 官方
DEEPSEEK_API_KEY=你的API密钥
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# 或者使用小米 Mimo
DEEPSEEK_API_KEY=tp-xxxx
DEEPSEEK_MODEL=mimo-v2.5-pro
DEEPSEEK_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1

# 或者使用阿里百炼
DEEPSEEK_API_KEY=sk-xxxx
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_BASE_URL=https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
```

也可以直接编辑项目根目录的 `config.json` 文件（优先级较低）。

### 4. 启动

```bash
python web_app.py
```

打开浏览器访问 `http://127.0.0.1:8080` 即可。

**启动后系统自动运行交易引擎，无需任何手动操作。** 服务启动时会：
1. 自动创建数据库和所有表结构（无需手动建表）
2. 初始化账户（默认 10 万资金）
3. 启动全自动交易引擎
4. 非交易时间自动休眠等待

## 📦 部署指南

### 本地开发运行

```bash
# 前台运行（可看到日志）
python web_app.py

# 后台运行
nohup python web_app.py > trader.log 2>&1 &
```

### macOS 一键启动

双击项目中的 `启动Web版.command` 文件即可自动启动。

### Linux 服务部署（systemd）

创建服务文件 `/etc/systemd/system/sim-trader.service`：

```ini
[Unit]
Description=A股模拟短线交易训练器
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/project
ExecStart=/usr/bin/python3 web_app.py
Restart=always
RestartSec=10
Environment=DEEPSEEK_API_KEY=your_api_key
Environment=DEEPSEEK_MODEL=mimo-v2.5-pro
Environment=DEEPSEEK_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable sim-trader
sudo systemctl start sim-trader
sudo systemctl status sim-trader  # 查看状态
sudo journalctl -u sim-trader -f  # 查看日志
```

### Docker 部署（可选）

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["python", "web_app.py"]
```

```bash
docker build -t sim-trader .
docker run -d -p 8080:8080 -v ~/.a_share_sim_trader_web:/root/.a_share_sim_trader_web sim-trader
```

### 停止服务

```bash
# 找到进程
ps aux | grep web_app.py

# 杀掉进程
kill <PID>

# 或者直接杀掉占用 8080 端口的进程
lsof -ti:8080 | xargs kill
```

## ⚙️ 配置说明

所有配置项均可通过环境变量或 `.env` 文件设置：

| 变量名 | 必填 | 默认值 | 说明 |
|--------|------|--------|------|
| `DEEPSEEK_API_KEY` | ✅ | — | AI API 密钥 |
| `DEEPSEEK_MODEL` | — | `deepseek-chat` | 模型名称 |
| `DEEPSEEK_BASE_URL` | — | `https://api.deepseek.com/v1` | API 地址 |
| `DB_TYPE` | — | `sqlite` | 数据库类型：`sqlite` 或 `mysql` |
| `DB_HOST` | — | `127.0.0.1` | MySQL 主机（仅 mysql 模式） |
| `DB_PORT` | — | `3306` | MySQL 端口（仅 mysql 模式） |
| `DB_USER` | — | `root` | MySQL 用户名（仅 mysql 模式） |
| `DB_PASS` | — | — | MySQL 密码（仅 mysql 模式） |
| `DB_NAME` | — | `sim_trader` | MySQL 数据库名（仅 mysql 模式） |
| `PORT` | — | `8080` | Web 服务端口 |

### 使用 MySQL

如果需要使用 MySQL 而非默认的 SQLite，在 `.env` 中设置：

```env
DB_TYPE=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASS=your_password
DB_NAME=sim_trader
```

### 兼容 config.json

项目也支持通过 `config.json` 文件配置 AI 参数（向后兼容），优先级为：

**环境变量 > .env > config.json > 默认值**

## 🗄️ 数据库说明

### 支持的数据库

| 数据库 | 默认 | 说明 |
|--------|------|------|
| **SQLite** | ✅ 默认 | 零配置，数据文件存储在 `~/.a_share_sim_trader_web/trader.db` |
| **MySQL** | ❌ | 需要手动配置连接信息 |

### 自动建表

**服务启动时会自动创建所有数据库表，无需手动执行 SQL。** 启动流程：

1. 检测数据库类型（SQLite/MySQL）
2. 如果是 MySQL，自动创建数据库（如果不存在）
3. 自动创建所有表结构（如果不存在）
4. 自动补齐旧表缺失的字段（兼容升级）

### 数据库表结构

| 表名 | 说明 |
|------|------|
| `account` | 账户信息（初始资金、当前资金） |
| `positions` | 当前持仓（股票代码、数量、成本价、止损价等） |
| `lots` | 持仓批次（用于计算盈亏，支持 T+1 卖出） |
| `trades` | 交易历史记录（买卖时间、价格、费用、盈亏等） |
| `equity_snapshots` | 账户净值快照（用于绘制净值曲线） |
| `decision_log` | AI 决策日志（记录每次 AI 的判断和理由） |

### 切换数据库

#### 使用 SQLite（默认，推荐新手）

无需任何配置，启动即用：

```bash
python web_app.py
```

数据库文件位置：`~/.a_share_sim_trader_web/trader.db`

#### 使用 MySQL

1. 确保已安装 MySQL 并启动服务

2. 在 `.env` 文件中配置：

```env
DB_TYPE=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASS=your_password
DB_NAME=sim_trader
```

3. 重启服务即可，系统会自动创建数据库和表

> 💡 **提示**：SQLite 适合个人使用，MySQL 适合多用户或需要远程访问的场景。

## 📁 项目结构

```
├── web_app.py              # Web 版主程序（FastAPI + AI 交易引擎）
├── a_share_sim_trader.py   # CLI 版命令行工具
├── templates/
│   └── index.html          # Web 前端（单页应用）
├── static/
│   ├── pet-widget.js       # 仓鼠宠物组件
│   ├── pet-widget.css      # 宠物样式
│   └── favicon.png         # 网站图标
├── .env.example            # 配置文件模板
├── requirements.txt        # Python 依赖
└── README.md               # 本文件
```

## 🔌 API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/account` | GET | 账户状态（资金、净值、收益率） |
| `/api/positions` | GET | 当前持仓列表 |
| `/api/trades` | GET | 交易历史记录 |
| `/api/picks` | GET | AI 选股推荐 |
| `/api/engine/status` | GET | 交易引擎状态 |
| `/api/engine/start` | POST | 启动交易引擎 |
| `/api/engine/stop` | POST | 停止交易引擎 |
| `/api/snapshots` | GET | 账户快照（净值曲线数据） |
| `/api/logs` | GET | 实时运行日志 |

## ❓ 常见问题

**Q: 启动后 AI 功能不工作？**
A: 检查 `.env` 中的 `DEEPSEEK_API_KEY` 是否正确配置。启动时会显示 AI 引擎状态。

**Q: 支持哪些 AI 模型？**
A: 支持所有兼容 OpenAI Chat Completions 格式的 API，包括 DeepSeek、阿里百炼、OpenAI、智谱等。只需修改 `DEEPSEEK_BASE_URL` 和 `DEEPSEEK_MODEL` 即可。

**Q: 数据库存在哪里？**
A: SQLite 模式下，数据库文件存储在 `~/.a_share_sim_trader_web/trader.db`。

**Q: 非交易时间系统在做什么？**
A: 系统会自动检测 A 股交易时间（工作日 9:30-11:30、13:00-15:00），非交易时间跳过 AI 调用和行情获取，节省 token。

**Q: 交易费用是怎么计算的？**
A: 模拟了真实的 A 股交易费用：佣金万三（最低 5 元）、印花税千分之一（仅卖出）、过户费万分之零点一。

**Q: 如何切换 SQLite 和 MySQL？**
A: 在 `.env` 文件中设置 `DB_TYPE=sqlite` 或 `DB_TYPE=mysql`，然后重启服务即可。SQLite 无需额外配置，MySQL 需要配置连接信息。

**Q: 数据会丢失吗？**
A: SQLite 模式下数据保存在本地文件，除非手动删除 `~/.a_share_sim_trader_web/trader.db` 文件。MySQL 模式下数据保存在数据库中。

**Q: 如何备份数据？**
A: SQLite 模式直接复制 `~/.a_share_sim_trader_web/trader.db` 文件即可。MySQL 模式使用 `mysqldump` 命令备份。

**Q: 端口被占用怎么办？**
A: 可以通过 `PORT` 环境变量修改端口，如 `PORT=8081 python web_app.py`，或者杀掉占用端口的进程：`lsof -ti:8080 | xargs kill`。

**Q: 如何重置账户？**
A: SQLite 模式删除数据库文件后重启即可。MySQL 模式清空 `account`、`positions`、`lots`、`trades` 等表后重启。

## 📄 License

MIT License
