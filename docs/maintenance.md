# 后续维护

首次部署请按 [首页四步教程](../README.md) 操作。

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
