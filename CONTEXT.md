# 项目上下文

更新：2026-10-07，macOS。

- 目标：公开的独立 Xray + HTTPS 静态订阅项目，供使用者在自己的全新 Ubuntu 24.04 VPS 部署；不含看板或个人服务器记录。
- 沿用已有公开仓库 masterqii/xray-subscription，不复制 VPS 看板仓库或其历史、配置和凭据。
- 本轮首页按“买服务器（免费订阅地址，自有域名可选） → SSH → 部署 → 获取订阅并验收”重写；补充 Windows/macOS 登录、七项参数、客户端字段和常见问题，原维护说明迁入 docs/maintenance.md。
- 首次教程固定 Xray 26.3.27；2026-10-07 从官方 GitHub release API 核对 x86_64、ARM64 ZIP SHA256。摘要只证明下载内容匹配，不证明线路或客户端端到端成功。
- 未操作任何真实服务器。实际安装、DNS/证书、客户端出口与续期需使用者部署后验收；既有验证边界见 docs/verification.md。
- 验证：现有 13 项单元测试中 10 项通过、3 项跳过（Linux chown/symlink、真实 Xray 二进制、可选 PyYAML）；文档 Bash 语法与相对链接检查通过。未做真实 VPS 部署；本轮不修改部署程序。
- 发布前已通过 GitHub API 确认仓库 Public；只提交教程、维护文档和脱敏项目上下文。
- 用户确认无需购买域名：首页增加 sslip.io 免费主机名路径，说明第三方 DNS/ACME 依赖；REALITY 本身使用 IP，当前安装器未增加纯 IP HTTP 或 IP 证书模式。
