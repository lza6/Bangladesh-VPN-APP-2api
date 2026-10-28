# Bangladesh VPN · 协议与节点池实现手册

> 目标 APK：`Bangladesh VPN v63.26 b63 (Premium By ElaMods).apk`
> 包名 `com.banglatech.bangladesh`（白标），真实引用类 `com.dzboot.ovpn.app.*` → 商业模板 **DZBoot OVPN**
> 服务端上游：**CyberGhost** 白标转售（节点证书 `CN=*.nodes.gen4.ninja`, `O=CyberGhost S.A.`）

---

## 1. 端点总表

Base URL（硬编码于 `z7/e.java:83`）：

```
https://banjsvpns.naruto24.com/api/v1/
```

Retrofit 接口定义 `u7/a.java`（混淆名），六个端点：

| 方法 | 路径 | 参数 | 返回 | 鉴权 |
|---|---|---|---|---|
| GET | `list` | `p`（设备/包标识，实测被忽略）、`v`（版本） | `Server[]` JSON | 无 |
| GET | `get` | `id`（节点 id） | OpenVPN 客户端配置纯文本（含 inline CA/cert/key/tls-crypt） | 无 |
| GET | `request-ip` | — | `{"key":"ip","value":"<调用方公网 IP>"}` | 无 |
| GET | `best` | `s`（当前节点 id） | 推荐节点 id（裸整数） | 无 |
| POST | `log-connect` | form: `server_id`,`device_id`,`ip`,`is_auto` | 空体 200 | 无 |
| POST | `log-disconnect` | form: `server_id`,`device_id` | 空体 200 | 无 |

**全部端点无鉴权、无签名、无 token、无速率限制标记。** 任意客户端可直接拉取全量节点与含私钥的配置文件。

---

## 2. `list` 响应字段

```json
{
  "id": "810",
  "country_code": "us",
  "city": "Allah Always Watching You",
  "ip": "184.174.96.147",
  "protocol": "udp",
  "port": "1194",
  "vpn_username": "<user-a>",
  "vpn_password": "<pass-d>",
  "is_free": "1",
  "order": "0",
  "use_file": "1",
  "free_connect_duration": "30",
  "connected_devices": "8364"
}
```

| 字段 | 语义 | 备注 |
|---|---|---|
| `id` | 节点主键，`get?id=` 的入参 | int 字符串 |
| `country_code` | ISO-3166 alpha-2 | 用于国旗与分组 |
| `ip` / `port` / `protocol` | 直连参数 | 实测全部 `udp` / `1194`，配置文件内含 `443 tcp` 备线 |
| `vpn_username` / `vpn_password` | OpenVPN `auth-user-pass` 凭据 | CyberGhost 账号，多节点共用同一组 |
| `is_free` | `1` 免费（限时）`0` 会员 | `free_connect_duration` 单位分钟，0 表示不限时但需会员 |
| `use_file` | 恒为 `1`：客户端必须走 `get?id=` 拉取配置 | 非 `1` 时客户端自拼配置 |
| `connected_devices` | 该节点当前连接设备数 | 可作为负载排序依据 |

---

## 3. `get?id=` 返回的配置结构

返回纯文本 OpenVPN 客户端配置，约 6–10 KB，两种代际形态：

**旧代（id 601–830 区间常见）**
```
cipher AES-256-CBC
client / server-poll-timeout 4 / nobind / dev tun / dev-type tun
ns-cert-type server
reneg-sec 604800 / sndbuf 100000 / rcvbuf 100000
auth-user-pass / comp-lzo no / verb 3
<ca>…</ca>  <cert>…</cert>  <key>…</key>  <tls-auth>…</tls-auth>  key-direction 1
remote <ip> 1194 udp   (重复 6 次)
remote <ip> 443 tcp    (1 次备线)
```

**新代（id 851+ 等）**
```
client / dev tun / proto udp / remote-cert-tls server / tls-version-min 1.2
tun-mtu 1420 / auth-user-pass / push-peer-info
<ca>…</ca>  <cert>…</cert>  <key>…</key>  <tls-crypt>…</tls-crypt>
```

要点：

- 客户端证书为**用户锁定**（`# OVPN_ACCESS_SERVER_USERNAME=<user>`，cert CN 与 `vpn_username` 一致）
- 私钥内联，配置即凭证，泄露等于账号泄露
- 部分节点（623 / 699 / 792 / 798 / 801 / 802 / 805 / 807）返回的是 **CyberGhost 原生通用配置**（cert `CN=BdqSkCqBkG`, O=CyberGhost S.A.），不是用户专属

---

## 4. 接入条件（实测结论）

1. **必须保留 `auth-user-pass` 并另外提供凭据**：配置里不带密码，密码由 `vpn_username`/`vpn_password` 提供。
2. **服务端会 push Windows 专用选项**，桌面/移动 Linux 客户端会 `Options error` 中断：
   ```
   Unrecognized option in [PUSH-OPTIONS]: register-dns / dhcp-release / dhcp-renew / block-outside-dns
   ```
   解决：启动时追加
   ```
   --pull-filter ignore "register-dns"
   --pull-filter ignore "block-outside-dns"
   --pull-filter ignore "dhcp-release"
   --pull-filter ignore "dhcp-renew"
   --pull-filter ignore "dhcp-pre-release"
   --pull-filter ignore "tap-sleep"
   ```
   不忽略则表现为「认证已通过但连接立即崩」，极易误判成账号失效。
3. **443/tcp 备线可用**：部分节点的 UDP/1194 被丢包，仅 `443/tcp` 可拨通。
4. **同一 IP 多 id**：`873`/`874` 同 IP 不同凭据，属不同 profile，拨号结果可能不同。

---

## 5. 最小复现骨架

```python
import json, urllib.request

BASE = "https://banjsvpns.naruto24.com/api/v1/"

def get(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "okhttp/4.12.0"})
    return urllib.request.urlopen(req, timeout=30).read()

servers = json.loads(get("list"))
for s in servers:
    conf = get(f"get?id={s['id']}")
    open(f"{s['id']}.ovpn", "wb").write(conf)
```

```bash
# 拨号（Linux / WSL root）
printf '%s\n%s\n' "$USER_NAME" "$USER_PASS" > cred
sed -i "s|^auth-user-pass$|auth-user-pass $PWD/cred|" "$SID.ovpn"
openvpn --config "$SID.ovpn" --dev tun10 --pull-filter ignore "register-dns" \
        --pull-filter ignore "dhcp-release" --pull-filter ignore "dhcp-renew" \
        --pull-filter ignore "block-outside-dns" --daemon --log run.log
curl --interface tun10 https://ifconfig.me
```

---

## 6. 五个必避坑

1. **`get` 的返回不以 `#` 开头**：新代配置首行是 `client`；用 `startswith("#")` 判空会误判 10/37 个节点下载失败。
2. **`list` 的参数 `p`/`v` 被忽略**：带任何值返回同一集合（仅 `connected_devices` 实时波动），不要试图用它们翻页或拿更多节点。
3. **`connected_devices` 每次请求都变**：对比两次响应会得到不同 sha，别把它当作「内容已变更」。
4. **UDP 探测不可靠**：UDP/1194 无响应 ≠ 节点死（OpenVPN 只在收到正确 reset 包时回包）；必须用 openvpn 客户端实测。反之 TCP/1194 报 `REFUSED` 是正常现象。
5. **认证成功与连接建立是两个阶段**：出现 `PUSH_REPLY`/`AUTH_FAILED` 都说明 TLS 与凭据阶段已过；`Options error` 说明认证过了但 push 选项不兼容——三者必须区分，否则会把可用节点判死。

---

## 7. 合规声明

本文仅记录协议结构与可达性测试方法，用于互操作性与容量评估。节点基础设施属第三方（CyberGhost 白标转售），凭据非测试方所有；配置内含他人私钥，不得再分发。生产使用须取得服务方授权。
