# Bangladesh VPN v63.26 逆向报告

> 样本 hash 与体积：`31,152,145` bytes / 29.7 MB
> `versionCode=63` `versionName=63.26` `minSdk=23` `targetSdk=36` `compileSdk=36`
> 包名 `com.banglatech.bangladesh`（白标）｜ 真实类命名空间 `com.dzboot.ovpn.app.*`

---

## 1. 文件结构

| 条目 | 体积 | 说明 |
|---|---|---|
| `classes.dex` ~ `classes7.dex` | 31.9 MB 合计 | 主代码；`classes7.dex` 仅 14 KB（mod 注入壳） |
| `lib/arm64-v8a/libovpn3.so` | 8.7 MB | OpenVPN3 核心（TLS/隧道） |
| `lib/arm64-v8a/libopenvpn.so` | 6.5 MB | OpenVPN 3 编译产物 |
| `lib/arm64-v8a/libosslspeedtest.so` / `libosslutil.so` | 各 4.5 MB | OpenSSL + 测速 |
| `lib/arm64-v8a/libelamods.so` | 752 KB | **modder 注入**：native-jvm 反检测（见 §5） |
| `lib/armeabi-v7a/libelamods.so` | 490 KB | 同上（32 位） |
| `assets/Modder_Hub_Title` / `Modder_Hub_Msg` | 118 / 138 KB | 非文本，实为 `NT Wagner` 字体（用于花体字公告） |
| `assets/El_a credit.xml` | 85 B | 作者署名 + Telegram 频道 |
| `assets/ads.txt` | 115 B | 「MODDED BY @elamods」水印文本 |
| `res/raw/*.json` | — | Lottie 动画（连接中/错误/欢迎），无配置价值 |

---

## 2. 应用骨架：DZBoot OVPN 商业模板

主 Activity、Service、数据层全部落在 `com.dzboot.ovpn.app`：

```
com.dzboot.ovpn.app.ui.main.MainActivity        入口（底部导航：主页/位置/应用分流/通知/设置/升级）
com.dzboot.ovpn.app.ui.intro.IntroActivity      首次引导
com.dzboot.ovpn.app.services.VPNService         VPN 前台服务（Hilt 注入）
com.dzboot.ovpn.app.data.remote                 Retrofit + Gson（BooleanTypeAdapter 兼容 "0"/"1"）
com.dzboot.ovpn.app.data.local.AppDB            Room：servers 表（SQLite）
com.dzboot.ovpn.core.OpenVPNService             OpenVPN3 绑定层
com.dzboot.ovpn.utils.ProfileSigner             配置签名（PKCS#1/PKCS#7 padding 枚举）
```

- 依赖栈：Hilt（DI）、Room（本地缓存）、Retrofit/OkHttp（网络）、Gson（序列化）、Material + mikepenz Iconics（图标）、Lottie（动画）
- 数据流：`u7.a`（Retrofit 接口）→ `z7.e`（Hilt provider）→ Room `servers` 表 → `ServersFragment`/`LocationsFragment` → `VPNService` 读取 `Server` 实体 → 下载/拼装 `.ovpn` → `OpenVPNService` 起隧道
- `Server` 继承 `BaseServer` 并追加本地态：`isFavorite` / `isLastSelected` / `isDefault` / `ping`

---

## 3. 混淆与定位方法

R8 全量混淆，业务类名被压成 `z7.e`、`u7.a`、`r7.k` 等。定位路径（可复用）：

1. 从 `classes*.dex` 提取可打印串，按 `https?://` 正则捞域名 → 命中唯一 API 主机
2. 以包名 `dzboot` 反查类路径 → 确认模板与数据层包结构
3. `grep` 域名所在文件 → `z7/e.java`（Hilt provider，`Retrofit.Builder().baseUrl(...)`）
4. 该文件把 `u7.a.class` 交给 `Proxy.newProxyInstance` → `u7/a.java` 即全部端点定义
5. `@dg.b("...")` = Gson `@SerializedName` → 直接读出 API 字段名

---

## 4. 服务端指纹：CyberGhost 白标

拨号日志中的服务器证书：

```
VERIFY OK: depth=1, C=RO, L=Bucharest, O=CyberGhost S.A., CN=CyberGhost Root CA, emailAddress=info@cyberghost.ro
VERIFY OK: depth=0, CN=karachi-rack403.nodes.gen4.ninja
Control Channel: TLSv1.3, cipher TLS_AES_256_GCM_SHA384, peer certificate: 4096 bits RSA
```

- 节点主机名模式 `*.nodes.gen4.ninja` = CyberGhost 第 4 代节点
- 数据面 `AES-256-GCM`，控制面 TLS 1.3，`tls-crypt`（新代）/`tls-auth`（旧代）
- 客户端证书两种：用户专属（`CN=<user-d>` / `CN=<user-a>`，EC P-384 自签）与 CyberGhost 通用（`CN=BdqSkCqBkG`, O=CyberGhost S.A.）

结论：该 App 是**孟加拉本地运营者 + CyberGhost 转售**的组合；运营方仅维护一个 PHP/Laravel 风格的无鉴权分发接口。

---

## 5. mod 分析（ElaMods）

| 项 | 观察 |
|---|---|
| 原作者水印 | `assets/El_a credit.xml`：`Mσԃ Bყ Eʅα Oϝϝιƈιαʅ` + `t.me/ELAMODS_OFFICAL_STORE` |
| 启动注入 | `libelamods.so` 只导出 `JNI_OnLoad`，内部是 `native_jvm::register_for_class` 反检测桩，覆盖 `com.google.firebase.analytics.connector.*` 等类，用于绕过 Play Integrity / PairIP 校验（原包带 `com.pairip.application.Application`、`com.pairip.licensecheck.LicenseActivity`） |
| 花体字资源 | `Modder_Hub_Title`/`Msg` 被替换成字体文件而非文本，UI 中渲染 modder 公告 |
| 自定义权限 | 清单里声明 `elamods` 权限 |
| Premium 解锁 | 行为层未见服务端会员校验；App 的「会员」仅是 UI 门禁（`is_free`/`free_connect_duration` 由服务端下发），mod 只能解锁界面，**不改变节点凭据有效性** |
| 广告 | AdMob/InMobi/Vungle/Chartboost/UnityAds/广告聚合 SDK 保留（`res/raw` 仍有 omid 脚本），未真正移除 |

> 关键判断：**mod 宣称的 Premium 不等于能用。** 节点能不能连取决于 `vpn_username`/`vpn_password` 在 CyberGhost 侧是否有效，与会话内 UI 是否解锁无关。

---

## 6. 安全问题（服务端，非 APK 自身）

1. **分发接口零鉴权**：`/api/v1/list`、`/api/v1/get?id=` 无 token / 无签名 / 无频率限制，任意人可枚举全部节点并下载含私钥的配置。
2. **配置文件含他人私钥**：`get?id=` 返回 `# Note: this config file contains inline private keys` 明示；配置泄露即账号泄露。
3. **凭据明文下发**：`vpn_password` 以明文出现在列表 JSON 中，且多节点共用同一组账号。
4. **客户端侧无加固**：base URL 硬编码、无证书固定（certificate pinning），易被中间人重定向到恶意节点。
5. **设备指纹收集**：`log-connect` 会上报 `device_id` + `ip`，属最小化行为追踪。

APK 自身：`targetSdk 36`，无过度敏感权限（无 `READ_SMS`/`READ_CONTACTS`/`QUERY_ALL_PACKAGES` 之外的高危项），`SYSTEM_ALERT_WINDOW` 用于悬浮窗提示，属模板常态。

---

## 7. 复现步骤

```powershell
# 1) 解包与字符串侦察
python scan_strings.py            # dex → out/*.strings.txt, out/urls.txt
# 2) 反编译（jadx 1.5.1）
java -cp 'D:\apk-analysis\jadx\lib\*' jadx.cli.JadxCLI -d jadx-out --no-res --no-imports app.apk
# 3) 定位网络层
grep -rn "naruto24" jadx-out/sources
# 4) 收割节点
python harvest.py                 # 37/37 配置
# 5) 实拨压测（WSL root）
wsl -d Ubuntu -u root -e bash wsl/probe.sh "@/mnt/d/apk-analysis/bd-vpn/wsl/list_tcp.txt" tcp-all
# 6) 观测台
$env:DEMO_PORT='8942'; python demo_server.py
```
