package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log/slog"
	"math/rand"
	"os"
	"os/signal"

	"capstone/shared"
	"github.com/google/uuid"
	_ "github.com/lib/pq"
	"github.com/segmentio/kafka-go"
)

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

	broker := shared.Env("KAFKA_BROKER", "localhost:9092")
	reader := shared.Reader(broker, "payment-service", "order-events")
	defer reader.Close()
	writer := shared.Writer(broker)
	defer writer.Close()

	for {
		msg, err := reader.FetchMessage(ctx)
		if err != nil {
			return
		}
		if err := handle(ctx, db, writer, msg.Value); err != nil {
			slog.Error("payment handling failed", "error", err)
			continue
		}
		_ = reader.CommitMessages(ctx, msg)
	}
}

func handle(ctx context.Context, db *sql.DB, writer *kafka.Writer, payload []byte) error {
	var event shared.Event
	if err := json.Unmarshal(payload, &event); err != nil {
		return err
	}
	if event.EventType != "order.created.v1" {
		return nil
	}
	seen, err := shared.MarkInbox(ctx, db, event, "payment-service")
	if err != nil || !seen {
		return err
	}
	order, err := shared.DecodeData[shared.OrderCreatedData](event)
	if err != nil {
		return err
	}

	paymentID := "pay_" + uuid.NewString()
	status := "COMPLETED"
	if rand.Intn(100) < 5 {
		status = "FAILED"
	}
	_, err = db.ExecContext(ctx, `
		INSERT INTO payments (id, order_id, amount, status, transaction_ref)
		VALUES ($1, $2, $3, $4, $5)
		ON CONFLICT (id) DO NOTHING`,
		paymentID, order.OrderID, order.TotalAmount, status, "txn_"+uuid.NewString(),
	)
	if err != nil {
		return err
	}

	if status == "FAILED" {
		failed := shared.NewEvent("payment.failed.v1", event.CorrelationID, event.EventID, "payment-service", shared.OrderCancelledData{
			OrderID: order.OrderID,
			Reason:  "payment_failed",
		})
		slog.Info("payment failed", "orderId", order.OrderID, "correlationId", event.CorrelationID)
		return shared.Publish(ctx, writer, "payment-events", order.OrderID, failed)
	}

	completed := shared.NewEvent("payment.completed.v1", event.CorrelationID, event.EventID, "payment-service", shared.PaymentCompletedData{
		PaymentID:      paymentID,
		OrderID:        order.OrderID,
		Amount:         order.TotalAmount,
		TransactionRef: fmt.Sprintf("txn_%s", paymentID),
		Items:          order.Items,
	})
	slog.Info("payment completed", "orderId", order.OrderID, "correlationId", event.CorrelationID)
	return shared.Publish(ctx, writer, "payment-events", order.OrderID, completed)
}
