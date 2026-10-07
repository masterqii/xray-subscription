# 常见问题

## SSH 连不上

- `Connection timed out`：检查公网 IP、云防火墙 / 安全组 22 端口，以及自己的网络；不要由此直接认定服务器离线。
- `Permission denied (publickey)`：核对镜像登录用户名、私钥文件、实例绑定的公钥。用 `IdentitiesOnly=yes` 明确选定密钥；不要公开私钥。
- `UNPROTECTED PRIVATE KEY FILE`：macOS/Linux 使用 `chmod 600`；Windows 调整文件 ACL，仅当前用户有读取权限。
- 主机密钥变化：先核实是否重装或 IP 变化，确认新指纹后再更新本机记录，不关闭校验。

## 安装器报 Operation failed

安装器隐藏详细异常以免打印生成凭据。先确认 Ubuntu 24.04、sudo、七项 JSON 参数、域名解析和端口，再查看本机服务日志：

```bash
sudo nginx -t
sudo journalctl -u xray -n 50 --no-pager
sudo tail -n 50 /var/log/letsencrypt/letsencrypt.log
```

分享日志前脱敏。证书失败时常见原因是 A 记录未生效、存在错误 AAAA、启用了 CDN 代理、TCP 80 未放行或 ACME 限流。检查配置中的 domain 确实仅解析到 server；使用免费 sslip.io 时，还要核对嵌入的 IP 是否正确，免费 DNS 是否可用及共享证书额度是否受限。已有其他网站 / Xray 或占用端口的服务也会被安装器拒绝。

若已有 `/etc/xray-subscription/INSTALLING`，表示安装未完成，不是可直接清理的缓存。保留现场和私有备份，确认已执行到哪一步再制定恢复方案。不要删除目录盲目重跑；已有业务服务器应使用另一台全新实例。

## 找不到订阅交付文件

`/root/xray-subscription-delivery.json` 只在安装成功后生成，使用 sudo 查看。缺失时先检查安装是否完成；不要把缺文件等同于节点已部署。

## 订阅更新失败或节点连不上

- 链接必须完整，包括 HTTPS、域名、8443 端口和随机路径。域名首页 404 属正常行为。
- 下载失败：检查 DNS、8443 防火墙、Nginx 和证书；不要使用跳过证书验证的办法。
- 能下载但不能连接：检查客户端是否支持 REALITY/Vision、443 端口、Xray 服务及 SNI 目标可达性。下载成功仅验证订阅通道。
- 路由器连接绕圈：确认 VPS 公网 IP `/32` 直连，保留原有 PT 整机直连。
- 重启 SSH 会话后若要发布订阅，先 `cd ~/xray-subscription`，再执行维护文档中的命令。

更完整的出口和 HTTPS 验收见 [验证说明](verification.md)。
