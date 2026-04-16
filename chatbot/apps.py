from django.apps import AppConfig


class ChatbotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chatbot'

    def ready(self):
        # ── Warmup: prime vectorstore at server start ─────────────────────
        try:
            from .rag import warmup
            warmup()
        except Exception:
            pass  # Fail silently — DB/env may not be ready in all startup paths

        # ── Auto-reindex: register post_save signal on Product ────────────
        from django.db.models.signals import post_save
        post_save.connect(_on_product_saved, sender='products.Product')


def _on_product_saved(sender, instance, **kwargs):
    """
    Chạy sau mỗi Product.save() trong admin hoặc ORM.
    Incremental reindex vào ChromaDB trong background thread (không block admin save).
    """
    import threading

    def _reindex():
        try:
            from chatbot.rag import index_documents
            cat = instance.category.name if getattr(instance, 'category_id', None) else ""
            text = (
                f"Tên sản phẩm: {instance.name}\n"
                f"Danh mục: {cat}\n"
                f"Mô tả: {instance.description or ''}\n"
            ).strip()
            doc = {
                "id": f"product:{instance.id}",
                "text": text,
                "metadata": {
                    "type": "product",
                    "product_id": instance.id,
                    "name": instance.name,
                    "title": instance.name,
                    "category": cat,
                },
            }
            index_documents([doc])
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Background reindex failed for product_id=%s", instance.id
            )

    threading.Thread(target=_reindex, daemon=True).start()
