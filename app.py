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
    margin-bottom: 0.25rem;
    color: var(--rose-600);
    font-size: 0.82rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

.product-name {
    margin: 0;
    font-size: 1.35rem;
    line-height: 1.3;
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
                ui.h1(
                    "Your Skinfluencer",
                    style=(
                        "font-family: 'Playfair Display', 'Didot', "
                        "'Georgia', serif; font-weight: 600; "
                        "letter-spacing: 1px; color: #333;"
                    ),
                ),
                ui.p(
                    "Kendine en uygun influencer'ı seç, ilgilendiğin "
                    "ürünün gerçek yorumunu hemen gör."
                ),
            ),
            ui.div("🎀", class_="hero-icon"),
            class_="hero",
        ),
        ui.div(
            ui.div(
                ui.input_select(
                    "influencer",
                    "Influencer",
                    choices=INITIAL_INFLUENCERS,
                    selected=(
                        "naturally_serein"
                        if "naturally_serein" in INITIAL_INFLUENCERS
                        else next(iter(INITIAL_INFLUENCERS))
                    ),
                ),
                ui.input_selectize(
                    "product_query",
                    "Marka veya ürün adı",
                    choices={},
                    selected=None,
                    multiple=False,
                    options={
                        "placeholder": (
                            "Örn. Dr. Korea güneş kremi veya Round Lab"
                        ),
                        "create": True,
                        "createOnBlur": True,
                        "persist": False,
                        "maxOptions": 150,
                        "closeAfterSelect": True,
                        "selectOnTab": True,
                    },
                ),
                ui.input_action_button(
                    "search_button",
                    "Yorumu göster",
                    class_="btn-primary search-button",
                ),
                class_="search-grid",
            ),
            ui.p(
                "İpucu: Marka adıyla, tam ürün adıyla veya yaklaşık bir "
                "ifadeyle arayabilirsin. Küçük yazım hataları ve "
                "“güneş kremi / sun cream” gibi ifadeler de eşleştirilir.",
                class_="search-help",
            ),
            class_="search-panel",
        ),
        ui.output_ui("database_message"),
        ui.output_ui("search_results"),
        class_="app-shell",
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
    @reactive.effect
    def update_product_suggestions() -> None:
        if not database_ready():
            return

        catalog = get_product_catalog(input.influencer())

        # Brand is deliberately part of the visible label. Selectize searches
        # option labels, so typing "Round Lab" now returns its products.
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

    @reactive.calc
    @reactive.event(
        input.search_button,
        ignore_none=False,
    )
    def product_search() -> dict[str, Any] | None:
        raw_query = str(input.product_query() or "").strip()

        if not raw_query:
            return None

        products = search_products(
            raw_query,
            input.influencer(),
            limit=5,
            score_cutoff=48.0,
        )

        results: list[dict[str, Any]] = []

        for product in products:
            comments = get_product_comments(
                product["product_id"],
                input.influencer(),
            )
            if comments:
                results.append(
                    {
                        "product": product,
                        "comments": comments,
                    }
                )

        return {
            "query": raw_query,
            "results": results,
        }

    @render.ui
    def database_message() -> Any:
        if database_ready():
            return None

        return ui.div(
            ui.div("⚠️", class_="status-icon"),
            ui.h3("Veritabanı bulunamadı"),
            ui.p(
                f"Önce SQLite importer'ı çalıştır: {DB_PATH}"
            ),
            class_="status-card",
        )

    @render.ui
    def search_results() -> Any:
        if not database_ready():
            return None

        response = product_search()

        if response is None:
            return ui.div(
                ui.div("✨", class_="status-icon"),
                ui.h3("Bir ürün seçerek başlayın"),
                ui.p(
                    "Influencer'ı seçin, marka veya ürün adını yazın. "
                    "Listeden seçim yapabilir ya da kendi arama ifadenizi "
                    "yazıp Yorumu göster düğmesine basabilirsiniz."
                ),
                class_="status-card",
            )

        results = response["results"]

        if not results:
            return ui.div(
                ui.div("🔎", class_="status-icon"),
                ui.h3("Ürün bulunamadı"),
                ui.p(
                    f"“{response['query']}” için yeterince güçlü bir "
                    "eşleşme bulunamadı."
                ),
                class_="status-card",
            )

        return ui.div(
            ui.div(
                ui.h3(
                    f"{len(results)} ürün eşleşmesi bulundu"
                ),
                ui.p(
                    "En güçlü marka ve ürün eşleşmeleri önce gösteriliyor."
                ),
                class_="results-heading",
            ),
            *[
                result_card(
                    result["product"],
                    result["comments"],
                )
                for result in results
            ],
        )


app = App(app_ui, server)
