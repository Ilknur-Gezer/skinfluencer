PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS influencers (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY,
    influencer_id INTEGER NOT NULL REFERENCES influencers(id) ON DELETE CASCADE,
    youtube_video_id TEXT NOT NULL,
    title TEXT NOT NULL,
    upload_date TEXT,
    url TEXT NOT NULL,
    source_file TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (influencer_id, youtube_video_id)
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    brand TEXT NOT NULL,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'other_beauty',
    normalized_brand TEXT NOT NULL,
    normalized_product_name TEXT NOT NULL,
    search_text TEXT NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'approved'
        CHECK (verification_status IN ('approved', 'review', 'rejected')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (normalized_brand, normalized_product_name)
);

CREATE TABLE IF NOT EXISTS product_mentions (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    influencer_id INTEGER NOT NULL REFERENCES influencers(id) ON DELETE CASCADE,
    candidate_id TEXT,
    mention_status TEXT NOT NULL,
    display_summary TEXT NOT NULL,
    grounded_summary TEXT,
    sentiment TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    raw_product_mentions_json TEXT NOT NULL DEFAULT '[]',
    evidence_texts_json TEXT NOT NULL DEFAULT '[]',
    opinion_points_json TEXT NOT NULL DEFAULT '[]',
    quality_warnings_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'approved'
        CHECK (status IN ('approved', 'review', 'rejected')),
    status_reason TEXT,
    source_prompt_version TEXT,
    source_summary_style_version TEXT,
    extracted_at TEXT,
    source_file TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (product_id, video_id)
);

CREATE TABLE IF NOT EXISTS unresolved_mentions (
    id INTEGER PRIMARY KEY,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    influencer_id INTEGER NOT NULL REFERENCES influencers(id) ON DELETE CASCADE,
    candidate_id TEXT,
    canonical_brand TEXT,
    canonical_product_name TEXT,
    category TEXT,
    mention_status TEXT,
    status TEXT NOT NULL CHECK (status IN ('review', 'rejected')),
    reason TEXT,
    confidence REAL,
    display_summary TEXT,
    raw_payload_json TEXT NOT NULL,
    source_file TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (
        video_id,
        candidate_id,
        canonical_brand,
        canonical_product_name,
        status
    )
);

CREATE TABLE IF NOT EXISTS import_runs (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    database_path TEXT NOT NULL,
    source_subdir TEXT NOT NULL,
    influencer_slugs_json TEXT NOT NULL,
    files_seen INTEGER NOT NULL DEFAULT 0,
    videos_imported INTEGER NOT NULL DEFAULT 0,
    approved_mentions_imported INTEGER NOT NULL DEFAULT 0,
    unresolved_mentions_imported INTEGER NOT NULL DEFAULT 0,
    errors_json TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_videos_influencer
    ON videos(influencer_id);

CREATE INDEX IF NOT EXISTS idx_products_category
    ON products(category);

CREATE INDEX IF NOT EXISTS idx_products_search_text
    ON products(search_text);

CREATE INDEX IF NOT EXISTS idx_mentions_influencer
    ON product_mentions(influencer_id);

CREATE INDEX IF NOT EXISTS idx_mentions_product
    ON product_mentions(product_id);

CREATE INDEX IF NOT EXISTS idx_mentions_status
    ON product_mentions(status);

CREATE INDEX IF NOT EXISTS idx_unresolved_status
    ON unresolved_mentions(status);

DROP VIEW IF EXISTS approved_product_comments;

CREATE VIEW approved_product_comments AS
SELECT
    pm.id AS mention_id,
    p.id AS product_id,
    p.brand,
    p.product_name,
    p.category,
    p.search_text,
    i.id AS influencer_id,
    i.slug AS influencer_slug,
    i.display_name AS influencer_name,
    v.id AS video_id,
    v.youtube_video_id,
    v.title AS video_title,
    v.upload_date,
    v.url AS video_url,
    pm.display_summary,
    pm.grounded_summary,
    pm.sentiment,
    pm.confidence,
    pm.raw_product_mentions_json,
    pm.evidence_texts_json,
    pm.opinion_points_json,
    pm.quality_warnings_json,
    pm.status_reason,
    pm.extracted_at
FROM product_mentions pm
JOIN products p ON p.id = pm.product_id
JOIN videos v ON v.id = pm.video_id
JOIN influencers i ON i.id = pm.influencer_id
WHERE pm.status = 'approved';

PRAGMA user_version = 1;
