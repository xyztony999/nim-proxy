---
# nim-proxy 工作区索引（schema 见 engine/01-pipeline-definition.md §4；
# 由 /profile create 初始化，流水线阶段状态随 /design、/feature、/validate 推进更新）
pipeline: []
reference:
  - { title: 业务枚举池, path: workspace/01-solution/common-spec/04-business-enum.md }
  - { title: 公共枚举池, path: workspace/01-solution/common-spec/03-common-enums.md }
  - { title: 选择服务池, path: workspace/01-solution/common-spec/05-select-service-pool.md }
modules:
  - name: relay
    domain: core
    stages:
      requirement:  { status: complete, note: "D0-D2 完成（BA/AA/FL + PRD + 领域模型）" }
      api:          { status: complete, note: "D3 完成（api-admin.md 含 relay 透传/健康）" }
      interaction:  { status: complete, note: "中转无界面（N/A）" }
      backend:      { status: complete, note: "B 完成：app/ 包 + 管理 API + 双目标适配 + 14 测试通过" }
      frontend:     { status: complete, note: "F 完成：web/ React+Vite+TS，typecheck/lint/build 全过" }
      validation:   { status: complete, note: "Gate 2 PASS（2026-11-23，后端覆盖 89%）" }
    gates:
      gate1: { status: pass, note: "Gate 1 PASS（2026-11-23，报告 05-reports）" }
      gate2: { status: pass, note: "Gate 2 PASS（2 项 WARN：暗色模式/前端单测）" }
  - name: admin
    domain: supporting
    stages:
      requirement:  { status: complete, note: "D0-D2 完成（标准版管理台）" }
      api:          { status: complete, note: "D3 完成（api-admin.md）" }
      interaction:  { status: complete, note: "D4 完成（PageSpec owner/admin）" }
      backend:      { status: complete, note: "B 完成（管理 API + 遥测 + 仓储）" }
      frontend:     { status: complete, note: "F 完成（7 页面，门禁全过）" }
      validation:   { status: complete, note: "Gate 2 PASS（2026-11-23，后端覆盖 89%）" }
    gates:
      gate1: { status: pass, note: "Gate 1 PASS（2026-11-23，报告 05-reports）" }
      gate2: { status: pass, note: "Gate 2 PASS（2 项 WARN：暗色模式/前端单测）" }
---
