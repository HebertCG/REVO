ALTER TABLE ml_training_data ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'synthetic';
UPDATE ml_training_data SET source='synthetic' WHERE source IS NULL;

CREATE TABLE IF NOT EXISTS prediction_feedbacks (
    id SERIAL PRIMARY KEY,
    prediction_id INTEGER NOT NULL REFERENCES predictions(id),
    user_id INTEGER NOT NULL,
    session_id INTEGER,
    diagnostic_affinity BOOLEAN NOT NULL,
    discovery_level VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(prediction_id)
);
