import re, sys, os, collections

PAT_STR = re.compile(rb"[\x20-\x7e]{5,}")
URL = re.compile(rb"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]{4,}")

def dump(path):
    data = open(path, "rb").read()
    return data

os.makedirs("out", exist_ok=True)
urls = collections.Counter()
hosts = collections.Counter()
paths = collections.Counter()

for dex in sorted(x for x in os.listdir("dex") if x.endswith(".dex")):
    data = dump(os.path.join("dex", dex))
    strs = [m.group(0).decode("ascii", "ignore") for m in PAT_STR.finditer(data)]
    open(f"out/{dex}.strings.txt", "w", encoding="utf-8").write("\n".join(strs))
    for m in URL.finditer(data):
        u = m.group(0).decode("ascii", "ignore")
        urls[u] += 1
    for s in strs:
        if s.startswith("/api") or "/api/" in s:
            paths[s] += 1

with open("out/urls.txt", "w", encoding="utf-8") as f:
    for u, c in urls.most_common():
        f.write(f"{c}\t{u}\n")

with open("out/api_paths.txt", "w", encoding="utf-8") as f:
    for p, c in paths.most_common():
        f.write(f"{c}\t{p}\n")

print("urls:", len(urls), "api paths:", len(paths))
