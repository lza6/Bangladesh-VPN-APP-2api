# Bangladesh VPN · APK 逆向与节点池评估

![status](https://img.shields.io/badge/status-research%20archive-blue)
![platform](https://img.shields.io/badge/platform-Android%20%7C%20OpenVPN-informational)
![protocol](https://img.shields.io/badge/protocol-OpenVPN%20TLS1.3%2FAES--256--GCM-green)

> 样本：`Bangladesh VPN v63.26 b63 (Premium By ElaMods).apk`（29.7 MB / 31,152,145 bytes）
> 包名：`com.banglatech.bangladesh`（白标）｜ 真实引用类：`com.dzboot.ovpn.app.*` → 商业模板 **DZBoot OVPN**
> 上游：**CyberGhost** 白标转售（节点证书 `CN=*.nodes.gen4.ninja`、`O=CyberGhost S.A.`）

---

## 一句话结论

这个 App 的**节点分发接口完全无鉴权**，可直接拉出 37 条 OpenVPN 配置（含内联私钥、证书有效期到 2036）；但节点是第三方 CyberGhost 资源 + 共享账号，**37 条中只有 5 条当前能真正拨通**，带宽 0.02–0.36 MB/s。

定位：**可复现的研究样本 + 可观测小池**，不是可长期依赖的生产节点源。

---

## 关键结论速查

| 问题 | 答案 |
|---|---|
| 有没有隐藏 API？ | 有，`https://banjsvpns.naruto24.com/api/v1/`，**零鉴权** |
| 能拉多少节点？ | `GET /list` → 37 条，18 国，30 个唯一出口 IP |
| 能拉配置文件吗？ | 能，`GET /get?id=<id>` → 6–10 KB 完整 `.ovpn`（inline CA + 客户端证书 + 私钥 + tls-auth/tls-crypt） |
| 真能连上吗？ | TCP/443 **5 条**可拨通（两次独立复测均通）；UDP/1194 抽样 5/5 全不通 |
| 为什么有些报 AUTH_FAILED？ | TLS 与证书全过、仅账号被拒 → 凭据失效（9 条） |
| 适合做生产代理池吗？ | **不适合**：共享他人账号、出口多为数据中心 IP（部分已被 ip-marked `proxy=true`）、带宽不足 |

---

## 逆向链路

```
APK (7 dex, 31.9 MB)
  └─ classes*.dex 字符串 → 唯一 API 主机：banjsvpns.naruto24.com
      └─ grep 命中 z7/e.java（Hilt provider，Retrofit.Builder().baseUrl(...)）
          └─ 该文件把 u7.a.class 交给 Proxy.newProxyInstance
              └─ u7/a.java = 全部端点（混淆名，注解即路径）
                  └─ @dg.b("...") = Gson @SerializedName → API 字段名
```

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/v1/list` | GET | 节点清单（`p`/`v` 参数被服务端忽略） |
| `/api/v1/get?id=<sid>` | GET | OpenVPN 客户端配置（纯文本，用户锁定） |
| `/api/v1/request-ip` | GET | 回显调用方公网 IP |
| `/api/v1/best?s=<sid>` | GET | 推荐节点 id（裸整数） |
| `/api/v1/log-connect` / `log-disconnect` | POST | 上报 `server_id` + `device_id` + `ip` |

完整字段语义、配置结构、最小复现骨架见 [`docs/PROTOCOL.md`](docs/PROTOCOL.md)。

---

## 实测数据

环境：WSL2 Ubuntu + OpenVPN 2.6.19（root），本机出口为中国大陆家宽。

### 两轮全量压测（37 节点）

| 通道 | OK | AUTH_FAILED | 不可达 | 判断 |
|---|---|---|---|---|
| `443/tcp` | **5** | 9 | 23 | 唯一可用通道 |
| `1194/udp` | **0** | — | 抽样 5/5 不通 | 本机出口 UDP 1194 被丢包，含孟加拉本地节点 |

`AUTH_FAILED` 的 9 条（`860 776 861 699 798 801 802 805 807`）说明 TLS 握手、证书校验全部通过，仅账号被拒 —— 是**凭据失效**，不是网络问题。

### 可拨通节点（两次独立复测均连通）

| id | 国家 | 城市（运营方标注） | 出口 IP | ASN | 延迟 | 速率 |
|---|---|---|---|---|---|---|
| 872 | 🇧🇩 BD | High Speed Alaap/Dial App | 103.112.62.240 | AS150156 99IT | 1.07 s | **362 KB/s** |
| 871 | 🇧🇩 BD | Alaap/Dial App | 103.112.62.240 | AS150156 99IT | 1.43 s | 308 KB/s |
| 869 | 🇧🇩 BD | Alaap/Dial App | 103.112.63.118 | AS150156 99IT | 1.36 s | 226 KB/s |
| 851 | 🇧🇩 BD | Nagad/Cellfin Used | 151.158.158.214 | AS149783 Intelwebhost | 1.68 s | 30 KB/s |
| 878 | 🇵🇭 PH | Manila | 130.94.50.28 | AS154177 Light Node | 1.20 s | 20 KB/s |

补充判断：

- `Intelwebhost` 被 ip-api 标记 `hosting=true`（数据中心）；`M247`（Karachi）、`Colocation America`（Singapore）节点被标记 `proxy=true`，信誉差。
- 全部节点共用 4 组 CyberGhost 账号，并发会抢占同一账号配额。
- 延迟 1–1.7 s 偏高（TCP over TCP 叠加跨境），只适合轻量 API 转发。

---

## 快速开始

```powershell
# 1) 收割节点与配置（写入 raw/，已被 .gitignore 排除）
python harvest.py                 # → raw/list.json + raw/ovpn/*.ovpn

# 2) 生成 udp/tcp 双变体配置（注入凭据路径）
python prepare_wsl.py             # → wsl/conf/*.{udp,tcp}.ovpn + wsl/creds/*.txt

# 3) 实拨压测（需要 root，因为要建 tun）
wsl -d Ubuntu -u root -e bash wsl/probe2.sh "@/mnt/d/apk-analysis/bd-vpn/wsl/list_tcp.txt" tcp-all

# 4) 生成可用池（SOCKS5 清单 + netns 部署脚本）
python pool_build.py              # → builds/proxies-bangladesh.txt / deploy_pool.sh

# 5) 观测台
$env:DEMO_PORT='8942'; python demo_server.py     # http://127.0.0.1:8942

# 6) 契约测试
python -m unittest tests.test_demo_server -v
```

---

## 仓库结构

```
.
├── README.md                       # 本文件
├── docs/
│   ├── PROTOCOL.md                 # 端点表 / 字段语义 / 配置结构 / 最小骨架 / 五个坑
│   ├── REVERSE_REPORT.md           # 完整逆向过程（结构→混淆→网络层→服务器指纹→mod 分析）
│   └── NEWAPI_INTEGRATION.md       # 接入 new-api 的实操步骤与故障排查
├── demo_server.py / demo.html      # 节点池观测台（标准库，零依赖，含脱敏）
├── tests/test_demo_server.py       # 6 条契约测试（结构/脱敏/404）
├── api.py                          # API 客户端（gzip + 重试 + 无 SNI 校验）
├── harvest.py                      # 批量下载 37 份配置（断点续传）
├── prepare_wsl.py                  # 生成 udp/tcp 双变体 + 凭据文件
├── pool_build.py                   # 压测结果 → SOCKS5 清单 + netns 部署脚本
├── wsl/probe.sh / probe2.sh        # OpenVPN 实拨压测（v2 支持失败快速判定）
├── samples/                        # 脱敏样例（列表 + 配置结构）
├── results/                        # 压测原始 TSV（证据）
└── shots/                          # demo 截图
```

未入库（`.gitignore`）：`raw/`（真实配置与凭据）、`wsl/conf/`、`wsl/creds/`、反编译产物。

---

## 五个必避坑

1. **服务端会 push Windows 专用选项**（`register-dns` / `dhcp-release` / `dhcp-renew` / `block-outside-dns`），桌面 OpenVPN 2.6 直接 `Options error` 中断 —— 看起来像认证失败，其实认证已过。必须 `--pull-filter ignore "..."`。
2. **`get?id=` 新代配置首行是 `client` 不是 `#`**：用 `startswith("#")` 判空会误报 10/37 下载失败。
3. **`list` 的 `p`/`v` 参数被忽略**：带任何值返回同一集合，别指望翻页。
4. **UDP 无响应 ≠ 节点死**：OpenVPN 只在收到包时回；必须用 openvpn 客户端实测。TCP/1194 `REFUSED` 也是正常现象。
5. **三态必须区分**：`AUTH_FAILED`（凭据废）/ `Options error`（认证过但 push 不兼容）/ `Server poll timeout`（网络不通）。混在一起会把可用节点判死。

---

## 对接 new-api

见 [`docs/NEWAPI_INTEGRATION.md`](docs/NEWAPI_INTEGRATION.md) —— 含 netns + SOCKS5 实施方案、`TRYINGOPEN_PROXY_FILE` 配置、健康探测与摘除策略、故障排查表。

---

## 合规与限用

本项目仅用于**协议互操作研究与容量评估**。

- 节点基础设施属第三方（CyberGhost 白标转售），凭据非本项目所有；
- `raw/` 下的配置文件包含**他人私钥**，仓库已排除，不得再分发；
- 对目标服务施压、将其节点投入商业流量均可能违反服务条款；
- 文中所有账号、密码、私钥均已脱敏为 `<user-x>` / `<pass-x>` / `[BODY REDACTED]`。

仅限授权安全研究与学习用途。使用者自行承担合规责任。
