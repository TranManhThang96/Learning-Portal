# Day 3: Document — Linux Networking Cheat Sheet

---

## 1. Networking Tools Quick Reference

### DNS Tools

| Tool | Mục đích | Command phổ biến |
|------|---------|-----------------|
| `dig` | DNS query chi tiết | `dig example.com`, `dig +trace example.com`, `dig @8.8.8.8 example.com` |
| `nslookup` | DNS lookup đơn giản | `nslookup example.com`, `nslookup example.com 8.8.8.8` |
| `host` | DNS lookup ngắn gọn | `host example.com`, `host -t MX example.com` |
| `resolvectl` | systemd-resolved status | `resolvectl status`, `resolvectl flush-caches` |

### TCP/Connection Tools

| Tool | Mục đích | Command phổ biến |
|------|---------|-----------------|
| `ss` | Socket statistics (thay netstat) | `ss -tuanp`, `ss -tlnp`, `ss -s` |
| `netstat` | Legacy socket stats | `netstat -tuanp` (dùng `ss` thay thế) |
| `lsof -i` | Process ↔ port mapping | `lsof -i :8080`, `lsof -i -P -n` |
| `curl` | HTTP client + debugging | `curl -v`, `curl -w`, `curl --resolve` |
| `wget` | HTTP download | `wget -q -O- http://example.com` |
| `nc` (netcat) | TCP/UDP raw connection | `nc -zv host port`, `nc -l 8080` |

### Packet Analysis

| Tool | Mục đích | Command phổ biến |
|------|---------|-----------------|
| `tcpdump` | Packet capture (CLI) | `tcpdump -i any port 8080 -nn` |
| `tshark` | Wireshark CLI | `tshark -i any -f "port 8080"` |
| `traceroute` | Route tracing | `traceroute example.com` |
| `mtr` | traceroute + ping combined | `mtr example.com` |
| `ping` | ICMP connectivity test | `ping -c 4 example.com` |

### IP/Routing

| Tool | Mục đích | Command phổ biến |
|------|---------|-----------------|
| `ip addr` | Show IP addresses | `ip addr show`, `ip a` |
| `ip route` | Show routing table | `ip route`, `ip route get 8.8.8.8` |
| `ip link` | Network interfaces | `ip link show` |
| `arp` | ARP table | `arp -n`, `ip neigh` |

---

## 2. ss Command Cheat Sheet

```bash
# === Listing ===
ss -tuanp          # All TCP/UDP, all states, numeric, show process
ss -tlnp           # TCP listening only, numeric, process
ss -tn             # TCP established, numeric
ss -tunp           # TCP + UDP, numeric, process

# === Filter by state ===
ss -tn state established
ss -tn state time-wait
ss -tn state close-wait    # ⚠️ Potential leak indicator
ss -tn state listening
ss -tn state fin-wait-1
ss -tn state syn-sent

# === Filter by port ===
ss -tn sport = :8080       # Source port 8080
ss -tn dport = :5432       # Destination port 5432
ss -tn '( sport = :80 or sport = :443 )'

# === Filter by address ===
ss -tn dst 10.0.1.5
ss -tn src 10.0.0.1

# === Summary ===
ss -s
# Output:
# TCP:   250 (estab 180, closed 20, orphaned 5, timewait 45)

# === Count connections ===
ss -tn state established | wc -l
ss -tn state time-wait | wc -l
ss -tn state close-wait | wc -l

# === With timer info ===
ss -tnio               # Show TCP internal info (RTT, congestion window)
```

---

## 3. curl Timing Breakdown Template

```bash
# Full timing breakdown
curl -o /dev/null -s -w "\
  namelookup:  %{time_namelookup}s\n\
  connect:     %{time_connect}s\n\
  appconnect:  %{time_appconnect}s\n\
  pretransfer: %{time_pretransfer}s\n\
  redirect:    %{time_redirect}s\n\
  starttransfer:%{time_starttransfer}s\n\
  ----------\n\
  total:       %{time_total}s\n\
  http_code:   %{http_code}\n\
  size:        %{size_download} bytes\n\
  speed:       %{speed_download} bytes/s\n" \
  https://example.com/

# Explanation:
# namelookup  = DNS resolution time
# connect     = TCP handshake complete
# appconnect  = TLS handshake complete (HTTPS only)
# starttransfer = First byte received (TTFB)
# total       = Complete transfer

# Derived metrics:
# TCP handshake    = connect - namelookup
# TLS handshake    = appconnect - connect
# Server processing = starttransfer - appconnect (or - connect if HTTP)
# Content transfer  = total - starttransfer
```

---

## 4. tcpdump Cheat Sheet

```bash
# === Basic ===
tcpdump -i any                    # All interfaces
tcpdump -i eth0                   # Specific interface
tcpdump -i any -nn                # No DNS/port resolution (faster)
tcpdump -i any -vv                # Very verbose

# === Filter by port ===
tcpdump -i any port 8080
tcpdump -i any port 80 or port 443
tcpdump -i any portrange 8080-8090

# === Filter by host ===
tcpdump -i any host 10.0.1.5
tcpdump -i any src host 10.0.1.5
tcpdump -i any dst host 10.0.1.5

# === Filter by protocol ===
tcpdump -i any tcp
tcpdump -i any udp
tcpdump -i any icmp

# === Filter TCP flags ===
tcpdump -i any 'tcp[tcpflags] & tcp-syn != 0'     # SYN packets
tcpdump -i any 'tcp[tcpflags] & tcp-rst != 0'     # RST packets
tcpdump -i any 'tcp[tcpflags] & tcp-fin != 0'     # FIN packets
tcpdump -i any 'tcp[tcpflags] == tcp-syn'          # SYN only (no ACK)

# === Save/Read ===
tcpdump -i any port 8080 -w /tmp/capture.pcap      # Save to file
tcpdump -r /tmp/capture.pcap                        # Read from file

# === Limit ===
tcpdump -i any -c 100 port 8080                    # Stop after 100 packets
tcpdump -i any -G 60 -W 5 -w /tmp/cap_%Y%m%d%H%M.pcap  # Rotate every 60s, keep 5 files

# === Show payload ===
tcpdump -i any port 80 -A                           # ASCII
tcpdump -i any port 80 -X                           # Hex + ASCII
```

---

## 5. TCP Connection States Diagram

```
                              ┌───────────┐
                    Active    │  CLOSED   │   Passive
                    Open      └─────┬─────┘   Open
                   ┌────────────────┤──────────────────┐
                   │                │                   │
                   ▼                │                   ▼
             ┌───────────┐         │            ┌───────────┐
             │ SYN_SENT  │         │            │  LISTEN   │
             └─────┬─────┘         │            └─────┬─────┘
                   │ Recv SYN-ACK  │                  │ Recv SYN
                   │ Send ACK      │                  │ Send SYN-ACK
                   ▼               │                  ▼
             ┌─────────────────────┴───────────┐
             │          ESTABLISHED             │
             └─────────────┬───────────────────┘
                           │
              Active Close │           Passive Close
              Send FIN     │           Recv FIN
              ┌────────────┤───────────────────┐
              ▼            │                   ▼
        ┌───────────┐      │            ┌───────────┐
        │FIN_WAIT_1 │      │            │CLOSE_WAIT │ ← ⚠️ If stuck here
        └─────┬─────┘      │            └─────┬─────┘   = app bug (not
              │ Recv ACK   │                  │             closing socket)
              ▼            │                  │ Send FIN
        ┌───────────┐      │                  ▼
        │FIN_WAIT_2 │      │            ┌───────────┐
        └─────┬─────┘      │            │ LAST_ACK  │
              │ Recv FIN   │            └─────┬─────┘
              │ Send ACK   │                  │ Recv ACK
              ▼            │                  ▼
        ┌───────────┐      │            ┌───────────┐
        │ TIME_WAIT │      │            │  CLOSED   │
        │ (2×MSL)   │      │            └───────────┘
        └─────┬─────┘      │
              │ Timeout    │
              ▼            │
        ┌───────────┐      │
        │  CLOSED   │◄─────┘
        └───────────┘
```

---

## 6. Network Tuning Reference

### Production Kernel Parameters (/etc/sysctl.conf)

```bash
# === Connection Handling ===
net.core.somaxconn = 65535                    # Socket listen backlog
net.ipv4.tcp_max_syn_backlog = 65535          # SYN queue size
net.core.netdev_max_backlog = 65535           # Network device queue

# === Port Range ===
net.ipv4.ip_local_port_range = 10240 65535    # Ephemeral port range

# === TIME_WAIT ===
net.ipv4.tcp_tw_reuse = 1                    # Reuse TIME_WAIT for outbound
net.ipv4.tcp_fin_timeout = 30                # Reduce FIN timeout (default 60)

# === Keepalive ===
net.ipv4.tcp_keepalive_time = 600            # Start keepalive after 600s idle
net.ipv4.tcp_keepalive_intvl = 60            # Keepalive interval
net.ipv4.tcp_keepalive_probes = 3            # Keepalive retries

# === Buffer Sizes ===
net.core.rmem_max = 16777216                 # Max receive buffer
net.core.wmem_max = 16777216                 # Max send buffer
net.ipv4.tcp_rmem = 4096 87380 16777216      # TCP receive buffer (min/default/max)
net.ipv4.tcp_wmem = 4096 65536 16777216      # TCP send buffer

# === Connection Tracking ===
net.nf_conntrack_max = 262144                # Max tracked connections
net.netfilter.nf_conntrack_tcp_timeout_time_wait = 30

# Apply: sysctl -p
```

---

## 7. Common Error Messages and Meaning

| Error Message | Meaning | Debug Command |
|---------------|---------|---------------|
| `Connection refused` | Port không listen hoặc firewall REJECT | `ss -tlnp \| grep <port>` |
| `Connection timed out` | Server không respond, firewall DROP, network down | `ping <ip>`, `traceroute <ip>` |
| `No route to host` | Routing table không có path | `ip route get <ip>` |
| `Name resolution failed` | DNS không resolve | `dig <hostname>` |
| `Cannot assign requested address` | Ephemeral port exhausted | `ss -s`, check `ip_local_port_range` |
| `Too many open files` | fd limit reached | `ls /proc/<pid>/fd \| wc -l` |
| `Connection reset by peer` | Remote side RST connection | `tcpdump`, check server logs |
| `Broken pipe` | Write to closed connection | Handle SIGPIPE, check connection state |
| `Address already in use` | Port đang bị occupy | `lsof -i :<port>`, cần `SO_REUSEADDR` |

---

## 8. Load Balancing Decision Matrix

```
                       ┌─────────────────────────────────┐
                       │    Chọn Load Balancing Algo      │
                       └──────────────┬──────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                  │
              Servers đồng     Servers khác      Cần session
              nhất capacity?    capacity?        persistence?
                    │                 │                  │
                    ▼                 ▼                  ▼
             Round Robin      Weighted RR          IP Hash
                    │                 │            (hoặc cookie)
                    │                 │
              Request time      Request time
              đều nhau?         khác nhau nhiều?
                    │                 │
                    ▼                 ▼
             Round Robin      Least Connections
             (vẫn tốt)
                    
         ┌───────────────────────────────────┐
         │  Đặc biệt: gRPC / HTTP/2          │
         │  → KHÔNG dùng L4 Load Balancing    │
         │  → Dùng L7 (Envoy, Linkerd)        │
         │    hoặc client-side LB             │
         └───────────────────────────────────┘
```

