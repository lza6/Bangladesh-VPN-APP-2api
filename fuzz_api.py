import api, time

WORDS = """users user admin login register upload uploads files download downloads
config settings servers server nodes location locations cities countries country
plans plan payment payments order orders coupon device devices notification notifications
push token auth verify health ping version update app home index list get best
request-ip log-connect log-disconnect debug test dev api v1 v2 status stats metrics
graphql docs swagger openapi robots sitemap flag flags banner banners ad ads
premium free trial subscribe subscription profile account accounts me session sessions
report reports analytics track click install video-complete""".split()

found = []
for w in WORDS:
    st, body = api.get(w, timeout=15, retries=0)
    n = len(body) if isinstance(body, bytes) else 0
    if st == 200:
        head = body[:110].decode("utf-8", "ignore").replace("\n", " ")
        found.append((w, n, head))
        print(f"[200] {w:<18} len={n:<6} {head}")
    time.sleep(0.15)

print("\nhits:", [f[0] for f in found])
