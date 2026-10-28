#!/bin/bash
# 由 pool_build.py 生成：netns 隔离 + openvpn + microsocks
set -eu
W=/mnt/d/apk-analysis/bd-vpn
CONF=$W/wsl/conf
UPLINK=${UPLINK:?请先 export UPLINK=<宿主网卡名>}
# new-api 跑在 Docker 里，127.0.0.1 是容器自己的命名空间，必须绑网桥网关
BIND=${BIND:-172.18.0.1}
mkdir -p /var/log/bdv

# ---- 872 BD High Speed Alaap/Dial App Used → 103.112.62.240 ----
ip netns add bdv0 2>/dev/null || true
ip netns exec bdv0 ip link set lo up
ip link add veth60 type veth peer name veth60b 2>/dev/null || true
ip link set veth60b netns bdv0
ip addr add 10.60.0.1/24 dev veth60 2>/dev/null || true
ip -n bdv0 addr add 10.60.0.2/24 dev veth60b 2>/dev/null || true
ip link set veth60 up; ip -n bdv0 link set veth60b up
ip -n bdv0 route add default via 10.60.0.1 2>/dev/null || true
iptables -t nat -C POSTROUTING -s 10.60.0.0/24 -o $UPLINK -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 10.60.0.0/24 -o $UPLINK -j MASQUERADE
ip netns exec bdv0 openvpn --config $CONF/872.tcp.ovpn --dev tun60 \
  --pull-filter ignore "register-dns" --pull-filter ignore "block-outside-dns" \
  --pull-filter ignore "dhcp-release" --pull-filter ignore "dhcp-renew" \
  --daemon --log /var/log/bdv/872.log
sleep 8
ip netns exec bdv0 microsocks -i $BIND -p 44000 >/dev/null 2>&1 &
echo "[872] socks5://127.0.0.1:44000 expect egress 103.112.62.240"

# ---- 871 BD এইটাতে আলাপ এবং ডাইল এ্যাপ্স ব্যাবহার করা যায় → 103.112.62.240 ----
ip netns add bdv1 2>/dev/null || true
ip netns exec bdv1 ip link set lo up
ip link add veth61 type veth peer name veth61b 2>/dev/null || true
ip link set veth61b netns bdv1
ip addr add 10.61.0.1/24 dev veth61 2>/dev/null || true
ip -n bdv1 addr add 10.61.0.2/24 dev veth61b 2>/dev/null || true
ip link set veth61 up; ip -n bdv1 link set veth61b up
ip -n bdv1 route add default via 10.61.0.1 2>/dev/null || true
iptables -t nat -C POSTROUTING -s 10.61.0.0/24 -o $UPLINK -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 10.61.0.0/24 -o $UPLINK -j MASQUERADE
ip netns exec bdv1 openvpn --config $CONF/871.tcp.ovpn --dev tun61 \
  --pull-filter ignore "register-dns" --pull-filter ignore "block-outside-dns" \
  --pull-filter ignore "dhcp-release" --pull-filter ignore "dhcp-renew" \
  --daemon --log /var/log/bdv/871.log
sleep 8
ip netns exec bdv1 microsocks -i $BIND -p 44001 >/dev/null 2>&1 &
echo "[871] socks5://127.0.0.1:44001 expect egress 103.112.62.240"

# ---- 869 BD এইটাতে আলাপ এবং ডাইল এ্যাপ্স ব্যাবহার করা যায় → 103.112.63.118 ----
ip netns add bdv2 2>/dev/null || true
ip netns exec bdv2 ip link set lo up
ip link add veth62 type veth peer name veth62b 2>/dev/null || true
ip link set veth62b netns bdv2
ip addr add 10.62.0.1/24 dev veth62 2>/dev/null || true
ip -n bdv2 addr add 10.62.0.2/24 dev veth62b 2>/dev/null || true
ip link set veth62 up; ip -n bdv2 link set veth62b up
ip -n bdv2 route add default via 10.62.0.1 2>/dev/null || true
iptables -t nat -C POSTROUTING -s 10.62.0.0/24 -o $UPLINK -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 10.62.0.0/24 -o $UPLINK -j MASQUERADE
ip netns exec bdv2 openvpn --config $CONF/869.tcp.ovpn --dev tun62 \
  --pull-filter ignore "register-dns" --pull-filter ignore "block-outside-dns" \
  --pull-filter ignore "dhcp-release" --pull-filter ignore "dhcp-renew" \
  --daemon --log /var/log/bdv/869.log
sleep 8
ip netns exec bdv2 microsocks -i $BIND -p 44002 >/dev/null 2>&1 &
echo "[869] socks5://127.0.0.1:44002 expect egress 103.112.63.118"

# ---- 851 BD Nagad/Cellfin Used → 151.158.158.214 ----
ip netns add bdv3 2>/dev/null || true
ip netns exec bdv3 ip link set lo up
ip link add veth63 type veth peer name veth63b 2>/dev/null || true
ip link set veth63b netns bdv3
ip addr add 10.63.0.1/24 dev veth63 2>/dev/null || true
ip -n bdv3 addr add 10.63.0.2/24 dev veth63b 2>/dev/null || true
ip link set veth63 up; ip -n bdv3 link set veth63b up
ip -n bdv3 route add default via 10.63.0.1 2>/dev/null || true
iptables -t nat -C POSTROUTING -s 10.63.0.0/24 -o $UPLINK -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 10.63.0.0/24 -o $UPLINK -j MASQUERADE
ip netns exec bdv3 openvpn --config $CONF/851.tcp.ovpn --dev tun63 \
  --pull-filter ignore "register-dns" --pull-filter ignore "block-outside-dns" \
  --pull-filter ignore "dhcp-release" --pull-filter ignore "dhcp-renew" \
  --daemon --log /var/log/bdv/851.log
sleep 8
ip netns exec bdv3 microsocks -i $BIND -p 44003 >/dev/null 2>&1 &
echo "[851] socks5://127.0.0.1:44003 expect egress 151.158.158.214"

# ---- 878 PH High Speed Server → 130.94.50.28 ----
ip netns add bdv4 2>/dev/null || true
ip netns exec bdv4 ip link set lo up
ip link add veth64 type veth peer name veth64b 2>/dev/null || true
ip link set veth64b netns bdv4
ip addr add 10.64.0.1/24 dev veth64 2>/dev/null || true
ip -n bdv4 addr add 10.64.0.2/24 dev veth64b 2>/dev/null || true
ip link set veth64 up; ip -n bdv4 link set veth64b up
ip -n bdv4 route add default via 10.64.0.1 2>/dev/null || true
iptables -t nat -C POSTROUTING -s 10.64.0.0/24 -o $UPLINK -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 10.64.0.0/24 -o $UPLINK -j MASQUERADE
ip netns exec bdv4 openvpn --config $CONF/878.tcp.ovpn --dev tun64 \
  --pull-filter ignore "register-dns" --pull-filter ignore "block-outside-dns" \
  --pull-filter ignore "dhcp-release" --pull-filter ignore "dhcp-renew" \
  --daemon --log /var/log/bdv/878.log
sleep 8
ip netns exec bdv4 microsocks -i $BIND -p 44004 >/dev/null 2>&1 &
echo "[878] socks5://127.0.0.1:44004 expect egress 130.94.50.28"

