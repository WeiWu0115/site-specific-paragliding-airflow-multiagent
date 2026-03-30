# CLAUDE.md — Project Memory & Context

> This file is loaded automatically by Claude Code at the start of every session.
> It records what this project is, what has been built, what phase we are on,
> and the non-negotiable design constraints that must always be respected.

---

## 项目是什么 / What This Project Is

**site-specific-paragliding-airflow-multiagent**

一个针对**单一飞行场地**的多智能体滑翔伞气流规划系统。
A multi-agent airflow planning system scoped to **one paragliding site only**.

核心定位：
> "A site-specific multi-agent environmental sensemaking system for paragliding that integrates
> terrain reasoning, weather interpretation, cloud context, local pilot expertise, flight history,
> and uncertainty-aware recommendation generation, with Unity-based 3D spatial visualization
> as the first embodiment of airflow hypotheses."

这不是：
- 不是自动驾驶系统
- 不是航空安全认证系统
- 不是通用多场地平台（第一版只做一个场地）

所有输出必须是：advisory（建议性）/ explainable（可解释）/ confidence-scored（有置信度）/ uncertainty-aware（不确定性感知）

---

## 种子场地 / Seed Site

**Eagle Ridge Flying Site**
- 位置：Tehachapi Mountains, CA（35.492°N, 118.187°W，海拔约 1340m）
- 配置文件：`backend/config/site_profiles/eagle_ridge.json`
- 包含：3个起飞点、2个降落区、6+个命名地形特征、10条本地经验规则

---

## 当前阶段 / Current Phase

```
Phase 1 ← 当前阶段（MVP）
  ✅ 仓库脚手架 + Docker Compose + DB 迁移
  ✅ Eagle Ridge 场地配置文件
  ✅ Open-Meteo 天气提供商 + Mock 提供商
  ✅ 所有7个 Agent 骨架代码（带真实逻辑）
  ✅ FastAPI 后端（10个路由模块）
  ✅ NegotiationAgent 仲裁流程
  ✅ PlanningService 完整编排
  ✅ /unity/overlays 端点 + UnityOverlayBuilder
  ✅ Next.js 前端仪表盘（9个组件）
  ✅ 数据库模型（15张表，含 PostGIS）
  ✅ 测试骨架（20+个测试）
  ✅ 种子脚本、IGC/GPX 导入脚本

Phase 2 — 下一阶段（本地知识 + 飞行历史）
  ⬜ 专家访谈摄取流水线验证
  ⬜ LocalKnowledgeAgent 完整 DB 集成
  ⬜ 真实 IGC 文件批量导入 + FlightHistoryAgent 热点聚类
  ⬜ NegotiationAgent 跨智能体证据比较增强
  ⬜ /replay 端点完整实现
  ⬜ 前端：AgentExplanationPanel + ReplayPanel 接通真实数据

Phase 3 — ML 评分层
  ⬜ XGBoost/LightGBM 热柱可能性评分器（需要真实飞行数据）
  ⬜ 置信度校准（Platt scaling / 等渗回归）
  ⬜ 特征重要性 / SHAP 可解释性
  ⬜ 笔记本：notebooks/03_baseline_thermal_model.ipynb

Phase 4 — Unity 3D 集成
  ⬜ 实际 Unity 场景搭建（Unity 2022 LTS 推荐）
  ⬜ DEM 地形导入
  ⬜ 时间轴回放 + 智能体图层切换
  ⬜ 基于置信度的视觉映射（透明度、粒子密度）

Phase 5 — XR 扩展架构准备
  ⬜ 后端坐标系解耦
  ⬜ XR 交互约束设计文档完善
```

---

## 系统架构速查 / Architecture Quick Reference

```
数据源（天气API / DEM / IGC / 专家访谈）
    ↓
数据摄取层（data_ingestion/）
    ↓
数据库（PostgreSQL + PostGIS）
    ↓
解释层（agents/）
  WeatherAgent → TerrainAgent → CloudAgent
  LocalKnowledgeAgent → FlightHistoryAgent → RiskAgent
    ↓ Claims（claim + evidence + confidence + spatial_scope + temporal_validity）
仲裁层（NegotiationAgent）
  → 比较声明 → 检测分歧 → 排名推荐 → 保留解释链
    ↓
FastAPI 后端（api/）
    ↓
      ┌── Next.js 仪表盘（frontend/web/）
      └── Unity 3D 客户端（/unity/overlays 端点）
```

---

## 文件结构速查 / Key File Locations

| 内容 | 路径 |
|------|------|
| FastAPI 入口 | `backend/api/main.py` |
| 所有 Agent | `backend/agents/` |
| Eagle Ridge 场地配置 | `backend/config/site_profiles/eagle_ridge.json` |
| 数据库模型（ORM） | `backend/db/models.py` |
| 数据库迁移 | `backend/alembic/versions/001_initial_schema.py` |
| 规划服务编排 | `backend/services/planning_service.py` |
| Unity 数据包构建 | `backend/spatial/overlay_builder.py` |
| Agent 基础数据结构 | `backend/agents/base.py` |
| 环境变量说明 | `.env.example` |
| Unity 集成规范 | `unity/INTEGRATION_SPEC.md` |
| C# 数据模型存根 | `unity/csharp_stubs/` |
| Unity 载荷示例 | `unity/payloads/` |
| 架构文档 | `docs/architecture.md` |
| 专家访谈指南 | `docs/expert_interview_guide.md` |
| ML 规划 | `docs/ml_plan.md` |
| Unity 3D 设计规范 | `docs/unity_3d_design_spec.md` |
| 未来 XR 扩展 | `docs/future_xr_extension.md` |
| 种子脚本 | `scripts/seed_site.py` |

---

## 技术栈 / Stack

```
后端:   Python 3.11+ · FastAPI · SQLAlchemy (async) · Alembic
        PostgreSQL 15 + PostGIS 3.3 · Redis 7
        依赖管理: uv (pyproject.toml)

前端:   Next.js 14 · TypeScript · Tailwind CSS · Recharts · React-Leaflet

3D可视化: Unity 2022 LTS (Phase 4)
XR:      Unity XR Toolkit (Phase 5)

ML:     scikit-learn · XGBoost · LightGBM · numpy · pandas
空间:   rasterio · shapely · pyproj · GeoAlchemy2
HTTP:   httpx (异步)
日志:   loguru
```

---

## 本地开发快速启动 / Local Dev Quickstart

```bash
# 1. 复制环境变量
cp .env.example .env

# 2. 启动数据库 + Redis
docker compose up postgres redis -d

# 3. 安装后端依赖
cd backend && uv sync

# 4. 运行数据库迁移
uv run alembic upgrade head

# 5. 种子初始数据（Eagle Ridge 场地）
uv run python ../scripts/seed_site.py

# 6. 启动 API
uv run uvicorn api.main:app --reload --port 8000
# API 文档: http://localhost:8000/docs

# 7. 启动前端（新终端）
cd frontend/web && npm install && npm run dev
# 仪表盘: http://localhost:3000

# 默认使用 Mock 提供商（无需真实 API key）
# 切换真实天气: WEATHER_PROVIDER=open_meteo in .env
```

---

## 不可违反的设计约束 / Non-Negotiable Design Constraints

1. **单场地优先** — 第一版只深入 Eagle Ridge，不做多场地泛化
2. **建议性输出** — 所有推荐必须带 `confidence` + `uncertainty_note` + `evidence_summary`
3. **可解释性** — 每个推荐必须能追溯到具体 Agent 声明和证据
4. **不确定性不可压制** — NegotiationAgent 暴露分歧，不平滑掉冲突
5. **ML 是评分层** — ML 在规则型 Agent 之上叠加，不替代 Agent 推理
6. **Unity 先于 XR** — Phase 4 是 Unity 3D，Phase 5 才是 XR，不可跳步
7. **本地优先** — Mock 提供商覆盖所有外部依赖，本地开发无需真实 API key

---

## Agent 声明数据结构 / Claim Schema (Quick Reference)

```python
@dataclass
class Claim:
    agent_name: str           # 哪个 Agent 产生
    claim_type: ClaimType     # thermal_zone / ridge_lift / sink_zone / caution / launch_window
    claim_text: str           # 人类可读描述
    evidence: list[Evidence]  # 每条证据的来源 + 描述
    confidence: float         # 0.0 - 1.0
    assumptions: list[str]    # 隐含假设（用于透明度）
    spatial_scope: SpatialScope        # 关联的地理区域
    temporal_validity: TemporalValidity # 时间有效性（时段、季节）
```

---

## 重要文档 / Key Docs to Read

- **正在修改 Agent 逻辑前** → 读 `docs/architecture.md`
- **正在添加本地知识前** → 读 `docs/expert_interview_guide.md`
- **正在接入 Unity 前** → 读 `unity/INTEGRATION_SPEC.md` + `docs/unity_integration_contract.md`
- **正在开发 ML 功能前** → 读 `docs/ml_plan.md`
- **正在规划 XR 前** → 读 `docs/future_xr_extension.md`
