# AI Radar

> AI 开源项目雷达 & 团队技术吸收工作台

AI Radar 是面向团队内部的轻量化工具，把"**发现 → 评估 → 认领 → 试用 → 归档 → 沉淀**"这条 AI 开源技术消化链路串成完整闭环，并自动沉淀为可检索、可问答的项目知识图谱。

---

## 为什么需要 AI Radar

AI 开源生态每天井喷，团队真正的痛不在"看见新项目"，而在：

- **重复造轮子 / 重复趟坑**：不同人在试同一个项目而不自知，卡点经验各自吞掉。
- **看完即焚，团队没有复利**：试用结论散落在个人脑子里、聊天记录里、各自的 Notion 里，下一次别人遇到类似需求又要从零开始。
- **评估口径靠拍脑袋**：谁声音大谁说了算，没有可对比、可追溯的维度。
- **"我们有没有人试过 X？"没人能秒答**：技术资产没有横向关联，检索靠人脑。
- **内部工具部署劝退**：没人有精力为一个轻量工具运维一整套复杂技术栈。

AI Radar 的目标是把"**看见 → 评估 → 试用 → 沉淀 → 被复用**"这条链路做成一条流水线，让团队的每一次试用都变成可被检索、可被引用、可被复利的资产。

---

## 项目亮点

### 让"试过/学到"形成复利，而不是看完即焚
试用结论以结构化字段归档（`Key Findings / 可复用模式 / 适用场景`），同步建立到项目与方向的图谱关系，并支持 Markdown 一键导出到团队知识库。归档不是终点，而是下一次检索的起点。

### 同一个项目不被重复趟坑
试用看板 + 完整状态机（`claimed → running → demo_done → shared`，含 `blocked / dropped` 分支）让"谁认领了什么、卡在哪、何时出结论"全员可见。状态切换由后端前置校验——`blocked` 必填 blockers、`demo_done` 必填 result_summary——避免试用半途而废、悬而未决。

### 端到端闭环，不是工具拼盘
发现、评估、认领、试用、归档、图谱沉淀**全部收敛到同一个系统**，状态自动流转。无需在 Notion / Excel / Issue / Slack 之间来回搬数据。

### 候选项目自动汇聚，不再手工捞 Trending
内置三通道：GitHub Search API（按 `Agent / RAG / Eval / Inference / Workflow / Developer Tooling / MCP` 方向关键词分类检索） + GitHub Trending 抓取 + 任意 GitHub URL 手动添加，汇聚去重后入池；一个 `sync_interval_minutes` 开关即开启周期自动同步，新项目自动进入待评估池。

### 评估有维度，决策可追溯
内置 `relevance / trialability / value / recommendation` 四维评分 + 决策理由与证据字段，让"为什么 try、为什么 reject"留下痕迹，新人接手不必从头再判断一次。

### 一图看清团队技术地形
基于 vis-network 的知识图谱将 `Project ↔ Domain ↔ Capability ↔ TeamAsset` 用 `belongs_to / provides / produced` 关系串联，按方向聚合即可回答"我们在 RAG 方向上铺过哪些项目、产出了哪些团队资产"。Tech Lead 与新成员的全景视角一次到位。

### "我们试过 X 吗？" — 一句话能问出来
AI 助手把全量项目元数据 + 评估结论 + 试用状态喂给 LLM，提供基于本地知识图谱的 SSE 流式问答；对话里识别到项目名会带跳转标记，点一下直达项目详情。

### LLM 服务商可热切换，不绑死
完全走 OpenAI 兼容协议，`base_url + api_key + model` 三参数在 Settings 页面热切换并立即生效——内部自托管、商业 API、灰度试新模型，无需改一行代码。

### 企业身份打通，不再自建账号体系
对接 IX-Auth（LDAP），后端签发 HS256 JWT，前端自动注入并在 401 时清理会话。员工直接登录，零额外账号管理负担。

### Docker 单容器部署，"运维"等于一行命令
多阶段镜像把前端 dist 打进后端镜像，FastAPI 直接托管 Vue SPA，单端口对外，SQLite 数据卷持久化。`docker compose up -d --build` 一行启动，没有 Redis、没有外部 DB、没有反向代理的额外搭建。

---

## 主要功能

| 模块 | 说明 |
|---|---|
| **AI Assistant** | 基于本地项目知识图谱的流式问答，支持识别项目名跳转 |
| **Radar** | 候选项目池：方向标签筛选、推荐排序/未评估优先、卡片详情抽屉、一键认领 |
| **Trials** | 试用看板：状态机驱动的流转、负责人/截止日期/环境/Demo URL/Blocker 全字段维护 |
| **Shares** | 试用结论归档：Key Findings / 可复用模式 / 适用场景 / 文档链接，支持 Markdown 导出 |
| **Knowledge Graph** | 项目-方向-能力-团队资产的关系图谱，支持方向聚合统计 |
| **Settings** | LLM Key / Base URL / Model / GitHub Token / 自动同步周期，所有配置热生效 |

---

## 技术栈

**后端**：FastAPI · SQLModel · SQLite · python-jose (JWT) · sse-starlette · httpx · requests · pydantic-settings

**前端**：Vue 3 + TypeScript · Vite · Element Plus · Pinia · Vue Router · vis-network · ECharts · marked · axios

**部署**：Docker 多阶段构建（Node 构建前端 + Python 运行后端）· `uv` 依赖管理

---

## 快速开始

### 本地开发

后端：

```bash
uv sync
uv run python scripts/init_db.py     # 首次需初始化 SQLite
./run_backend.sh                      # 等价于 PYTHONPATH=backend uv run uvicorn app.main:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev                           # http://localhost:5173 ，已配置代理到 8000
```

### Docker 一键部署

```bash
cp .env.example .env                  # 按需填入 GITHUB_TOKEN / LLM_API_KEY 等
docker compose up -d --build
```

启动后访问 `http://localhost:8001`，前后端均由该端口提供。

---

## 配置

### `.env`（运行时配置）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `GITHUB_TOKEN` | _空_ | GitHub API token（可选，未配置时使用匿名速率） |
| `LLM_API_KEY` | _空_ | OpenAI 兼容服务的 API Key |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | LLM 服务地址 |
| `LLM_MODEL` | `gpt-4o-mini` | 默认模型 |
| `JWT_SECRET` | `change-me-in-production` | JWT 签名密钥（**生产必改**） |
| `JWT_EXPIRE_HOURS` | `24` | Token 有效期 |
| `SYNC_INTERVAL_MINUTES` | `0` | 自动同步周期，`0` 表示关闭 |
| `DB_PATH` | `./data/ai_radar.db` | SQLite 文件路径 |

也可登录后在 **Settings** 页面直接修改并热生效。

### `config/keywords.yaml`

按方向分类的搜索关键词；新增方向只需在此追加一段即可参与下次同步。

### `config/filters.yaml`

候选项目最小 Stars、最大不活跃天数、单日候选上限等过滤策略。

---

## 项目结构

```
backend/app/             FastAPI 主应用
  ├── main.py            入口 / lifespan / 自动同步任务
  ├── routers/           auth / projects / evaluations / trials / shares / graph / chat / settings
  ├── services/          ai_chat / graph_builder / state_machine / markdown_export / sync / ...
  ├── auth.py            JWT 签发与解码
  ├── models.py          SQLModel 数据模型
  └── repositories.py    数据访问层

frontend/                Vue 3 SPA
  └── src/views/         Chat / Radar / Trials / Shares / KnowledgeGraph / Settings / Login

src/                     发现源（GitHub Search / Trending）与配置加载
scripts/                 init_db / seed / refresh / smoke_test 等运维脚本
config/                  keywords.yaml · filters.yaml
tests/                   pytest 测试用例（11 个模块覆盖）
```

> 注：`src/` 与 `backend/app/` 中存在部分重复的 `models.py / repositories.py` —— 前者是 Streamlit 时期的遗留代码与发现源脚本共用；FastAPI 已是主路径，后续会收敛到单一来源。

---

## 测试

```bash
uv run pytest                         # 跑全部测试
uv run pytest tests/test_state_machine.py -v
```

---

## License

Internal use.
