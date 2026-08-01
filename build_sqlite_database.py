from __future__ import annotations

import argparse
import json
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_DATA_ROOT = Path("data")
DEFAULT_DATABASE = Path("data/database/skinfluencer.sqlite")
DEFAULT_SOURCE_SUBDIR = "product_mentions_llm_final_v2"
IGNORED_FILENAMES = {
    "summary.json",
    "failures.json",
    "product_mentions_all.json",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(value: str | None) -> str:
    """Create a stable, accent-insensitive search/deduplication value."""
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
    ascii_like = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(ascii_like.casefold().split()).strip()


def format_upload_date(value: str | None) -> str | None:
    if not value:
        return None

    value = str(value).strip()
    if len(value) == 8 and value.isdigit():
        return f"{value[:4]}-{value[4:6]}-{value[6:8]}"

    return value


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def load_schema(schema_path: Path) -> str:
    if not schema_path.exists():
        raise FileNotFoundError(f"SQL şema dosyası bulunamadı: {schema_path}")
    return schema_path.read_text(encoding="utf-8")


def connect_database(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection


def discover_influencers(
    data_root: Path,
    requested_slugs: list[str],
    source_subdir: str,
) -> list[str]:
    if requested_slugs:
        return list(dict.fromkeys(requested_slugs))

    discovered = [
        path.name
        for path in sorted(data_root.iterdir())
        if path.is_dir() and (path / source_subdir).exists()
    ]
    return discovered


def iter_source_payloads(source_dir: Path) -> Iterable[tuple[Path, dict[str, Any]]]:
    individual_paths = [
        path
        for path in sorted(source_dir.glob("*.json"))
        if path.name not in IGNORED_FILENAMES
    ]

    if individual_paths:
        for path in individual_paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            yield path, payload
        return

    combined_path = source_dir / "product_mentions_all.json"
    if not combined_path.exists():
        return

    combined = json.loads(combined_path.read_text(encoding="utf-8"))
    if not isinstance(combined, list):
        raise ValueError(
            f"Birleşik çıktı JSON listesi değil: {combined_path}"
        )

    for index, payload in enumerate(combined, start=1):
        synthetic_path = combined_path.with_name(
            f"{combined_path.stem}__item_{index:04d}.json"
        )
        yield synthetic_path, payload


def upsert_influencer(
    connection: sqlite3.Connection,
    slug: str,
    display_name: str,
) -> int:
    connection.execute(
        """
        INSERT INTO influencers (slug, display_name, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(slug) DO UPDATE SET
            display_name = excluded.display_name,
            updated_at = CURRENT_TIMESTAMP
        """,
        (slug, display_name),
    )
    row = connection.execute(
        "SELECT id FROM influencers WHERE slug = ?",
        (slug,),
    ).fetchone()
    assert row is not None
    return int(row["id"])


def upsert_video(
    connection: sqlite3.Connection,
    *,
    influencer_id: int,
    youtube_video_id: str,
    title: str,
    upload_date: str | None,
    url: str,
    source_file: str,
) -> int:
    connection.execute(
        """
        INSERT INTO videos (
            influencer_id,
            youtube_video_id,
            title,
            upload_date,
            url,
            source_file,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(influencer_id, youtube_video_id) DO UPDATE SET
            title = excluded.title,
            upload_date = excluded.upload_date,
            url = excluded.url,
            source_file = excluded.source_file,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            influencer_id,
            youtube_video_id,
            title,
            upload_date,
            url,
            source_file,
        ),
    )
    row = connection.execute(
        """
        SELECT id
        FROM videos
        WHERE influencer_id = ? AND youtube_video_id = ?
        """,
        (influencer_id, youtube_video_id),
    ).fetchone()
    assert row is not None
    return int(row["id"])


def upsert_product(
    connection: sqlite3.Connection,
    *,
    brand: str,
    product_name: str,
    category: str,
) -> int:
    normalized_brand = normalize_text(brand)
    normalized_product_name = normalize_text(product_name)
    search_text = normalize_text(f"{brand} {product_name}")

    connection.execute(
        """
        INSERT INTO products (
            brand,
            product_name,
            category,
            normalized_brand,
            normalized_product_name,
            search_text,
            verification_status,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 'approved', CURRENT_TIMESTAMP)
        ON CONFLICT(normalized_brand, normalized_product_name) DO UPDATE SET
            brand = excluded.brand,
            product_name = excluded.product_name,
            category = CASE
                WHEN products.category = 'other_beauty'
                     AND excluded.category <> 'other_beauty'
                THEN excluded.category
                ELSE products.category
            END,
            search_text = excluded.search_text,
            verification_status = 'approved',
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            brand,
            product_name,
            category,
            normalized_brand,
            normalized_product_name,
            search_text,
        ),
    )
    row = connection.execute(
        """
        SELECT id
        FROM products
        WHERE normalized_brand = ? AND normalized_product_name = ?
        """,
        (normalized_brand, normalized_product_name),
    ).fetchone()
    assert row is not None
    return int(row["id"])


def import_approved_mention(
    connection: sqlite3.Connection,
    *,
    influencer_id: int,
    video_id: int,
    mention: dict[str, Any],
    payload: dict[str, Any],
    source_file: str,
) -> None:
    brand = str(mention.get("canonical_brand") or "").strip()
    product_name = str(
        mention.get("canonical_product_name") or ""
    ).strip()
    summary = str(
        mention.get("display_summary")
        or mention.get("summary")
        or ""
    ).strip()

    if not brand or not product_name or not summary:
        raise ValueError(
            "Approved kayıtta marka, ürün adı veya display_summary eksik."
        )

    category = str(mention.get("category") or "other_beauty")
    product_id = upsert_product(
        connection,
        brand=brand,
        product_name=product_name,
        category=category,
    )

    connection.execute(
        """
        INSERT INTO product_mentions (
            product_id,
            video_id,
            influencer_id,
            candidate_id,
            mention_status,
            display_summary,
            grounded_summary,
            sentiment,
            confidence,
            raw_product_mentions_json,
            evidence_texts_json,
            opinion_points_json,
            quality_warnings_json,
            status,
            status_reason,
            source_prompt_version,
            source_summary_style_version,
            extracted_at,
            source_file,
            updated_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved',
            ?, ?, ?, ?, ?, CURRENT_TIMESTAMP
        )
        ON CONFLICT(product_id, video_id) DO UPDATE SET
            influencer_id = excluded.influencer_id,
            candidate_id = excluded.candidate_id,
            mention_status = excluded.mention_status,
            display_summary = excluded.display_summary,
            grounded_summary = excluded.grounded_summary,
            sentiment = excluded.sentiment,
            confidence = excluded.confidence,
            raw_product_mentions_json = excluded.raw_product_mentions_json,
            evidence_texts_json = excluded.evidence_texts_json,
            opinion_points_json = excluded.opinion_points_json,
            quality_warnings_json = excluded.quality_warnings_json,
            status = 'approved',
            status_reason = excluded.status_reason,
            source_prompt_version = excluded.source_prompt_version,
            source_summary_style_version = excluded.source_summary_style_version,
            extracted_at = excluded.extracted_at,
            source_file = excluded.source_file,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            product_id,
            video_id,
            influencer_id,
            mention.get("candidate_id"),
            mention.get("mention_status") or "reviewed",
            summary,
            mention.get("grounded_summary"),
            mention.get("sentiment") or "unclear",
            float(mention.get("confidence") or 0.0),
            json_text(mention.get("raw_product_mentions") or []),
            json_text(mention.get("evidence_texts") or []),
            json_text(mention.get("opinion_points") or []),
            json_text(mention.get("quality_warnings") or []),
            mention.get("status_reason"),
            payload.get("prompt_version"),
            payload.get("summary_style_version"),
            payload.get("extracted_at"),
            source_file,
        ),
    )


def import_unresolved_mention(
    connection: sqlite3.Connection,
    *,
    influencer_id: int,
    video_id: int,
    mention: dict[str, Any],
    source_file: str,
) -> None:
    status = str(mention.get("status") or "review")
    if status not in {"review", "rejected"}:
        status = "review"

    connection.execute(
        """
        INSERT INTO unresolved_mentions (
            video_id,
            influencer_id,
            candidate_id,
            canonical_brand,
            canonical_product_name,
            category,
            mention_status,
            status,
            reason,
            confidence,
            display_summary,
            raw_payload_json,
            source_file,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(
            video_id,
            candidate_id,
            canonical_brand,
            canonical_product_name,
            status
        ) DO UPDATE SET
            reason = excluded.reason,
            confidence = excluded.confidence,
            display_summary = excluded.display_summary,
            raw_payload_json = excluded.raw_payload_json,
            source_file = excluded.source_file,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            video_id,
            influencer_id,
            mention.get("candidate_id"),
            mention.get("canonical_brand"),
            mention.get("canonical_product_name"),
            mention.get("category"),
            mention.get("mention_status"),
            status,
            mention.get("status_reason"),
            mention.get("confidence"),
            mention.get("display_summary") or mention.get("summary"),
            json_text(mention),
            source_file,
        ),
    )


def import_video_payload(
    connection: sqlite3.Connection,
    *,
    influencer_slug: str,
    source_path: Path,
    payload: dict[str, Any],
) -> tuple[int, int]:
    if payload.get("extraction_status") != "success":
        raise ValueError("Extraction durumu success değil.")

    youtube_video_id = str(payload.get("video_id") or "").strip()
    if not youtube_video_id:
        raise ValueError("video_id eksik.")

    channel_name = str(
        payload.get("channel")
        or influencer_slug.replace("_", " ").title()
    ).strip()

    influencer_id = upsert_influencer(
        connection,
        influencer_slug,
        channel_name,
    )
    video_id = upsert_video(
        connection,
        influencer_id=influencer_id,
        youtube_video_id=youtube_video_id,
        title=str(payload.get("title") or youtube_video_id),
        upload_date=format_upload_date(payload.get("upload_date")),
        url=str(
            payload.get("url")
            or f"https://www.youtube.com/watch?v={youtube_video_id}"
        ),
        source_file=str(source_path),
    )

    # This source file is authoritative for this video. Remove stale rows before
    # importing the newly generated extraction output.
    connection.execute(
        "DELETE FROM product_mentions WHERE video_id = ?",
        (video_id,),
    )
    connection.execute(
        "DELETE FROM unresolved_mentions WHERE video_id = ?",
        (video_id,),
    )

    approved_count = 0
    unresolved_count = 0

    mentions = payload.get("product_mentions") or []
    if not isinstance(mentions, list):
        raise ValueError("product_mentions alanı liste değil.")

    for mention in mentions:
        status = str(mention.get("status") or "review")
        if status == "approved":
            import_approved_mention(
                connection,
                influencer_id=influencer_id,
                video_id=video_id,
                mention=mention,
                payload=payload,
                source_file=str(source_path),
            )
            approved_count += 1
        else:
            import_unresolved_mention(
                connection,
                influencer_id=influencer_id,
                video_id=video_id,
                mention=mention,
                source_file=str(source_path),
            )
            unresolved_count += 1

    return approved_count, unresolved_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "OpenAI product_mentions_llm_final_v2 JSON çıktılarını "
            "idempotent biçimde SQLite veritabanına aktarır."
        )
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE,
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).with_name("schema.sql"),
    )
    parser.add_argument(
        "--source-subdir",
        default=DEFAULT_SOURCE_SUBDIR,
    )
    parser.add_argument(
        "--influencer",
        action="append",
        default=[],
        help=(
            "İçe aktarılacak influencer slug'ı. Birden fazla kez verilebilir. "
            "Verilmezse source klasörü bulunan tüm influencer'lar taranır."
        ),
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Mevcut SQLite dosyasını silip sıfırdan oluştur.",
    )
    args = parser.parse_args()

    influencer_slugs = discover_influencers(
        args.data_root,
        args.influencer,
        args.source_subdir,
    )
    if not influencer_slugs:
        raise RuntimeError(
            "İçe aktarılabilecek influencer kaynak klasörü bulunamadı."
        )

    if args.reset and args.database.exists():
        args.database.unlink()

    schema_sql = load_schema(args.schema)
    connection = connect_database(args.database)
    errors: list[dict[str, str]] = []
    files_seen = 0
    videos_imported = 0
    approved_total = 0
    unresolved_total = 0
    started_at = utc_now_iso()

    try:
        connection.executescript(schema_sql)
        cursor = connection.execute(
            """
            INSERT INTO import_runs (
                started_at,
                database_path,
                source_subdir,
                influencer_slugs_json
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                started_at,
                str(args.database),
                args.source_subdir,
                json_text(influencer_slugs),
            ),
        )
        run_id = int(cursor.lastrowid)

        for slug in influencer_slugs:
            source_dir = args.data_root / slug / args.source_subdir
            if not source_dir.exists():
                errors.append(
                    {
                        "source": str(source_dir),
                        "error": "Kaynak klasör bulunamadı.",
                    }
                )
                continue

            for source_path, payload in iter_source_payloads(source_dir):
                files_seen += 1
                try:
                    with connection:
                        approved_count, unresolved_count = import_video_payload(
                            connection,
                            influencer_slug=slug,
                            source_path=source_path,
                            payload=payload,
                        )
                    videos_imported += 1
                    approved_total += approved_count
                    unresolved_total += unresolved_count
                    print(
                        f"[{slug}] {payload.get('video_id')}: "
                        f"{approved_count} approved, "
                        f"{unresolved_count} unresolved"
                    )
                except Exception as error:
                    errors.append(
                        {
                            "source": str(source_path),
                            "error": f"{type(error).__name__}: {error}",
                        }
                    )
                    print(
                        f"[{slug}] HATA {source_path.name}: "
                        f"{type(error).__name__}: {error}"
                    )

        # Remove products that are no longer referenced by an approved mention.
        with connection:
            connection.execute(
                """
                DELETE FROM products
                WHERE id NOT IN (
                    SELECT DISTINCT product_id
                    FROM product_mentions
                )
                """
            )
            connection.execute(
                """
                UPDATE import_runs
                SET
                    finished_at = ?,
                    files_seen = ?,
                    videos_imported = ?,
                    approved_mentions_imported = ?,
                    unresolved_mentions_imported = ?,
                    errors_json = ?
                WHERE id = ?
                """,
                (
                    utc_now_iso(),
                    files_seen,
                    videos_imported,
                    approved_total,
                    unresolved_total,
                    json_text(errors),
                    run_id,
                ),
            )

        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM influencers) AS influencers,
                (SELECT COUNT(*) FROM videos) AS videos,
                (SELECT COUNT(*) FROM products) AS products,
                (SELECT COUNT(*) FROM product_mentions) AS mentions,
                (SELECT COUNT(*) FROM unresolved_mentions) AS unresolved
            """
        ).fetchone()

        print()
        print("=" * 80)
        print("SQLITE IMPORT TAMAMLANDI")
        print("=" * 80)
        print(f"Veritabanı:          {args.database}")
        print(f"Influencer:          {counts['influencers']}")
        print(f"Video:               {counts['videos']}")
        print(f"Benzersiz ürün:      {counts['products']}")
        print(f"Approved yorum:      {counts['mentions']}")
        print(f"İncelenecek kayıt:   {counts['unresolved']}")
        print(f"Bu çalışmada hata:   {len(errors)}")

        if errors:
            error_path = args.database.with_suffix(".import_errors.json")
            error_path.write_text(
                json.dumps(errors, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"Hata raporu:         {error_path}")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
