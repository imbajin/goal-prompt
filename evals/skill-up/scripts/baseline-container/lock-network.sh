#!/bin/bash
# 仅由宿主可信启动器以 docker exec --privileged 执行，不授予 Agent 网络管理能力。
set -euo pipefail
proxy_ip="$1"
[[ "$proxy_ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]
iptables -F OUTPUT
iptables -F INPUT
iptables -P OUTPUT DROP
iptables -P INPUT DROP
iptables -A OUTPUT -o lo -j ACCEPT
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -d "$proxy_ip" -p tcp --dport 3128 -j ACCEPT
ip6tables -F OUTPUT
ip6tables -F INPUT
ip6tables -P OUTPUT DROP
ip6tables -P INPUT DROP
