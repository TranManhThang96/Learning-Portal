package main

import (
	"context"
	"encoding/json"
	"log/slog"
	"os"
	"os/signal"
	"sync"

	"capstone/shared"
)

func main() {
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, nil)))
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()

	broker := shared.Env("KAFKA_BROKER", "localhost:9092")
	topics := []string{"order-events", "payment-events", "inventory-events", "notification-events"}

	var wg sync.WaitGroup
	for _, topic := range topics {
		wg.Add(1)
		go func(topic string) {
			defer wg.Done()
			reader := shared.Reader(broker, "notification-service-"+topic, topic)
			defer reader.Close()
			for {
				msg, err := reader.FetchMessage(ctx)
				if err != nil {
					return
				}
				var event shared.Event
				if err := json.Unmarshal(msg.Value, &event); err == nil {
					slog.Info("notification observed event",
						"topic", topic,
						"eventType", event.EventType,
						"eventId", event.EventID,
						"correlationId", event.CorrelationID,
					)
				}
				_ = reader.CommitMessages(ctx, msg)
			}
		}(topic)
	}
	wg.Wait()
}
