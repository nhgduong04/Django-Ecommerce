"""
Management command: export_products_csv

Exports all products from the DB to chatbot/knowledge/products_static.csv.
Run this once initially, then re-run whenever product catalog changes significantly.

Usage:
    python manage.py export_products_csv
"""
import csv
from pathlib import Path

from django.core.management.base import BaseCommand

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge"


class Command(BaseCommand):
    help = "Export all DB products to chatbot/knowledge/products_static.csv"

    def handle(self, *args, **options):
        from products.models import Product

        KNOWLEDGE_DIR.mkdir(exist_ok=True)
        out = KNOWLEDGE_DIR / "products_static.csv"

        qs = Product.objects.select_related("category").order_by("id")
        count = 0

        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["id", "name", "category", "material", "description", "care_instructions", "tags"],
            )
            writer.writeheader()
            for p in qs:
                writer.writerow(
                    {
                        "id": p.id,
                        "name": p.name,
                        "category": p.category.name if getattr(p, "category_id", None) else "",
                        "material": "",
                        "description": (p.description or "").replace("\n", " ").replace("\r", " "),
                        "care_instructions": "",
                        "tags": p.slug or "",
                    }
                )
                count += 1

        self.stdout.write(self.style.SUCCESS(f"Exported {count} products to {out}"))
        self.stdout.write(
            self.style.WARNING(
                "Tip: Fill in 'material' and 'care_instructions' columns manually for richer RAG context, "
                "then run: python manage.py reindex_csv_knowledge"
            )
        )