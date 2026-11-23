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
      requirement:  { status: todo, note: "既有实现，尚无设计文档（kb 首批登记）" }
      api:          { status: todo, note: "待设计阶段补齐" }
      interaction:  { status: todo, note: "无界面" }
      backend:      { status: partial, note: "既有单文件实现，无自动化测试" }
      frontend:     { status: todo, note: "无前端" }
      validation:   { status: todo, note: "Gate 2 未执行" }
    gates:
      gate1: { status: pending, note: "待设计完成" }
      gate2: { status: pending, note: "待代码完成" }
---
