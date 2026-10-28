import zipfile, re, sys, os, collections

TARGETS = [
    r"C:\Users\Administrator.DESKTOP-EGNE9ND\Desktop\逆向产物\INDONESIA VPN v1.8.5.7 b1857 (Premium by @ElaMods).apk",
    r"C:\Users\Administrator.DESKTOP-EGNE9ND\Desktop\逆向产物\RUSSIA VPN v4.2.8.6 b4286 (Premium by @ElaMods).apk",
    r"C:\Users\Administrator.DESKTOP-EGNE9ND\Desktop\逆向产物\SuperVPN Pro_2.0.9_HEROMODS.apk",
]
PAT = re.compile(rb"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]{4,}")
SKIP = ("google", "android", "schemas", "w3.org", "facebook", "inmobi", "unity3d", "vungle",
        "chartboost", "adcolony", "applovin", "doubleclick", "crashlytics", "gstatic",
        "cloudflare", "github.com/google", "apache.org", "json-schema", "fabric.io",
        "smartdigimkt", "secmtp", "tramini", "mossturbo", "unioneeu", "spadsync", "naruto24.com/")


def scan(apk):
    z = zipfile.ZipFile(apk)
    hits = collections.Counter()
    for n in z.namelist():
        if not n.endswith(".dex"):
            continue
        data = z.read(n)
        for m in PAT.finditer(data):
            u = m.group(0).decode("ascii", "ignore")
            if any(s in u for s in SKIP):
                continue
            hits[u] += 1
    return hits


for t in TARGETS:
    if not os.path.exists(t):
        print("MISSING", t)
        continue
    print("=" * 70)
    print(os.path.basename(t))
    h = scan(t)
    for u, c in h.most_common(25):
        print(f"  {c}\t{u}")
