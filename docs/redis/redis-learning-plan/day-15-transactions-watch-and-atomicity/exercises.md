# Day 15: Transactions, WATCH & Atomicity — Exercises

**Thời gian**: ~2 giờ
**Ngôn ngữ**: Go (Day 14 dùng TypeScript nên Day 15 luân phiên sang Go)
**Môi trường**: Docker Compose với Redis 7.2

---

## 0. Setup

```bash
# Thư mục làm việc
mkdir -p ~/redis-tx-lab && cd ~/redis-tx-lab

# Docker Compose
cat > docker-compose.yml <<'EOF'
version: '3.8'
services:
  redis:
    image: redis:7.2
    ports:
      - "6379:6379"
    command: redis-server --save "" --appendonly no
    # disable persistence để lab chạy nhanh, không cần durability ở đây
EOF

docker compose up -d
redis-cli PING  # expect: PONG
```

---

## 1. Warm-up Exercises (15-20 phút)

Muc tiêu: làm quen với MULTI/EXEC/WATCH behavior bằng redis-cli, gây conflict thủ công.

### Exercise 1.1: MULTI/EXEC cơ bản

```bash
redis-cli
```

Thực hiện:

```txt
DEL counter
MULTI
INCR counter
INCR counter
INCR counter
EXEC
```

Kết quả mong đợi:
```txt
QUEUED
QUEUED
QUEUED
1) (integer) 1
2) (integer) 2
3) (integer) 3
```

Giải thích: mỗi INCR tăng giá trị, trả về giá trị sau mỗi increment.

### Exercise 1.2: Syntax error cancel cả transaction

```txt
MULTI
SET a 1
NONEXISTENT_COMMAND param
INCR b
EXEC
```

Kết quả mong đợi:
```txt
(error) ERR unknown command 'NONEXISTENT_COMMAND'
```

Lưu ý: không trả về QUEUED cho command tiếp theo. Syntax error xảy ra tại queue time → cancel toàn bộ.

### Exercise 1.3: Runtime error không cancel transaction

```txt
SET strkey "hello"
MULTI
SET numkey 100
INCR strkey
INCR numkey
EXEC
```

Kết quả mong đợi:
```txt
1) OK
2) (error) WRONGTYPE Operation against a key holding the wrong kind of value
3) (integer) 101
```

Giải thích: INCR strkey lỗi runtime (WRONGTYPE), nhưng INCR numkey vẫn chạy. Response là array với error object ở position 2.

### Exercise 1.4: WATCH gây conflict thủ công

Terminal 1:
```txt
SET inventory:sku001 10
WATCH inventory:sku001
GET inventory:sku001   -- đọc giá trị (local, chưa modify)
```

Terminal 2 (trong khi Terminal 1 đang watch):
```txt
DECR inventory:sku001   -- modify key
```

Terminal 1 (quay lại):
```txt
MULTI
DECR inventory:sku001
EXEC
```

Kết quả mong đợi: EXEC trả về (nil). Vì key đã bị modify giữa WATCH và EXEC.

Kiểm tra giá trị:
```txt
GET inventory:sku001   -- vẫn là 9 (không phải 8)
```

### Exercise 1.5: UNWATCH

```txt
SET x 0
WATCH x
UNWATCH
SET x 99
MULTI
INCR x
EXEC
```

Kết quả mong đợi: EXEC trả về `(integer) 100`. Vì UNWATCH đã hủy watched key, SET x 99 không trigger conflict.

---

## 2. Hands-on Lab (60-70 phút)

**Lab: Inventory Reservation — 3 Approaches So sánh**

### Mục tiêu

Implement inventory reservation system cho một e-commerce platform. So sánh 3 approach:

1. **No protection** (race condition demo)
2. **WATCH + MULTI/EXEC** (optimistic locking)
3. **Lua script** (atomic DECR + conditional check)

### Bước 1: Setup project Go

```bash
mkdir -p ~/redis-tx-lab/inventory-lab
cd ~/redis-tx-lab/inventory-lab

# Initialize Go module
go mod init inventory-lab

# Install go-redis
go get github.com/redis/go-redis/v9@latest
```

```go
// main.go
package main

import (
    "context"
    "fmt"
    "sync"
    "time"

    "github.com/redis/go-redis/v9"
)

var ctx = context.Background()
var rdb *redis.Client

func init() {
    rdb = redis.NewClient(&redis.Options{
        Addr: "localhost:6379",
    })
}

// Reset inventory for testing
func resetInventory(sku string, stock int) {
    rdb.Set(ctx, "inventory:"+sku, stock, 0)
    rdb.Del(ctx, "reserved:users")
}

func main() {
    defer rdb.Close()

    sku := "SKU-LAPTOP-001"
    initialStock := 100
    numWorkers := 20
    reservationsPerWorker := 10

    // Test each approach
    approaches := []struct {
        name string
        fn   func(string, int, int) (success, failed int)
    }{
        {"No Protection (race demo)", reserveNoProtection},
        {"WATCH + MULTI/EXEC", reserveWithWatch},
        {"Lua Script (atomic)", reserveWithLua},
    }

    for _, ap := range approaches {
        resetInventory(sku, initialStock)
        success, failed := ap.fn(sku, numWorkers, reservationsPerWorker)
        finalStock, _ := rdb.Get(ctx, "inventory:"+sku).Int()
        fmt.Printf("%-30s success=%-3d failed=%-3d final_stock=%-3d (expected=%d)\n",
            ap.name, success, failed, finalStock, initialStock-success)
    }
}
```

### Bước 2: No Protection (race condition)

```go
// reserveNoProtection demonstrates race condition
func reserveNoProtection(sku string, numWorkers, perWorker int) (success, failed int) {
    var wg sync.WaitGroup
    var mu sync.Mutex

    for i := 0; i < numWorkers; i++ {
        wg.Add(1)
        go func(workerID int) {
            defer wg.Done()
            for j := 0; j < perWorker; j++ {
                // Race: GET and DECR are not atomic together
                stockStr, err := rdb.Get(ctx, "inventory:"+sku).Result()
                if err == redis.Nil {
                    mu.Lock()
                    failed++
                    mu.Unlock()
                    continue
                }
                if err != nil {
                    mu.Lock()
                    failed++
                    mu.Unlock()
                    continue
                }

                stock := 0
                fmt.Sscanf(stockStr, "%d", &stock)
                if stock <= 0 {
                    mu.Lock()
                    failed++
                    mu.Unlock()
                    continue
                }

                // Another goroutine may have decremented between GET and DECR
                _, err = rdb.Decr(ctx, "inventory:"+sku).Result()
                if err == nil {
                    mu.Lock()
                    success++
                    mu.Unlock()
                } else {
                    mu.Lock()
                    failed++
                    mu.Unlock()
                }
            }
        }(i)
    }
    wg.Wait()
    return
}
```

**Expected output**: `success` > `initialStock - numWorkers*perWorker` (oversold!). Ví dụ: initial 100, 20 workers × 10 = 200 attempts → có thể success ~150+ (oversell 50+ units).

### Bước 3: WATCH + MULTI/EXEC

WATCH phù hợp ở đây vì bài lab cần minh họa optimistic locking. Trong production nếu chỉ cần check `stock > 0` rồi decrement một key, Lua thường tốt hơn vì ít RTT hơn và không tạo retry storm khi contention cao.

```go
// reserveWithWatch uses optimistic locking.
// go-redis TxPipelined inside Watch sends MULTI/EXEC and returns redis.TxFailedErr
// when the watched key was modified before EXEC.
func reserveWithWatch(sku string, numWorkers, perWorker int) (success, failed int) {
    var wg sync.WaitGroup
    var mu sync.Mutex
    const maxRetries = 10

    for i := 0; i < numWorkers; i++ {
        wg.Add(1)
        go func(workerID int) {
            defer wg.Done()
            for j := 0; j < perWorker; j++ {
                var ok bool
                for retry := 0; retry < maxRetries; retry++ {
                    if retry > 0 {
                        time.Sleep(time.Duration(1<<uint(retry)) * time.Millisecond)
                    }

                    stockKey := "inventory:" + sku
                    err := rdb.Watch(ctx, func(tx *redis.Tx) error {
                        stock, err := tx.Get(ctx, stockKey).Int()
                        if err != nil && err != redis.Nil {
                            return err
                        }
                        if stock <= 0 {
                            return fmt.Errorf("out of stock")
                        }

                        _, err = tx.TxPipelined(ctx, func(pipe redis.Pipeliner) error {
                            pipe.Decr(ctx, stockKey)
                            return nil
                        })
                        return err
                    }, "inventory:"+sku)

                    if err == nil {
                        ok = true
                        break
                    }
                    if err == redis.TxFailedErr {
                        continue
                    }
                    break
                }

                mu.Lock()
                if ok {
                    success++
                } else {
                    failed++
                }
                mu.Unlock()
            }
        }(i)
    }
    wg.Wait()
    return
}
```

### Bước 4: Lua Script

```go
var reserveInventoryScript = redis.NewScript(`
local stock = redis.call('GET', KEYS[1])
if stock == false then
    return -1
end
stock = tonumber(stock)
if stock <= 0 then
    return 0
end
redis.call('DECR', KEYS[1])
return 1
`)

func reserveWithLua(sku string, numWorkers, perWorker int) (success, failed int) {
    var wg sync.WaitGroup
    var mu sync.Mutex
    stockKey := "inventory:" + sku

    for i := 0; i < numWorkers; i++ {
        wg.Add(1)
        go func(workerID int) {
            defer wg.Done()
            for j := 0; j < perWorker; j++ {
                result, err := reserveInventoryScript.Run(ctx, rdb,
                    []string{stockKey},
                ).Int(ctx)

                mu.Lock()
                if err != nil {
                    failed++
                } else if result == 1 {
                    success++
                } else {
                    // result == 0 (out of stock) or -1 (key not found)
                    failed++
                }
                mu.Unlock()
            }
        }(i)
    }
    wg.Wait()
    return
}
```

### Bước 5: Benchmark & Compare

Chạy main.go:

```bash
go run main.go
```

**Expected results**:

```txt
No Protection (race demo)        success=147  failed=53   final_stock=-47 (expected=0)
WATCH + MULTI/EXEC               success=100  failed=100  final_stock=0   (expected=0)
Lua Script (atomic)              success=100  failed=100  final_stock=0   (expected=0)
```

Observations:
- No protection: oversold (final stock negative) — demonstrates race condition
- WATCH: correct inventory (no oversell), nhưng nếu bug thì sẽ khác
- Lua: correct, slightly faster than WATCH (fewer RTTs)

**Thêm benchmark cho latency**:

```go
func benchmarkLatency(name string, fn func() error, iterations int) {
    durations := make([]time.Duration, iterations)
    for i := 0; i < iterations; i++ {
        start := time.Now()
        fn()
        durations[i] = time.Since(start)
    }

    sort.Slice(durations, func(i, j int) bool { return durations[i] < durations[j] })
    p50 := durations[iterations/2]
    p99 := durations[iterations*99/100]

    fmt.Printf("%-20s p50=%-8s p99=%-8s\n", name, p50, p99)
}
```

---

## 3. Challenge Exercise (30-40 phút)

### Seat Booking: 100 Seats, 1000 Concurrent Users

**Scenario**: Một concert có 100 seats. 1000 users đồng thời cố gắng book seats. Mỗi user muốn book 1 seat. Implement seat booking system.

**Yêu cầu**:
1. Dùng Redis SET để track booked seats: `booked:concert:123` (SET of seat IDs)
2. Dùng WATCH approach để implement booking
3. Đo retry rate, p99 latency
4. Phân tích: khi nào nên switch sang Lua? Xác định threshold.

```go
// Starter code
const (
    totalSeats   = 100
    totalUsers   = 1000
    seatsPerUser = 1
)

func initSeats() {
    rdb.Del(ctx, "booked:concert:123")
}

// Approach: WATCH + SCARD để count booked seats
// Problem: contention cao làm nhiều EXEC abort và retry.
// Better ở production: Lua để check + SADD trong 1 RTT, hoặc pre-allocate seats qua queue.

func bookSeatWatch(concertID string, userID string) (string, error) {
    bookedKey := fmt.Sprintf("booked:concert:%s", concertID)
    maxRetries := 20

    for retry := 0; retry < maxRetries; retry++ {
        if retry > 0 {
            time.Sleep(time.Duration(1<<uint(retry)) * time.Millisecond)
        }

        var bookedSeat string
        err := rdb.Watch(ctx, func(tx *redis.Tx) error {
            booked, err := tx.SCard(ctx, bookedKey).Int()
            if err != nil {
                return err
            }
            if booked >= totalSeats {
                return fmt.Errorf("sold out")
            }

            // Deterministic probe keeps the example runnable without external state.
            start := int(time.Now().UnixNano()%int64(totalSeats)) + 1
            for offset := 0; offset < totalSeats; offset++ {
                seatNum := ((start + offset - 1) % totalSeats) + 1
                seatID := fmt.Sprintf("SEAT-%03d", seatNum)
                exists, err := tx.SIsMember(ctx, bookedKey, seatID).Result()
                if err != nil {
                    return err
                }
                if exists {
                    continue
                }

                _, err = tx.TxPipelined(ctx, func(pipe redis.Pipeliner) error {
                    pipe.SAdd(ctx, bookedKey, seatID)
                    pipe.Set(ctx, fmt.Sprintf("booking:%s:%s", concertID, userID), seatID, 24*time.Hour)
                    return nil
                })
                bookedSeat = seatID
                return err
            }
            return fmt.Errorf("sold out")
        }, bookedKey)

        if err == nil {
            return bookedSeat, nil
        }
        if err == redis.TxFailedErr {
            continue
        }
        return "", err
    }
    return "", fmt.Errorf("max retries exceeded")
}
```

**Phân tích yêu cầu**:

1. **Vẽ latency distribution**:
   - p50, p95, p99 của mỗi approach
   - Retry rate: (total attempts - successful) / total attempts

2. **So sánh WATCH vs Lua**:
   - WATCH: mỗi retry = WATCH + SCARD + SADD (3+ RTTs)
   - Lua: mỗi attempt = 1 RTT, chọn random seat trong script

3. **Xác định switch threshold**:
   - Khi retry rate > X%, Lua tốt hơn
   - Khi nào WATCH acceptable (retry rate < 5%)?

**Deliverable**:
- Code chạy được
- Số liệu retry rate, latency
- Phân tích bằng văn bản: khi nào nên switch

---

## 4. Reflection Questions

### Câu 1
Bạn đang thiết kế inventory system cho một e-commerce platform với 10 triệu SKUs, 50K requests/giây vào Black Friday. Mỗi request cần kiểm tra và decrement stock. Chọn approach nào? Vì sao không dùng WATCH?

### Câu 2
Transaction trong Redis khác với transaction trong PostgreSQL như thế nào? Nêu ít nhất 3 điểm khác biệt quan trọng trong production.

### Câu 3
Một dev nói: "Tôi dùng WATCH + MULTI/EXEC nên transaction của tôi atomic." Bạn phản bác điều này như thế nào?

### Câu 4
Trong Cluster, bạn cần atomic operation trên 2 keys ở 2 hash slots khác nhau. WATCH không hoạt động. Lua cũng không hoạt động. Bạn giải quyết như thế nào?

### Câu 5
Stripe dùng `SET key value NX EX 86400` cho idempotency. Tại sao approach này đủ cho idempotency mà không cần MULTI/EXEC hay WATCH?

---

## 5. Solution Guide

### Warning: Spoiler

Phần dưới chứa lời giải. Hãy thử làm bài tập trước khi đọc.

---

### Warm-up Solutions

**1.1**: Output là `[1, 2, 3]`. MULTI/EXEC serialize execution, mỗi INCR tăng giá trị.

**1.2**: Toàn bộ transaction bị cancel. Syntax error xảy ra khi Redis parse command để queue, trước khi EXEC. Đây là safety check.

**1.3**: Response là `[OK, error_object, 101]`. Runtime error không cancel transaction — đây là design decision. Application phải iterate response.

**1.4**: EXEC trả nil. Watched key đã bị modify. Transaction bị abort, giá trị inventory không đổi (vẫn 9). Lý do: WATCH chỉ detect conflict tại EXEC time, không prevent conflict.

**1.5**: EXEC thành công. UNWATCH hủy watched key, nên SET x 99 không trigger conflict.

---

### Lab Solutions

**No Protection Bug**: GET và DECR không atomic cùng nhau. Race window tồn tại giữa 2 commands. Kết quả: oversell.

**WATCH Fix**: Dùng `rdb.Watch(..., "inventory:"+sku)` và chỉ queue `DECR` trong `TxPipelined` sau khi đã đọc `stock > 0`. Nếu key bị modify giữa `GET` và `EXEC`, go-redis trả `redis.TxFailedErr`; application phải retry có giới hạn và backoff.

**Lua Script**: Chạy trong single event-loop step, không có race window, không retry storm. Script đọc stock, kiểm tra `stock > 0`, rồi mới `DECR`; vì check trước khi ghi nên không cần revert.

**Benchmark Expectations**:
- No protection: final stock < 0 (oversell), success count > actual stock
- WATCH: final stock = 0, success = initial stock, failed = extra attempts
- Lua: same correctness as WATCH, lower latency (fewer RTTs per attempt)

---

### Challenge Solution

**Key insight**: WATCH approach có retry storm với high contention. 1000 users cùng book 100 seats = contention rate ~90%.

```txt
Simulation results (estimated):
  WATCH approach:
    - Retry rate: ~85-90% (900/1000 attempts fail at first try)
    - Average attempts per booking: ~8-10
    - p99 latency: ~50-100ms (due to retry backoff)
    - Correctness: 100% (no oversell)

  Lua approach:
    - Retry rate: ~0% (atomic, no conflict detection needed)
    - Average attempts per booking: 1
    - p99 latency: ~0.3-0.5ms
    - Correctness: 100% (atomic check-and-decrement)

Switch threshold analysis:
  - Retry rate < 5%: WATCH acceptable
  - Retry rate 5-20%: WATCH with backoff, monitor
  - Retry rate > 20%: Switch to Lua
  - Retry rate > 50%: Lua mandatory, WATCH will cause retry storm

In this scenario (90% contention): Lua is mandatory.
```

**Lua script cho seat booking**:

```lua
local booked_key = KEYS[1]
local total_seats = tonumber(ARGV[1])

local booked_count = redis.call('SCARD', booked_key)
if booked_count >= total_seats then
    return redis.error_reply('SOLD_OUT')
end

-- Try random seats until one is available
for i = 1, 20 do
    local seat_num = math.random(1, total_seats)
    local seat_id = 'SEAT-' .. string.format('%03d', seat_num)
    local added = redis.call('SADD', booked_key, seat_id)
    if added == 1 then
        return seat_id
    end
end

return redis.error_reply('MAX_ATTEMPTS_EXCEEDED')
```

---

### Reflection Answers

**Câu 1**: Atomic single command (Lua) là approach đúng. WATCH không phù hợp vì: (1) 50K RPS = contention cực cao → retry storm, (2) mỗi request cần 1 atomic check-and-decrement → Lua làm trong 1 RTT, (3) WATCH cần retry logic, Lua không. Lua script kiểm tra stock > 0 rồi DECR atomically.

**Câu 2**:
1. Redis không có rollback, PostgreSQL có.
2. Redis không có isolation (WATCH là OCC, không phải serializable), PostgreSQL có full isolation levels.
3. Redis không có consistency enforcement (foreign key, constraint), PostgreSQL có.
4. Redis không có nested transaction, PostgreSQL có savepoints.
5. Redis failure không phục hồi tự động (application phải handle), PostgreSQL có WAL recovery.

**Câu 3**: WATCH + MULTI/EXEC đảm bảo serialized execution (tất cả commands chạy tuần tự không interrupt), nhưng KHÔNG đảm bảo atomicity theo nghĩa database. WATCH có thể abort (nil response) → application phải retry. Không có rollback. Runtime error không cancel other commands. Đây không phải ACID transaction.

**Câu 4**:
1. **Dùng hash tag**: thiết kế lại key để 2 keys cùng hash slot: `order:{userID}:items`, `order:{userID}:meta` → cùng hash tag `{userID}`.
2. **Tách thành 2 operations**: nếu acceptable, dùng 2 transactions riêng trên 2 keys (không atomic với nhau).
3. **Single key design**: gộp 2 keys thành 1 Hash: `order:{userID}` với fields `items` và `meta`.
4. **Application-level coordination**: dùng distributed lock trên userID, thực hiện 2 operations, release lock.

**Câu 5**: `SET key value NX EX 86400` là atomic single command (NX = not exists). Nếu key đã tồn tại (request đã được process), SET fail → client nhận biết idempotency, không process lại. Không cần transaction vì operation là single command. Nếu request là mới, SET thành công → process. Retry của client → SET fail → known response được trả lại. Đây là pattern "check-and-set" tự nhiên.
