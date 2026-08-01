# Your Skinfluencer

Your Skinfluencer is a data-preparation pipeline and local Shiny application for exploring beauty influencers' product opinions.

The pipeline downloads YouTube video metadata, full descriptions, and transcripts; extracts canonical product names from descriptions; matches those products to noisy automatic transcripts; generates grounded, conversational summaries; and stores approved results in SQLite. The end-user application reads only from SQLite and does **not** call an LLM during search.

## Why this approach?

Automatic YouTube transcripts often distort beauty brand and product names. A transcript may render a known product as a phonetic approximation, making transcript-only product discovery unreliable.

This project uses the video's own description as the product catalog for that video:

```text
YouTube description -> canonical product candidates
YouTube transcript  -> product-specific opinions and evidence
                       |
                       v
               approved / review / rejected
                       |
                       v
                    SQLite
                       |
                       v
                 Shiny application
```

This separation improves product-name accuracy while preserving the influencer's original transcript evidence.

## Features

- Downloads complete YouTube descriptions and transcripts without downloading video or audio.
- Uses a transcript fallback when the primary transcript request fails.
- Extracts beauty products from unstructured descriptions with OpenAI Structured Outputs.
- Matches canonical description products to noisy automatic transcript mentions.
- Produces conversational Turkish summaries grounded in exact transcript excerpts.
- Classifies each result as `approved`, `review`, or `rejected`.
- Stores approved comments in SQLite and preserves unresolved records separately.
- Searches by brand, full product name, approximate spelling, and selected Turkish/English aliases.
- Runs the user-facing application without OpenAI API calls.

## Current creators

- Naturally Serein
- Yağmur Vardar

The pipeline is creator-agnostic: additional channels can be processed with the same commands.

## Repository structure

```text
.
├── app.py
├── build_sqlite_database.py
├── download_youtube_data.py
├── extract_description_products_openai.py
├── extract_transcript_product_comments_openai.py
├── schema.sql
├── requirements.txt
├── .env.example
├── .gitignore
└── data/
    └── .gitkeep
```

Generated files under `data/` are intentionally excluded from version control.

## Requirements

- Python 3.11 or newer
- An OpenAI API key for preprocessing
- Internet access for YouTube ingestion and preprocessing

SQLite is included with Python; a separate database server is not required.

## Installation

```bash
git clone <your-repository-url>
cd <your-repository-folder>

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
```

Add your API key to `.env`:

```text
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-5-mini
```

Never commit `.env` or an API key.

## Pipeline

### 1. Download metadata, descriptions, and transcripts

Naturally Serein:

```bash
python download_youtube_data.py \
  --channel-url "https://www.youtube.com/@NaturallySerein/videos" \
  --influencer naturally_serein
```

Yağmur Vardar:

```bash
python download_youtube_data.py \
  --channel-url "https://www.youtube.com/@yagmurvardar/videos" \
  --influencer yagmurvardar
```

The downloader creates:

```text
data/<influencer>/
├── metadata/
├── transcripts/
├── downloaded_videos.json
├── failures.json
└── summary.json
```

Metadata is saved before transcript retrieval. If transcript retrieval fails, the complete video description is still preserved and the video can be retried later.

Useful options:

```bash
python download_youtube_data.py --help
```

For example, to retry every eligible video:

```bash
python download_youtube_data.py \
  --channel-url "https://www.youtube.com/@NaturallySerein/videos" \
  --influencer naturally_serein \
  --force
```

### 2. Extract canonical products from descriptions

```bash
python extract_description_products_openai.py \
  --influencer naturally_serein
```

```bash
python extract_description_products_openai.py \
  --influencer yagmurvardar
```

Output:

```text
data/<influencer>/description_products_llm/
```

Each extracted product includes an exact evidence excerpt from the original video description. Products without exact evidence or a reliable brand remain in review status.

### 3. Extract grounded product comments from transcripts

```bash
python extract_transcript_product_comments_openai.py \
  --influencer naturally_serein
```

```bash
python extract_transcript_product_comments_openai.py \
  --influencer yagmurvardar
```

Output:

```text
data/<influencer>/product_mentions_llm_final_v2/
```

The extractor does not discover new canonical products. It receives a fixed candidate list from the description stage and determines whether each product is reviewed, merely mentioned, or unsupported by the transcript.

For every validated review it stores:

- canonical brand and product name;
- noisy transcript product mention;
- conversational display summary;
- sentiment;
- exact transcript evidence;
- confidence and validation status.

### 4. Build the SQLite database

```bash
python build_sqlite_database.py \
  --influencer naturally_serein \
  --influencer yagmurvardar \
  --reset
```

Output:

```text
data/database/skinfluencer.sqlite
```

Database behavior:

- `approved` results are added to the searchable application tables;
- `review` and `rejected` results are retained in `unresolved_mentions`;
- imports are idempotent and do not duplicate the same product/video record;
- a newly generated extraction for a video replaces that video's previous imported rows.

### 5. Run the Shiny application

```bash
shiny run --reload --launch-browser app.py
```

The application supports:

- influencer selection;
- brand-aware product autocomplete;
- fuzzy matching for approximate names and minor spelling mistakes;
- aliases such as `güneş kremi`, `sun cream`, and `sunscreen`;
- conversational influencer summaries;
- sentiment, source video, confidence, and transcript evidence.

The application reads SQLite in read-only mode and does not call OpenAI.

## Example

A description may contain the canonical product:

```text
La Roche-Posay - Effaclar Azelaic Acid Serum
```

The automatic transcript may contain a distorted mention such as:

```text
Laro Pos'in efektler... azalik asit serumu
```

Because the product catalog comes from the description, the transcript stage can match the noisy mention to the correct product and extract only the evidence-backed opinion.

## Data model

Main SQLite tables:

- `influencers`
- `videos`
- `products`
- `product_mentions`
- `unresolved_mentions`
- `import_runs`

The `approved_product_comments` view powers the Shiny application.

## Cost model

OpenAI is used only during offline preprocessing:

- description product extraction;
- transcript-product matching;
- grounded summary and sentiment extraction.

Search, autocomplete, SQLite queries, and normal application use do not create OpenAI API costs.

## Privacy and repository hygiene

Do not commit:

- `.env`;
- API keys;
- raw transcripts or metadata;
- generated LLM outputs;
- local SQLite databases.

The included `.gitignore` excludes these files by default.

## Limitations

- Product lists in descriptions may include alternatives that are not meaningfully reviewed in the transcript; these are rejected at the transcript stage.
- Automatic captions can still be unavailable or temporarily rate-limited.
- `review` results require manual inspection before they should be exposed to users.
- Product names are grounded in the video's description and are not independently verified against a live retail catalog.

## Roadmap

- Add more Turkish and international beauty creators.
- Add a manual review dashboard for unresolved records.
- Add product aliases and canonical catalog maintenance tools.
- Add PostgreSQL support for deployment.
- Add tests and a modular package structure under `src/skinfluencer/`.

## Disclaimer

The application summarizes public influencer statements. It does not provide medical or dermatological advice. Product suitability varies by person, and source videos should be consulted for full context.
