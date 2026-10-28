import json, sys, time, os
import urllib.request, urllib.error, ssl

BASE = "https://banjsvpns.naruto24.com/api/v1/"
UA = "okhttp/4.12.0"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

os.makedirs("raw", exist_ok=True)


def get(path, timeout=45, retries=3):
    url = BASE + path.lstrip("/")
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
            })
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                data = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    import gzip
                    data = gzip.decompress(data)
                return r.status, data
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except Exception as e:
            last = e
            time.sleep(1 + i)
    return None, str(last).encode()


if __name__ == "__main__":
    st, body = get("list")
    print("status", st, "len", len(body) if body else 0)
    if st == 200:
        open("raw/list.json", "wb").write(body)
        d = json.loads(body)
        print("type", type(d).__name__, "count", len(d) if isinstance(d, (list, dict)) else "?")
        if isinstance(d, list) and d:
            print("keys:", sorted(d[0].keys()))
            print(json.dumps(d[0], indent=2, ensure_ascii=False)[:800])
