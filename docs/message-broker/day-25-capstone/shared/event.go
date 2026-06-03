package shared

import (
	"context"
	"database/sql"
	"encoding/json"
	"log/slog"
	"time"

	"github.com/google/uuid"
	"github.com/segmentio/kafka-go"
)

type Event struct {
	EventID       string          `json:"eventId"`
	EventType     string          `json:"eventType"`
	Timestamp     string          `json:"timestamp"`
	CorrelationID string          `json:"correlationId"`
	CausationID   string          `json:"causationId"`
	Source        string          `json:"source"`
	Version       int             `json:"version"`
	Data          json.RawMessage `json:"data"`
}

type OrderItem struct {
	ProductID string  `json:"productId"`
	Quantity  int     `json:"quantity"`
	Price     float64 `json:"price"`
}

type OrderCreatedData struct {
	OrderID     string      `json:"orderId"`
	CustomerID  string      `json:"customerId"`
	Items       []OrderItem `json:"items"`
	TotalAmount float64     `json:"totalAmount"`
	Currency    string      `json:"currency"`
}

type PaymentCompletedData struct {
	PaymentID      string      `json:"paymentId"`
	OrderID        string      `json:"orderId"`
	Amount         float64     `json:"amount"`
	TransactionRef string      `json:"transactionRef"`
	Items          []OrderItem `json:"items"`
}

type InventoryReservedData struct {
	OrderID string `json:"orderId"`
}

type OrderCancelledData struct {
	OrderID string `json:"orderId"`
	Reason  string `json:"reason"`
}

func NewEvent(eventType, correlationID, causationID, source string, data any) Event {
	body, err := json.Marshal(data)
	if err != nil {
		panic(err)
	}
	return Event{
		EventID:       "evt_" + uuid.NewString(),
		EventType:     eventType,
		Timestamp:     time.Now().UTC().Format(time.RFC3339Nano),
		CorrelationID: correlationID,
		CausationID:   causationID,
		Source:        source,
		Version:       1,
		Data:          body,
	}
}

func DecodeData[T any](event Event) (T, error) {
	var out T
	err := json.Unmarshal(event.Data, &out)
	return out, err
}

func Writer(broker string) *kafka.Writer {
	return &kafka.Writer{
		Addr:         kafka.TCP(broker),
		Balancer:     &kafka.Hash{},
		RequiredAcks: kafka.RequireAll,
		BatchTimeout: 10 * time.Millisecond,
	}
}

func Reader(broker, groupID, topic string) *kafka.Reader {
	return kafka.NewReader(kafka.ReaderConfig{
		Brokers:        []string{broker},
		GroupID:        groupID,
		Topic:          topic,
		MinBytes:       1,
		MaxBytes:       10e6,
		CommitInterval: 0,
	})
}

func Publish(ctx context.Context, writer *kafka.Writer, topic, key string, event Event) error {
	payload, err := json.Marshal(event)
	if err != nil {
		return err
	}
	return writer.WriteMessages(ctx, kafka.Message{
		Topic: topic,
		Key:   []byte(key),
		Value: payload,
		Headers: []kafka.Header{
			{Key: "X-Correlation-ID", Value: []byte(event.CorrelationID)},
			{Key: "X-Causation-ID", Value: []byte(event.CausationID)},
			{Key: "X-Event-Type", Value: []byte(event.EventType)},
		},
	})
}

func MarkInbox(ctx context.Context, db *sql.DB, event Event, owner string) (bool, error) {
	res, err := db.ExecContext(ctx, `
		INSERT INTO inbox (event_id, owner_service, event_type)
		VALUES ($1, $2, $3)
		ON CONFLICT DO NOTHING`,
		event.EventID, owner, event.EventType,
	)
	if err != nil {
		return false, err
	}
	n, err := res.RowsAffected()
	return n == 1, err
}

func InsertOutbox(ctx context.Context, tx *sql.Tx, owner, topic, key string, event Event) error {
	payload, err := json.Marshal(event)
	if err != nil {
		return err
	}
	_, err = tx.ExecContext(ctx, `
		INSERT INTO outbox (owner_service, topic, event_key, event_type, payload)
		VALUES ($1, $2, $3, $4, $5)`,
		owner, topic, key, event.EventType, string(payload),
	)
	return err
}

func OutboxPoller(ctx context.Context, db *sql.DB, writer *kafka.Writer, owner string, every time.Duration) {
	ticker := time.NewTicker(every)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			publishOutbox(ctx, db, writer, owner)
		}
	}
}

func publishOutbox(ctx context.Context, db *sql.DB, writer *kafka.Writer, owner string) {
	rows, err := db.QueryContext(ctx, `
		SELECT id, topic, event_key, event_type, payload
		FROM outbox
		WHERE owner_service = $1 AND published_at IS NULL
		ORDER BY id
		LIMIT 20`, owner)
	if err != nil {
		slog.Error("outbox query failed", "owner", owner, "error", err)
		return
	}
	defer rows.Close()

	for rows.Next() {
		var id int64
		var topic, key, eventType string
		var payload []byte
		if err := rows.Scan(&id, &topic, &key, &eventType, &payload); err != nil {
			slog.Error("outbox scan failed", "owner", owner, "error", err)
			continue
		}
		if err := writer.WriteMessages(ctx, kafka.Message{Topic: topic, Key: []byte(key), Value: payload}); err != nil {
			slog.Error("outbox publish failed", "owner", owner, "topic", topic, "error", err)
			continue
		}
		if _, err := db.ExecContext(ctx, "UPDATE outbox SET published_at = NOW() WHERE id = $1", id); err != nil {
			slog.Error("outbox mark failed", "owner", owner, "id", id, "error", err)
			continue
		}
		slog.Info("outbox event published", "owner", owner, "eventType", eventType, "topic", topic, "key", key)
	}
}
