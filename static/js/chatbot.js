/**
 * Chatbot widget (vanilla JS)
 * - UI markup lives in templates/base.html
 * - Styles live in static/custom/components.css
 * - API endpoint default: /api/chatbot/
 */
(function () {
  'use strict';

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }

  function getCookie(name) {
    if (!document.cookie) return null;
    for (const cookie of document.cookie.split(';')) {
      const c = cookie.trim();
      if (c.substring(0, name.length + 1) === name + '=') {
        return decodeURIComponent(c.substring(name.length + 1));
      }
    }
    return null;
  }

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str == null ? '' : String(str);
    return div.innerHTML;
  }

  function renderMarkdown(str) {
    // Bước 1: HTML-escape TRƯỚC (security gate)
    var s = escapeHtml(str == null ? '' : String(str));

    // Bước 2: Chuyển markdown → HTML (chỉ subset an toàn)
    // Dòng trống → paragraph break
    s = s.replace(/\n{2,}/g, '<br><br>');
    // Bullet list: dòng bắt đầu bằng "- " hoặc "* "
    s = s.replace(/^[ \t]*[-*] (.+)$/gm, '<li>$1</li>');
    s = s.replace(/(<li>[^]*?<\/li>\s*)+/g, '<ul>$&</ul>');
    // Bold
    s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/__(.+?)__/g, '<strong>$1</strong>');
    // Italic (single * or _)
    s = s.replace(/\*([^*\n]+?)\*/g, '<em>$1</em>');
    s = s.replace(/_([^_\n]+?)_/g, '<em>$1</em>');
    // Newlines còn lại → <br>
    s = s.replace(/\n/g, '<br>');

    return s;
  }

  function safeToast(msg, type) {
    try {
      if (typeof window.showToast === 'function') window.showToast(msg, type || 'info');
    } catch (e) { }
  }

  function fakeReply(userText) {
    var t = (userText || '').toLowerCase();
    if (t.includes('momo')) return 'Thanh toán MoMo: chọn MoMo ở checkout, bạn sẽ được chuyển sang cổng thanh toán và quay lại trang xác nhận.';
    if (t.includes('ship') || t.includes('phí')) return 'Phí ship phụ thuộc địa chỉ. Bạn hãy cho mình quận/huyện để mình gợi ý nhanh nhé.';
    if (t.includes('đổi') || t.includes('trả')) return 'Đổi/trả: vui lòng giữ nguyên tem mác, sản phẩm chưa sử dụng và liên hệ shop trong thời gian sớm nhất để được hỗ trợ.';
    if (t.includes('đơn') || t.includes('order')) return 'Bạn có thể xem đơn hàng trong mục Profile → Orders. Nếu cần, gửi mình mã đơn để mình hướng dẫn chi tiết.';
    return 'Mình đã nhận câu hỏi. Hiện backend chatbot chưa bật API, nên đây là phản hồi demo. Bạn muốn hỏi về sản phẩm/đơn hàng/thanh toán phần nào?';
  }

  function init() {
    var widget = qs('#chatbot-widget');
    if (!widget) return;

    var toggle = qs('#chatbot-toggle');
    var panel = qs('#chatbot-panel');
    var closeBtn = qs('#chatbot-close');
    var form = qs('#chatbot-form');
    var input = qs('#chatbot-input');
    var sendBtn = qs('#chatbot-send');
    var messages = qs('#chatbot-messages');

    if (!toggle || !panel || !closeBtn || !form || !input || !sendBtn || !messages) return;

    var API_URL = widget.getAttribute('data-api-url') || '/api/chatbot/';
    var abortCtrl = null;
    var HISTORY_KEY = 'chatbot_history';

    function isOpen() {
      return panel.classList.contains('show');
    }

    function scrollToBottom() {
      messages.scrollTop = messages.scrollHeight;
    }

    function setOpen(open) {
      if (open) {
        panel.classList.add('show');
        toggle.setAttribute('aria-expanded', 'true');
        try { localStorage.setItem('chatbot_open', '1'); } catch (e) { }
        setTimeout(function () {
          input.focus();
          scrollToBottom();
        }, 50);
      } else {
        panel.classList.remove('show');
        toggle.setAttribute('aria-expanded', 'false');
        try { localStorage.setItem('chatbot_open', '0'); } catch (e) { }
      }
    }

    function setSending(sending) {
      sendBtn.disabled = !!sending;
      input.disabled = !!sending;
    }

    function syncSendEnabled() {
      var hasText = (input.value || '').trim().length > 0;
      sendBtn.disabled = !hasText || input.disabled;
    }

    function saveHistory() {
      try {
        var items = [];
        var nodes = messages.querySelectorAll('.chatbot-msg:not(.typing)');
        for (var i = 0; i < nodes.length; i++) {
          var node = nodes[i];
          var role = node.classList.contains('user') ? 'user' : 'bot';
          var bubble = node.querySelector('.bubble');
          if (bubble) items.push({ role: role, text: bubble.textContent });
        }
        sessionStorage.setItem(HISTORY_KEY, JSON.stringify(items));
      } catch (e) { }
    }

    function restoreHistory() {
      try {
        var raw = sessionStorage.getItem(HISTORY_KEY);
        if (!raw) return;
        var items = JSON.parse(raw);
        if (!Array.isArray(items) || !items.length) return;
        for (var i = 0; i < items.length; i++) {
          var cls = items[i].role === 'user' ? 'user' : 'bot';
          messages.insertAdjacentHTML(
            'beforeend',
            '<div class="chatbot-msg ' + cls + '">' +
            '<div class="bubble">' + (items[i].role === 'user' ? escapeHtml(items[i].text) : renderMarkdown(items[i].text)) + '</div>' +
            '</div>'
          );
        }
        scrollToBottom();
      } catch (e) { }
    }

    function appendMessage(role, text, extraClass) {
      var cls = role === 'user' ? 'user' : 'bot';
      if (extraClass) cls += ' ' + extraClass;
      messages.insertAdjacentHTML(
        'beforeend',
        '<div class="chatbot-msg ' + cls + '">' +
        '<div class="bubble">' + (role === 'user' ? escapeHtml(text) : renderMarkdown(text)) + '</div>' +
        '</div>'
      );
      scrollToBottom();
      saveHistory();
    }

    function appendTyping() {
      messages.insertAdjacentHTML(
        'beforeend',
        '<div class="chatbot-msg bot typing" data-typing="1">' +
        '<div class="bubble">Đang trả lời...</div>' +
        '</div>'
      );
      scrollToBottom();
      var nodes = messages.querySelectorAll('[data-typing="1"]');
      return nodes.length ? nodes[nodes.length - 1] : null;
    }

    function removeNode(node) {
      if (node && node.parentNode) node.parentNode.removeChild(node);
    }

    // Restore chat history & open state
    restoreHistory();
    try {
      if (localStorage.getItem('chatbot_open') === '1') setOpen(true);
    } catch (e) { }

    // Events
    toggle.addEventListener('click', function () {
      setOpen(!isOpen());
    });

    closeBtn.addEventListener('click', function () {
      setOpen(false);
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && isOpen()) setOpen(false);
    });

    document.addEventListener('click', function (e) {
      if (!isOpen()) return;
      var t = e.target;
      if (panel.contains(t) || toggle.contains(t)) return;
      setOpen(false);
    });

    input.addEventListener('input', syncSendEnabled);
    syncSendEnabled();

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var text = (input.value || '').trim();
      if (!text) return;

      appendMessage('user', text);
      input.value = '';
      syncSendEnabled();

      var typingNode = appendTyping();
      setSending(true);

      if (abortCtrl) abortCtrl.abort();
      abortCtrl = new AbortController();

      var csrf = getCookie('csrftoken');

      fetch(API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': csrf || ''
        },
        credentials: 'same-origin',
        body: JSON.stringify({ message: text }),
        signal: abortCtrl.signal
      })
        .then(function (res) {
          return res.text().then(function (raw) {
            var data = null;
            try {
              data = raw ? JSON.parse(raw) : null;
            } catch (e) {
              data = null;
            }
            if (!res.ok) {
              var errMsg =
                data && (data.error || data.detail || data.message)
                  ? (data.error || data.detail || data.message)
                  : res.status === 403
                    ? 'Phiên làm việc hết hạn hoặc thiếu CSRF. Vui lòng tải lại trang.'
                    : 'Lỗi máy chủ (' + res.status + ').';
              throw new Error(errMsg);
            }
            return data;
          });
        })
        .then(function (data) {
          removeNode(typingNode);
          var reply =
            data && (data.reply || data.message || data.answer)
              ? (data.reply || data.message || data.answer)
              : 'Mình chưa có câu trả lời phù hợp.';
          appendMessage('bot', reply);
        })
        .catch(function (err) {
          removeNode(typingNode);
          if (err && err.name === 'AbortError') return;
          var fallback = fakeReply(text);
          var msg = err && err.message ? err.message : String(err || '');
          if (msg && msg.indexOf('Failed to fetch') !== -1) {
            msg = 'Không kết nối được máy chủ. Kiểm tra mạng hoặc thử lại sau.';
          }
          appendMessage('bot', msg || fallback);
          if (msg && (msg.indexOf('Phiên làm việc') !== -1 || msg.indexOf('Không kết nối') !== -1)) {
            safeToast(msg, 'warning');
          }
        })
        .finally(function () {
          setSending(false);
          syncSendEnabled();
          input.focus();
        });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

