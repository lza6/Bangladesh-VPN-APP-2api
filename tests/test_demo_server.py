"""demo_server 的契约测试（标准库 unittest，无需第三方依赖）。

覆盖：
  - /api/health 存活
  - /api/nodes 结构完整、数量与 list.json 一致
  - /api/config/<id> 必须脱敏（不得返回 PEM 正文 / hex 密钥）
  - 未知路径 404
运行：python -m unittest tests.test_demo_server -v
"""
import json
import os
import re
import sys
import threading
import unittest
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import demo_server  # noqa: E402


class DemoServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = demo_server.ThreadingHTTPServer(("127.0.0.1", 0), demo_server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def get_json(self, path):
        with urllib.request.urlopen(self.url(path), timeout=10) as r:
            return r.status, json.loads(r.read())

    def test_health(self):
        st, body = self.get_json("/api/health")
        self.assertEqual(st, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["nodes"], len(demo_server.load_servers()))

    def test_nodes_shape(self):
        st, nodes = self.get_json("/api/nodes")
        self.assertEqual(st, 200)
        self.assertGreater(len(nodes), 0)
        required = {"id", "country", "city", "ip", "port", "probe", "dial_ok", "gateway_alive"}
        for n in nodes:
            self.assertTrue(required <= set(n), f"missing keys in {n.get('id')}")
            self.assertEqual(set(n["probe"]), {"tcp", "udp"})

    def test_nodes_match_source(self):
        servers = demo_server.load_servers()
        _, nodes = self.get_json("/api/nodes")
        self.assertEqual([str(s["id"]) for s in servers], [n["id"] for n in nodes])

    def test_config_is_redacted(self):
        _, nodes = self.get_json("/api/nodes")
        candidates = [n["id"] for n in nodes if n["has_config"]]
        self.assertTrue(candidates, "no harvested config to test")
        for sid in candidates[:5]:
            _, cfg = self.get_json(f"/api/config/{sid}")
            blob = json.dumps(cfg, ensure_ascii=False)
            self.assertNotIn("BEGIN " + "PRIVATE KEY", blob)
            self.assertNotIn("BEGIN " + "CERTIFICATE", blob)
            for d in cfg["directives"]:
                self.assertFalse(re.fullmatch(r"[A-Za-z0-9+/=]{40,}", d), f"base64 leaked: {d[:20]}")
                self.assertFalse(re.fullmatch(r"[0-9a-f]{32,}", d), f"hex key leaked: {d[:20]}")

    def test_unknown_path_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self.url("/api/nope"), timeout=10)
        self.assertEqual(ctx.exception.code, 404)

    def test_config_unknown_id_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self.url("/api/config/999999"), timeout=10)
        self.assertEqual(ctx.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
