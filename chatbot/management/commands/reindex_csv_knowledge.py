"""
Management command: reindex_csv_knowledge

Indexes all CSV knowledge files (products_static, policies, faq) into ChromaDB.
Uses upsert semantics (stable IDs) — safe to re-run any time.

Usage:
    python manage.py reindex_csv_knowledge
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Index CSV knowledge files (products_static, policies, faq) into ChromaDB"

    def handle(self, *args, **options):
        from chatbot.csv_rag import load_csv_documents
        from chatbot.rag import index_documents

        docs = load_csv_documents()
        if not docs:
            self.stdout.write(self.style.WARNING("No CSV documents found. Check chatbot/knowledge/ directory."))
            return

        count = index_documents(docs)
        self.stdout.write(self.style.SUCCESS(f"Indexed {count} CSV documents into ChromaDB."))