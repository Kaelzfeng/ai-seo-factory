# Private Beta Demo 流程

本文件描述 AI SEO Content Factory 的 Private Beta 演示步骤。

> 不含真实 API key、密码或站点后台地址。

## 前置条件

1. 启动 Flask 应用 (`python app.py`)
2. 数据库已初始化 (`python models.py` 或自动建表)
3. 至少配置了 mock LLM 或真实 DeepSeek/OpenAI provider

## Demo 步骤

### 1. 登录 Demo 用户

- 打开 `http://localhost:5000/login`
- 使用 demo 账号登录（email: `demo@example.com`，密码由 `DEMO_PASSWORD` 环境变量或自动生成）
- 首次登录后会自动创建 demo workspace

### 2. 创建项目

- 进入 Dashboard，点击 "New Project"
- 填写项目名，例如 "PU Leather B2B Export Site"
- 选择行业配置（可从 `industries/` 目录加载 YAML）
- 设置目标语言（Chinese / English）

### 3. 输入中文需求

- 在项目设置页输入种子关键词，例如 "PU皮革"
- 可通过关键词研究工具扩展长尾词
- 配置页面类型：guide / vs / faq / product

### 4. 生成 Preview

- 在项目页点击 "Generate Preview"
- 系统会调用 LLM 生成 HTML 页面内容
- 可在 `output_src/` 目录查看生成的 HTML 文件
- 预览页展示标题、meta description、正文和图片

### 5. 查看 Competitor Report

- 在项目页点击 "Competitor Analysis"
- 系统会抓取 SERP 结果并生成竞品报告
- 报告包含：竞争对手列表、内容差距分析、超越策略建议

### 6. Dry-run WordPress Sync

- 在项目设置中配置 WordPress 站点信息（wp_url / wp_username / wp_app_password）
- 使用 demo/test 凭据，不连接真实生产站点
- 点击 "Dry-run Sync" 执行模拟发布
- 系统会生成 CMS log 和 publish snapshot，但不实际写入 WordPress

### 7. Collect Beta Feedback

- 在任意页面点击 "Feedback" 按钮
- 选择评分（1-5 星）和分类（content_quality / speed / ui / other）
- 填写反馈消息
- 提交后可在 `/api/beta/feedback` 查看汇总
- 在 Dashboard 可查看 Private Beta Report（`/api/beta/report`）

## 技术说明

- 所有数据存储在 SQLite (`data/app.db`)
- Beta 反馈隔离到 tenant 级别
- WordPress adapter 支持 dry-run 模式，不会修改远程站点
- 完整的 Phase 9.3 测试覆盖见 `tests/test_phase9_beta.py`
