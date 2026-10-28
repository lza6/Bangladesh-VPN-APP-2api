"""从压测结果生成可用节点池：SOCKS5 清单 + netns 部署脚本 + 节点台账。

输入：raw/list.json、results/*.tsv（只取 OK）
输出（默认 builds/ 下）：
  proxies-bangladesh.txt    socks5://127.0.0.1:<port> 一行一条，供 new-api TRYINGOPEN_PROXY_FILE
  pool-nodes.csv            端口 / 节点 id / 出口 IP / 城市 / 国家 / 延迟 / 带宽
  deploy_pool.sh            netns + openvpn + microsocks 一键拉起（需 root，Linux）
  teardown_pool.sh          清理
"""
import csv
import re
import glob
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "builds")
PORT_BASE = 44000
IFACE_BASE = 60  # netns 内 tun 编号起点


def load_servers():
    with open(os.path.join(BASE, "raw", "list.json"), encoding="utf-8") as f:
        return {str(s["id"]): s for s in json.load(f)}


def load_ok_results():
    """返回 {id: 最佳结果}，只保留 status == OK 的。"""
    best = {}
    for fp in sorted(glob.glob(os.path.join(BASE, "results", "*.tsv")), key=os.path.getmtime):
        for line in open(fp, encoding="utf-8", errors="ignore"):
            p = line.rstrip("\n").split("\t")
            if len(p) < 7 or p[0] in ("id", ""):
                continue
            sid, proto, status = p[0], p[1], p[2]
            if status != "OK":
                continue
            # curl -w 输出可能夹带控制字符（如尾部 \r），只取前导数字
            m = re.match(r"[\d.]+", p[6])
            speed = float(m.group()) if m else 0.0
            lm = re.match(r"[\d.]+", p[5])
            row = {
                "proto": proto,
                "egress_ip": p[4],
                "latency_s": float(lm.group()) if lm else 99.0,
                "speed_Bps": speed,
            }
            if sid not in best or speed > best[sid]["speed_Bps"]:
                best[sid] = row
    return best


def main():
    os.makedirs(OUT, exist_ok=True)
    servers = load_servers()
    ok = load_ok_results()

    rows = []
    for i, (sid, r) in enumerate(sorted(ok.items(), key=lambda kv: -kv[1]["speed_Bps"])):
        s = servers.get(sid, {})
        rows.append({
            "port": PORT_BASE + i,
            "iface": IFACE_BASE + i,
            "ns": f"bdv{i}",
            "id": sid,
            "proto": r["proto"],
            "egress_ip": r["egress_ip"],
            "country": s.get("country_code", ""),
            "city": s.get("city", ""),
            "latency_s": r["latency_s"],
            "kbps": round(r["speed_Bps"] / 1024, 1),
        })

    bind_host = os.environ.get("BIND", "172.18.0.1")
    with open(os.path.join(OUT, "proxies-bangladesh.txt"), "w", encoding="utf-8") as f:
        f.write("# Bangladesh VPN 可用出口（由压测结果生成，勿提交到仓库）\n")
        f.write(f"# 监听地址 {bind_host}：new-api 在 Docker 内，必须用网桥网关而非 127.0.0.1\n")
        for r in rows:
            f.write(f"socks5://{bind_host}:{r['port']}  # {r['id']} {r['city']} {r['egress_ip']} {r['kbps']}KB/s\n")

    with open(os.path.join(OUT, "pool-nodes.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["port", "id", "proto", "egress_ip", "country", "city", "latency_s", "kbps"])
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in w.fieldnames})

    deploy = ["#!/bin/bash", "# 由 pool_build.py 生成：netns 隔离 + openvpn + microsocks", "set -eu",
              'W=/mnt/d/apk-analysis/bd-vpn', 'CONF=$W/wsl/conf', "UPLINK=${UPLINK:?请先 export UPLINK=<宿主网卡名>}",
              "# new-api 跑在 Docker 里，127.0.0.1 是容器自己的命名空间，必须绑网桥网关",
              "BIND=${BIND:-172.18.0.1}",
              "mkdir -p /var/log/bdv", ""]
    teardown = ["#!/bin/bash", "set -u"]
    for r in rows:
        deploy += [
            f"# ---- {r['id']} {r['country'].upper()} {r['city']} → {r['egress_ip']} ----",
            f"ip netns add {r['ns']} 2>/dev/null || true",
            f"ip netns exec {r['ns']} ip link set lo up",
            f"ip link add veth{r['iface']} type veth peer name veth{r['iface']}b 2>/dev/null || true",
            f"ip link set veth{r['iface']}b netns {r['ns']}",
            f"ip addr add 10.{r['iface']}.0.1/24 dev veth{r['iface']} 2>/dev/null || true",
            f"ip -n {r['ns']} addr add 10.{r['iface']}.0.2/24 dev veth{r['iface']}b 2>/dev/null || true",
            f"ip link set veth{r['iface']} up; ip -n {r['ns']} link set veth{r['iface']}b up",
            f"ip -n {r['ns']} route add default via 10.{r['iface']}.0.1 2>/dev/null || true",
            f"iptables -t nat -C POSTROUTING -s 10.{r['iface']}.0.0/24 -o $UPLINK -j MASQUERADE 2>/dev/null || "
            f"iptables -t nat -A POSTROUTING -s 10.{r['iface']}.0.0/24 -o $UPLINK -j MASQUERADE",
            f"ip netns exec {r['ns']} openvpn --config $CONF/{r['id']}.{r['proto']}.ovpn --dev tun{r['iface']} \\",
            '  --pull-filter ignore "register-dns" --pull-filter ignore "block-outside-dns" \\',
            '  --pull-filter ignore "dhcp-release" --pull-filter ignore "dhcp-renew" \\',
            f"  --daemon --log /var/log/bdv/{r['id']}.log",
            f"sleep 8",
            f"ip netns exec {r['ns']} microsocks -i $BIND -p {r['port']} >/dev/null 2>&1 &",
            f"echo \"[{r['id']}] socks5://127.0.0.1:{r['port']} expect egress {r['egress_ip']}\"",
            "",
        ]
        teardown += [f"pkill -f 'microsocks -i .* -p {r['port']}' 2>/dev/null || true",
                     f"ip netns del {r['ns']} 2>/dev/null || true",
                     f"iptables -t nat -D POSTROUTING -s 10.{r['iface']}.0.0/24 -o ${{UPLINK:-eth0}} -j MASQUERADE 2>/dev/null || true"]

    open(os.path.join(OUT, "deploy_pool.sh"), "w", encoding="utf-8").write("\n".join(deploy) + "\n")
    open(os.path.join(OUT, "teardown_pool.sh"), "w", encoding="utf-8").write("\n".join(teardown) + "\n")

    print(f"usable nodes: {len(rows)}")
    for r in rows:
        print(f"  {r['id']:>4} {r['proto']:<4} {r['country']:>3} {r['city'][:22]:<24} {r['egress_ip']:<16} "
              f"{r['kbps']:>8} KB/s  socks5://127.0.0.1:{r['port']}")


if __name__ == "__main__":
    main()

