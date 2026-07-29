# Day 13: Latency Analysis & Benchmarking — Reference Document

---

## 1. Cheat Sheet: SLOWLOG

```txt
-- Configuration (redis.conf or CONFIG SET)
slowlog-log-slower-than 1000   -- log commands > 1ms (microseconds)
slowlog-max-len 10000          -- keep last 10000 entries (ring buffer)

-- Commands
SLOWLOG GET          -- get all entries (ring buffer, newest first)
SLOWLOG GET 10       -- get last 10 entries only
SLOWLOG LEN          -- return current slowlog entry count
SLOWLOG RESET        -- clear all entries (not persisted, in-memory only)

-- Read-only introspection
SLOWLOG GET | jq '.[] | {duration_ms: (.[2] / 1000), cmd: .[3][0], time: .[1]}'
```

**Entry format** (array of 6 elements):

| Index | Field | Type | Description |
|---|---|---|---|
| 0 | id | integer | Unique entry ID (increments each entry) |
| 1 | timestamp | integer | Unix timestamp when command started |
| 2 | duration | integer | Execution time in **microseconds** |
| 3 | command | array | Command + arguments |
| 4 | client_ip | integer | Client IP (numeric in older Redis, string in v6+) |
| 5 | client_name | string | CLIENT SETNAME value |

**Threshold guidelines**:

| Use case | `slowlog-log-slower-than` | Reason |
|---|---|---|
| Ultra-low latency (< 5ms p99 SLA) | 500 (0.5ms) | Catch everything above p95 |
| Standard web service (< 50ms p99) | 5000 (5ms) | Default too high, miss many issues |
| Background/analytics | 10000 (10ms) | Only significant slow commands |
| Development/debug | 1000 (1ms) | Catch command-level issues early |

---

## 2. Cheat Sheet: LATENCY Commands (Redis 7+)

```txt
-- Enable latency monitor (default: 0 = disabled)
CONFIG SET latency-monitor-threshold 100   -- track events > 100ms (milliseconds)

-- Commands
LATENCY DOCTOR       -- human-readable diagnosis of latency events
LATENCY HISTORY <event>     -- time-series of latency samples (microseconds)
LATENCY LATEST              -- most recent latency events
LATENCY RESET <event>       -- reset history for specific event
LATENCY RESET               -- reset all events
LATENCY GRAPH <event>       -- ASCII graph of latency over time (Redis 7.2+)
```

**LATENCY DOCTOR output sections**:

```txt
Dave, I have observed latency spikes in your Redis instance.
Your Redis version 7.2 has a configured slowlog-log-slower-than threshold of 1000 microseconds.
I have detected 45 latency spikes in the last 2 hours.
The latest latency event was 127 milliseconds.

I have found 4 distinct latency events in this Redis instance:

1. Command: (command execution) - 3 events, avg 95ms
   Slow commands detected by SLOWLOG. Expected if you have slow commands.

2. Command: fork (fork time) - 1 event, 543ms
   Fork time indicates slow disk or high memory usage.

3. Command: rdb-unlink-temp-file (temp file unlink) - 1 event, 42ms
   Time needed to unlink temporary RDB file.

4. Command: fast-command (non-commands) - 40 events, avg 0.8ms
   Non-command time such as TTL and key eviction. Expected under memory pressure.
```

**LATENCY LATEST output format**:

```txt
1) 1) "command"              -- event name
   2) (integer) 1700000600  -- Unix timestamp
   3) (integer) 127000       -- latency in microseconds (127ms)
   4) (integer) 45           -- number of samples for this event
   5) 1) "ZRANGEBYSCORE"    -- command that triggered it
      2) "leaderboard:global"
      3) "0"
      4) "+inf"
```

**LATENCY HISTORY fork output format**:

```txt
1) 1) (integer) 1700000000   -- timestamp
   2) (integer) 543210       -- latency in microseconds (543ms)
2) 1) (integer) 1699990000
   2) (integer) 432100
```

**Key difference**: `slowlog-log-slower-than` logs slow **commands** (microseconds threshold). `latency-monitor-threshold` tracks latency **events** including fork, eviction, disk I/O (milliseconds threshold).

---

## 3. Cheat Sheet: redis-cli Latency Tools

```bash
# Measure round-trip latency continuously (PING every second)
redis-cli --latency
# Output: min: 0, max: 1, avg: 0.12 (3821 samples)

# Measure latency with per-sample history (30-second intervals)
redis-cli --latency-history
# Output: latency is 0.12ms (repeats every 30s)

# Show latency distribution histogram (Redis 7+, ASCII)
redis-cli --latency-dist
# Output: ASCII histogram of latency buckets

# Measure intrinsic (server-side, no network) latency
# Run for 120 seconds for accurate baseline
redis-cli --intrinsic-latency 120
# Output:
# Max latency base: 0.54 microseconds
# This instance is a good candidate for benchmarking.
# 120 seconds total, 2345678 operations sampled.

# Scan and measure SORT latency on keys (big key detection)
redis-cli --scan-and-sort
```

**Intrinsic latency interpretation**:

| Intrinsic latency | Status |
|---|---|
| < 0.5 microseconds | Excellent (baseline on dedicated host) |
| 0.5 - 2 microseconds | Good (normal on VM) |
| 2 - 10 microseconds | Degraded (CPU contention, THP enabled) |
| > 10 microseconds | Critical (co-located VMs, noisy neighbor) |

---

## 4. redis-benchmark — Full Flag Reference

```bash
redis-benchmark [OPTIONS]

Connection & load:
  -h <hostname>     Server hostname (default: 127.0.0.1)
  -p <port>         Server port (default: 6379)
  -a <password>     Password (default: none)
  -c <clients>      Number of parallel connections (default: 50)
  -n <requests>     Total number of requests (default: 100000)
  -k <0|1>          Keep alive (default: 1)
  --threads <n>     Number of threads (Redis 6+, default: 1)
  --cluster         Enable cluster mode
  --sni <name>      Server Name Indication for TLS

Workload:
  -d <size>         Data size in bytes for SET/GET value (default: 3)
  -r <range>        Use random keys (random suffix 0 to range-1)
  -P <num>          Pipeline N commands per request (default: 1 = no pipeline)
  -t <commands>     Run only specific commands (comma-separated, e.g. set,get,lpush)
  -q                 Quiet mode (shows only ops/sec and latency)
  --csv             Output in CSV format
  -l                 Loop (run forever until Ctrl+C)
  --dbnum <db>       Database number (default: 0)
  -D <sec>           Duration in seconds (run for N seconds)

Throughput test:
  --enable-trim     Continuously trim histogram tail (Redis 7.2+)
  --force          Run even if redis-benchmark detects external redis-server
```

**Common examples**:

```bash
# Basic GET (default: 50 clients, 100K requests, 3 bytes)
redis-benchmark

# GET with realistic payload
redis-benchmark -t get -d 1024 -n 100000 -c 50

# GET p50/p95/p99
redis-benchmark -t get -n 10000 -c 10 --latency

# Random keys, mixed commands
redis-benchmark -t get,set -r 1000000 -n 500000 -c 100

# Pipeline benchmark (16 commands per RTT)
redis-benchmark -t get -P 16 -n 100000 -c 50

# Multi-threaded (Redis 6+)
redis-benchmark -t get -n 200000 -c 50 --threads 4

# CSV output for automation
redis-benchmark -t get,set -n 10000 --csv > /tmp/bench.csv

# 60-second sustained run
redis-benchmark -t get -c 50 -d 256 -D 60 -q
```

**Output interpretation**:

```txt
# ===== GET =====
# 100000 requests completed in 1.23 seconds
# 50 parallel clients

# throughput summary: 81300.82 requests per second

# latency summary (microseconds):
#       50.000%   0.063000 ms   <- p50
#       75.000%   0.078000 ms   <- p75
#       90.000%   0.094000 ms   <- p90
#       99.000%   0.156000 ms   <- p99
#       99.900%   0.516000 ms   <- p99.9
#       99.999%   2.847000 ms   <- p99.999
```

---

## 5. memtier_benchmark — Full Flag Reference

```bash
memtier_benchmark [options]

Connection & load:
  -s, --server=<addr>           Server address (default: localhost)
  -p, --port=<port>             Server port (default: 6379)
  -a, --auth-password=<pwd>     Password
  -c, --clients=<n>            Concurrent clients per thread (default: 50)
  -t, --threads=<n>            Worker threads (default: 4)
  -P, --pipeline=<n>           Pipeline depth (default: 1)
  --ratio=<N:M>                 SET:GET ratio (e.g., 1:9 = 10% writes)
  --random-data                 Use random data (random suffix + random value)

Workload:
  -n, --requests=<n>           Requests per client (default: 10000)
  -d, --data-size=<bytes>      Value size (default: 32)
  -R, --random-data             Random key suffix + random value data
  --key-pattern=<pattern>       Key pattern:
                                 G:G = fixed keys (hot key)
                                 G:R = GET fixed, SET random (standard)
                                 R:R = all random (random distribution)
                                 R:G = random SET, fixed GET
  --lookaside-ratio=<N:M>       Ratio for key lookaside pattern
  --select-db=<num>            Database number

Output:
  -q, --quiet                  Quiet mode
  --show-config                Show config before running
  --print=<masks>             Print latency per operation type
  --json-out-file=<file>       JSON output file
  --csv-out-file=<file>        CSV output file
  --latency-resolution=<ms>   Latency histogram resolution (default: 1ms)
  --print-full-latency         Print full percentile histogram

Cluster:
  --cluster-mode               Enable Redis Cluster mode
  --use-cluster-slots-verification  Verify cluster slot mapping
```

**Common examples**:

```bash
# Basic GET benchmark
memtier_benchmark -s localhost -p 6379 -t 4 -c 50 -n 100000

# 10% writes, 90% reads, 1KB values
memtier_benchmark \
  -s localhost -t 4 -c 100 \
  --ratio=1:9 -d 1024 -n 100000

# Random keys (avoid hot key)
memtier_benchmark -s localhost -R --key-pattern=R:R \
  -t 4 -c 50 -n 100000

# Full latency histogram (p50/p95/p99/p99.9)
memtier_benchmark -s localhost -t 4 -c 50 \
  --latency-resolution=0.1 -n 50000 --print-full-latency

# Pipeline benchmark (batch 16)
memtier_benchmark -s localhost -P 16 -t 4 -c 50 -n 100000

# JSON output for Prometheus/Grafana
memtier_benchmark -s localhost -t 4 -c 50 \
  --json-out-file=/tmp/bench.json -n 100000

# Benchmark over WAN (realistic remote deployment)
memtier_benchmark -s redis.prod.example.com \
  -p 6379 -t 4 -c 20 -d 512 -n 100000
```

---

## 6. Comparison: redis-benchmark vs memtier_benchmark vs Custom Benchmark

| Aspect | redis-benchmark | memtier_benchmark | Custom (Go/TS) |
|---|---|---|---|
| **Use case** | Quick smoke test | Production capacity planning | Specific scenarios |
| **Multi-threading** | Basic (`--threads`, Redis 6+) | Full (multi-threaded workers) | Full (goroutines/async) |
| **Latency percentiles** | p50 to p99.999 | p50 to p99.9+ (histogram) | p50 to p99.9 (HDR) |
| **Pipeline support** | Yes | Yes | Yes |
| **Cluster mode** | Yes | Yes | Manual |
| **Random keys** | Yes (`-r`) | Yes (`-R`, `--key-pattern`) | Fully configurable |
| **Mixed ratio (SET:GET)** | No | Yes (`--ratio`) | Configurable |
| **JSON/CSV output** | CSV only | Both | Both |
| **Histogram resolution** | Fixed | Configurable (`--latency-resolution`) | Configurable |
| **Auth support** | Yes (`-a`) | Yes (`--auth-password`) | Configurable |
| **Realistic workload** | No (single command) | Yes (mixed, configurable) | Yes |
| **Installation** | Built into Redis | Separate (`apt`/`make`/Docker) | Language runtime |
| **WAN latency simulation** | No | No | Yes (custom RTT) |
| **HDR histogram export** | No | Yes (`--json-out-file`) | Yes (hdrhistogram-go) |
| **Run anywhere** | Any host with redis-cli | Any host with binary | Same as app |
| **Reproducible** | Yes | Yes | Yes (seeded RNG) |

**When to use which**:

| Scenario | Tool | Reason |
|---|---|---|
| Compare Redis versions on same host | redis-benchmark | Built-in, fast, comparable |
| Capacity planning for production | memtier_benchmark | Multi-threaded, realistic, production-grade |
| App-level latency measurement | Custom Go/TypeScript | Measure real application code |
| WAN latency simulation | Custom + tc/netem | Inject artificial RTT |
| CI/CD regression test | redis-benchmark + `--csv` | Simple, fast, pass/fail |
| SLA validation with percentile | memtier_benchmark `--print-full-latency` | HDR histogram, p99.9+ |

---

## 7. Config Templates: redis.conf

```txt
# ---- SLOWLOG TEMPLATE ----

# Low-latency service (< 10ms p99 SLA)
slowlog-log-slower-than 500
slowlog-max-len 10000

# Standard service (< 50ms p99 SLA)
slowlog-log-slower-than 5000
slowlog-max-len 5000

# Background analytics (< 200ms SLA)
slowlog-log-slower-than 10000
slowlog-max-len 1000
```

```bash
# ---- LATENCY MONITORING TEMPLATE ----

# Enable latency tracking (threshold in milliseconds)
latency-monitor-threshold 100
# NOTE: Only tracks events > N ms (fork, eviction, etc.)
# Does NOT replace slowlog (which tracks command latency in microseconds)

# ---- RECOMMENDED PRODUCTION redis.conf SECTIONS ----

# --- Network ---
timeout 300                    # Close idle clients after 300s
tcp-keepalive 60               # TCP keepalive every 60s
tcp-backlog 511                # OS-level connection queue (tune if needed)

# --- Slowlog ---
slowlog-log-slower-than 5000   # 5ms threshold
slowlog-max-len 10000          # Keep last 10K entries

# --- Latency monitor ---
latency-monitor-threshold 100  # Track events > 100ms

# --- Persistence (affects latency) ---
# appendfsync everysec (default, recommended)
appendfsync everysec

# For maximum durability (adds latency):
# appendfsync always

# For cache (no durability, lowest latency):
# appendfsync no

# --- Memory ---
maxmemory 4gb
maxmemory-policy allkeys-lru

# --- Disable dangerous commands in production ---
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command KEYS ""
# rename-command DEBUG ""

# --- Disable transparent huge pages (reduce fork latency) ---
# OS-level: echo never > /sys/kernel/mm/transparent_hugepage/enabled
```

---

## 8. TypeScript — Parse SLOWLOG with ioredis

```typescript
// src/slowlog-parser.ts
import Redis from 'ioredis';

interface SlowLogEntry {
  id: number;
  timestamp: number;
  durationUs: number;
  durationMs: number;
  command: string[];
  clientIp: string;
  clientName: string;
}

interface SlowLogReport {
  totalEntries: number;
  timeRange: { start: number; end: number; durationSec: number };
  durationStats: {
    minUs: number;
    maxUs: number;
    avgUs: number;
    p50Us: number;
    p95Us: number;
    p99Us: number;
  };
  commandFrequency: Record<string, number>;
  slowCommands: { command: string; durationMs: number; timestamp: number }[];
  alerts: string[];
}

async function parseSlowLog(
  redis: Redis,
  limit = 1000,
): Promise<SlowLogReport> {
  const raw = await redis.slowlogGet(limit);
  if (!raw || raw.length === 0) {
    return {
      totalEntries: 0,
      timeRange: { start: 0, end: 0, durationSec: 0 },
      durationStats: { minUs: 0, maxUs: 0, avgUs: 0, p50Us: 0, p95Us: 0, p99Us: 0 },
      commandFrequency: {},
      slowCommands: [],
      alerts: ['slowlog is empty — no slow commands detected'],
    };
  }

  const entries: SlowLogEntry[] = raw.map((entry) => {
    // ioredis returns array-like objects: [id, timestamp, duration, command, client_ip, client_name]
    return {
      id: Number(entry[0]),
      timestamp: Number(entry[1]),
      durationUs: Number(entry[2]),
      durationMs: Number(entry[2]) / 1000,
      command: entry[3] as string[],
      clientIp: String(entry[4] ?? ''),
      clientName: String(entry[5] ?? ''),
    };
  });

  const durations = entries.map((e) => e.durationUs).sort((a, b) => a - b);
  const sum = durations.reduce((acc, v) => acc + v, 0);

  const percentile = (arr: number[], p: number) => {
    const idx = Math.ceil((p / 100) * arr.length) - 1;
    return arr[Math.max(0, idx)];
  };

  const commandFreq: Record<string, number> = {};
  for (const entry of entries) {
    const cmd = (entry.command[0] ?? '?').toUpperCase();
    commandFreq[cmd] = (commandFreq[cmd] ?? 0) + 1;
  }

  const slowCommands = entries
    .filter((e) => e.durationMs > 5) // flag > 5ms
    .map((e) => ({
      command: e.command.join(' '),
      durationMs: e.durationMs,
      timestamp: e.timestamp,
    }))
    .sort((a, b) => b.durationMs - a.durationMs);

  const alerts: string[] = [];
  const maxDurationMs = durations[durations.length - 1] / 1000;
  if (maxDurationMs > 100) {
    alerts.push(`CRITICAL: max slow command duration = ${maxDurationMs.toFixed(0)}ms`);
  }
  if (commandFreq['KEYS'] !== undefined) {
    alerts.push('WARNING: KEYS command detected — O(N), should use SCAN');
  }
  const zrangeNoLimit = entries.some(
    (e) =>
      (e.command[0] ?? '').toUpperCase() === 'ZRANGE' &&
      !e.command.includes('LIMIT'),
  );
  if (zrangeNoLimit) {
    alerts.push('WARNING: ZRANGE without LIMIT detected — O(N) risk');
  }

  return {
    totalEntries: entries.length,
    timeRange: {
      start: entries[entries.length - 1]?.timestamp ?? 0,
      end: entries[0]?.timestamp ?? 0,
      durationSec: (entries[0]?.timestamp ?? 0) - (entries[entries.length - 1]?.timestamp ?? 0),
    },
    durationStats: {
      minUs: durations[0],
      maxUs: durations[durations.length - 1],
      avgUs: Math.round(sum / durations.length),
      p50Us: percentile(durations, 50),
      p95Us: percentile(durations, 95),
      p99Us: percentile(durations, 99),
    },
    commandFrequency: commandFreq,
    slowCommands,
    alerts,
  };
}

async function main() {
  const redis = new Redis({ host: 'localhost', port: 6379 });

  console.log('=== Parsing SLOWLOG (last 1000 entries) ===\n');

  const report = await parseSlowLog(redis, 1000);

  console.log(`Total slowlog entries: ${report.totalEntries}`);
  console.log(
    `Time range: ${report.timeRange.durationSec}s (${new Date(report.timeRange.start * 1000).toISOString()} → ${new Date(report.timeRange.end * 1000).toISOString()})`,
  );
  console.log('\n--- Duration Stats ---');
  console.log(`  Min:   ${report.durationStats.minUs} µs (${(report.durationStats.minUs / 1000).toFixed(3)}ms)`);
  console.log(`  Avg:   ${report.durationStats.avgUs} µs (${(report.durationStats.avgUs / 1000).toFixed(3)}ms)`);
  console.log(`  p50:   ${report.durationStats.p50Us} µs (${(report.durationStats.p50Us / 1000).toFixed(3)}ms)`);
  console.log(`  p95:   ${report.durationStats.p95Us} µs (${(report.durationStats.p95Us / 1000).toFixed(3)}ms)`);
  console.log(`  p99:   ${report.durationStats.p99Us} µs (${(report.durationStats.p99Us / 1000).toFixed(3)}ms)`);
  console.log(`  Max:   ${report.durationStats.maxUs} µs (${(report.durationStats.maxUs / 1000).toFixed(3)}ms)`);

  console.log('\n--- Command Frequency ---');
  const sorted = Object.entries(report.commandFrequency).sort((a, b) => b[1] - a[1]);
  for (const [cmd, count] of sorted.slice(0, 10)) {
    console.log(`  ${cmd.padEnd(20)} ${count} occurrences`);
  }

  console.log('\n--- Slowest Commands (top 10) ---');
  for (const sc of report.slowCommands.slice(0, 10)) {
    console.log(`  ${sc.durationMs.toFixed(2).padStart(8)}ms | ${sc.command}`);
  }

  console.log('\n--- Alerts ---');
  for (const alert of report.alerts) {
    console.log(`  [!] ${alert}`);
  }

  await redis.quit();
}

main().catch(console.error);
```

---

## 9. Go — Parse SLOWLOG + LATENCY HISTORY with go-redis/v9

```go
// slowlog.go
package main

import (
	"context"
	"fmt"
	"log"
	"sort"
	"time"

	"github.com/redis/go-redis/v9"
)

// SlowLogEntry represents a SLOWLOG entry (6-element array).
type SlowLogEntry struct {
	ID         int64
	Timestamp  int64
	DurationUs int64 // microseconds
	Command    []string
	ClientIP   string
	ClientName string
}

func (e SlowLogEntry) DurationMs() float64 {
	return float64(e.DurationUs) / 1000.0
}

// LatencyEvent represents a LATENCY LATEST event.
type LatencyEvent struct {
	Event      string
	Timestamp  int64
	LatencyUs  int64
	NumSamples int64
	Command    []string
}

func (e LatencyEvent) LatencyMs() float64 {
	return float64(e.LatencyUs) / 1000.0
}

// SlowLogReport aggregates SLOWLOG data.
type SlowLogReport struct {
	Entries        []SlowLogEntry
	DurationSorted []int64
	CommandFreq    map[string]int
	Alerts         []string
}

func ParseSlowLog(ctx context.Context, rdb *redis.Client, limit int64) (*SlowLogReport, error) {
	raw, err := rdb.SlowLogGet(ctx, limit).Result()
	if err != nil {
		return nil, fmt.Errorf("SLOWLOG GET: %w", err)
	}

	report := &SlowLogReport{
		CommandFreq: make(map[string]int),
	}

	for _, entry := range raw {
		e := SlowLogEntry{
			ID:         entry.ID,
			Timestamp:  entry.StartedAt.Unix(),
			DurationUs: entry.Duration.Microseconds(),
			Command:    entry.Args,
		}
		if entry.ClientName != "" {
			e.ClientName = entry.ClientName
		}

		report.Entries = append(report.Entries, e)
		report.DurationSorted = append(report.DurationSorted, e.DurationUs)

		if len(e.Command) > 0 {
			cmd := e.Command[0]
			report.CommandFreq[cmd]++
		}
	}

	sort.Slice(report.DurationSorted, func(i, j int) bool {
		return report.DurationSorted[i] < report.DurationSorted[j]
	})

	// Alerts
	if len(report.DurationSorted) > 0 {
		maxMs := float64(report.DurationSorted[len(report.DurationSorted)-1]) / 1000
		if maxMs > 100 {
			report.Alerts = append(report.Alerts,
				fmt.Sprintf("CRITICAL: max slow command = %.1fms (exceeds 100ms)", maxMs))
		}
		if count := report.CommandFreq["keys"]; count > 0 {
			report.Alerts = append(report.Alerts,
				fmt.Sprintf("WARNING: KEYS command executed %d times — O(N), should use SCAN", count))
		}
	}

	return report, nil
}

func GetLatencyHistory(ctx context.Context, rdb *redis.Client, event string) ([]LatencyEvent, error) {
	// LATENCY HISTORY returns raw interface{} array
	// Use redis-cli internally: LATENCY HISTORY fork
	raw, err := rdb.Do(ctx, "LATENCY", "HISTORY", event).Result()
	if err != nil {
		return nil, fmt.Errorf("LATENCY HISTORY %s: %w", event, err)
	}

	// Parse raw []interface{} — each entry is [timestamp, latency_us]
	rawSlice, ok := raw.([]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected LATENCY HISTORY format for event %s", event)
	}

	var events []LatencyEvent
	for _, item := range rawSlice {
		entry, ok := item.([]interface{})
		if !ok || len(entry) < 2 {
			continue
		}
		ts, _ := entry[0].(int64)
		latUs, _ := entry[1].(int64)
		events = append(events, LatencyEvent{
			Event:     event,
			Timestamp: ts,
			LatencyUs: latUs,
		})
	}
	return events, nil
}

func GetLatencyLatest(ctx context.Context, rdb *redis.Client) ([]LatencyEvent, error) {
	raw, err := rdb.Do(ctx, "LATENCY", "LATEST").Result()
	if err != nil {
		return nil, fmt.Errorf("LATENCY LATEST: %w", err)
	}

	rawSlice, ok := raw.([]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected LATENCY LATEST format")
	}

	var events []LatencyEvent
	for _, item := range rawSlice {
		entry, ok := item.([]interface{})
		if !ok || len(entry) < 4 {
			continue
		}
		eventName, _ := entry[0].(string)
		ts, _ := entry[1].(int64)
		latUs, _ := entry[2].(int64)
		numSamples, _ := entry[3].(int64)
		var cmd []string
		if len(entry) > 4 {
			if cmdArr, ok := entry[4].([]interface{}); ok {
				for _, c := range cmdArr {
					if s, ok := c.(string); ok {
						cmd = append(cmd, s)
					}
				}
			}
		}
		events = append(events, LatencyEvent{
			Event:      eventName,
			Timestamp:  ts,
			LatencyUs:  latUs,
			NumSamples: numSamples,
			Command:    cmd,
		})
	}
	return events, nil
}

func percentile(sorted []int64, p float64) int64 {
	if len(sorted) == 0 {
		return 0
	}
	idx := int(float64(len(sorted)-1)*p/100.0 + 0.5)
	if idx >= len(sorted) {
		idx = len(sorted) - 1
	}
	return sorted[idx]
}

func printSlowLogReport(r *SlowLogReport) {
	fmt.Println("=== SLOWLOG Report ===")
	fmt.Printf("Total entries: %d\n", len(r.Entries))

	if len(r.DurationSorted) > 0 {
		fmt.Println("\n--- Duration Stats ---")
		fmt.Printf("  Min:   %d µs (%.3fms)\n", r.DurationSorted[0], float64(r.DurationSorted[0])/1000)
		fmt.Printf("  p50:   %d µs (%.3fms)\n", percentile(r.DurationSorted, 50), float64(percentile(r.DurationSorted, 50))/1000)
		fmt.Printf("  p95:   %d µs (%.3fms)\n", percentile(r.DurationSorted, 95), float64(percentile(r.DurationSorted, 95))/1000)
		fmt.Printf("  p99:   %d µs (%.3fms)\n", percentile(r.DurationSorted, 99), float64(percentile(r.DurationSorted, 99))/1000)
		fmt.Printf("  Max:   %d µs (%.3fms)\n",
			r.DurationSorted[len(r.DurationSorted)-1],
			float64(r.DurationSorted[len(r.DurationSorted)-1])/1000)

		fmt.Println("\n--- Command Frequency ---")
		type pair struct{ cmd string; count int }
		var pairs []pair
		for cmd, cnt := range r.CommandFreq {
			pairs = append(pairs, pair{cmd, cnt})
		}
		sort.Slice(pairs, func(i, j int) bool { return pairs[i].count > pairs[j].count })
		for i, p := range pairs {
			if i >= 10 {
				break
			}
			fmt.Printf("  %-20s %d\n", p.cmd, p.count)
		}

		fmt.Println("\n--- Slowest Entries (top 10) ---")
		sorted := make([]SlowLogEntry, len(r.Entries))
		copy(sorted, r.Entries)
		sort.Slice(sorted, func(i, j int) bool {
			return sorted[i].DurationUs > sorted[j].DurationUs
		})
		for i, e := range sorted {
			if i >= 10 {
				break
			}
			ts := time.Unix(e.Timestamp, 0).Format(time.RFC3339)
			cmd := e.Command
			if len(cmd) > 5 {
				cmd = cmd[:5]
			}
			fmt.Printf("  %s | %7.2fms | %v\n", ts, e.DurationMs(), cmd)
		}
	}

	fmt.Println("\n--- Alerts ---")
	for _, a := range r.Alerts {
		fmt.Printf("  [!] %s\n", a)
	}
}

func printLatencyHistory(events []LatencyEvent, eventName string) {
	fmt.Printf("\n=== LATENCY HISTORY: %s ===\n", eventName)
	if len(events) == 0 {
		fmt.Println("  No events recorded.")
		return
	}
	var maxUs int64
	for _, e := range events {
		if e.LatencyUs > maxUs {
			maxUs = e.LatencyUs
		}
		ts := time.Unix(e.Timestamp, 0).Format(time.RFC3339)
		fmt.Printf("  %s | %.2fms\n", ts, e.LatencyMs())
	}
	fmt.Printf("Max recorded: %.2fms\n", float64(maxUs)/1000)
}

func main() {
	ctx := context.Background()
	rdb := redis.NewClient(&redis.Options{
		Addr: "localhost:6379",
		DB:   0,
	})
	defer rdb.Close()

	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Fatalf("Cannot connect to Redis: %v", err)
	}

	// 1. SLOWLOG report
	fmt.Println("Fetching SLOWLOG...")
	report, err := ParseSlowLog(ctx, rdb, 1000)
	if err != nil {
		log.Printf("SLOWLOG error: %v", err)
	} else {
		printSlowLogReport(report)
	}

	// 2. LATENCY LATEST
	fmt.Println("\nFetching LATENCY LATEST...")
	latest, err := GetLatencyLatest(ctx, rdb)
	if err != nil {
		log.Printf("LATENCY LATEST error: %v", err)
	} else {
		fmt.Println("=== LATENCY LATEST ===")
		for _, e := range latest {
			ts := time.Unix(e.Timestamp, 0).Format(time.RFC3339)
			fmt.Printf("  %s | %-30s | %.2fms | samples=%d\n",
				ts, e.Event, e.LatencyMs(), e.NumSamples)
		}
	}

	// 3. LATENCY HISTORY for specific events
	for _, event := range []string{"fork", "command"} {
		events, err := GetLatencyHistory(ctx, rdb, event)
		if err != nil {
			log.Printf("LATENCY HISTORY %s: %v", event, err)
			continue
		}
		printLatencyHistory(events, event)
	}
}
```

---

## 10. Production Checklist: Latency Monitoring & Benchmarking

```txt
PRE-BENCHMARK CHECKLIST
-----------------------
[ ] 1.  Run redis-cli --intrinsic-latency 120 to establish server baseline.
          Target: < 1 microsecond. If > 5µs → investigate CPU/THP before benchmarking.

[ ] 2.  Verify Redis config: CONFIG GET slowlog-log-slower-than, latency-monitor-threshold.
          Recommended: slowlog-log-slower-than=5000, latency-monitor-threshold=100.

[ ] 3.  Clear slowlog before benchmark: SLOWLOG RESET.

[ ] 4.  Warm up Redis: populate with realistic dataset (same size as production).
          Cold cache fit in CPU cache → unrealistically fast results.

[ ] 5.  Use realistic payload size: benchmark with 1KB, 4KB, 16KB (not default 3 bytes).

[ ] 6.  Use realistic mix: --ratio=1:9 (10% SET, 90% GET) if production is read-heavy.
          GET-only benchmark underestimates write latency.

[ ] 7.  Benchmark from same network location as production clients.
          Localhost vs WAN: 0.05ms vs 15ms RTT → 300× difference.

[ ] 8.  Run benchmark for at least 5-10 minutes to capture sustained-load patterns.
          10-second one-shot misses burst behavior and periodic events (BGSAVE, AOF rewrite).

[ ] 9.  Run each benchmark 3 times and use median values (discard first run).
          First run: cold start, JIT warmup, COW page allocation.

[ ] 10. Disable THP on Redis host: echo never > /sys/kernel/mm/transparent_hugepage/enabled
          THP increases fork latency 2-5× and causes latency spikes.

POST-BENCHMARK CHECKLIST
------------------------
[ ] 11. After benchmark: check SLOWLOG GET to see if any commands were slow.
          Slowlog entries > 0 → those commands exceeded threshold during test.

[ ] 12. Compare p50/p95/p99 against SLA targets.
          Record results with hardware spec, Redis version, and config.

[ ] 13. Export benchmark results to JSON/CSV for historical tracking.
          Revisit benchmarks quarterly or after major config changes.

[ ] 14. Alerting: set up SLOWLOG LEN monitoring.
          slowlog_len > 0 (for threshold-based alert) or slowlog_len growing.

[ ] 15. Document network topology (RTT, bandwidth) with benchmark results.
          Same benchmark on different network → different results.
```

---

## 11. Links & References

### Official Redis Documentation
- https://redis.io/docs/reference/latency/ — Latency monitoring internals
- https://redis.io/commands/slowlog-get/ — SLOWLOG command reference
- https://redis.io/commands/latency-doctor/ — LATENCY DOCTOR reference
- https://redis.io/docs/management/optimize/redis-throughput/ — Redis throughput optimization

### Redis Built-in Tools
- https://redis.io/docs/reference/clients/redis-cli/ — redis-cli latency flags
- https://redis.io/docs/management/security/protected-mode/ — Protected mode considerations

### Benchmarking Tools
- https://github.com/RedisLabs/memtier_benchmark — memtier_benchmark GitHub
- https://github.com/redis/redis — redis-benchmark source (included in Redis repo)
- https://github.com/HdrHistogram/hdrhistogram-go — HDR histogram for Go latency measurement
- https://github.com/RussellLuo/hdrhist — Alternative HDR histogram for Go

### Blog Posts & Articles
- https://redis.com/blog/latency spikes-in-redis/ — antirez on Redis latency (archived)
- https://instagram-engineering.com/ — Instagram Redis latency case studies
- https://githubengineering.com/ — GitHub engineering blog (Redis at scale)

### Monitoring & Visualization
- https://redis.io/docs/management/redis-insight/ — RedisInsight (free GUI, slowlog viewer)
- https://grafana.com/ — Grafana dashboards for Redis (Prometheus exporter)
- https://prometheus.io/ — Prometheus Redis exporter (redis_exporter on GitHub)

### Additional Learning
- https://redis.io/topics/redis-cluster-spec — Redis Cluster and network topology
- https://man7.org/linux/man-pages/man7/tcp.7.html — TCP keepalive tuning
- https://www.kernel.org/doc/html/latest/admin-guide/mm/transhuge.html — Transparent Huge Pages
