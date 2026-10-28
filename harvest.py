import json, os, re, time
import api

os.makedirs("raw/ovpn", exist_ok=True)
servers = json.load(open("raw/list.json", encoding="utf-8"))

manifest = []
for s in servers:
    sid = s["id"]
    fp = f"raw/ovpn/{sid}.ovpn"
    if os.path.exists(fp) and os.path.getsize(fp) > 500:
        manifest.append((sid, s, os.path.getsize(fp), "cached"))
        continue
    st, body = api.get(f"get?id={sid}", timeout=40, retries=3)
    if st == 200 and body and body.lstrip().startswith(b"#"):
        open(fp, "wb").write(body)
        manifest.append((sid, s, len(body), "ok"))
    else:
        manifest.append((sid, s, 0, f"fail:{st}"))
    time.sleep(0.3)

ok = sum(1 for m in manifest if m[3] in ("ok", "cached"))
print(f"configs downloaded: {ok}/{len(servers)}")
for sid, s, size, state in manifest:
    if state not in ("ok", "cached"):
        print("  MISS", sid, s["ip"], state)

# inspect one
sample = "raw/ovpn/810.ovpn"
if os.path.exists(sample):
    t = open(sample, encoding="utf-8", errors="ignore").read()
    print("\n=== sections present ===")
    for tag in ("<ca>", "</ca>", "<cert>", "<key>", "<tls-auth>", "<tls-crypt>"):
        print(f"  {tag}: {tag in t}")
    print("\n=== client directives ===")
    for line in t.splitlines():
        if line and not line.startswith("#") and not line.startswith(" ") and "<" not in line:
            print("  ", line)
    print("\n=== remote lines ===")
    for line in t.splitlines():
        if line.startswith("remote ") or line.startswith("proto ") or line.startswith("port "):
            print("  ", line)
