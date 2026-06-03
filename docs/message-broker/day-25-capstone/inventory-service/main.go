package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"log/slog"
	"os"
	"os/signal"

	"capstone/shared"
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
	reader := shared.Reader(broker, "inventory-service", "payment-events")
	defer reader.Close()
	writer := shared.Writer(broker)
	defer writer.Close()

	for {
		msg, err := reader.FetchMessage(ctx)
		if err != nil {
			return
		}
		if err := handle(ctx, db, writer, msg.Value); err != nil {
			slog.Error("inventory handling failed", "error", err)
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
	seen, err := shared.MarkInbox(ctx, db, event, "inventory-service")
	if err != nil || !seen {
		return err
	}

	switch event.EventType {
	case "payment.failed.v1":
		data, err := shared.DecodeData[shared.OrderCancelledData](event)
		if err != nil {
			return err
		}
		cancelled := shared.NewEvent("inventory.skipped.v1", event.CorrelationID, event.EventID, "inventory-service", data)
		return shared.Publish(ctx, writer, "inventory-events", data.OrderID, cancelled)
	case "payment.completed.v1":
		data, err := shared.DecodeData[shared.PaymentCompletedData](event)
		if err != nil {
			return err
		}
		tx, err := db.BeginTx(ctx, nil)
		if err != nil {
			return err
		}
		defer tx.Rollback()
		for _, item := range data.Items {
			res, err := tx.ExecContext(ctx, `
				UPDATE inventory
				SET reserved = reserved + $1
				WHERE product_id = $2 AND quantity - reserved >= $1`,
				item.Quantity, item.ProductID,
			)
			if err != nil {
				return err
			}
			affected, err := res.RowsAffected()
			if err != nil {
				return err
			}
			if affected != 1 {
				insufficient := shared.NewEvent("inventory.insufficient.v1", event.CorrelationID, event.EventID, "inventory-service", shared.OrderCancelledData{
					OrderID: data.OrderID,
					Reason:  "insufficient_stock",
				})
				if err := tx.Rollback(); err != nil {
					slog.Warn("rollback failed", "error", err)
				}
				slog.Info("inventory insufficient", "orderId", data.OrderID, "productId", item.ProductID)
				return shared.Publish(ctx, writer, "inventory-events", data.OrderID, insufficient)
			}
		}
		if err := tx.Commit(); err != nil {
			return err
		}
		reserved := shared.NewEvent("inventory.reserved.v1", event.CorrelationID, event.EventID, "inventory-service", shared.InventoryReservedData{OrderID: data.OrderID})
		slog.Info("inventory reserved", "orderId", data.OrderID)
		return shared.Publish(ctx, writer, "inventory-events", data.OrderID, reserved)
	default:
		return nil
	}
}
