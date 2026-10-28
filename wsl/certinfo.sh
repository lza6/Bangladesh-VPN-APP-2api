#!/bin/bash
cd /mnt/d/apk-analysis/bd-vpn
for f in raw/ovpn/*.ovpn; do
  awk '/<cert>/{flag=1;next}/<\/cert>/{flag=0}flag' "$f" > /tmp/c.pem
  subj=$(openssl x509 -in /tmp/c.pem -noout -subject 2>/dev/null | sed 's/^subject=//')
  echo -e "$(basename "$f" .ovpn)\t${subj:-NO_CERT}"
done
