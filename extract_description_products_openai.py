from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

try:
    from openai import OpenAI
except ImportError as exc:
    raise ImportError(
        "Güncel OpenAI Python SDK gerekli. Şunu çalıştır: "
        "pip install -U openai pydantic python-dotenv"
    ) from exc

from pydantic import BaseModel, Field


PROMPT_VERSION = "description-products-v1"
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
DEFAULT_DATA_ROOT = Path("data")


class ExtractedProduct(BaseModel):
    """One commercial beauty or personal-care product explicitly present in the description."""

    brand: str | None = Field(
        description=(
            "Brand explicitly present or unambiguously written in the evidence text. "
            "Use null when the brand is not given."
        )
    )
    product_name: str = Field(
        description=(
            "Product name as supported by the description. Preserve shade, number, "
            "variant, concentration, SPF and size when present."
        )
    )
    category: Literal[
        "skincare",
        "makeup",
        "haircare",
        "bodycare",
        "fragrance",
        "other_beauty",
    ] = Field(description="Best matching product category.")
    evidence_text: str = Field(
        description=(
            "An exact, contiguous excerpt copied from the supplied YouTube description. "
            "Do not correct spelling or punctuation in this field."
        )
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence that this excerpt names a specific commercial product.",
    )
    notes: str | None = Field(
        description=(
            "Brief uncertainty note. Use null when no clarification is necessary."
        )
    )


class DescriptionExtraction(BaseModel):
    products: list[ExtractedProduct] = Field(
        description="All specific commercial beauty products explicitly supported by the description."
    )
    no_products_reason: str | None = Field(
        description="Why no products were returned; null when products were found."
    )


SYSTEM_PROMPT = """You extract beauty-product catalog records from YouTube video descriptions.

Your task is narrow: identify specific commercial beauty or personal-care products that
are explicitly written in the supplied description.

STRICT RULES

1. Use only the supplied title and description. Do not use web knowledge.
2. Never invent, complete, correct or expand a brand/product beyond what the description supports.
3. Every returned product MUST include evidence_text copied exactly and contiguously from
   the description. Preserve its original spelling, punctuation, emojis and capitalization.
4. Include products appearing in:
   - headings such as "Videodaki Ürünler", "Kullandığım Ürünler",
     "Bahsettiğim Ürünler" or similar natural-language variants;
   - numbered lists;
   - bullet lists;
   - plain consecutive product lines;
   - prose, but only when a specific commercial product is clearly named.
5. In patterns such as "Brand - Product", treat the left side as brand and the right side
   as product only when that interpretation is supported by the text.
6. Preserve shades, product numbers, variants, concentrations, SPF values and sizes.
7. Exclude:
   - category headings such as "Göz Altı Patch", "Nazik AHA / Eksfoliyasyon";
   - ingredients or generic product classes without a specific commercial product;
   - sponsor/reklam disclosures, affiliate statements and discount codes;
   - social-media links, channel membership messages, contact information and timestamps;
   - cameras, lights, microphones, music and other creator equipment;
   - medicines or active ingredients unless a branded beauty product is explicitly named.
8. A line may contain explanatory language after a genuine product name. Keep the supported
   product wording, and mention uncertainty in notes rather than fabricating a canonical name.
9. If the brand is absent, return brand=null instead of guessing.
10. Return each product once. Do not return category headings as products.

The output must follow the provided structured schema.
"""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalized_for_dedupe(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(text.casefold().split()).strip(" :;,.-–—")


def find_exact_evidence(description: str, evidence_text: str) -> tuple[bool, int | None]:
    """Validate that evidence_text is an exact substring and return its 1-based line number."""
    if not evidence_text:
        return False, None

    index = description.find(evidence_text)
    if index < 0:
        return False, None

    line_number = description.count("\n", 0, index) + 1
    return True, line_number


def get_parsed_output(response: Any) -> DescriptionExtraction:
    """Read the parsed Pydantic object from a Responses API result."""
    for output in response.output:
        if getattr(output, "type", None) != "message":
            continue

        for item in getattr(output, "content", []):
            if getattr(item, "type", None) != "output_text":
                continue

            parsed = getattr(item, "parsed", None)
            if parsed is not None:
                if isinstance(parsed, DescriptionExtraction):
                    return parsed
                return DescriptionExtraction.model_validate(parsed)

    raise RuntimeError("OpenAI yanıtında parse edilmiş structured output bulunamadı.")


def build_user_input(metadata: dict[str, Any]) -> str:
    title = metadata.get("title") or ""
    description = metadata.get("description") or ""

    return (
        "VIDEO TITLE\n"
        "===========\n"
        f"{title}\n\n"
        "VIDEO DESCRIPTION\n"
        "=================\n"
        f"{description}"
    )


def validate_and_finalize_products(
    extraction: DescriptionExtraction,
    description: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate evidence, remove duplicates and assign approved/review status."""
    products: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for item in extraction.products:
        brand = item.brand.strip() if item.brand else None
        product_name = item.product_name.strip()
        evidence_text = item.evidence_text

        evidence_exact, evidence_line_number = find_exact_evidence(
            description,
            evidence_text,
        )

        if not product_name:
            rejected.append(
                {
                    "model_output": item.model_dump(),
                    "reason": "empty_product_name",
                }
            )
            continue

        dedupe_key = (
            normalized_for_dedupe(brand),
            normalized_for_dedupe(product_name),
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        if not evidence_exact:
            status = "review"
            validation_reason = "evidence_not_exact_substring"
        elif brand is None:
            status = "review"
            validation_reason = "brand_missing"
        elif item.confidence < 0.80:
            status = "review"
            validation_reason = "model_confidence_below_0_80"
        else:
            status = "approved"
            validation_reason = "exact_evidence_brand_and_product_present"

        products.append(
            {
                "brand": brand,
                "product_name": product_name,
                "category": item.category,
                "evidence_text": evidence_text,
                "evidence_exact": evidence_exact,
                "evidence_line_number": evidence_line_number,
                "confidence": item.confidence,
                "notes": item.notes,
                "status": status,
                "validation_reason": validation_reason,
            }
        )

    return products, rejected


def output_path_for(metadata_path: Path, output_dir: Path) -> Path:
    return output_dir / metadata_path.name


def existing_output_is_current(
    output_path: Path,
    *,
    description_sha256: str,
    model: str,
) -> bool:
    if not output_path.exists():
        return False

    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    return (
        payload.get("extraction_status") == "success"
        and payload.get("description_sha256") == description_sha256
        and payload.get("model") == model
        and payload.get("prompt_version") == PROMPT_VERSION
    )


def extract_one_video(
    client: OpenAI,
    metadata: dict[str, Any],
    *,
    model: str,
) -> tuple[dict[str, Any], Any]:
    description = metadata.get("description") or ""

    if not description.strip():
        raise ValueError("Metadata JSON içindeki description alanı boş.")

    response = client.responses.parse(
        model=model,
        store=False,
        input=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": build_user_input(metadata),
            },
        ],
        text_format=DescriptionExtraction,
    )

    parsed = get_parsed_output(response)
    products, rejected = validate_and_finalize_products(parsed, description)

    approved_count = sum(item["status"] == "approved" for item in products)
    review_count = sum(item["status"] == "review" for item in products)

    usage = getattr(response, "usage", None)
    usage_payload = usage.to_dict() if usage is not None and hasattr(usage, "to_dict") else None

    result = {
        "schema_version": 1,
        "prompt_version": PROMPT_VERSION,
        "extraction_status": "success",
        "extracted_at": utc_now_iso(),
        "model": model,
        "response_id": getattr(response, "id", None),
        "video_id": metadata.get("video_id"),
        "title": metadata.get("title"),
        "channel": metadata.get("channel"),
        "upload_date": metadata.get("upload_date"),
        "url": metadata.get("url"),
        "description": description,
        "description_sha256": sha256_text(description),
        "description_character_count": len(description),
        "model_output": parsed.model_dump(),
        "products": products,
        "approved_count": approved_count,
        "review_count": review_count,
        "rejected_model_items": rejected,
        "no_products_reason": parsed.no_products_reason,
        "usage": usage_payload,
    }

    return result, response


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def collect_metadata_files(
    metadata_dir: Path,
    *,
    video_id: str | None,
    limit: int | None,
) -> list[Path]:
    paths = sorted(metadata_dir.glob("*.json"))

    if video_id:
        selected: list[Path] = []
        for path in paths:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if payload.get("video_id") == video_id:
                selected.append(path)
        paths = selected

    if limit is not None:
        paths = paths[:limit]

    return paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "YouTube metadata descriptions içinden OpenAI Structured Outputs "
            "kullanarak beauty ürünlerini çıkarır."
        )
    )
    parser.add_argument("--influencer", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--video-id")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="OpenAI Python SDK ağ/API retry sayısı.",
    )
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY bulunamadı. .env dosyasına veya terminal ortamına ekle."
        )

    influencer_dir = args.data_root / args.influencer
    metadata_dir = influencer_dir / "metadata"
    output_dir = influencer_dir / "description_products_llm"

    if not metadata_dir.exists():
        raise FileNotFoundError(f"Metadata klasörü bulunamadı: {metadata_dir}")

    metadata_paths = collect_metadata_files(
        metadata_dir,
        video_id=args.video_id,
        limit=args.limit,
    )

    if not metadata_paths:
        raise RuntimeError("İşlenecek metadata JSON dosyası bulunamadı.")

    output_dir.mkdir(parents=True, exist_ok=True)

    client = OpenAI(max_retries=args.max_retries)

    combined: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    processed_count = 0
    skipped_count = 0

    print("=" * 88)
    print("OPENAI DESCRIPTION PRODUCT EXTRACTOR")
    print("=" * 88)
    print(f"Influencer: {args.influencer}")
    print(f"Model:      {args.model}")
    print(f"Metadata:   {metadata_dir}")
    print(f"Çıktı:      {output_dir}")
    print(f"Dosya:      {len(metadata_paths)}")
    print()

    for index, metadata_path in enumerate(metadata_paths, start=1):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            failure = {
                "metadata_file": str(metadata_path),
                "reason": f"{type(error).__name__}: {error}",
            }
            failures.append(failure)
            print(f"[{index}/{len(metadata_paths)}] JSON HATASI: {metadata_path.name}")
            continue

        video_id = metadata.get("video_id") or metadata_path.stem
        title = metadata.get("title") or ""
        description = metadata.get("description") or ""
        description_sha256 = sha256_text(description)
        output_path = output_path_for(metadata_path, output_dir)

        if (
            not args.force
            and existing_output_is_current(
                output_path,
                description_sha256=description_sha256,
                model=args.model,
            )
        ):
            existing = json.loads(output_path.read_text(encoding="utf-8"))
            combined.append(existing)
            skipped_count += 1
            print(
                f"[{index}/{len(metadata_paths)}] {video_id}: "
                f"ATLANDI ({existing.get('approved_count', 0)} approved)"
            )
            continue

        print(f"[{index}/{len(metadata_paths)}] {video_id}: {title}")

        try:
            result, _ = extract_one_video(
                client,
                metadata,
                model=args.model,
            )
            write_json(output_path, result)
            combined.append(result)
            processed_count += 1

            print(
                "    "
                f"{result['approved_count']} approved, "
                f"{result['review_count']} review"
            )

        except Exception as error:
            reason = f"{type(error).__name__}: {error}"
            failure_payload = {
                "schema_version": 1,
                "prompt_version": PROMPT_VERSION,
                "extraction_status": "failed",
                "extracted_at": utc_now_iso(),
                "model": args.model,
                "video_id": video_id,
                "title": title,
                "metadata_file": str(metadata_path),
                "description_sha256": description_sha256,
                "error": reason,
            }
            write_json(output_path, failure_payload)
            failures.append(failure_payload)
            print(f"    HATA: {reason}")

        if args.delay > 0 and index < len(metadata_paths):
            time.sleep(args.delay)

    combined.sort(key=lambda item: str(item.get("upload_date") or ""))

    approved_total = sum(item.get("approved_count", 0) for item in combined)
    review_total = sum(item.get("review_count", 0) for item in combined)
    videos_with_products = sum(bool(item.get("products")) for item in combined)

    combined_path = output_dir / "description_products_all.json"
    summary_path = output_dir / "summary.json"
    failures_path = output_dir / "failures.json"

    write_json(combined_path, combined)
    write_json(
        summary_path,
        {
            "influencer": args.influencer,
            "model": args.model,
            "prompt_version": PROMPT_VERSION,
            "run_at": utc_now_iso(),
            "metadata_file_count": len(metadata_paths),
            "processed_now_count": processed_count,
            "skipped_current_count": skipped_count,
            "success_count": len(combined),
            "failure_count": len(failures),
            "videos_with_products": videos_with_products,
            "approved_product_count": approved_total,
            "review_product_count": review_total,
            "combined_output": str(combined_path),
        },
    )
    write_json(failures_path, failures)

    print()
    print("=" * 88)
    print("İŞLEM TAMAMLANDI")
    print("=" * 88)
    print(f"Başarılı video:     {len(combined)}")
    print(f"Bu çalışmada yeni:  {processed_count}")
    print(f"Atlanan güncel:     {skipped_count}")
    print(f"Ürün bulunan video: {videos_with_products}")
    print(f"Approved ürün:      {approved_total}")
    print(f"Review ürün:        {review_total}")
    print(f"Hata:               {len(failures)}")
    print(f"Birleşik çıktı:     {combined_path}")
    print(f"Özet:               {summary_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nİşlem kullanıcı tarafından durduruldu.", file=sys.stderr)
        raise SystemExit(130)
