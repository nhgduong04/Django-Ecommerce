import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from .services import get_chat_reply_text


@require_POST
@csrf_protect
def chatbot_api(request):
    try:
        # Decode dữ liệu dạng byte và chuyển đổi thành dict rồi lưu vào biến payload
        payload = json.loads((request.body or b"{}").decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    message = (payload.get("message") or "").strip()
    if not message:
        return JsonResponse({"error": "Message is required."}, status=400)
    if len(message) > 500:
        return JsonResponse({"error": "Message is too long."}, status=400)

    history = request.session.get("chatbot_history", [])
    reply = get_chat_reply_text(
        message,
        user=getattr(request, "user", None),
        history=history,
    )

    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": reply})
    request.session["chatbot_history"] = history[-10:]
    return JsonResponse({"reply": reply})
