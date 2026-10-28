"""生成可公开的脱敏样例：节点列表 + OpenVPN 配置结构。"""
import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "samples")
os.makedirs(OUT, exist_ok=True)

with open(os.path.join(BASE, "raw", "list.json"), encoding="utf-8") as f:
    servers = json.load(f)

users = sorted({s["vpn_username"] for s in servers}, key=len, reverse=True)
passes = sorted({s["vpn_password"] for s in servers}, key=len, reverse=True)


def scrub(text):
    for i, p in enumerate(passes):
        text = text.replace(p, f"<pass-{chr(97 + i)}>")
    for i, u in enumerate(users):
        text = re.sub(r"(?<![A-Za-z0-9_])" + re.escape(u) + r"(?![A-Za-z0-9_])", f"<user-{chr(97 + i)}>", text)
    for ip in sorted({s["ip"] for s in servers}, key=len, reverse=True):
        text = text.replace(ip, "203.0.113.10")
    return text


# 1) 列表样例：3 条，IP 用文档保留段（203.0.113.0/24 RFC 5737）
sample = []
for i, s in enumerate(servers[:3]):
    row = dict(s)
    row["vpn_username"] = f"<user-{chr(97 + i)}>"
    row["vpn_password"] = f"<pass-{chr(97 + i)}>"
    row["ip"] = f"203.0.113.{10 + i}"
    row["connected_devices"] = "0"
    sample.append(row)

with open(os.path.join(OUT, "sample-list.redacted.json"), "w", encoding="utf-8") as f:
    json.dump(sample, f, indent=2, ensure_ascii=False)

# 2) 配置样例：保留结构与指令，正文全部替换
src = os.path.join(BASE, "raw", "ovpn", "869.ovpn")
if os.path.exists(src):
    with open(src, encoding="utf-8", errors="ignore") as f:
        conf = f.read()
    conf = scrub(conf)
    conf = re.sub(r"remote \S+ (\d+)", r"remote 203.0.113.10 \1", conf)
    # 替换 PEM / 静态密钥正文，以及注释中的 base64 证书块
    out_lines = []
    block = None
    for line in conf.splitlines():
        s = line.strip()
        m = re.match(r"<(ca|cert|key|tls-auth|tls-crypt)>", s)
        if m:
            block = m.group(1)
            out_lines.append(line)
            out_lines.append(f"[{block.upper()} BODY REDACTED]")
            continue
        if s.startswith("</"):
            block = None
            out_lines.append(line)
            continue
        if block:
            continue
        # 注释行里的 base64 证书/密钥同样清掉（含 PEM 头尾标记，避免被扫描器误报）
        if s.startswith("#") and ("-----BEGIN" in s or "-----END" in s):
            out_lines.append("# [PEM MARKER REDACTED]")
            continue
        if s.startswith("#") and re.search(r"[A-Za-z0-9+/]{40,}={0,2}$", s):
            out_lines.append("# [BASE64 REDACTED]")
            continue
        out_lines.append(line)
    with open(os.path.join(OUT, "sample-client.redacted.ovpn"), "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")

print("samples:", sorted(os.listdir(OUT)))
