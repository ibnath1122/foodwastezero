/* Tiny chat client used by the customer widget and the admin assistant page. */
(function () {
  var T = window.FWZ_T || function (x) { return x; };
  function esc(s) { return s.replace(/[&<>"]/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
  function fmt(s) { return esc(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/\n/g, '<br>'); }

  window.FWZChat = function (root) {
    var url = root.getAttribute('data-endpoint');
    var log = root.querySelector('.chat-log'), form = root.querySelector('form'), input = form.querySelector('input');
    var hist = [], busy = false;

    function add(role, text) {
      var d = document.createElement('div'); d.className = 'msg ' + role; d.innerHTML = fmt(text);
      log.appendChild(d); log.scrollTop = log.scrollHeight; return d;
    }
    function send(text) {
      text = (text || '').trim(); if (!text || busy) return;
      busy = true; add('user', text); hist.push({role: 'user', text: text}); input.value = '';
      var wait = add('bot typing', T('Thinking…'));
      fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({messages: hist})})
        .then(function (r) { return r.json(); })
        .then(function (j) { wait.className = 'msg bot'; wait.innerHTML = fmt(j.reply); hist.push({role: 'bot', text: j.reply}); })
        .catch(function () { wait.className = 'msg bot'; wait.textContent = T('Sorry, I could not connect. Please try again.'); hist.pop(); })
        .then(function () { busy = false; log.scrollTop = log.scrollHeight; input.focus(); });
    }
    form.addEventListener('submit', function (e) { e.preventDefault(); send(input.value); });
    root.addEventListener('click', function (e) {
      var c = e.target.closest('[data-q]'); if (c) send(c.getAttribute('data-q'));
    });
    add('bot', root.getAttribute('data-hello'));
  };
})();
