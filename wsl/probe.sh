#!/bin/bash
# 批量 OpenVPN 拨号压测：参数 "sid:proto[,sid:proto...]" tag
set -u
W=/mnt/d/apk-analysis/bd-vpn
OUT=$W/results
mkdir -p "$OUT"
LIST="${1:?need list}"
TAG="${2:-run}"
[[ "$LIST" == @* ]] && LIST=$(cat "${LIST:1}")

probe_one() {
  local sid=$1 proto=$2
  local conf="$W/wsl/conf/$sid.$proto.ovpn"
  local log="/tmp/ovpn-$sid-$proto.log"
  local pidf="/tmp/ovpn-$sid-$proto.pid"
  [ -f "$conf" ] || { printf '%s\t%s\tNO_CONFIG\n' "$sid" "$proto"; return; }

  local ifn="tun$(( (sid + RANDOM) % 200 + 10 ))"
  rm -f "$log" "$pidf"
  local t0 t1
  t0=$(date +%s%3N)
  openvpn --config "$conf" --daemon --writepid "$pidf" --log "$log" --dev "$ifn" \
          --pull-filter ignore "register-dns" --pull-filter ignore "block-outside-dns" \
          --pull-filter ignore "dhcp-release" --pull-filter ignore "dhcp-renew" \
          --pull-filter ignore "dhcp-pre-release" --pull-filter ignore "tap-sleep" 2>/dev/null

  local ok="FAIL" i
  for i in $(seq 1 25); do
    grep -q "Initialization Sequence Completed" "$log" 2>/dev/null && { ok="OK"; break; }
    grep -qE "AUTH_FAILED|Options error|Cannot open TUN|Cannot ioctl" "$log" 2>/dev/null && {
      ok=$(grep -oE "AUTH_FAILED|Options error|Cannot open TUN|Cannot ioctl" "$log" | head -1 | tr ' ' '_'); break; }
    sleep 1
  done
  t1=$(date +%s%3N)
  local hs=$(( (t1 - t0) / 1000 ))

  local egress="-" lat="-" spd="-" note="-"
  if [ "$ok" = "OK" ]; then
    egress=$(curl -s -m 10 --interface "$ifn" https://ifconfig.me 2>/dev/null || echo "-")
    lat=$(curl -s -m 8 -o /dev/null -w '%{time_total}' --interface "$ifn" https://1.1.1.1 2>/dev/null || echo "-")
    spd=$(curl -s -m 20 -o /dev/null -w '%{speed_download}' --interface "$ifn" "https://speed.cloudflare.com/__down?bytes=2000000" 2>/dev/null || echo "-")
  else
    note=$(grep -oE "(TLS Error[^,]*|AUTH_FAILED|Server poll timeout|Connection timed out|Connection refused|TLS handshake failed|Cannot ioctl|Options error[^\"]*)" "$log" 2>/dev/null | tail -1 | tr '\t' ' ')
  fi

  [ -f "$pidf" ] && kill "$(cat "$pidf")" 2>/dev/null
  sleep 1
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$sid" "$proto" "$ok" "$hs" "$egress" "$lat" "$spd" "$note"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$sid" "$proto" "$ok" "$hs" "$egress" "$lat" "$spd" "$note" >> "$OUT/$TAG.tsv"
}

printf 'id\tproto\tstatus\tconnect_s\tegress_ip\tlatency_s\tspeed_Bps\tnote\n'
: > "$OUT/$TAG.tsv"
IFS=',' read -ra ITEMS <<< "$LIST"
for it in "${ITEMS[@]}"; do
  probe_one "${it%%:*}" "${it##*:}"
done
