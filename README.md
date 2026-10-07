# Xray Subscription · 自建代理简化版

**买服务器 → SSH 登录 → 部署 Xray → 获取订阅链接。**

在自己的 VPS 上部署 **VLESS + REALITY / Vision**，自动生成 HTTPS 订阅。只有 Xray、Nginx 和静态订阅文件，没有看板、注册、数据库或流量统计。所有凭据在你自己的服务器生成，无需使用原作者的服务器或账号。

## 1. 买服务器（无需购买域名）

选择一台**全新 Ubuntu 24.04 LTS** 服务器，支持 x86_64 / ARM64，具有公网 IPv4 和 sudo 权限。可选腾讯云轻量应用服务器，2 核 2 GB 作为入门配置；其他云厂商满足这些条件也可以。地域按实际访问需求选择，购买前核对带宽、月流量、超额费用及续费价格；线路速度需要实测。不要把本安装器用于已有网站或 Xray 的服务器。

**不必购买域名。** REALITY 代理直接连接服务器 IP；HTTPS 订阅使用免费的 `sslip.io` 地址申请证书和下载配置。将自己的公网 IPv4 中的点换成横线，再加 `.sslip.io`，例如 `203.0.113.10` 对应 `203-0-113-10.sslip.io`。地址会自动解析到嵌入的 IP，无需注册或手动添加 DNS 记录。原理及证书说明见 [sslip.io 官方说明](https://sslip.io/)。

准备好：

| 内容 | 示例（全部需换成自己的） |
|---|---|
| 公网 IPv4 | `203.0.113.10` |
| SSH 登录用户名 | Ubuntu 镜像常见为 `ubuntu`，以控制台为准 |
| SSH 私钥 | 下载到本机的 `.pem` 文件，私下保存 |
| 免费订阅地址 | `203-0-113-10.sslip.io`（按自己的 IP 生成） |
| 证书通知邮箱 | `you@example.com` |

免费地址依赖第三方 DNS 可用性及证书签发额度，申请和续期仍需 TCP 80 可从公网访问；不能保证所有地区和时间都可用。**自有域名是可选项**：如已有域名，也可添加 A 记录直接指向服务器 IPv4，使用 DNS-only、不启用 CDN 代理、不添加 AAAA；本安装器只配置 IPv4 监听。

这里的“无需购买域名”仍使用免费 DNS 主机名。如果只需要单个 `vless://` 分享链接，REALITY 不要求自己的域名；本仓库当前交付的是可更新的 HTTPS 订阅，没有纯 IP HTTP 订阅模式。

在云防火墙 / 安全组放行以下 **TCP** 端口；如果服务器已启用系统防火墙，也需放行对应端口。不要直接关闭防火墙。

| 端口 | 用途 | 来源 |
|---|---|---|
| 22 | SSH 管理 | 建议只允许自己的管理 IP |
| 80 | 申请和续期证书 | 公网，部署后也保留 |
| 443 | VLESS + REALITY | 需要使用代理的客户端 |
| 8443 | HTTPS 订阅 | 需要下载订阅的客户端 |

## 2. SSH 登录服务器

在云控制台给实例绑定自己的 SSH 公钥 / 密钥对，私钥保存在本机。若镜像提供密码登录，也可先按云厂商流程登录再配置密钥。腾讯云操作参考：[使用 SSH 终端登录 Linux](https://cloud.tencent.com/document/product/1207/44578)。

macOS / Linux：在**本机终端**执行，将路径、用户名和 IP 替换为自己的：

```bash
chmod 600 ~/Downloads/my-server.pem
ssh -o IdentitiesOnly=yes -i ~/Downloads/my-server.pem ubuntu@203.0.113.10
```

Windows：在 **PowerShell** 执行，路径有空格也保留引号：

```powershell
ssh -o IdentitiesOnly=yes -i "$HOME\Downloads\my-server.pem" ubuntu@203.0.113.10
```

首次连接前，按云厂商提供的方法核对主机指纹，再接受保存；不要关闭主机密钥校验。Windows 若提示私钥权限过宽，按云厂商说明将文件权限限定到当前用户，再重试。

登录后在**服务器终端**确认环境：

```bash
cat /etc/os-release
uname -m
sudo -v
```

应为 Ubuntu 24.04、`x86_64` 或 `aarch64`。之后第 3、4 步的命令都在这个 SSH 会话中执行。

## 3. 部署项目

安装依赖并下载公开源码（无需 GitHub 登录）：

```bash
sudo apt update
sudo apt install -y git python3 openssl nginx certbot nano
git clone https://github.com/masterqii/xray-subscription.git
cd xray-subscription
mkdir -m 700 private
cp settings.example.json private/settings.json
chmod 600 private/settings.json
nano private/settings.json
```

配置文件只有下面七项；替换免费订阅地址（或自有域名）、邮箱、IP 和节点显示名，端口初次部署建议保持默认：

```json
{
  "domain": "203-0-113-10.sslip.io",
  "email": "you@example.com",
  "server": "203.0.113.10",
  "name": "My VPS",
  "sni": "www.cloudflare.com",
  "vpn_port": 443,
  "https_port": 8443
}
```

`domain` 填按自己 IP 生成的免费地址，或自己的域名；`sni` 是 REALITY 的 TLS 目标，二者不同。目标必须从 VPS 可访问，示例不是所有线路都能用的保证。JSON 不要添加注释或尾部逗号。nano 中按 **Ctrl+O → Enter** 保存，**Ctrl+X** 退出。

下面使用明确版本 **26.3.27**，ZIP SHA256 已于 2026-10-07 从 [Xray 官方 Release](https://github.com/XTLS/Xray-core/releases/tag/v26.3.27) 的资产摘要核对。命令自动选择服务器架构；版本更新需同时核对兼容性及对应 ZIP 摘要，不只改版本号。

```bash
XRAY_VERSION='26.3.27'
case "$(uname -m)" in
  x86_64) XRAY_SHA256='23cd9af937744d97776ee35ecad4972cf4b2109d1e0fe6be9930467608f7c8ae' ;;
  aarch64) XRAY_SHA256='4d30283ae614e3057f730f67cd088a42be6fdf91f8639d82cb69e48cde80413c' ;;
  *) echo '不支持的架构'; XRAY_SHA256='' ;;
esac
if [ -n "$XRAY_SHA256" ]; then
  sudo python3 deploy.py install --settings private/settings.json \
    --xray-version "$XRAY_VERSION" --xray-sha256 "$XRAY_SHA256"
fi
```

安装器从官方下载并校验 Xray，生成 UUID、REALITY 密钥和随机订阅 token，检查配置，安装低权限 systemd 服务并设置开机启动，申请免费 HTTPS 证书并配置续期。它不会修改防火墙或上传节点给第三方转换服务。

看到 `Installed. Subscription URLs: ...` 后继续。**安装失败不要反复执行**：可能已留下部分文件和 `INSTALLING` 标记；先看 [常见问题](docs/troubleshooting.md)，不要删保护文件强行重装。

## 4. 获取订阅链接，导入客户端

```bash
sudo cat /root/xray-subscription-delivery.json
```

输出是四个客户端对应的 HTTPS URL。**复制字段的值作为订阅链接，不要把 JSON 文件或服务器 SSH 私钥导入客户端。** 四种格式共享同一套节点凭据，是同一个节点的不同格式。

| 客户端 | 复制字段 | 操作 |
|---|---|---|
| Stash | `stash` | 添加远程配置 / 从 URL 下载 |
| Clash Meta / Mihomo | `clashmeta` | 新建 URL 配置 / 订阅 |
| Shadowrocket | `shadowrocket` | 添加订阅并更新 |
| fancyss 路由器插件 | `fancyss` | 添加订阅地址并更新 |

入口名称随客户端版本而异。客户端须支持 **VLESS + REALITY + Vision**，旧 Clash 内核不支持。Stash/Mihomo 输出完整 YAML，默认内网和中国 GEOIP 直连，其余走 `PROXY`；Shadowrocket/fancyss 输出 Base64 VLESS 节点列表，分流由客户端配置。

启用导入的配置，选择自己的节点，再验证：

1. 订阅更新成功、节点出现，HTTPS 证书正常。
2. 经该节点访问 IP 查询服务，出口应等于自己的 VPS 公网 IP；排除其他代理节点或自动故障转移。
3. 经代理访问实际要使用的 HTTPS 网站，手机可再用移动网络验证一次。
4. 在服务器执行 `sudo certbot renew --dry-run`，确认续期可用。

订阅 URL 是访问凭据，拿到它的人能获取节点。只在自己的终端查看、私下保存，别发到公开 issue、Git 或第三方在线转换网站。浏览器访问域名根路径返回 404 是正常现象，要使用输出的完整订阅 URL（含 `:8443`）。

如接入路由器，先备份配置，保留 VPS IP `/32` 直连和 NAS/PT 整机直连规则，再导入。服务器部署不会替你配置这些规则。

## 以后怎么维护

- [常见问题](docs/troubleshooting.md)：SSH、DNS、安装和导入失败怎么查。
- [维护说明](docs/maintenance.md)：服务检查、备份、发布订阅和开发。
- [验证边界](docs/verification.md)：已做检查和真实服务器需验收的项目。

本项目没有自动升级、自动备份、按用户管理或流量限制。当前安装器尚未在朋友的新服务器上实际部署，服务 active 不能代替真实代理出口验收。
