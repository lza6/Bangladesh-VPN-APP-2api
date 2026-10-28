# Bangladesh VPN → new-api 代理池接入指南

把本源的 **OpenVPN 节点**转成一组本地 **SOCKS5** 端口，喂给 new-api 共享代理池
（`relay/channel/tryingopen`，环境变量 `TRYINGOPEN_PROXY_FILE`），供 TryingOpen / NoTrack 这类
「每 IP 每小时限额」的渠道轮换出口。

> **先读这一段再动手。** 本池只有 5 条、带宽 0.02–0.36 MB/s、凭据是他人的 CyberGhost 账号。
> 它适合当**孟加拉/东南亚本地出口的稀缺补充**，不适合当主力池。建议单独分组、单独限流，
> 随时准备整池摘除。

---

## 1. 为什么需要协议转换

节点是原生 **OpenVPN over TCP 443**（TLS 1.3 + AES-256-GCM），new-api 的上游客户端只会说
HTTP / SOCKS5。中间必须有一层转换，并且**每个节点要独立出口**，否则多节点共用一个 tun 会串味。

```
Bangladesh VPN API ──harvest──> ≤5 份 .ovpn
                                    │
                        netns bdv0..N (每节点一个命名空间)
                                    │  openvpn + microsocks
                                    ▼
                    172.18.0.1:44000..44004  (SOCKS5)
                                    │
                        new-api 代理池轮换
```

用 `netns` 而不是「一个 openvpn + redsocks」的原因：多节点需要多个并发隧道，
默认路由会互相覆盖；netns 天然隔离，节点掉线也不会把流量漏回宿主直连。

---

## 2. 关键约束（都是踩过的坑）

1. **监听地址不能是 `127.0.0.1`**。new-api 跑在 Docker 容器里，容器内的 `127.0.0.1` 是它自己的
   命名空间。必须绑 Docker 网桥网关（默认 `172.18.0.1`），并放行防火墙：
   ```bash
   ufw allow from 172.18.0.0/16 to any port 44000:44004 proto tcp
   ```
2. **必须加 `--pull-filter ignore`**。服务端会 push `register-dns` / `dhcp-release` / `dhcp-renew` /
   `block-outside-dns` 这些 Windows 专用选项，Linux 版 OpenVPN 2.6 会直接 `Options error` 中断。
   不加就会误判成「账号失效」，白白丢掉可用节点。
3. **只有 TCP/443 通道可用**。37 个节点的 UDP/1194 从常规出口全部丢包（抽样 5/5 不通，含孟加拉本地
   节点）。生成配置时用 `.tcp.ovpn` 变体，别用 `.udp.ovpn`。
4. **凭据会失效**。`AUTH_FAILED` 代表 TLS 与证书全过、仅账号被拒。定期重拉 `/api/v1/list`
   对比凭据指纹，变了就重建实例。
5. **同一 IP 多 id**（如 871/872 都在 `103.112.62.240`）属于不同 profile，可用性可能不同，
   但**出口 IP 相同**，做 IP 轮换时要去重。
6. **不要并发压测**。5 条节点共享 4 组账号，同时拨号会互相挤掉；测活请串行。

---

## 3. 部署步骤（在 new-api 宿主上执行）

### 3.1 依赖

```bash
apt-get update
apt-get install -y openvpn iproute2 iptables curl microsocks
openvpn --version | head -1     # 需 ≥ 2.4
```

### 3.2 准备配置

把仓库里的工具放到宿主（路径按需调整）：

```bash
mkdir -p /opt/bdvpn && cd /opt/bdvpn
# 放入：api.py harvest.py prepare_wsl.py pool_build.py 以及 wsl/probe2.sh
python3 harvest.py            # 拉 raw/list.json + raw/ovpn/*.ovpn
python3 prepare_wsl.py        # 生成 wsl/conf/*.{udp,tcp}.ovpn + wsl/creds/*.txt
```

> `prepare_wsl.py` 里的 `WSL` 常量默认是 `/mnt/d/...`（WSL 路径）。在原生 Linux 上要把
> `WSL = "/mnt/d/apk-analysis/bd-vpn/wsl"` 改成实际目录，否则 `auth-user-pass` 会指向不存在的文件。

### 3.3 拨测（必做，别跳过）

```bash
UPLINK=$(ip route | awk '/^default/{print $5; exit}')   # 宿主上行网卡，如 eth0
sudo bash wsl/probe2.sh "@/opt/bdvpn/wsl/list_tcp.txt" tcp-all
# 看 results/tcp-all.tsv 里 status == OK 的 id，这些才是能用的
```

### 3.4 生成并拉起池

```bash
sudo UPLINK=eth0 python3 pool_build.py       # → builds/proxies-bangladesh.txt / deploy_pool.sh
sudo UPLINK=eth0 BIND=172.18.0.1 bash builds/deploy_pool.sh
```

脚本对每个可用节点：建 netns → 建 veth 对 → 加 MASQUERADE → 在 netns 内起 openvpn →
起 microsocks 监听 `$BIND:4400x`。

### 3.5 验证出口（这一步决定成败）

```bash
# 宿主席位：必须返回节点 IP，不是宿主公网 IP
ip netns exec bdv0 curl -s --interface tun60 https://ifconfig.me; echo

# 从 Docker 容器内席位：模拟 new-api 的真实视角
docker exec -it <new-api容器名> sh -c \
  'curl -s -x socks5h://172.18.0.1:44000 https://ifconfig.me; echo'
# 期望：103.112.62.240（与 builds/pool-nodes.csv 中 id=872 的出口 IP 一致）
```

**两次结果都必须等于台账里的出口 IP。** 如果容器内返回的是宿主 IP，说明 SOCKS5 没生效
（或 netns 路由没兜住），**立即停池**，否则等于裸奔。

### 3.6 接进 new-api

```bash
# /opt/new-api/.env
TRYINGOPEN_PROXY_FILE=/data/tunneldoom_proxies.txt,/data/bangladesh_proxies.txt
```

清单文件内容（`pool_build.py` 已生成，复制到 `/data/`）：

```
socks5://172.18.0.1:44000  # 872 103.112.62.240 362KB/s
socks5://172.18.0.1:44001  # 871 103.112.62.240 308KB/s
socks5://172.18.0.1:44002  # 869 103.112.63.118 226KB/s
socks5://172.18.0.1:44003  # 851 151.158.158.214 30KB/s
socks5://172.18.0.1:44004  # 878 130.94.50.28    20KB/s
```

多文件用逗号分隔是 new-api 原生支持的能力（见 `relay/channel/tryingopen/proxy_pool.go`），
宿主住宅清单与本池互不影响。

> 若想让本池只服务特定业务，建议在管理端把它单独做成一个池/分组，不要和主池混跑——
> 混跑的结果是慢节点拖累整体 P99。

---

## 4. 运维

| 频率 | 动作 | 命令 |
|---|---|---|
| 每日 1 次 | 重拉节点清单，比对凭据指纹 | `python3 harvest.py && python3 prepare_wsl.py` |
| 每日 1 次 | 串行拨测，淘汰 `AUTH_FAILED`/不可达 | `bash wsl/probe2.sh "@/opt/bdvpn/wsl/list_tcp.txt" daily` |
| 每日 1 次 | 重建清单（可用集合可能变化） | `python3 pool_build.py` |
| 每周 | 出口 IP 复核 | `ip netns exec bdvN curl https://ifconfig.me` |

systemd 常驻示例（每天 04:00 全量刷新）：

```ini
# /etc/systemd/system/bdvpn-refresh.service
[Unit]
Description=Bangladesh VPN pool refresh
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/opt/bdvpn
Environment=UPLINK=eth0
Environment=BIND=172.18.0.1
ExecStart=/bin/bash /opt/bdvpn/builds/teardown_pool.sh
ExecStart=/usr/bin/python3 /opt/bdvpn/harvest.py
ExecStart=/usr/bin/python3 /opt/bdvpn/prepare_wsl.py
ExecStart=/bin/bash /opt/bdvpn/wsl/probe2.sh @/opt/bdvpn/wsl/list_tcp.txt scheduled
ExecStart=/usr/bin/python3 /opt/bdvpn/pool_build.py
ExecStart=/bin/bash /opt/bdvpn/builds/deploy_pool.sh
ExecStartPost=/bin/cp /opt/bdvpn/builds/proxies-bangladesh.txt /data/bangladesh_proxies.txt
```

```ini
# /etc/systemd/system/bdvpn-refresh.timer
[Unit]
Description=Daily Bangladesh VPN pool refresh

[Timer]
OnCalendar=*-*-* 04:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

---

## 5. 故障排查

| 现象 | 根因 | 处置 |
|---|---|---|
| 全节点 `AUTH_FAILED` | 上游账号改密/封号 | 该源已死，整池摘除，等运营方更新 `/list` |
| 全部 `Server poll timeout` | 出口到 443 被 QoS/阻断 | 换出口线路；本池对线路敏感 |
| `Options error: ... register-dns` | 少了 `--pull-filter ignore` | deploy 脚本已内置，确认没被手改 |
| netns 内 `curl` 返回宿主 IP | tun 未建立或默认路由没走 tun | 看 `/var/log/bdv/<id>.log` 是否有 `Initialization Sequence Completed` |
| 容器内 `curl -x socks5` 超时 | microsocks 绑了 `127.0.0.1` 或防火墙未放行 | 改绑 `172.18.0.1`，`ufw allow from 172.18.0.0/16 ...` |
| 速度突然掉到几 KB/s | 同账号其他设备挤占配额 | 见 §2.6，降低并发；或直接从清单移除 |

---

## 6. 实测数据（2026-10-29）

| 项 | 结果 |
|---|---|
| 收割节点 | 37 条 / 30 唯一 IP / 18 国 |
| TCP/443 可拨通 | **5**（872 871 869 851 878） |
| AUTH_FAILED | 9（凭据失效） |
| 443 不可达 | 23 |
| UDP/1194 | 抽样 5/5 不通 |
| 复测一致性 | 5/5 两次独立复测均连通 |
| 带宽区间 | 20 – 362 KB/s |
| 延迟区间 | 1.07 – 1.68 s（到 1.1.1.1） |

---

## 7. 回滚

```bash
bash /opt/bdvpn/builds/teardown_pool.sh     # 杀 microsocks + 删 netns + 清 iptables
# 并从 .env 的 TRYINGOPEN_PROXY_FILE 中移除 /data/bangladesh_proxies.txt
```

回滚后 new-api 会自动回落到清单里的其它池，不需要重启（代理池按需重载文件）。

---

## 8. 合规

节点基础设施与凭据属第三方（CyberGhost 白标转售方），配置文件内含他人私钥。
**投入生产流量前请自行确认授权与合规边界**；本项目仅提供协议层面的互操作能力。
