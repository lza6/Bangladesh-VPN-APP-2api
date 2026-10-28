"""把交付文档中的真实凭据替换为占位符。运行后自检确认零残留。"""
import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE, "raw", "list.json"), encoding="utf-8") as f:
    servers = json.load(f)

users = sorted({s["vpn_username"] for s in servers}, key=len, reverse=True)
passes = sorted({s["vpn_password"] for s in servers}, key=len, reverse=True)

# 稳定映射：同一凭据始终映射到同一占位符
user_map = {u: f"<user-{chr(97 + i)}>" for i, u in enumerate(users)}
pass_map = {p: f"<pass-{chr(97 + i)}>" for i, p in enumerate(passes)}

TARGETS = ["README.md", "docs/PROTOCOL.md", "docs/REVERSE_REPORT.md",
           "docs/NEWAPI_INTEGRATION.md", "demo_server.py", "demo.html",
           "pool_build.py", "api.py", "harvest.py", "prepare_wsl.py"]

changed = []
for rel in TARGETS:
    path = os.path.join(BASE, rel)
    if not os.path.exists(path):
        continue
    with open(path, encoding="utf-8") as f:
        text = f.read()
    orig = text
    for p, placeholder in pass_map.items():
        text = text.replace(p, placeholder)
    for u, placeholder in user_map.items():
        # 用前后不接字母数字的断言，避免短账号名误伤长账号名（长串已先替换）
        text = re.sub(r"(?<![A-Za-z0-9_])" + re.escape(u) + r"(?![A-Za-z0-9_])", placeholder, text)
    if text != orig:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        changed.append(rel)

print("rewritten:", changed)

# 自检
leaks = []
for rel in TARGETS:
    path = os.path.join(BASE, rel)
    if not os.path.exists(path):
        continue
    with open(path, encoding="utf-8") as f:
        text = f.read()
    for u in users:
        if re.search(r"(?<![A-Za-z0-9_])" + re.escape(u) + r"(?![A-Za-z0-9_])", text):
            leaks.append((rel, "user", u))
    for p in passes:
        if p in text:
            leaks.append((rel, "pass", p))

print("leaks:", leaks if leaks else "NONE")
