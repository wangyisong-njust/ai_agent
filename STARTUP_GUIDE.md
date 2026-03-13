# NUS Campus Intelligent Assistant — 启动攻略

> Powered by **OpenClaw** (Multi-Agent) · **WaveSpeed AI** (LLM + Vision) · **ChromaDB** (RAG)

---

## 前置要求

| 工具 | 版本 | 检查命令 |
|------|------|---------|
| Python | 3.11+ | `python --version` |
| Node.js | 18+ | `node --version` |
| pip | 最新 | `pip --version` |

---

## 第一步：配置环境变量

`.env` 文件已在项目根目录配置好。确认以下内容已填写：

```
WAVESPEED_API_KEY=f9b39a2f...          ✅ 已填
CANVAS_ACCESS_TOKEN=21450~...          ✅ 已填
GOOGLE_CLIENT_ID=33255509...           ✅ 已填
GOOGLE_CLIENT_SECRET=GOCSPX-...       ✅ 已填
SMTP_PASSWORD=nutgxdqhjfsxbdki        ✅ 已填
SECRET_KEY=???                         ❌ 需要生成
SMTP_USER=???                          ❌ 需要填写 Gmail 地址
```

**生成 SECRET_KEY（在任意终端运行）：**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
把输出填入 `.env` 的 `SECRET_KEY=`

---

## 第二步：安装后端依赖

打开终端，进入项目目录：

```ba sh
cd D:\code\PythonProject_New\AI_agent\backend

pip install -r requirements.txt
```

安装 Playwright 浏览器（Job Agent 用）：
```bash
playwright install chromium
```

> 首次安装约需 5-10 分钟，请耐心等待。

---

## 第三步：安装前端依赖

```bash
cd D:\code\PythonProject_New\AI_agent\frontend

npm install
```

---

## 第四步：启动后端服务

```bash
cd D:\code\PythonProject_New\AI_agent\backend

uvicorn app.main:app --reload --port 8000
```

启动成功后应看到：
```
[App] Database initialized
[App] NUS Campus Intelligent Assistant started
[App] Powered by: OpenClaw + WaveSpeed AI
INFO:     Uvicorn running on http://0.0.0.0:8000
```

验证后端正常：打开 http://localhost:8000/docs 查看 API 文档

---

## 第五步：摄入 NUS 知识库（首次运行必做）

**新开一个终端**，运行：

```bash
cd D:\code\PythonProject_New\AI_agent

python scripts/ingest_knowledge.py
```

这一步会：
- 爬取 NUS 官网（研究生项目、注册处等）
- 获取 NUSMods 模块列表
- 生成向量嵌入存入 ChromaDB

> 首次约需 3-5 分钟，之后有缓存无需重复运行。

---

## 第六步：启动前端

```bash
cd D:\code\PythonProject_New\AI_agent\frontend

npm run dev
```

启动成功后访问：**http://localhost:5173**

---

## 功能使用说明

### 功能一：NUS 知识问答（首页 Chat）

1. 打开 http://localhost:5173
2. 直接在输入框提问，例如：
   - `"What are the requirements for PhD in Computer Science at NUS?"`
   - `"Tell me about NUS Master of Computing program"`
   - `"What modules are available for CS3216?"`
3. 支持流式输出，答案实时显示
4. 回答末尾会附上信息来源 URL

---

### 功能二：Canvas 课程同步

1. 点击侧边栏 **Canvas Sync**
2. 在输入框粘贴你的 Canvas Personal Access Token
   - 获取方式：登录 https://canvas.nus.edu.sg → Account → Settings → Approved Integrations → New Access Token
3. 点击 **Sync Now** 按钮
4. 等待同步完成，查看：
   - **Assignments** 标签：所有即将到期的作业（按截止日期排序，3天内标红）
   - **Announcements** 标签：老师公告 + WaveSpeed AI 自动摘要

**推送到 Google Calendar：**
1. 先访问 http://localhost:8000/api/canvas/gcal/auth 获取授权 URL
2. 在浏览器打开授权 URL，完成 Google 授权
3. 回调后复制返回的 credentials JSON
4. 在 Canvas 页面的 Sync 请求中携带 gcal_credentials 即可

---

### 功能三：简历投递 Job Agent

1. 点击侧边栏 **Job Agent**
2. **Step 1**：上传简历 PDF（拖拽或点击上传）
   - WaveSpeed AI 自动解析为结构化数据
3. **Step 2**：粘贴 LinkedIn 职位 URL + 职位描述文本
   - 点击 **Analyze Match**，AI 给出匹配分数和 Cover Letter
4. **Step 3**：查看分析结果
   - 分数 ≥ 65 才会出现 Confirm & Apply 按钮
   - 点击后打开浏览器自动填写并提交

---

### 功能四：Syllabus 照片 → Google Calendar ⭐ 新功能

1. 点击侧边栏 **Syllabus → Calendar**
2. 拖拽或点击上传一张课程大纲照片（支持手机拍照）
3. 观看 Agent 思考动画：
   ```
   🔍 Analyzing syllabus image...
   🤖 Calling WaveSpeed Vision AI...
   📋 Extracting deadlines and exam dates...
   ✅ Structuring events as JSON...
   ```
4. 看到提取结果卡片，勾选你想同步的事件
5. 粘贴 Google Calendar Credentials JSON
6. 点击 **Confirm & Sync to Calendar**
7. 事件自动创建，带有 24 小时邮件提醒 + 1 小时弹出提醒

**颜色区分：**
- 🔴 红色 = Exam
- 🔵 蓝色 = Deadline
- 🟡 黄色 = Quiz
- 🟢 绿色 = Project

---

## Demo 演示脚本（比赛用）

**顺序：**

```
1. Syllabus 功能（最震撼，先展示）
   → 拍一张有表格的课程大纲
   → 上传 → 展示 Agent 思考过程
   → 事件卡片弹出 → 点 Confirm
   → "已同步 X 个事件到 Google Calendar"

2. Knowledge Q&A
   → "What are the PhD requirements for Computer Science at NUS?"
   → 流式输出，带来源链接

3. Canvas Sync
   → 粘贴 Token → Sync
   → 展示作业列表和 AI 公告摘要

4. Job Agent（时间允许时展示）
   → 上传简历 → 分析 JD → 看 Cover Letter
```

---

## 常见问题

**Q: 后端启动报 ModuleNotFoundError**
```bash
# 确保在 backend 目录下运行，且已激活正确 Python 环境
cd backend
pip install -r requirements.txt
```

**Q: Canvas 同步失败 "Canvas API error"**
- 检查 Token 是否正确（重新生成一个）
- 确认网络能访问 nus.instructure.com

**Q: WaveSpeed Vision 返回空结果**
- 确保图片清晰，文字可读
- 图片文件不要超过 5MB
- 检查 WAVESPEED_API_KEY 是否有余额

**Q: 前端 npm install 很慢**
```bash
npm install --registry https://registry.npmmirror.com
```

---

## 项目结构速查

```
AI_agent/
├── backend/app/
│   ├── agents/
│   │   ├── canvas_agent/      # Canvas 同步 Agent
│   │   ├── job_agent/         # 求职 Agent
│   │   ├── knowledge_agent/   # RAG 问答 Agent
│   │   ├── syllabus_agent/    # Syllabus 解析 Agent ⭐
│   │   └── orchestrator.py    # OpenClaw 多 Agent 调度
│   ├── services/
│   │   └── wavespeed_service.py  # WaveSpeed AI 统一入口
│   └── routers/               # API 路由
├── frontend/src/pages/
│   ├── ChatPage.tsx           # 知识问答
│   ├── CanvasPage.tsx         # Canvas 同步
│   ├── JobsPage.tsx           # 求职投递
│   └── SyllabusPage.tsx       # Syllabus → Calendar ⭐
└── openclaw/skills/           # OpenClaw SKILL.md 定义
```
