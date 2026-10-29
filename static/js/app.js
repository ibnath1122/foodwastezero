/* Theme (light/dark), accent (orange/purple) and chart helper */
(function () {
  var root = document.documentElement;
  function save(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  /* Bangla support: the server translates the page itself; these helpers translate text that JS builds. */
  var BN = document.documentElement.lang === 'bn';
  var BN_TXT = {
    'Search…': 'খুঁজুন…', 'Search': 'খুঁজুন', 'Reset': 'রিসেট', 'CSV': 'CSV', 'Download the rows currently matching': 'বর্তমান সারিগুলো ডাউনলোড করুন',
    'Nothing matches your search or filters.': 'আপনার অনুসন্ধান বা ফিল্টারে কিছু মেলেনি।', 'Show less': 'কম দেখান', 'Showing ': 'দেখানো হচ্ছে ',
    ' of ': ' / ', ' (filtered from ': ' (ফিল্টার করা হয়েছে, মোট ', 'Show all (': 'সব দেখান (', 'All ': 'সব ',
    'Thinking…': 'ভাবছি…', 'Sorry, I could not connect. Please try again.': 'দুঃখিত, সংযোগ করা যায়নি। আবার চেষ্টা করুন।',
    'Actual': 'প্রকৃত', 'Forecast': 'পূর্বাভাস'
  };
  var BN_WORDS = { 'Category': 'ক্যাটাগরি', 'Status': 'অবস্থা', 'Expiry': 'মেয়াদ', 'Partner': 'সহযোগী', 'Urgency': 'জরুরিত্ব', 'Action': 'পদক্ষেপ', 'Price': 'দাম' };
  function bnDigits(s) { return String(s).replace(/[0-9]/g, function (d) { return '০১২৩৪৫৬৭৮৯'.charAt(d); }); }
  function asciiDigits(s) { return String(s).replace(/[০-৯]/g, function (d) { return '০১২৩৪৫৬৭৮৯'.indexOf(d); }); }
  function T(s) { return BN && BN_TXT[s] ? BN_TXT[s] : s; }
  function N(x) { return BN ? bnDigits(x) : String(x); }
  function V(v) { return BN && window.FWZ_VAL && window.FWZ_VAL[v] ? window.FWZ_VAL[v] : v; }   // filter option labels
  window.FWZ_T = T;

  var FWZ = window.FWZ = {
    t: T, n: N, val: V, ascii: asciiDigits, bn: BN,
    rebuilders: [],
    v: function (n) { return getComputedStyle(root).getPropertyValue(n).trim(); },
    colors: function () {
      var v = this.v.bind(this);
      return {
        text: v('--muted'), grid: v('--line'), surface: v('--surface'),
        accent: v('--accent'), accent2: v('--accent-2'),
        ok: v('--ok'), warn: v('--warn'), bad: v('--bad'), info: v('--info'),
        series: [1, 2, 3, 4, 5, 6].map(function (i) { return v('--s' + i); })
      };
    },
    // FWZ.chart('canvasId', function(colors){ return chartConfig; }) - rebuilt automatically when the theme changes
    chart: function (id, build) {
      var el = document.getElementById(id);
      if (!el || !window.Chart) return;
      var self = this;
      function make() {
        if (el._chart) el._chart.destroy();
        var c = self.colors();
        Chart.defaults.color = c.text;
        Chart.defaults.borderColor = c.grid;
        Chart.defaults.font.family = "'Hind Siliguri', system-ui, sans-serif";
        el._chart = new Chart(el, build(c));
      }
      make();
      this.rebuilders.push(make);
    }
  };

  function refresh() { FWZ.rebuilders.forEach(function (f) { f(); }); }

  document.addEventListener('click', function (e) {
    var t = e.target.closest('[data-toggle-theme]');
    if (t) {
      var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next); save('fwz-theme', next); refresh(); return;
    }
    var a = e.target.closest('[data-accent-set]');
    if (a) {
      var x = a.getAttribute('data-accent-set');
      root.setAttribute('data-accent', x); save('fwz-accent', x); refresh();
    }
  });
})();

/* ---------------------------------------------------------------------------------------------
   Table / list tools. Add  data-enhance  to a wrapper that contains a <table> (or items marked
   data-item).  Options:  data-limit="10"  data-search="placeholder"  data-csv="file-name"
   data-filters="key:Label,key2:Label2"   (rows/items carry  data-f-key="value")
   --------------------------------------------------------------------------------------------- */
(function () {
  var F = window.FWZ, T = F.t, N = F.n, V = F.val, BN = F.bn, asciiDigits = F.ascii;
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html) e.innerHTML = html; return e; }
  function icon(n) { return '<svg class="ic"><use href="#' + n + '"/></svg>'; }

  function enhance(root) {
    var table = root.querySelector('table');
    var items = table
      ? [].filter.call(table.querySelectorAll('tr'), function (r) { return r.querySelector('td'); })
      : [].slice.call(root.querySelectorAll('[data-item]'));
    if (!items.length) return;

    var limit = parseInt(root.dataset.limit || '10', 10);
    var showAll = false, q = '', fv = {}, sortIdx = -1, sortDir = 1;
    var cfg = (root.dataset.filters || '').split(',').filter(Boolean).map(function (s) {
      var p = s.split(':'); return { key: p[0], label: p[1] || p[0] };
    });
    var anchor = table || items[0];

    /* toolbar */
    var bar = el('div', 'toolbar');
    var sbox = el('label', 'searchbox', icon('i-search') + '<input type="search" placeholder="' + (root.dataset.search || T('Search…')) + '" aria-label="Search">');
    bar.appendChild(sbox);
    var sinput = sbox.querySelector('input');
    var selects = cfg.map(function (c) {
      var vals = []; items.forEach(function (it) { var v = it.getAttribute('data-f-' + c.key); if (v && vals.indexOf(v) < 0) vals.push(v); });
      vals.sort(function (a, b) { return a.localeCompare(b, undefined, { numeric: true }); });
      var s = el('select', 'filter', '<option value="">' + T('All ') + (BN ? c.label : c.label.toLowerCase()) + '</option>' +
        vals.map(function (v) { return '<option value="' + v.replace(/&/g, '&amp;').replace(/"/g, '&quot;') + '">' + V(v).replace(/&/g, '&amp;') + '</option>'; }).join(''));
      s.setAttribute('aria-label', c.label);
      s.addEventListener('change', function () { fv[c.key] = s.value; showAll = false; apply(); });
      bar.appendChild(s); return s;
    });
    var reset = el('button', 'btn ghost sm', T('Reset')); reset.type = 'button'; reset.hidden = true;
    bar.appendChild(reset);
    if (root.dataset.csv && table) {
      var csv = el('button', 'btn ghost sm push', icon('i-download') + 'CSV'); csv.type = 'button'; csv.title = T('Download the rows currently matching');
      csv.addEventListener('click', exportCsv); bar.appendChild(csv);
    }
    anchor.parentNode.insertBefore(bar, anchor);

    /* footer */
    var foot = el('div', 'tfoot'); var count = el('span', 'muted small'); var more = el('button', 'btn ghost sm'); more.type = 'button';
    foot.appendChild(count); foot.appendChild(more);
    if (table) anchor.parentNode.insertBefore(foot, table.nextSibling); else root.appendChild(foot);
    var empty = el('div', 'empty', T('Nothing matches your search or filters.')); empty.hidden = true;
    foot.parentNode.insertBefore(empty, foot);

    function apply() {
      var matched = [];
      items.forEach(function (it) {
        var ok = !q || asciiDigits(it.textContent).toLowerCase().indexOf(q) > -1;
        cfg.forEach(function (c) { if (fv[c.key] && it.getAttribute('data-f-' + c.key) !== fv[c.key]) ok = false; });
        it._m = ok; if (ok) matched.push(it);
      });
      var idx = 0;
      items.forEach(function (it) { if (it._m) { it.hidden = !(showAll || idx < limit); idx++; } else it.hidden = true; });
      var shown = Math.min(matched.length, showAll ? matched.length : limit);
      count.textContent = matched.length ? T('Showing ') + N(shown) + T(' of ') + N(matched.length) + (matched.length !== items.length ? T(' (filtered from ') + N(items.length) + ')' : '') : '';
      more.hidden = matched.length <= limit;
      more.textContent = showAll ? T('Show less') : T('Show all (') + N(matched.length) + ')';
      empty.hidden = matched.length > 0;
      reset.hidden = !(q || Object.keys(fv).some(function (k) { return fv[k]; }));
      if (table) table.style.display = matched.length ? '' : 'none';
    }
    sinput.addEventListener('input', function () { q = asciiDigits(sinput.value).trim().toLowerCase(); showAll = false; apply(); });
    more.addEventListener('click', function () { showAll = !showAll; apply(); });
    reset.addEventListener('click', function () { sinput.value = ''; q = ''; fv = {}; selects.forEach(function (s) { s.value = ''; }); showAll = false; apply(); });

    /* sorting (tables only) */
    if (table) {
      var ths = [].slice.call(table.querySelectorAll('tr th'));
      ths.forEach(function (th, i) {
        if (!th.textContent.trim() || th.hasAttribute('data-nosort')) return;
        th.classList.add('sortable'); th.tabIndex = 0;
        function go() {
          sortDir = (sortIdx === i) ? -sortDir : 1; sortIdx = i;
          ths.forEach(function (t) { t.classList.remove('asc', 'desc'); });
          th.classList.add(sortDir > 0 ? 'asc' : 'desc');
          var num = th.classList.contains('num');
          function key(it) {
            var c = it.cells[i]; if (!c) return '';
            var v = c.getAttribute('data-sort'); if (v === null) v = asciiDigits(c.textContent.trim());
            if (num || (v !== '' && !isNaN(Number(v)))) { var n = parseFloat(String(v).replace(/[^0-9.\-]/g, '')); return isNaN(n) ? -Infinity : n; }
            return v.toLowerCase();
          }
          var parent = items[0].parentNode;
          items.sort(function (a, b) {
            var x = key(a), y = key(b);
            if (typeof x === 'number' && typeof y === 'number') return (x - y) * sortDir;
            return String(x).localeCompare(String(y), undefined, { numeric: true }) * sortDir;
          });
          items.forEach(function (it) { parent.appendChild(it); });
          apply();
        }
        th.addEventListener('click', go);
        th.addEventListener('keydown', function (e) { if (e.key === 'Enter') go(); });
      });
    }

    function exportCsv() {
      var heads = [].map.call(table.querySelectorAll('tr th'), function (t) { return t.textContent.trim(); });
      var keep = heads.map(function (h, i) { return h ? i : -1; }).filter(function (i) { return i >= 0; });
      function cell(s) { s = String(s).replace(/\s+/g, ' ').trim(); return '"' + s.replace(/"/g, '""') + '"'; }
      var lines = [keep.map(function (i) { return cell(heads[i]); }).join(',')];
      items.forEach(function (it) { if (it._m) lines.push(keep.map(function (i) { return cell(it.cells[i] ? it.cells[i].textContent : ''); }).join(',')); });
      var blob = new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
      var a = document.createElement('a'); a.href = URL.createObjectURL(blob);
      a.download = (root.dataset.csv || 'export') + '-' + new Date().toISOString().slice(0, 10) + '.csv';
      document.body.appendChild(a); a.click(); a.remove();
    }
    apply();
    root._enh = { focus: function () { sinput.focus(); } };
  }

  document.addEventListener('DOMContentLoaded', function () {
    [].forEach.call(document.querySelectorAll('[data-enhance]'), enhance);
  });
  // press "/" anywhere to jump to the first search box
  document.addEventListener('keydown', function (e) {
    var t = e.target.tagName;
    if (e.key === '/' && t !== 'INPUT' && t !== 'SELECT' && t !== 'TEXTAREA') {
      var f = document.querySelector('[data-enhance]'); if (f && f._enh) { e.preventDefault(); f._enh.focus(); }
    }
  });
})();

/* KPI / hero numbers count up once on load (skipped when the visitor prefers reduced motion) */
document.addEventListener('DOMContentLoaded', function () {
  if (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  var fmt = function (n, d) { return n.toLocaleString('en-US', {minimumFractionDigits: d, maximumFractionDigits: d}); };
  document.querySelectorAll('.kpi .value, [data-count]').forEach(function (el) {
    var node = null;
    (function walk(n) { n.childNodes.forEach(function (c) {
      if (c.nodeType === 3 && /\d/.test(c.nodeValue)) node = c; else if (c.nodeType === 1 && !c.classList.contains('cur')) walk(c); }); })(el);
    if (!node) return;
    var m = node.nodeValue.match(/[\d,]*\.?\d+/); if (!m) return;
    var target = parseFloat(m[0].replace(/,/g, '')), dec = (m[0].split('.')[1] || '').length;
    if (!isFinite(target) || target === 0) return;
    var before = node.nodeValue.slice(0, m.index), after = node.nodeValue.slice(m.index + m[0].length), t0 = null;
    (function step(t) {
      if (t0 === null) t0 = t;
      var p = Math.min(1, (t - t0) / 900), e = 1 - Math.pow(1 - p, 3);
      node.nodeValue = before + fmt(target * e, dec) + after;
      if (p < 1) requestAnimationFrame(step);
    })(performance.now());
  });
});
