package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"time"

	"capstone/shared"
	"github.com/google/uuid"
	_ "github.com/lib/pq"
)

type createOrderRequest struct {
	CustomerID string             `json:"customerId"`
	Items      []shared.OrderItem `json:"items"`
	Currency   string             `json:"currency"`
}

func main() {
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, nil)))
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()

	db, err := sql.Open("postgres", shared.Env("DATABASE_URL", "postgres://ecommerce:ecommerce@localhost:5432/ecommerce?sslmode=disable"))
	if err != nil {
		slog.Error("db open failed", "error", err)
		os.Exit(1)
	}
	defer db.Close()

	writer := shared.Writer(shared.Env("KAFKA_BROKER", "localhost:9092"))
	defer writer.Close()
	go shared.OutboxPoller(ctx, db, writer, "order-service", 250*time.Millisecond)
	go consumeInventory(ctx, db)
	go consumePaymentFailures(ctx, db)

	mux := http.NewServeMux()
	mux.HandleFunc("/orders", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		createOrder(ctx, db, w, r)
	})
	mux.HandleFunc("/orders/", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		getOrder(ctx, db, w, r.URL.Path[len("/orders/"):])
	})
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	server := &http.Server{Addr: ":8080", Handler: mux}
	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = server.Shutdown(shutdownCtx)
	}()

	slog.Info("order-service listening", "addr", ":8080")
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		slog.Error("http server failed", "error", err)
		os.Exit(1)
	}
}

func createOrder(ctx context.Context, db *sql.DB, w http.ResponseWriter, r *http.Request) {
	var req createOrderRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if req.Currency == "" {
		req.Currency = "USD"
	}
	orderID := "ord_" + uuid.NewString()
	var total float64
	for _, item := range req.Items {
		total += float64(item.Quantity) * item.Price
	}

	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer tx.Rollback()

	items, _ := json.Marshal(req.Items)
	if _, err := tx.ExecContext(ctx, `
		INSERT INTO orders (id, customer_id, items, total_amount, currency, status)
		VALUES ($1, $2, $3, $4, $5, 'PENDING')`,
		orderID, req.CustomerID, items, total, req.Currency,
	); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	correlationID := r.Header.Get("X-Correlation-ID")
	if correlationID == "" {
		correlationID = "corr_" + uuid.NewString()
	}
	event := shared.NewEvent("order.created.v1", correlationID, orderID, "order-service", shared.OrderCreatedData{
		OrderID:     orderID,
		CustomerID:  req.CustomerID,
		Items:       req.Items,
		TotalAmount: total,
		Currency:    req.Currency,
	})
	if err := shared.InsertOutbox(ctx, tx, "order-service", "order-events", orderID, event); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	if err := tx.Commit(); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]string{"orderId": orderID, "status": "PENDING"})
}

func getOrder(ctx context.Context, db *sql.DB, w http.ResponseWriter, orderID string) {
	var row struct {
		ID         string          `json:"id"`
		CustomerID string          `json:"customerId"`
		Items      json.RawMessage `json:"items"`
		Total      float64         `json:"totalAmount"`
		Currency   string          `json:"currency"`
		Status     string          `json:"status"`
	}
	err := db.QueryRowContext(ctx, `
		SELECT id, customer_id, items, total_amount, currency, status
		FROM orders
		WHERE id = $1`, orderID,
	).Scan(&row.ID, &row.CustomerID, &row.Items, &row.Total, &row.Currency, &row.Status)
	if err == sql.ErrNoRows {
		http.NotFound(w, nil)
		return
	}
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(row)
}

func consumeInventory(ctx context.Context, db *sql.DB) {
	reader := shared.Reader(shared.Env("KAFKA_BROKER", "localhost:9092"), "order-service", "inventory-events")
	defer reader.Close()
	for {
		msg, err := reader.FetchMessage(ctx)
		if err != nil {
			return
		}
		var event shared.Event
		if err := json.Unmarshal(msg.Value, &event); err != nil {
			_ = reader.CommitMessages(ctx, msg)
			continue
		}
		seen, err := shared.MarkInbox(ctx, db, event, "order-service")
		if err != nil || !seen {
			_ = reader.CommitMessages(ctx, msg)
			continue
		}
		switch event.EventType {
		case "inventory.reserved.v1":
			data, _ := shared.DecodeData[shared.InventoryReservedData](event)
			_, _ = db.ExecContext(ctx, "UPDATE orders SET status='CONFIRMED', updated_at=NOW() WHERE id=$1", data.OrderID)
		case "inventory.insufficient.v1":
			data, _ := shared.DecodeData[shared.OrderCancelledData](event)
			_, _ = db.ExecContext(ctx, "UPDATE orders SET status='CANCELLED', updated_at=NOW() WHERE id=$1", data.OrderID)
		}
		_ = reader.CommitMessages(ctx, msg)
	}
}

func consumePaymentFailures(ctx context.Context, db *sql.DB) {
	reader := shared.Reader(shared.Env("KAFKA_BROKER", "localhost:9092"), "order-service-payment-failures", "payment-events")
	defer reader.Close()
	for {
		msg, err := reader.FetchMessage(ctx)
		if err != nil {
			return
		}
		var event shared.Event
		if err := json.Unmarshal(msg.Value, &event); err != nil {
			_ = reader.CommitMessages(ctx, msg)
			continue
		}
		if event.EventType != "payment.failed.v1" {
			_ = reader.CommitMessages(ctx, msg)
			continue
		}
		seen, err := shared.MarkInbox(ctx, db, event, "order-service-payment-failures")
		if err != nil || !seen {
			_ = reader.CommitMessages(ctx, msg)
			continue
		}
		data, _ := shared.DecodeData[shared.OrderCancelledData](event)
		_, _ = db.ExecContext(ctx, "UPDATE orders SET status='CANCELLED', updated_at=NOW() WHERE id=$1", data.OrderID)
		slog.Info("order cancelled due to payment failure", "orderId", data.OrderID, "correlationId", event.CorrelationID)
		_ = reader.CommitMessages(ctx, msg)
	}
}
