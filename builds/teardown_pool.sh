#!/bin/bash
set -u
pkill -f 'microsocks -i .* -p 44000' 2>/dev/null || true
ip netns del bdv0 2>/dev/null || true
iptables -t nat -D POSTROUTING -s 10.60.0.0/24 -o ${UPLINK:-eth0} -j MASQUERADE 2>/dev/null || true
pkill -f 'microsocks -i .* -p 44001' 2>/dev/null || true
ip netns del bdv1 2>/dev/null || true
iptables -t nat -D POSTROUTING -s 10.61.0.0/24 -o ${UPLINK:-eth0} -j MASQUERADE 2>/dev/null || true
pkill -f 'microsocks -i .* -p 44002' 2>/dev/null || true
ip netns del bdv2 2>/dev/null || true
iptables -t nat -D POSTROUTING -s 10.62.0.0/24 -o ${UPLINK:-eth0} -j MASQUERADE 2>/dev/null || true
pkill -f 'microsocks -i .* -p 44003' 2>/dev/null || true
ip netns del bdv3 2>/dev/null || true
iptables -t nat -D POSTROUTING -s 10.63.0.0/24 -o ${UPLINK:-eth0} -j MASQUERADE 2>/dev/null || true
pkill -f 'microsocks -i .* -p 44004' 2>/dev/null || true
ip netns del bdv4 2>/dev/null || true
iptables -t nat -D POSTROUTING -s 10.64.0.0/24 -o ${UPLINK:-eth0} -j MASQUERADE 2>/dev/null || true
