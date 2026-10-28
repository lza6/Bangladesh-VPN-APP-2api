import json, os, re

BASE = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(BASE, "wsl", "conf")
CRED = os.path.join(BASE, "wsl", "creds")
os.makedirs(CONF, exist_ok=True)
os.makedirs(CRED, exist_ok=True)

servers = json.load(open(os.path.join(BASE, "raw", "list.json"), encoding="utf-8"))
WSL = "/mnt/d/apk-analysis/bd-vpn/wsl"

DROP = ("setenv FORWARD_COMPATIBLE", "setenv opt tls-version-min",
        "setenv PUSH_PEER_INFO", "ns-cert-type", "server-poll-timeout",
        "remote-random", "sndbuf", "rcvbuf")


def build(sid, proto, port, cred_path):
    src = os.path.join(BASE, "raw", "ovpn", f"{sid}.ovpn")
    text = open(src, encoding="utf-8", errors="ignore").read()
    out = []
    for line in text.splitlines():
        lt = line.strip()
        if lt.startswith("remote "):
            continue  # 统一重写
        if lt == "auth-user-pass":
            out.append(f"auth-user-pass {cred_path}")
            continue
        if lt.startswith("proto ") or lt == "float" or lt.startswith("explicit-exit-notify"):
            continue
        if lt.startswith(DROP):
            continue
        out.append(line)
    # 在 client 之后插入 remote/proto
    final = []
    inserted = False
    for line in out:
        final.append(line)
        if line.strip() == "client" and not inserted:
            final.append(f"proto {proto}")
            final.append(f"remote {servers_by_id[sid]['ip']} {port}")
            inserted = True
    if not inserted:
        final = [f"proto {proto}", f"remote {servers_by_id[sid]['ip']} {port}"] + final
    return "\n".join(final) + "\n"


servers_by_id = {s["id"]: s for s in servers}
meta = []
for s in servers:
    sid = s["id"]
    if not os.path.exists(os.path.join(BASE, "raw", "ovpn", f"{sid}.ovpn")):
        continue
    cred_path = f"{WSL}/creds/{sid}.txt"
    open(os.path.join(CRED, f"{sid}.txt"), "w", encoding="utf-8").write(
        f"{s['vpn_username']}\n{s['vpn_password']}\n")
    open(os.path.join(CONF, f"{sid}.udp.ovpn"), "w", encoding="utf-8").write(build(sid, "udp", 1194, cred_path))
    open(os.path.join(CONF, f"{sid}.tcp.ovpn"), "w", encoding="utf-8").write(build(sid, "tcp", 443, cred_path))
    meta.append({"id": sid, "ip": s["ip"], "cc": s["country_code"], "free": s["is_free"]})

json.dump(meta, open(os.path.join(BASE, "wsl", "meta.json"), "w"), indent=1)
print("variants:", len(meta) * 2)
