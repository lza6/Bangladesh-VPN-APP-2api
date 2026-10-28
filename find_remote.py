import sys, os, re
from androguard.core.dex import DEX

TARGET = re.compile(r"^L?com/dzboot/ovpn/app/data/remote")

files = [f"dex/{x}" for x in sorted(os.listdir("dex")) if x.endswith(".dex")]
found = []
for fp in files:
    try:
        d = DEX(open(fp, "rb").read())
    except Exception as e:
        print("skip", fp, e)
        continue
    for c in d.get_classes():
        name = c.get_name()
        if "data/remote" in name:
            found.append((fp, name))

for fp, n in found:
    print(fp, n)
print("total", len(found))
