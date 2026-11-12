-- PostgreSQL equivalent of the media_plate_results confidence migration.
ALTER TABLE media_plate_results
    ALTER COLUMN plate_confidence DROP NOT NULL;

ALTER TABLE media_plate_results
    ALTER COLUMN ocr_confidence DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS raw_ocr_text TEXT,
    ADD COLUMN IF NOT EXISTS normalized_ocr_text VARCHAR(50),
    ADD COLUMN IF NOT EXISTS plate_validation_status VARCHAR(40);
