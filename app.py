from __future__ import annotations

import json
import os
import re
import sqlite3
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from shiny import App, Inputs, Outputs, Session, reactive, render, ui


DB_PATH = Path(
    os.getenv(
        "SKINFLUENCER_DB",
        "data/database/skinfluencer.sqlite",
    )
)

CATEGORY_LABELS = {
    "skincare": "Cilt bakımı",
    "makeup": "Makyaj",
    "haircare": "Saç bakımı",
    "bodycare": "Vücut bakımı",
    "fragrance": "Parfüm",
    "other_beauty": "Diğer",
}

SENTIMENT_LABELS = {
    "positive": "Olumlu",
    "negative": "Olumsuz",
    "mixed": "Karışık",
    "neutral": "Nötr",
    "unclear": "Belirsiz",
}

SENTIMENT_CLASSES = {
    "positive": "sentiment-positive",
    "negative": "sentiment-negative",
    "mixed": "sentiment-mixed",
    "neutral": "sentiment-neutral",
    "unclear": "sentiment-neutral",
}


CUSTOM_CSS = """
:root {
    --rose-50: #fff7f8;
    --rose-100: #fdecef;
    --rose-200: #f8d9df;
    --rose-500: #d97084;
    --rose-600: #bd566b;
    --ink-900: #2f2930;
    --ink-700: #5f5660;
    --ink-500: #8a808a;
    --surface: rgba(255, 255, 255, 0.94);
    --border: #eee4e7;
    --shadow: 0 18px 45px rgba(91, 62, 70, 0.10);
}

body {
    background:
        radial-gradient(
            circle at top left,
            rgba(248, 217, 223, 0.72),
            transparent 32%
        ),
        linear-gradient(180deg, #fffafa 0%, #f8f7f8 100%);
    color: var(--ink-900);
    min-height: 100vh;
}

.app-shell {
    max-width: 1180px;
    margin: 0 auto;
    padding: 2.2rem 1rem 3.5rem;
}

.hero {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 2rem;
    padding: 2rem;
    margin-bottom: 1.35rem;
    border: 1px solid rgba(255, 255, 255, 0.85);
    border-radius: 28px;
    background:
        linear-gradient(
            135deg,
            rgba(255, 255, 255, 0.97),
            rgba(255, 243, 246, 0.92)
        );
    box-shadow: var(--shadow);
}

.hero h1 {
    margin: 0;
    font-size: clamp(2rem, 4vw, 3.2rem);
    line-height: 1.04;
    letter-spacing: -0.045em;
}

.hero p {
    max-width: 720px;
    margin: 0.9rem 0 0;
    color: var(--ink-700);
    font-size: 1.06rem;
    line-height: 1.65;
}

.hero-icon {
    display: grid;
    place-items: center;
    min-width: 110px;
    height: 110px;
    border-radius: 30px;
    background: linear-gradient(145deg, #fff, var(--rose-100));
    box-shadow:
        inset 0 0 0 1px white,
        0 16px 30px rgba(189, 86, 107, 0.12);
    font-size: 3.1rem;
}

.search-panel {
    padding: 1.45rem;
    margin-bottom: 1.35rem;
    border: 1px solid var(--border);
    border-radius: 24px;
    background: var(--surface);
    box-shadow: 0 12px 35px rgba(76, 58, 64, 0.07);
    backdrop-filter: blur(10px);
}

.search-grid {
    display: grid;
    grid-template-columns:
        minmax(190px, 0.75fr)
        minmax(320px, 2fr)
        auto;
    align-items: end;
    gap: 1rem;
}

.form-label {
    color: var(--ink-700);
    font-weight: 700;
    margin-bottom: 0.48rem;
}

.form-control,
.selectize-input {
    min-height: 48px;
    border: 1px solid var(--border) !important;
    border-radius: 14px !important;
    background: white !important;
    box-shadow: none !important;
}

.selectize-input {
    display: flex;
    align-items: center;
    padding: 0.65rem 0.85rem !important;
}

.selectize-input.focus {
    border-color: var(--rose-500) !important;
    box-shadow:
        0 0 0 0.22rem rgba(217, 112, 132, 0.14) !important;
}

.selectize-dropdown {
    border: 1px solid var(--border);
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 16px 30px rgba(75, 57, 63, 0.12);
}

.selectize-dropdown .option {
    padding: 0.75rem 0.9rem;
}

.selectize-dropdown .active {
    background: var(--rose-100);
    color: var(--ink-900);
}

.search-button {
    min-height: 48px;
    padding: 0 1.4rem;
    border: 0;
    border-radius: 14px;
    background:
        linear-gradient(135deg, var(--rose-500), var(--rose-600));
    box-shadow: 0 10px 20px rgba(189, 86, 107, 0.22);
    font-weight: 700;
    white-space: nowrap;
}

.search-button:hover,
.search-button:focus {
    background: linear-gradient(135deg, #cf667b, #ad485e);
    transform: translateY(-1px);
}

.search-help {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    margin: 0.9rem 0 0;
    color: var(--ink-500);
    font-size: 0.88rem;
}

.status-card,
.result-card {
    border: 1px solid var(--border);
    border-radius: 22px;
    background: var(--surface);
    box-shadow: 0 12px 32px rgba(72, 55, 61, 0.07);
}

.status-card {
    padding: 2.2rem;
    text-align: center;
}

.status-icon {
    display: grid;
    place-items: center;
    width: 58px;
    height: 58px;
    margin: 0 auto 0.9rem;
    border-radius: 18px;
    background: var(--rose-100);
    font-size: 1.65rem;
}

.status-card h3 {
    margin-bottom: 0.45rem;
}

.status-card p {
    max-width: 650px;
    margin: 0 auto;
    color: var(--ink-700);
    line-height: 1.6;
}

.results-heading {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    margin: 0.35rem 0 0.9rem;
}

.results-heading h3 {
    margin: 0;
    font-size: 1.25rem;
}

.results-heading p {
    margin: 0;
    color: var(--ink-500);
    font-size: 0.9rem;
}

.result-card {
    padding: 1.4rem;
    margin-bottom: 1rem;
    transition: transform 160ms ease, box-shadow 160ms ease;
}

.result-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 16px 38px rgba(72, 55, 61, 0.10);
}

.result-topline {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
}

.product-brand {
    margin-bottom: 0.28rem;
    color: var(--rose-600);
    font-size: 1.00rem;
    font-weight: 800;
    letter-spacing: 0.035em;
    text-transform: uppercase;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.product-name {
    margin: 0;
    color: #655a62;
    font-size: 0.94rem;
    font-weight: 650;
    line-height: 1.42;
}

.score-pill {
    flex-shrink: 0;
    padding: 0.45rem 0.72rem;
    border-radius: 999px;
    background: #f3f0f1;
    color: var(--ink-700);
    font-size: 0.82rem;
    font-weight: 700;
}

.meta-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem;
    margin: 1rem 0;
}

.meta-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.42rem 0.65rem;
    border: 1px solid var(--border);
    border-radius: 999px;
    background: #fff;
    color: var(--ink-700);
    font-size: 0.83rem;
}

.sentiment-positive {
    background: #e6f5ec;
    color: #23653d;
}

.sentiment-negative {
    background: #fbe9e9;
    color: #8d3030;
}

.sentiment-mixed {
    background: #fff2d9;
    color: #8a5b08;
}

.sentiment-neutral {
    background: #ececf2;
    color: #555466;
}

.comment-block {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
}

.comment-block:first-of-type {
    border-top: 0;
    padding-top: 0;
}

.comment-heading {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 0.75rem;
    align-items: center;
    margin-bottom: 0.45rem;
}

.comment-label {
    color: var(--ink-700);
    font-size: 0.84rem;
    font-weight: 800;
}

.comment-box {
    padding: 1rem 1.05rem;
    border-left: 4px solid var(--rose-500);
    border-radius: 0 14px 14px 0;
    background: var(--rose-50);
    color: #443d44;
    line-height: 1.65;
    white-space: normal;
}

.comment-meta {
    margin-top: 0.55rem;
    color: var(--ink-500);
    font-size: 0.84rem;
}

.source-links {
    display: flex;
    flex-wrap: wrap;
    gap: 0.65rem;
    margin-top: 0.75rem;
}

.source-link {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.5rem 0.72rem;
    border-radius: 10px;
    background: #f4f1f2;
    color: var(--rose-600);
    font-size: 0.85rem;
    font-weight: 700;
    text-decoration: none;
}

.source-link:hover {
    background: var(--rose-100);
    color: var(--rose-600);
}

.evidence-details {
    margin-top: 0.8rem;
}

.evidence-details summary {
    cursor: pointer;
    color: var(--ink-700);
    font-size: 0.86rem;
    font-weight: 700;
}

.evidence-details li {
    margin-top: 0.45rem;
    color: var(--ink-700);
    line-height: 1.5;
}

@media (max-width: 820px) {
    .app-shell {
        padding-top: 1rem;
    }

    .hero {
        padding: 1.5rem;
    }

    .hero-icon {
        display: none;
    }

    .search-grid {
        grid-template-columns: 1fr;
    }

    .search-button {
        width: 100%;
    }

    .result-topline,
    .results-heading {
        align-items: flex-start;
        flex-direction: column;
    }
}
"""


# ---------------------------------------------------------------------------
# DATABASE
# ---------------------------------------------------------------------------

def connect_readonly() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"SQLite veritabanı bulunamadı: {DB_PATH}"
        )

    connection = sqlite3.connect(
        f"file:{DB_PATH.resolve()}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    return connection


def fetch_all(
    query: str,
    params: tuple[Any, ...] = (),
) -> list[sqlite3.Row]:
    with connect_readonly() as connection:
        return connection.execute(query, params).fetchall()


def database_ready() -> bool:
    return DB_PATH.exists()


def influencer_choices() -> dict[str, str]:
    """Influencer names without comment-count suffixes."""
    if not database_ready():
        return {"all": "Tüm influencer'lar"}

    rows = fetch_all(
        """
        SELECT DISTINCT influencer_slug, influencer_name
        FROM approved_product_comments
        ORDER BY influencer_name COLLATE NOCASE
        """
    )

    choices = {"all": "Tüm influencer'lar"}
    for row in rows:
        choices[str(row["influencer_slug"])] = str(
            row["influencer_name"]
        )
    return choices


def get_product_catalog(
    influencer_slug: str,
) -> list[dict[str, Any]]:
    conditions: list[str] = []
    params: list[Any] = []

    if influencer_slug != "all":
        conditions.append("influencer_slug = ?")
        params.append(influencer_slug)

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    rows = fetch_all(
        f"""
        SELECT
            product_id,
            brand,
            product_name,
            category,
            COUNT(*) AS comment_count
        FROM approved_product_comments
        {where}
        GROUP BY product_id, brand, product_name, category
        ORDER BY brand COLLATE NOCASE, product_name COLLATE NOCASE
        """,
        tuple(params),
    )

    return [
        {
            "product_id": int(row["product_id"]),
            "brand": str(row["brand"]),
            "product_name": str(row["product_name"]),
            "category": str(row["category"]),
            "comment_count": int(row["comment_count"]),
        }
        for row in rows
    ]


def get_product_comments(
    product_id: int,
    influencer_slug: str,
) -> list[sqlite3.Row]:
    conditions = ["product_id = ?"]
    params: list[Any] = [product_id]

    if influencer_slug != "all":
        conditions.append("influencer_slug = ?")
        params.append(influencer_slug)

    return fetch_all(
        f"""
        SELECT *
        FROM approved_product_comments
        WHERE {" AND ".join(conditions)}
        ORDER BY
            CASE WHEN upload_date IS NULL THEN 1 ELSE 0 END,
            upload_date DESC,
            influencer_name COLLATE NOCASE
        """,
        tuple(params),
    )


# ---------------------------------------------------------------------------
# SEARCH
# ---------------------------------------------------------------------------

def normalize_text(value: str | None) -> str:
    if not value:
        return ""

    translated = value.translate(
        str.maketrans(
            {
                "ı": "i",
                "İ": "i",
                "ş": "s",
                "Ş": "s",
                "ğ": "g",
                "Ğ": "g",
                "ü": "u",
                "Ü": "u",
                "ö": "o",
                "Ö": "o",
                "ç": "c",
                "Ç": "c",
            }
        )
    )
    decomposed = unicodedata.normalize("NFKD", translated)
    without_marks = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    without_punctuation = re.sub(
        r"[^a-zA-Z0-9%+]+",
        " ",
        without_marks,
    )
    return " ".join(
        without_punctuation.casefold().split()
    )


def search_aliases(
    brand: str,
    product_name: str,
    category: str,
) -> str:
    """Add a small deterministic bilingual synonym layer."""
    normalized = normalize_text(f"{brand} {product_name}")
    aliases: list[str] = []

    if any(
        token in normalized
        for token in (
            "sun cream",
            "suncream",
            "sunscreen",
            "sun screen",
            "sun protection",
            "spf",
        )
    ):
        aliases.extend(
            [
                "gunes kremi",
                "gunes koruyucu",
                "gunes krem",
                "sun crema",
                "sun creme",
            ]
        )

    if any(
        token in normalized
        for token in (
            "moisturizer",
            "moisturising",
            "moisturizing",
            "hydrating",
        )
    ):
        aliases.extend(["nemlendirici", "nemlendirici krem"])

    if any(
        token in normalized
        for token in ("cleanser", "cleansing", "wash")
    ):
        aliases.extend(["temizleyici", "yuz temizleyici"])

    if "serum" in normalized:
        aliases.append("serum")

    if category == "makeup":
        aliases.extend(["makyaj urunu", "makyaj"])
    elif category == "skincare":
        aliases.extend(["cilt bakimi", "bakim"])
    elif category == "haircare":
        aliases.extend(["sac bakimi", "sac urunu"])
    elif category == "bodycare":
        aliases.extend(["vucut bakimi", "vucut urunu"])

    return " ".join(dict.fromkeys(aliases))


def fuzzy_token_coverage(
    query_tokens: list[str],
    candidate_tokens: list[str],
) -> float:
    if not query_tokens:
        return 0.0

    matched = 0.0

    for query_token in query_tokens:
        if query_token in candidate_tokens:
            matched += 1.0
            continue

        best_similarity = max(
            (
                SequenceMatcher(
                    None,
                    query_token,
                    candidate_token,
                ).ratio()
                for candidate_token in candidate_tokens
            ),
            default=0.0,
        )

        if best_similarity >= 0.86:
            matched += 1.0
        elif best_similarity >= 0.74:
            matched += 0.65

    return matched / len(query_tokens)


def calculate_match_score(
    query: str,
    product: dict[str, Any],
) -> float:
    normalized_query = normalize_text(query)
    if not normalized_query:
        return 0.0

    normalized_brand = normalize_text(product["brand"])
    normalized_name = normalize_text(product["product_name"])
    aliases = search_aliases(
        product["brand"],
        product["product_name"],
        product["category"],
    )
    normalized_candidate = normalize_text(
        f"{product['brand']} {product['product_name']} {aliases}"
    )

    if normalized_query == normalized_brand:
        return 100.0

    if normalized_query == normalized_name:
        return 100.0

    if normalized_query in normalized_candidate:
        return 97.0

    query_tokens = normalized_query.split()
    candidate_tokens = normalized_candidate.split()

    coverage = fuzzy_token_coverage(
        query_tokens,
        candidate_tokens,
    )
    sequence_score = SequenceMatcher(
        None,
        normalized_query,
        normalized_candidate,
    ).ratio()

    # Also compare against brand and product name separately. This helps short
    # brand-only searches and long product names.
    brand_score = SequenceMatcher(
        None,
        normalized_query,
        normalized_brand,
    ).ratio()
    name_score = SequenceMatcher(
        None,
        normalized_query,
        normalized_name,
    ).ratio()

    score = max(
        coverage * 92.0 + sequence_score * 8.0,
        brand_score * 96.0,
        name_score * 94.0,
    )

    # Reward a clearly matched brand even when the rest of the query is a
    # Turkish category phrase, e.g. "Dr Korea güneş kremi".
    if normalized_brand and normalized_brand in normalized_query:
        score = max(score, 88.0 + 12.0 * coverage)

    return min(score, 100.0)


def search_products(
    raw_query: str,
    influencer_slug: str,
    *,
    limit: int = 5,
    score_cutoff: float = 48.0,
) -> list[dict[str, Any]]:
    catalog = get_product_catalog(influencer_slug)
    query = raw_query.strip()

    if not query:
        return []

    # A selected dropdown item returns its numeric product ID.
    if query.isdigit():
        selected_id = int(query)
        exact = [
            {
                **product,
                "match_score": 100.0,
            }
            for product in catalog
            if product["product_id"] == selected_id
        ]
        if exact:
            return exact

    scored = [
        {
            **product,
            "match_score": calculate_match_score(
                query,
                product,
            ),
        }
        for product in catalog
    ]

    scored = [
        product
        for product in scored
        if product["match_score"] >= score_cutoff
    ]
    scored.sort(
        key=lambda item: (
            -item["match_score"],
            item["brand"].casefold(),
            item["product_name"].casefold(),
        )
    )
    return scored[:limit]


# ---------------------------------------------------------------------------
# PRESENTATION
# ---------------------------------------------------------------------------

def safe_json_list(value: str | None) -> list[Any]:
    if not value:
        return []

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []

    return parsed if isinstance(parsed, list) else []


def format_date(value: str | None) -> str:
    if not value:
        return "Tarih bilinmiyor"

    parts = value.split("-")
    if len(parts) == 3:
        return f"{parts[2]}.{parts[1]}.{parts[0]}"

    return value


def sentiment_pill(sentiment: str) -> Any:
    return ui.span(
        SENTIMENT_LABELS.get(
            sentiment,
            sentiment.title(),
        ),
        class_=(
            "meta-pill "
            + SENTIMENT_CLASSES.get(
                sentiment,
                "sentiment-neutral",
            )
        ),
    )


def comment_block(row: sqlite3.Row) -> Any:
    evidence_texts = safe_json_list(
        row["evidence_texts_json"]
    )

    evidence_details = None
    if evidence_texts:
        evidence_details = ui.tags.details(
            ui.tags.summary("Transcript kanıtını göster"),
            ui.tags.ul(
                *[
                    ui.tags.li(text)
                    for text in evidence_texts
                ]
            ),
            class_="evidence-details",
        )

    return ui.div(
        ui.div(
            ui.div(
                f"{row['influencer_name']} yorumu",
                class_="comment-label",
            ),
            sentiment_pill(str(row["sentiment"])),
            class_="comment-heading",
        ),
        ui.div(
            row["display_summary"],
            class_="comment-box",
        ),
        ui.div(
            f"{format_date(row['upload_date'])} · "
            f"Güven: {float(row['confidence']):.0%}",
            class_="comment-meta",
        ),
        ui.div(
            row["video_title"],
            class_="comment-meta",
        ),
        evidence_details,
        ui.div(
            ui.tags.a(
                "Videoyu aç ↗",
                href=row["video_url"],
                target="_blank",
                rel="noopener noreferrer",
                class_="source-link",
            ),
            class_="source-links",
        ),
        class_="comment-block",
    )


def result_card(
    product: dict[str, Any],
    comments: list[sqlite3.Row],
) -> Any:
    category_label = CATEGORY_LABELS.get(
        product["category"],
        product["category"],
    )

    return ui.div(
        ui.div(
            ui.div(
                ui.div(
                    product["brand"],
                    class_="product-brand",
                ),
                ui.h3(
                    product["product_name"],
                    class_="product-name",
                ),
            ),
            ui.div(
                f"%{product['match_score']:.0f} eşleşme",
                class_="score-pill",
            ),
            class_="result-topline",
        ),
        ui.div(
            ui.span(
                ui.tags.strong("Kategori: "),
                category_label,
                class_="meta-pill",
            ),
            ui.span(
                ui.tags.strong("Yorum: "),
                str(len(comments)),
                class_="meta-pill",
            ),
            class_="meta-row",
        ),
        *[
            comment_block(comment)
            for comment in comments
        ],
        class_="result-card",
    )



# ---------------------------------------------------------------------------
# E-COMMERCE DEMO HELPERS
# ---------------------------------------------------------------------------

CATEGORY_TABS = {
    "all": "Tümü",
    "makeup": "Makyaj",
    "skincare": "Cilt Bakımı",
    "sunscreen": "Güneş Kremleri",
    "haircare": "Saç Bakımı",
    "bodycare": "Vücut Bakımı",
}


def get_commerce_catalog(
    influencer_slug: str,
) -> list[dict[str, Any]]:
    conditions: list[str] = []
    params: list[Any] = []

    if influencer_slug != "all":
        conditions.append("influencer_slug = ?")
        params.append(influencer_slug)

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    rows = fetch_all(
        f"""
        SELECT
            product_id,
            brand,
            product_name,
            category,
            COUNT(*) AS comment_count,
            COUNT(DISTINCT influencer_slug) AS influencer_count
        FROM approved_product_comments
        {where}
        GROUP BY product_id, brand, product_name, category
        ORDER BY
            influencer_count DESC,
            comment_count DESC,
            brand COLLATE NOCASE,
            product_name COLLATE NOCASE
        """,
        tuple(params),
    )

    return [
        {
            "product_id": int(row["product_id"]),
            "brand": str(row["brand"] or "Marka belirtilmemiş"),
            "product_name": str(row["product_name"]),
            "category": str(row["category"]),
            "comment_count": int(row["comment_count"]),
            "influencer_count": int(row["influencer_count"]),
        }
        for row in rows
    ]


def get_product_by_id(product_id: int) -> dict[str, Any] | None:
    rows = fetch_all(
        """
        SELECT
            product_id,
            brand,
            product_name,
            category,
            COUNT(*) AS comment_count,
            COUNT(DISTINCT influencer_slug) AS influencer_count
        FROM approved_product_comments
        WHERE product_id = ?
        GROUP BY product_id, brand, product_name, category
        """,
        (product_id,),
    )

    if not rows:
        return None

    row = rows[0]
    return {
        "product_id": int(row["product_id"]),
        "brand": str(row["brand"] or "Marka belirtilmemiş"),
        "product_name": str(row["product_name"]),
        "category": str(row["category"]),
        "comment_count": int(row["comment_count"]),
        "influencer_count": int(row["influencer_count"]),
    }


def product_matches_category(
    product: dict[str, Any],
    category_code: str,
) -> bool:
    if category_code == "all":
        return True

    if category_code == "sunscreen":
        searchable = normalize_text(
            f"{product['brand']} {product['product_name']} "
            f"{search_aliases(product['brand'], product['product_name'], product['category'])}"
        )
        tokens = (
            "gunes krem",
            "gunes koruyucu",
            "sun cream",
            "suncream",
            "sunscreen",
            "sun protection",
            "spf",
        )
        return any(token in searchable for token in tokens)

    return product["category"] == category_code


def browse_products(
    influencer_slug: str,
    category_code: str,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    products = [
        product
        for product in get_commerce_catalog(influencer_slug)
        if product_matches_category(product, category_code)
    ]
    return products[:limit]


def search_products_commerce(
    raw_query: str,
    influencer_slug: str,
    category_code: str,
    *,
    limit: int = 24,
    score_cutoff: float = 48.0,
) -> list[dict[str, Any]]:
    catalog = [
        product
        for product in get_commerce_catalog(influencer_slug)
        if product_matches_category(product, category_code)
    ]
    query = raw_query.strip()

    if not query:
        return []

    if query.isdigit():
        selected_id = int(query)
        exact = [
            {**product, "match_score": 100.0}
            for product in catalog
            if product["product_id"] == selected_id
        ]
        if exact:
            return exact

    scored = [
        {
            **product,
            "match_score": calculate_match_score(query, product),
        }
        for product in catalog
    ]
    scored = [
        product
        for product in scored
        if product["match_score"] >= score_cutoff
    ]
    scored.sort(
        key=lambda item: (
            -item["match_score"],
            -item["influencer_count"],
            -item["comment_count"],
            item["brand"].casefold(),
            item["product_name"].casefold(),
        )
    )
    return scored[:limit]


def js_set_input(input_name: str, payload: Any) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        f"Shiny.setInputValue('{input_name}', {serialized}, "
        "{priority: 'event'});"
    )


def payload_as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    try:
        return dict(value)
    except (TypeError, ValueError):
        return {}


def product_initials(brand: str) -> str:
    words = [
        word
        for word in re.split(r"\s+", brand.strip())
        if word
    ]
    initials = "".join(word[0] for word in words[:2]).upper()
    return initials or "SK"


def review_entry(row: sqlite3.Row) -> Any:
    evidence_texts = safe_json_list(
        row["evidence_texts_json"]
    )

    evidence_details = None
    if evidence_texts:
        evidence_details = ui.tags.details(
            ui.tags.summary("Transcript kanıtını göster"),
            ui.tags.ul(
                *[
                    ui.tags.li(str(text))
                    for text in evidence_texts
                ]
            ),
            class_="evidence-details",
        )

    return ui.div(
        ui.div(
            ui.div(
                f"{row['influencer_name']} incelemesi",
                class_="review-entry-label",
            ),
            sentiment_pill(str(row["sentiment"])),
            class_="review-entry-top",
        ),
        ui.div(
            str(row["display_summary"]),
            class_="review-summary",
        ),
        ui.div(
            f"{format_date(row['upload_date'])} · "
            f"Güven: {float(row['confidence']):.0%}",
            class_="review-meta",
        ),
        ui.div(
            str(row["video_title"]),
            class_="review-meta",
        ),
        evidence_details,
        ui.tags.a(
            "Kaynak videoyu aç ↗",
            href=row["video_url"],
            target="_blank",
            rel="noopener noreferrer",
            class_="video-link",
        ),
        class_="review-entry",
    )


def product_card(
    product: dict[str, Any],
    *,
    active_influencer: str,
    cart_product_ids: set[int],
) -> Any:
    comments = get_product_comments(
        product["product_id"],
        active_influencer,
    )

    creator_map: dict[str, str] = {}
    for comment in comments:
        creator_map[str(comment["influencer_slug"])] = str(
            comment["influencer_name"]
        )

    category_label = CATEGORY_LABELS.get(
        product["category"],
        product["category"],
    )

    if "match_score" in product:
        badge = f"%{product['match_score']:.0f} eşleşme"
    elif product["influencer_count"] >= 2:
        badge = f"{product['influencer_count']} içerik üreticisi"
    else:
        badge = f"{product['comment_count']} yorum"

    creator_buttons = [
        ui.tags.button(
            f"{creator_name} yorumunu gör",
            type="button",
            class_="creator-button",
            onclick=js_set_input(
                "review_request",
                {
                    "product_id": product["product_id"],
                    "influencer_slug": creator_slug,
                },
            ),
        )
        for creator_slug, creator_name in sorted(
            creator_map.items(),
            key=lambda item: item[1].casefold(),
        )
    ]

    in_cart = product["product_id"] in cart_product_ids

    cart_attributes: dict[str, Any] = {
        "type": "button",
        "class_": (
            "add-cart-button in-cart"
            if in_cart
            else "add-cart-button"
        ),
    }

    if in_cart:
        cart_attributes["disabled"] = "disabled"
    else:
        cart_attributes["onclick"] = js_set_input(
            "cart_add",
            {"product_id": product["product_id"]},
        )

    return ui.div(
        ui.div(
            ui.span(badge, class_="card-badge"),
            ui.div(
                product_initials(product["brand"]),
                class_="product-monogram",
            ),
            class_="product-visual",
        ),
        ui.div(
            ui.div(product["brand"], class_="product-brand"),
            ui.h3(product["product_name"], class_="product-name"),
            ui.p(category_label, class_="product-category"),
            ui.div(
                *creator_buttons,
                class_="creator-actions",
            ),
            ui.div(
                ui.tags.button(
                    "Sepette ✓" if in_cart else "Sepete Ekle",
                    **cart_attributes,
                ),
                class_="card-footer-actions",
            ),
            class_="product-card-body",
        ),
        class_="product-card",
    )


def category_tabs_ui(active_category: str) -> Any:
    return ui.div(
        *[
            ui.tags.button(
                label,
                type="button",
                class_=(
                    "category-tab active"
                    if code == active_category
                    else "category-tab"
                ),
                onclick=js_set_input(
                    "category_select",
                    {"category": code},
                ),
            )
            for code, label in CATEGORY_TABS.items()
        ],
        class_="category-strip",
    )


CUSTOM_CSS += """
body {
    background:
        radial-gradient(circle at 6% 0%, rgba(255, 213, 223, 0.54), transparent 28rem),
        linear-gradient(180deg, #fffdfd 0%, #f8f6f7 100%);
}

.commerce-shell {
    width: min(1400px, calc(100% - 2rem));
    margin: 0 auto;
    padding: 1rem 0 4rem;
}

.topbar {
    position: sticky;
    top: 0.65rem;
    z-index: 50;
    display: grid;
    grid-template-columns: minmax(190px, 0.52fr) minmax(340px, 1.75fr) auto;
    align-items: center;
    gap: 1rem;
    padding: 0.85rem;
    border: 1px solid rgba(238, 229, 232, 0.95);
    border-radius: 22px;
    background: rgba(255, 255, 255, 0.94);
    box-shadow: 0 18px 45px rgba(67, 46, 55, 0.12);
    backdrop-filter: blur(16px);
}

.brand-lockup {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    min-width: 0;
    padding: 0 0.45rem;
}

.brand-mark {
    display: grid;
    place-items: center;
    width: 42px;
    height: 42px;
    border-radius: 14px;
    background: linear-gradient(145deg, #e35f7a, #a9304d);
    box-shadow: 0 10px 22px rgba(201, 67, 98, 0.25);
    color: white;
    font-size: 1.2rem;
}

.brand-name {
    margin: 0;
    font-family: "Playfair Display", Didot, Georgia, serif;
    font-size: 1.65rem;
    font-weight: 650;
    letter-spacing: -0.025em;
    white-space: nowrap;
}

.demo-chip {
    display: inline-flex;
    margin-left: 0.3rem;
    padding: 0.2rem 0.46rem;
    border-radius: 999px;
    background: #ffeaf0;
    color: #a9304d;
    font-family: Inter, sans-serif;
    font-size: 0.66rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    vertical-align: middle;
}

.top-search {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.55rem;
    min-width: 0;
}

.top-search .form-group,
.top-search .shiny-input-container {
    width: 100%;
    margin: 0;
}

.top-search label {
    display: none;
}

.top-search .selectize-control {
    margin: 0;
}

.top-search .selectize-input {
    min-height: 48px;
    padding: 0.65rem 0.95rem !important;
    border-radius: 14px !important;
}

.search-submit,
.cart-trigger,
.checkout-button {
    border: 0 !important;
    background: linear-gradient(135deg, #e35f7a, #a9304d) !important;
    color: #fff !important;
    box-shadow: 0 10px 22px rgba(201, 67, 98, 0.21);
    font-weight: 800;
}

.search-submit {
    min-height: 48px;
    padding: 0 1.15rem;
    border-radius: 14px !important;
}

.cart-trigger {
    min-height: 46px;
    padding: 0.62rem 0.95rem !important;
    border-radius: 14px !important;
    white-space: nowrap;
}

.category-strip {
    display: flex;
    gap: 0.55rem;
    margin: 1rem 0 0;
    padding: 0.8rem;
    overflow-x: auto;
    border: 1px solid #eee5e8;
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.9);
    box-shadow: 0 8px 24px rgba(67, 46, 55, 0.08);
}

.category-tab {
    flex: 0 0 auto;
    padding: 0.65rem 0.9rem;
    border: 1px solid transparent;
    border-radius: 999px;
    background: transparent;
    color: #655a62;
    font-weight: 750;
    white-space: nowrap;
}

.category-tab:hover,
.category-tab.active {
    background: #ffeaf0;
    color: #a9304d;
}

.filter-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 1rem;
    margin: 1rem 0 1.3rem;
    padding: 0.9rem 1rem;
    border: 1px solid #eee5e8;
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.86);
}

.filter-copy {
    color: #655a62;
    font-size: 0.9rem;
    line-height: 1.5;
}

.influencer-filter {
    width: min(310px, 100%);
}

.influencer-filter .form-group {
    margin: 0;
}

.influencer-filter label {
    margin-bottom: 0.35rem;
    color: #655a62;
    font-size: 0.78rem;
    font-weight: 800;
    text-transform: uppercase;
}

.section-heading {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 1rem;
    margin: 1.2rem 0 1rem;
}

.section-heading h2 {
    margin: 0;
    font-size: clamp(1.45rem, 2.5vw, 2rem);
}

.section-heading p {
    max-width: 680px;
    margin: 0.35rem 0 0;
    color: #655a62;
}

.result-count {
    padding: 0.45rem 0.7rem;
    border-radius: 999px;
    background: #f0edef;
    color: #655a62;
    font-size: 0.82rem;
    font-weight: 800;
}

.product-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 1rem;
}

.product-card {
    display: flex;
    min-height: 100%;
    flex-direction: column;
    overflow: hidden;
    border: 1px solid #eee5e8;
    border-radius: 20px;
    background: white;
    box-shadow: 0 8px 24px rgba(67, 46, 55, 0.08);
    transition: 160ms ease;
}

.product-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 18px 45px rgba(67, 46, 55, 0.12);
}

.product-visual {
    position: relative;
    display: grid;
    place-items: center;
    min-height: 180px;
    background:
        radial-gradient(circle at 22% 18%, rgba(255,255,255,0.92), transparent 34%),
        linear-gradient(145deg, #ffeaf0, #f5eff2 68%, #fff);
}

.product-monogram {
    display: grid;
    place-items: center;
    width: 92px;
    height: 112px;
    border-radius: 28px 28px 20px 20px;
    background: rgba(255,255,255,0.75);
    box-shadow: 0 18px 35px rgba(169, 48, 77, 0.13);
    color: #a9304d;
    font-family: Georgia, serif;
    font-size: 1.55rem;
    font-weight: 800;
}

.card-badge {
    position: absolute;
    top: 0.8rem;
    left: 0.8rem;
    padding: 0.38rem 0.58rem;
    border-radius: 999px;
    background: rgba(255,255,255,0.9);
    color: #a9304d;
    font-size: 0.72rem;
    font-weight: 850;
}

.product-card-body {
    display: flex;
    flex: 1;
    flex-direction: column;
    padding: 1rem;
}

.product-category {
    margin: 0.5rem 0 0;
    color: #8f838b;
    font-size: 0.8rem;
}

.creator-actions {
    display: grid;
    gap: 0.45rem;
    margin-top: 1rem;
}

.creator-button {
    width: 100%;
    padding: 0.58rem 0.65rem;
    border: 1px solid #ffd5df;
    border-radius: 11px;
    background: #fff7f9;
    color: #a9304d;
    font-size: 0.79rem;
    font-weight: 800;
    text-align: left;
}

.creator-button:hover {
    background: #ffeaf0;
}

.card-footer-actions {
    margin-top: auto;
    padding-top: 1rem;
}

.add-cart-button {
    width: 100%;
    padding: 0.72rem 0.8rem;
    border: 0;
    border-radius: 12px;
    background: #221d21;
    color: white;
    font-weight: 850;
}

.add-cart-button:hover {
    background: #a9304d;
}

.add-cart-button.in-cart,
.add-cart-button:disabled {
    background: #ece8ea;
    color: #655a62;
}

.empty-card {
    padding: 2.5rem 1.2rem;
    border: 1px solid #eee5e8;
    border-radius: 22px;
    background: rgba(255,255,255,0.92);
    text-align: center;
}

.empty-icon {
    display: grid;
    place-items: center;
    width: 62px;
    height: 62px;
    margin: 0 auto 0.9rem;
    border-radius: 20px;
    background: #ffeaf0;
    font-size: 1.7rem;
}

.review-entry {
    margin-top: 0.85rem;
    padding: 1rem;
    border: 1px solid #eee5e8;
    border-radius: 15px;
    background: #fcf9fa;
}

.review-entry-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.65rem;
}

.review-entry-label {
    color: #655a62;
    font-size: 0.82rem;
    font-weight: 850;
}

.review-summary {
    padding: 0.85rem 0.95rem;
    border-left: 4px solid #e35f7a;
    border-radius: 0 12px 12px 0;
    background: #fff7f9;
    line-height: 1.65;
}

.review-meta {
    margin-top: 0.58rem;
    color: #8f838b;
    font-size: 0.79rem;
}

.video-link {
    display: inline-flex;
    margin-top: 0.75rem;
    padding: 0.5rem 0.7rem;
    border-radius: 10px;
    background: #f0edef;
    color: #a9304d;
    font-size: 0.82rem;
    font-weight: 850;
    text-decoration: none;
}

.cart-list {
    display: grid;
    gap: 0.7rem;
}

.cart-row {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 0.8rem;
    align-items: center;
    padding: 0.85rem;
    border: 1px solid #eee5e8;
    border-radius: 14px;
    background: #fcf9fa;
}

.remove-cart-button {
    padding: 0.45rem 0.6rem;
    border: 1px solid #eee5e8;
    border-radius: 9px;
    background: white;
    color: #655a62;
}

.cart-note,
.payment-note {
    margin-top: 1rem;
    padding: 0.85rem;
    border-radius: 12px;
    background: #fff7f9;
    color: #655a62;
}

.checkout-button {
    padding: 0.65rem 0.9rem;
    border-radius: 11px;
}

@media (max-width: 1120px) {
    .product-grid {
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }
}

@media (max-width: 900px) {
    .topbar {
        position: static;
        grid-template-columns: 1fr auto;
    }

    .top-search {
        grid-column: 1 / -1;
        grid-row: 2;
    }

    .product-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}

@media (max-width: 650px) {
    .commerce-shell {
        width: min(100% - 1rem, 1400px);
    }

    .topbar {
        grid-template-columns: minmax(0, 1fr) auto;
    }

    .demo-chip {
        display: none;
    }

    .top-search {
        grid-template-columns: 1fr;
    }

    .filter-row,
    .section-heading {
        align-items: stretch;
        flex-direction: column;
    }

    .influencer-filter {
        width: 100%;
    }

    .product-grid {
        grid-template-columns: 1fr;
    }
}
"""


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

INITIAL_INFLUENCERS = influencer_choices()

app_ui = ui.page_fluid(
    ui.tags.head(
        ui.tags.meta(
            name="viewport",
            content="width=device-width, initial-scale=1",
        ),
        ui.tags.style(CUSTOM_CSS),
    ),
    ui.div(
        ui.div(
            ui.div(
                ui.div("S", class_="brand-mark"),
                ui.h1(
                    "Skinfluencer",
                    ui.span("Demo", class_="demo-chip"),
                    class_="brand-name",
                ),
                class_="brand-lockup",
            ),
            ui.div(
                ui.input_selectize(
                    "product_query",
                    "",
                    choices={},
                    selected=None,
                    multiple=False,
                    options={
                        "placeholder": "Marka, ürün veya içerik ara...",
                        "create": True,
                        "createOnBlur": True,
                        "persist": False,
                        "maxOptions": 180,
                        "closeAfterSelect": True,
                    },
                ),
                ui.input_action_button(
                    "search_button",
                    "Ara",
                    class_="search-submit",
                ),
                class_="top-search",
            ),
            ui.output_ui("cart_button"),
            class_="topbar",
        ),
        ui.output_ui("category_navigation"),
        ui.div(
            ui.div(
                ui.tags.strong(
                    "Güvenilir ürün keşfi, gerçek video kanıtıyla."
                ),
                " Ürünleri inceleyin, içerik üreticisi yorumlarını "
                "açın ve demo sepet akışını deneyin.",
                class_="filter-copy",
            ),
            ui.div(
                ui.input_select(
                    "influencer",
                    "İçerik üreticisi",
                    choices=INITIAL_INFLUENCERS,
                    selected="all",
                ),
                class_="influencer-filter",
            ),
            class_="filter-row",
        ),
        ui.output_ui("database_message"),
        ui.output_ui("catalog_content"),
        class_="commerce-shell",
    ),
)


# ---------------------------------------------------------------------------
# SERVER
# ---------------------------------------------------------------------------

def server(
    input: Inputs,
    output: Outputs,
    session: Session,
) -> None:
    active_category = reactive.Value("all")
    submitted_query = reactive.Value("")
    cart = reactive.Value({})

    @reactive.effect
    def update_product_suggestions() -> None:
        if not database_ready():
            return

        catalog = [
            product
            for product in get_commerce_catalog(input.influencer())
            if product_matches_category(
                product,
                active_category.get(),
            )
        ]

        choices = {
            str(product["product_id"]): (
                f"{product['brand']} — {product['product_name']}"
            )
            for product in catalog
        }

        ui.update_selectize(
            "product_query",
            choices=choices,
            selected="",
            server=True,
            session=session,
        )

    @reactive.effect
    @reactive.event(input.search_button)
    def submit_search() -> None:
        submitted_query.set(
            str(input.product_query() or "").strip()
        )

    @reactive.effect
    @reactive.event(input.category_select)
    def select_category() -> None:
        payload = payload_as_dict(input.category_select())
        category = str(payload.get("category") or "all")

        if category not in CATEGORY_TABS:
            category = "all"

        active_category.set(category)
        submitted_query.set("")
        ui.update_selectize(
            "product_query",
            selected="",
            session=session,
        )

    @reactive.effect
    @reactive.event(input.cart_add)
    def add_to_cart() -> None:
        payload = payload_as_dict(input.cart_add())
        try:
            product_id = int(payload["product_id"])
        except (KeyError, TypeError, ValueError):
            return

        if get_product_by_id(product_id) is None:
            return

        updated = dict(cart.get())
        updated[product_id] = 1
        cart.set(updated)

    def show_cart_modal() -> None:
        current = dict(cart.get())

        if not current:
            body = ui.div(
                ui.div("🛍️", class_="empty-icon"),
                ui.h3("Sepetiniz henüz boş"),
                ui.p(
                    "Ürün kartlarındaki Sepete Ekle düğmesini "
                    "kullanarak demo sepetinizi oluşturabilirsiniz."
                ),
                class_="empty-card",
            )
            footer = ui.modal_button("Kapat")
        else:
            rows: list[Any] = []

            for product_id in current:
                product = get_product_by_id(product_id)
                if product is None:
                    continue

                rows.append(
                    ui.div(
                        ui.div(
                            ui.tags.strong(product["product_name"]),
                            ui.tags.small(product["brand"]),
                        ),
                        ui.tags.button(
                            "Kaldır",
                            type="button",
                            class_="remove-cart-button",
                            onclick=js_set_input(
                                "cart_remove",
                                {"product_id": product_id},
                            ),
                        ),
                        class_="cart-row",
                    )
                )

            body = ui.div(
                ui.div(*rows, class_="cart-list"),
                ui.div(
                    "Bu demo sürümünde fiyat, stok ve gerçek sipariş "
                    "işlemi bulunmamaktadır.",
                    class_="cart-note",
                ),
            )
            footer = ui.div(
                ui.tags.button(
                    "Ödemeye Geç",
                    type="button",
                    class_="checkout-button",
                    onclick=js_set_input(
                        "checkout_request",
                        {"requested": True},
                    ),
                ),
                ui.modal_button("Alışverişe Devam Et"),
            )

        ui.modal_show(
            ui.modal(
                body,
                title=f"Sepet ({len(current)})",
                easy_close=True,
                footer=footer,
                size="l",
            )
        )

    @reactive.effect
    @reactive.event(input.open_cart)
    def open_cart() -> None:
        show_cart_modal()

    @reactive.effect
    @reactive.event(input.cart_remove)
    def remove_from_cart() -> None:
        payload = payload_as_dict(input.cart_remove())
        try:
            product_id = int(payload["product_id"])
        except (KeyError, TypeError, ValueError):
            return

        updated = dict(cart.get())
        updated.pop(product_id, None)
        cart.set(updated)

        ui.modal_remove()
        show_cart_modal()

    @reactive.effect
    @reactive.event(input.checkout_request)
    def checkout_demo() -> None:
        ui.modal_remove()
        ui.modal_show(
            ui.modal(
                ui.div(
                    ui.div("✓", class_="empty-icon"),
                    ui.h3("Demo ödeme deneyimi"),
                    ui.p(
                        "Bu adım yatırımcı ve kullanıcı deneyimi "
                        "demosu için simüle edilmektedir."
                    ),
                    ui.div(
                        "Gerçek ödeme, fiyatlandırma, stok kontrolü "
                        "veya sipariş kaydı yapılmaz.",
                        class_="payment-note",
                    ),
                    class_="empty-card",
                ),
                title="Ödemeye Geç",
                easy_close=True,
                footer=ui.modal_button("Kapat"),
            )
        )

    @reactive.effect
    @reactive.event(input.review_request)
    def show_reviews() -> None:
        payload = payload_as_dict(input.review_request())
        try:
            product_id = int(payload["product_id"])
        except (KeyError, TypeError, ValueError):
            return

        influencer_slug = str(
            payload.get("influencer_slug") or "all"
        )
        product = get_product_by_id(product_id)
        if product is None:
            return

        comments = get_product_comments(
            product_id,
            influencer_slug,
        )
        if not comments:
            return

        influencer_name = str(comments[0]["influencer_name"])

        ui.modal_show(
            ui.modal(
                ui.div(
                    ui.div(
                        ui.div(
                            product["brand"],
                            class_="product-brand",
                        ),
                        ui.h3(product["product_name"]),
                        ui.div(
                            f"{influencer_name} · "
                            f"{len(comments)} onaylı inceleme",
                            class_="review-meta",
                        ),
                    ),
                    *[
                        review_entry(comment)
                        for comment in comments
                    ],
                ),
                title=f"{influencer_name} yorumları",
                easy_close=True,
                footer=ui.modal_button("Kapat"),
                size="l",
            )
        )

    @render.ui
    def cart_button() -> Any:
        return ui.input_action_button(
            "open_cart",
            f"Sepet ({len(cart.get())})",
            class_="cart-trigger",
        )

    @render.ui
    def category_navigation() -> Any:
        return category_tabs_ui(active_category.get())

    @render.ui
    def database_message() -> Any:
        if database_ready():
            return None

        return ui.div(
            ui.div("⚠️", class_="empty-icon"),
            ui.h3("Veritabanı bulunamadı"),
            ui.p(
                f"Önce SQLite importer'ı çalıştırın: {DB_PATH}"
            ),
            class_="empty-card",
        )

    @render.ui
    def catalog_content() -> Any:
        if not database_ready():
            return None

        influencer_slug = input.influencer()
        category = active_category.get()
        query = submitted_query.get()
        cart_ids = set(cart.get().keys())

        if query:
            products = search_products_commerce(
                query,
                influencer_slug,
                category,
                limit=24,
            )
            heading = f"“{query}” için sonuçlar"
            description = (
                "En güçlü marka ve ürün eşleşmeleri önce gösteriliyor."
            )
        elif category == "all":
            products = browse_products(
                influencer_slug,
                "skincare",
                limit=12,
            )
            heading = "En Çok Satan Cilt Bakımı Ürünleri"
            description = (
                "Gerçek satış verisi yerine yorum yoğunluğu ve içerik "
                "üreticisi kapsamına göre hazırlanmıştır."
            )
        else:
            products = browse_products(
                influencer_slug,
                category,
                limit=24,
            )
            heading = CATEGORY_TABS[category]
            description = (
                "Onaylanmış influencer yorumlarına sahip ürünler "
                "öne çıkarılıyor."
            )

        if not products:
            return ui.div(
                ui.div("🔎", class_="empty-icon"),
                ui.h3("Ürün bulunamadı"),
                ui.p(
                    "Bu arama ve filtre kombinasyonu için yeterince "
                    "güçlü bir eşleşme bulunamadı."
                ),
                class_="empty-card",
            )

        return ui.div(
            ui.div(
                ui.div(
                    ui.h2(heading),
                    ui.p(description),
                ),
                ui.div(
                    f"{len(products)} ürün",
                    class_="result-count",
                ),
                class_="section-heading",
            ),
            ui.div(
                *[
                    product_card(
                        product,
                        active_influencer=influencer_slug,
                        cart_product_ids=cart_ids,
                    )
                    for product in products
                ],
                class_="product-grid",
            ),
        )


app = App(app_ui, server)
