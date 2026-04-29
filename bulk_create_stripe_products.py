import stripe
import os
import argparse
from dotenv import load_dotenv  # optional, or just set env var

load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")   # or hardcode for testing (never commit)

PRODUCTS = [
    # === APPROVED SET (excluded: Soul Schema v4, CrimsonFrame, E-Drive System, Motion Doctrine → lore page) ===

    # --- AI Soul Upgrades ---
    {"name": "Single Shard", "description": "One-time RAM shard data pack for Soul Schema AI souls. Drag-and-drop, preview, and export.", "price": 99, "currency": "nzd", "category": "soul-upgrades", "tool_slug": "single-shard", "ready_for_stripe": False, "completeness": "partial"},
    {"name": "Booster Shard (15x)", "description": "15-use RAM shard booster pack for Soul Schema. Randomised trait boosts, batch upload support.", "price": 900, "currency": "nzd", "category": "soul-upgrades", "tool_slug": "booster-shard", "ready_for_stripe": False, "completeness": "partial"},

    # --- Music ---
    {"name": "RedVerse Music Pack Vol.1 (Curated Safe)", "description": "Curated safe-track edition only. No video bundle.", "price": 800, "currency": "usd", "category": "music", "tool_slug": "redverse-music-pack-safe", "ready_for_stripe": False, "completeness": "partial"},

    # --- Capture/Transcription ---
    {"name": "Scribe", "description": "Speech-to-text workspace tool.", "price": 900, "currency": "nzd", "category": "capture", "tool_slug": "scribe", "ready_for_stripe": False, "completeness": "partial"},

    # --- Live media/utility tools ---
    {"name": "Audio Cutter", "description": "Split any audio file into equal parts with clean cuts.", "price": 420, "currency": "usd", "category": "media", "tool_slug": "audiocutter", "ready_for_stripe": True, "completeness": "live"},
    {"name": "Dragon Forge", "description": "Drag-and-drop file processing pipeline — format conversion, metadata stripping, content extraction.", "price": 420, "currency": "usd", "category": "media", "tool_slug": "dragon-forge", "ready_for_stripe": True, "completeness": "live"},
    {"name": "Multitool", "description": "Utility bundle: WEBP, JSON merge, scraping helpers.", "price": 1500, "currency": "usd", "category": "media", "tool_slug": "multitool", "ready_for_stripe": True, "completeness": "live"},
    {"name": "Loop Pad", "description": "Pad-grid sample triggering and looping.", "price": 900, "currency": "usd", "category": "music", "tool_slug": "looppad", "ready_for_stripe": True, "completeness": "live"},
    {"name": "Speaker", "description": "Text-to-speech bench with selectable voices.", "price": 1200, "currency": "usd", "category": "media", "tool_slug": "speaker", "ready_for_stripe": True, "completeness": "live"},

    # --- System / File tools ---
    {"name": "Gauntlet Protocol", "description": "Live system telemetry and process management dashboard — RAM, swap, CPU, load average, and configurable kill rules.", "price": 900, "currency": "usd", "category": "system", "tool_slug": "gauntlet", "ready_for_stripe": True, "completeness": "live"},
    {"name": "Dragon Cleaner", "description": "Scan directories for junk files and duplicates, then obliterate them. Dave-AI smart-suggest mode. Port 8917.", "price": 420, "currency": "usd", "category": "system", "tool_slug": "dragon-cleaner", "ready_for_stripe": True, "completeness": "live"},
    {"name": "RedVault Indexer", "description": "Crawls directories and builds a structured, searchable file index — metadata, size, type, modification times. Port 8920.", "price": 420, "currency": "usd", "category": "file-tools", "tool_slug": "redvault-indexer", "ready_for_stripe": True, "completeness": "live"},
    {"name": "Void Eater", "description": "Timed file-shredding vault. Set retention window, files are cryptographically overwritten when the clock runs out. Multi-pass shred.", "price": 220, "currency": "usd", "category": "security", "tool_slug": "void-eater", "ready_for_stripe": False, "completeness": "partial"},

    # --- Vision ---
    {"name": "QuickCam", "description": "MJPEG webcam stream server with night vision processing modes — normal, green, thermal, lowlight, edge, spectral. Port 8910.", "price": 420, "currency": "usd", "category": "vision", "tool_slug": "quickcam", "ready_for_stripe": True, "completeness": "live"},
    {"name": "Vision Portal", "description": "Webcam AI pipeline with swappable vision mode pills — describe, detect, caption, OCR. Intensity slider. Runs via QuickCam server.", "price": 2200, "currency": "usd", "category": "vision", "tool_slug": "vision-portal", "ready_for_stripe": True, "completeness": "live"},
]

def preview_products():
    print("🧾 Stripe Draft Catalog (no API calls):\n")
    for idx, p in enumerate(PRODUCTS, start=1):
        amount = p["price"] / 100
        currency = p.get("currency", "usd").upper()
        status = p.get("completeness", "unknown")
        ready = "READY" if p.get("ready_for_stripe", False) else "HOLD"
        if p["price"] > 0:
            print(f"{idx:02d}. {p['name']} — {currency} {amount:.2f} [{ready} / {status}]")
        else:
            print(f"{idx:02d}. {p['name']} — FREE (Product only; no Price) [{ready} / {status}]")
    print("\n✅ Review complete. Use --execute to create only READY products.")
    print("   Use --execute --all to force-create every listed product.")


def create_products(selected_products):
    if not stripe.api_key:
        raise RuntimeError("Missing STRIPE_SECRET_KEY in environment")

    for p in selected_products:
        currency = p.get("currency", "usd").lower()

        # Create the Product
        product = stripe.Product.create(
            name=p["name"],
            description=p["description"],
            metadata={
                "category": p["category"],
                "tool_slug": p["tool_slug"],
                "source": "redverse-forge"
            }
        )

        print(f"✅ Created: {p['name']}")
        print(f"   Product ID: {product.id}")

        if p["price"] > 0:
            # Create a Price for it (one-time payment)
            price = stripe.Price.create(
                product=product.id,
                unit_amount=p["price"],        # minor units (e.g. 1900 = $19.00)
                currency=currency,
                metadata={"tool_slug": p["tool_slug"]}
            )
            print(f"   Price ID:   {price.id}")
            print(f"   Price:      {currency.upper()} {p['price'] / 100:.2f}\n")
        else:
            print("   Price:      FREE (no Stripe Price created)\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare or create Stripe products for RedVerse")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually call Stripe API (default is preview only; executes READY products)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="With --execute, include HOLD/partial products too",
    )
    args = parser.parse_args()

    if args.execute:
        selected = PRODUCTS if args.all else [p for p in PRODUCTS if p.get("ready_for_stripe", False)]
        if not selected:
            print("⚠️ No READY products selected. Mark products ready_for_stripe=True or run with --all.")
        else:
            create_products(selected)
            print(f"🎉 Created {len(selected)} product(s) in Stripe!")
    else:
        preview_products()