from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Reindex product descriptions into ChromaDB for chatbot RAG."

    def handle(self, *args, **options):
        from products.models import Product
        from chatbot.rag import index_documents

        docs = []
        qs = Product.objects.select_related("category").all().order_by("id")
        total = qs.count()
        self.stdout.write(self.style.NOTICE(f"Found {total} products. Building documents..."))

        for p in qs.iterator(chunk_size=200):
            cat = p.category.name if getattr(p, "category_id", None) else ""
            text = (
                f"Tên sản phẩm: {p.name}\n"
                f"Danh mục: {cat}\n"
                f"Mô tả: {p.description or ''}\n"
            ).strip()
            docs.append(
                {
                    "id": f"product:{p.id}",
                    "text": text,
                    "metadata": {
                        "type": "product",
                        "product_id": p.id,
                        "name": p.name,
                        "title": p.name,
                        "category": cat,
                    },
                }
            )

        indexed = index_documents(docs)
        self.stdout.write(self.style.SUCCESS(f"Indexed {indexed} documents into ChromaDB."))

