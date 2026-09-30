# Xray Subscription

在自己的 VPS 上部署 **VLESS + REALITY / Vision**，生成 Stash、Clash Meta/Mihomo、Shadowrocket 和 fancyss 的 HTTPS 订阅。

只有 Xray 和 Nginx 静态订阅文件，没有看板、注册系统、数据库、流量统计或多用户管理。四种订阅格式使用同一套节点凭据；它们不是四个独立账号。

## 服务器建议

- 云服务商：**腾讯云**，可按预算考虑轻量应用服务器。
- 参考预算：**99–199 元/年**，不是固定报价或价格承诺，实际以购买时的活动、地域、流量套餐及续费价格为准。
- 建议配置：**2 核 2G，Ubuntu 24.04 LTS**，x86_64 或 ARM64。
- 服务器地域按需求选择，综合考虑访问延迟、线路、目标服务所在地及流量套餐；不同地域的可用性和速度需要实测。

本仓库不绑定任何个人服务器、域名或云账户。请使用自己的云服务器与域名。

## 开始前

需要一台**新装、无现有 Xray 或其他网站的 Ubuntu 24.04**，一个直接解析到该服务器 IPv4 的域名，以及 sudo 权限。已有业务服务器不适用这个安装器。

默认开放 TCP 22（SSH）、80（证书验证及续期）、443（VPN）、8443（订阅 HTTPS）；在云防火墙及已启用的系统防火墙分别放行，22 建议限自己的管理 IP。脚本不修改防火墙，不切换客户端代理。

域名使用 DNS-only 的 A 记录，不经过 CDN 代理。安装器当前只配置 IPv4 监听；不要给该域名配置 AAAA 记录。REALITY 的目标域名 `sni` 与订阅域名不同，目标须从 VPS 可访问且支持合适的 TLS；示例目标只是起点，并不保证所有地区可用。

## 部署

在服务器执行：

```bash
sudo apt update
sudo apt install -y git python3 openssl nginx certbot
git clone https://github.com/masterqii/xray-subscription.git
cd xray-subscription
mkdir -m 700 private
cp settings.example.json private/settings.json
chmod 600 private/settings.json
nano private/settings.json
```

填写自己的域名、ACME 邮箱、服务器 IPv4、节点名称和端口。示例 IP 是文档保留地址，不能直接部署。

去 [Xray 官方 Releases](https://github.com/XTLS/Xray-core/releases) 选择明确版本，读取对应架构 ZIP 的 SHA256：x86_64 对应 `Xray-linux-64.zip`，ARM64 对应 `Xray-linux-arm64-v8a.zip`。可使用发布资产的 SHA256 或官方 `.dgst` 中的 SHA256，不能用 SHA512、二进制本身的摘要或另一架构的摘要。

```bash
# 不带 v 前缀；下面两个值由你从官方 release 填写。
XRAY_VERSION='填写版本号'
XRAY_SHA256='填写64位SHA256'
sudo python3 deploy.py install --settings private/settings.json \
  --xray-version "$XRAY_VERSION" --xray-sha256 "$XRAY_SHA256"
```

脚本从官方 release 下载并核对 SHA256，生成新的 UUID/REALITY 密钥及随机订阅 token，先通过 Xray 配置检查，再安装低权限 systemd 服务、申请免费证书并设置自动续期。不会上传参数到订阅转换网站。

支持的协议组合按 Xray 26.3.27 的配置格式编写；其他版本须先核对配置兼容性。**已做的本地检查及尚未完成的验收见 [验证说明](docs/verification.md)**，不承诺任意未来版本免测试可用。

安装失败时会留下 `/etc/xray-subscription/INSTALLING` 和已完成部分，拒绝覆盖重装。证书失败不会启动 Xray；不要直接删除保护文件重试。检查 DNS、防火墙、日志及现有状态后处理；这不是事务式回滚安装器。

## 获取订阅

```bash
sudo cat /root/xray-subscription-delivery.json
```

在自己的终端查看并私下保存，不要贴到公开 issue 或 Git。按客户端选择对应 URL：

| 客户端 | 字段 | 输出 |
|---|---|---|
| iPhone / Mac 的 Stash | `stash` | 完整 YAML，使用 `sni` |
| Android Clash Meta / Mihomo | `clashmeta` | 完整 YAML，使用 `servername` |
| Shadowrocket | `shadowrocket` | Base64 VLESS URI 列表 |
| 路由器 fancyss | `fancyss` | Base64 VLESS URI 列表 |

客户端须支持 VLESS + REALITY + Vision；旧 Clash 内核不支持。YAML 默认内网及中国 GEOIP 直连、其余走选择组；会替换导入配置中的对应规则。fancyss/Shadowrocket 输出仅含节点，分流规则由客户端自己管理。

先备份自己的路由器配置再导入；如有 NAS/PT 整机直连要求，应在客户端或路由器单独保留。模板不包含任何人的家庭设备 IP，也不自动修改路由器。

订阅链接本身就是访问凭据，任何拿到链接的人都能获取节点。随机路径不是账号系统，不提供按朋友隔离或撤销权限；泄漏时需同时处理订阅 token 和节点 UUID。公网根路径返回 404 是预期行为。

## 更新订阅内容

root-only 的 `/etc/xray-subscription/state.json` 保存用于订阅的节点参数；服务端私钥只在 Xray 配置中。可在 `nodes` 列表中加入你已部署好的其他节点（最多 32 个，每个名称唯一），再执行：

```bash
sudo python3 deploy.py publish
```

这会在原 URL 发布四种格式，不重启 Xray。客户端点“更新订阅”获取内容。**它不部署额外服务器，不同步远端凭据**；编辑 state 也不会改变 Xray 配置。先在对应节点配置、验证凭据，再发布订阅。不要修改 state 中的 domain/https_port/token 来尝试轮换入口：这些字段还对应 Nginx 和交付文件，需另行协调更新。

## 运维与限制

- Xray：`/usr/local/etc/xray/config.json`；服务 `xray.service`。
- 订阅：`/var/lib/xray-subscription/current/`；Nginx 仅开放四个精确路径，不提供目录浏览，关闭订阅访问日志。
- 证书：`certbot.timer` 自动续期；HTTP-01 使用 TCP 80，续期成功后校验并 reload Nginx。保持域名及 80 端口可用。
- 安装后执行 `sudo certbot renew --dry-run`，并检查 `systemctl list-timers certbot.timer`。
- 备份 Xray 配置、`/etc/xray-subscription/` 和证书等敏感资料到私有位置；本项目不做自动备份、自动升级或跨机同步。
- `systemctl is-active xray nginx`、配置检查成功及 HTTPS 可访问，只能说明对应环节正常；实际出口和目标 HTTPS 请求仍需在客户端验收。

日常检查：

```bash
sudo /usr/local/bin/xray run -test -config /usr/local/etc/xray/config.json
systemctl is-active xray nginx
sudo nginx -t
sudo journalctl -u xray -n 30 --no-pager
```

## 开发

```bash
python3 -m unittest discover -s tests -v
```

渲染及安装器使用 Python 标准库，无前端或 Python Web 服务。开发测试额外安装 PyYAML 可核验 YAML 解析。仓库只包含源码、文档及虚构测试参数；`private/`、生成状态、密钥、订阅链接不入 Git。

协议参考：[Xray transport](https://xtls.github.io/config/transport.html)、[Mihomo VLESS](https://wiki.metacubex.one/config/proxies/vless/)、[Stash 协议文档](https://stash.wiki/proxy-protocols/proxy-types)。
