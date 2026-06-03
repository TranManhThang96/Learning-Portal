CREATE TABLE IF NOT EXISTS orders (
    id            VARCHAR(64) PRIMARY KEY,
    customer_id   VARCHAR(64) NOT NULL,
    items         JSONB NOT NULL,
    total_amount  DECIMAL(12,2) NOT NULL,
    currency      VARCHAR(3) NOT NULL DEFAULT 'USD',
    status        VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS payments (
    id              VARCHAR(64) PRIMARY KEY,
    order_id        VARCHAR(64) NOT NULL,
    amount          DECIMAL(12,2) NOT NULL,
    status          VARCHAR(32) NOT NULL,
    transaction_ref VARCHAR(128),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS inventory (
    product_id VARCHAR(64) PRIMARY KEY,
    quantity   INT NOT NULL,
    reserved   INT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS inbox (
    event_id      VARCHAR(96) NOT NULL,
    owner_service VARCHAR(64) NOT NULL,
    event_type    VARCHAR(128) NOT NULL,
    processed_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (event_id, owner_service)
);

CREATE TABLE IF NOT EXISTS outbox (
    id             BIGSERIAL PRIMARY KEY,
    owner_service  VARCHAR(64) NOT NULL,
    topic          VARCHAR(128) NOT NULL,
    event_key      VARCHAR(128) NOT NULL,
    event_type     VARCHAR(128) NOT NULL,
    payload        JSONB NOT NULL,
    published_at   TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_outbox_unpublished ON outbox (owner_service, id) WHERE published_at IS NULL;

INSERT INTO inventory (product_id, quantity, reserved) VALUES
    ('PROD-001', 100, 0),
    ('PROD-002', 50, 0),
    ('PROD-003', 200, 0),
    ('PROD-004', 10, 0),
    ('PROD-005', 75, 0)
ON CONFLICT (product_id) DO NOTHING;
