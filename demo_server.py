#!/usr/bin/env python3
"""Bangladesh VPN 节点池 demo 服务（标准库实现，无第三方依赖）。

数据源：
  raw/list.json      API /api/v1/list 原始返回
  raw/ovpn/<id>.ovpn  /api/v1/get?id=<id> 下载的配置文件
  results/*.tsv       OpenVPN 拨号压测结果

对外提供：
  GET /                  demo.html
  GET /api/nodes         节点池合并视图
  GET /api/results       最近一次压测结果
  GET /api/config/<id>   脱敏配置摘要
  GET /api/health        服务自检
"""
import json
import os
import re
import glob
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "raw")
RESULTS = os.path.join(BASE, "results")
PORT = int(os.environ.get("DEMO_PORT", "8932"))


def load_servers():
    path = os.path.join(RAW, "list.json")
    if not os.path.exists(path):
        # 未收割时回落到脱敏样例，保证 demo 与测试可独立运行
        alt = os.path.join(BASE, "samples", "sample-list.redacted.json")
        if os.path.exists(alt):
            path = alt
        else:
            return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_results():
    """合并全部压测回合，按 (id, proto) 保留最新一次结论。"""
    merged = {}
    # 按写入时间升序，保证后写的回合覆盖先写的
    for fp in sorted(glob.glob(os.path.join(RESULTS, "*.tsv")), key=os.path.getmtime):
        round_name = os.path.basename(fp)[:-4]
        for line in open(fp, encoding="utf-8", errors="ignore"):
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3 or parts[0] in ("id", ""):
                continue
            sid, proto, status = parts[0], parts[1], parts[2]
            row = {
                "round": round_name,
                "status": status,
                "connect_s": parts[3] if len(parts) > 3 else "",
                "egress_ip": parts[4] if len(parts) > 4 else "",
                "latency_s": parts[5] if len(parts) > 5 else "",
                "speed_Bps": parts[6] if len(parts) > 6 else "",
                "note": parts[7] if len(parts) > 7 else "",
            }
            key = (sid, proto)
            # 成功结论优先，否则取最新
            if key not in merged or row["status"] == "OK" or merged[key]["status"] != "OK":
                merged[key] = row
    return merged


CONFIG_SECTIONS = ("<ca>", "<cert>", "<key>", "<tls-auth>", "<tls-crypt>")


def config_summary(sid):
    path = os.path.join(RAW, "ovpn", f"{sid}.ovpn")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8", errors="ignore") as f:
        text = f.read()
    remotes = []
    directives = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("remote "):
            remotes.append(s[7:])
            continue
        # 跳过 PEM 正文 / hex 密钥 / 注释，只留真实指令行
        if (not s or s.startswith("#") or s.startswith("<") or s.startswith("---")
                or re.fullmatch(r"[A-Za-z0-9+/=]{16,}", s) or re.fullmatch(r"[0-9a-f]{16,}", s)):
            continue
        directives.append(s)
    present = [tag for tag in CONFIG_SECTIONS if tag in text]
    return {
        "size": len(text),
        "remotes": remotes,
        "sections": present,
        "directives": directives,
        "has_inline_key": "<key>" in text,
        "has_tls_auth": "<tls-auth>" in text or "<tls-crypt>" in text,
    }


def build_nodes():
    servers = load_servers()
    results = load_results()
    out = []
    for s in servers:
        sid = str(s["id"])
        tcp = results.get((sid, "tcp"))
        udp = results.get((sid, "udp"))
        ok = any(r and r["status"] == "OK" for r in (tcp, udp))
        alive = any(r and r["status"] in ("OK", "Options_error", "AUTH_FAILED") for r in (tcp, udp))
        out.append({
            "id": sid,
            "country": s.get("country_code", ""),
            "city": s.get("city", ""),
            "ip": s.get("ip", ""),
            "protocol": s.get("protocol", ""),
            "port": s.get("port", ""),
            "username": s.get("vpn_username", ""),
            "is_free": str(s.get("is_free")) == "1",
            "free_minutes": s.get("free_connect_duration", ""),
            "devices": s.get("connected_devices", ""),
            "order": s.get("order", ""),
            "has_config": os.path.exists(os.path.join(RAW, "ovpn", f"{sid}.ovpn")),
            "probe": {"tcp": tcp, "udp": udp},
            "dial_ok": ok,
            "gateway_alive": alive,
        })
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "BdVpnDemo/1.0"

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False, indent=1).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _text(self, body, code=200, ctype="text/html; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", "/index.html"):
            fp = os.path.join(BASE, "demo.html")
            if os.path.exists(fp):
                with open(fp, encoding="utf-8") as f:
                    return self._text(f.read())
            return self._text("demo.html missing", 404, "text/plain; charset=utf-8")
        if p == "/api/health":
            return self._json({"ok": True, "nodes": len(load_servers()), "port": PORT})
        if p == "/api/nodes":
            return self._json(build_nodes())
        if p == "/api/results":
            return self._json({f"{k[0]}:{k[1]}": v for k, v in load_results().items()})
        m = re.fullmatch(r"/api/config/(\d+)", p)
        if m:
            summary = config_summary(m.group(1))
            if summary is None:
                return self._json({"error": "not found"}, 404)
            return self._json(summary)
        return self._json({"error": "not found"}, 404)

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"demo listening on http://127.0.0.1:{PORT}", flush=True)
    srv.serve_forever()
