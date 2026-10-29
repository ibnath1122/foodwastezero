"""Customer + admin chatbots. Gemini writes the reply, but every fact comes from live store data placed in the
prompt; if Gemini is unavailable a built-in rule-based answer (same data) is used instead."""
import re
import time
from datetime import timedelta

import config
import gemini
import i18n

# ---------------------------------------------------------------- customer bot
def shop_context(catalog, today):
    rows = []
    for p in sorted(catalog, key=lambda x: x["name"]):
        rows.append("- %s | %s | now %s%s per %s%s | %d in stock | best before %s (%s)" % (
            p["name"], p["category"], config.CURRENCY, _n(p["price"]), p["unit"],
            (" (was %s%s, %d%% off)" % (config.CURRENCY, _n(p["base"]), p["pct"])) if p["pct"] else "",
            p["qty"], p["expires"].strftime("%d %b"),
            "today" if p["days_left"] == 0 else "tomorrow" if p["days_left"] == 1 else "in %d days" % p["days_left"]))
    return "\n".join(rows)


def shop_system(catalog, today):
    return (
        "You are the friendly shop assistant for FoodWasteZero, a grocery shop in Bangladesh that discounts food "
        "close to its best-before date so it gets eaten instead of wasted. Today is %s. Currency is ৳ (taka).\n"
        "Answer customers about product prices, discounts, availability, stock and best-before dates using ONLY the "
        "live list below. Rules: never invent products, prices or stock; if a product is not in the list say it is not "
        "available right now and suggest similar items from the list; mention the discount and best-before date for "
        "discounted items; keep answers short (1-4 sentences or a tiny list); reply in the customer's language "
        "(English or Bangla); you cannot take orders or payments, tell them to visit the shop; don't discuss costs, "
        "profits or anything outside the shop.\n\nLIVE PRODUCT LIST (name | category | price | stock | best before):\n%s"
        % (today.strftime("%A %d %B %Y"), shop_context(catalog, today)))


def _n(v):
    v = float(v)
    return str(int(v)) if v == int(v) else "%.1f" % v


STOP = set("is are the a an of in on for do you have has any what whats what's how much price cost current currently "
           "available availability stock there it to me tell show can i get your with and or today now about".split())


def _tokens(s):
    return [w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 1]


def _stem(w):
    return w[:-1] if w.endswith("s") and len(w) > 3 else w


def _bn_tokens(s):
    return [w for w in re.findall(r"[\u0980-\u09FF]+", s) if len(w) > 1]


def shop_fallback_bn(msg, catalog):
    """Bangla rule-based answer used when Gemini is unreachable."""
    d = i18n.bn_digits
    cur = config.CURRENCY
    if any(k in msg for k in ("ছাড়", "অফার", "সস্তা", "কম দাম", "discount", "offer")):
        deals = sorted([p for p in catalog if p["pct"] > 0], key=lambda p: -p["pct"])[:6]
        if deals:
            return "আজকের সেরা রেসকিউ অফার:\n" + "\n".join(d("• %s — %s%s (%d%% ছাড়, আগের দাম %s%s), মজুত %d" % (
                i18n.tr(p["name"]), cur, _n(p["price"]), p["pct"], cur, _n(p["base"]), p["qty"])) for p in deals)
        return "এখন কোনো ছাড়ের পণ্য নেই, তবে শপ পেজের সবকিছু নিয়মিত দামে মজুত আছে।"
    toks = set(_bn_tokens(msg)) | {_stem(t) for t in _tokens(msg)}
    hits = []
    for p in catalog:
        words = set(_bn_tokens(i18n.tr(p["name"]))) | {_stem(w) for w in _tokens(p["name"])}
        words |= set(_bn_tokens(i18n.tr(p["category"]))) if not (toks & words) else set()
        n = len(toks & words)
        if n:
            hits.append((n, p))
    hits.sort(key=lambda x: (-x[0], x[1]["name"]))
    if hits:
        lines = []
        for _, p in hits[:5]:
            extra = " — %d%% ছাড় (আগের দাম %s%s)" % (p["pct"], cur, _n(p["base"])) if p["pct"] else ""
            lines.append(d("• %s: প্রতি %s %s%s%s। মজুত %d, মেয়াদ %s পর্যন্ত।" % (
                i18n.tr(p["name"]), i18n.UNITS.get(p["unit"], p["unit"]), cur, _n(p["price"]), extra, p["qty"],
                p["expires"].strftime("%d ") + i18n.MONTHS[p["expires"].strftime("%b")])))
        return "জি, আমাদের কাছে আছে:\n" + "\n".join(lines)
    if toks:
        return "দুঃখিত, এই পণ্যটি এখন মজুত দেখতে পাচ্ছি না। শপ পেজে সব পণ্য দেখতে পারেন।"
    return "যেকোনো পণ্য সম্পর্কে জিজ্ঞাসা করুন — যেমন “দুধের দাম” বা “কিসে ছাড় আছে?”"


def shop_fallback(msg, catalog, lang="en"):
    """Rule-based answer used when Gemini is unreachable."""
    if lang == "bn":
        return shop_fallback_bn(msg, catalog)
    low = msg.lower()
    if any(k in low for k in ("discount", "offer", "deal", "sale", "cheap", "off")):
        deals = sorted([p for p in catalog if p["pct"] > 0], key=lambda p: -p["pct"])[:6]
        if deals:
            return "Today's best rescue deals:\n" + "\n".join(
                "• %s — %s%s (%d%% off, was %s%s), %d in stock" % (p["name"], config.CURRENCY, _n(p["price"]), p["pct"],
                                                                 config.CURRENCY, _n(p["base"]), p["qty"]) for p in deals)
        return "There are no discounted items right now, but everything on the shop page is in stock at regular price."
    toks = {_stem(t) for t in _tokens(msg)}
    def find(use_cat):
        found = []
        for p in catalog:
            words = {_stem(w) for w in _tokens(p["name"] + (" " + p["category"] if use_cat else ""))}
            if toks & words:
                found.append((len(toks & words), p))
        return found
    hits = find(False) or find(True)      # product-name matches first, category only as a fallback
    hits.sort(key=lambda x: (-x[0], x[1]["name"]))
    if hits:
        lines = []
        for _, p in hits[:5]:
            extra = " — %d%% off (was %s%s)" % (p["pct"], config.CURRENCY, _n(p["base"])) if p["pct"] else ""
            lines.append("• %s: %s%s per %s%s. %d in stock, best before %s." % (
                p["name"], config.CURRENCY, _n(p["price"]), p["unit"], extra, p["qty"], p["expires"].strftime("%d %b")))
        return "Yes, we have:\n" + "\n".join(lines)
    if toks:
        return "Sorry, I can't find that in stock right now. You can browse everything on the shop page."
    return "Ask me about any product — for example \"price of milk\" or \"what's on discount?\""


# ---------------------------------------------------------------- admin bot
def admin_context(db, today, fc):
    iso = today.isoformat()
    since7 = (today - timedelta(days=7)).isoformat()
    since30 = (today - timedelta(days=30)).isoformat()
    items = fc.load_assessments(db, today)
    risky = sorted([b for b in items if b["at_risk"] > 0], key=lambda b: (b["days_left"], -b["at_risk"]))[:20]
    plan = fc.reorder_plan(db, today)
    lines = ["TODAY: %s. Currency ৳." % today.strftime("%A %d %B %Y")]
    lines.append("TOTALS: %d active batches, %d units at risk (cost value ৳%d), %d batches expiring within 3 days, "
                 "%d pending AI actions." % (
                     len(items), sum(b["at_risk"] for b in items),
                     round(sum(b["at_risk"] * float(b["unit_cost"]) for b in items)),
                     len([b for b in items if b["days_left"] <= 3]),
                     db.scalar("SELECT COUNT(*) FROM actions WHERE status='pending'")))
    rev7 = db.one("SELECT SUM(quantity*unit_price) AS r, SUM(quantity) AS q FROM sales WHERE sold_on>=%s", (since7,)) or {}
    lines.append("LAST 7 DAYS SALES: revenue ৳%d, %d units." % (round(float(rev7.get("r") or 0)), int(rev7.get("q") or 0)))
    top = db.all("SELECT p.name, SUM(s.quantity) AS q, SUM(s.quantity*s.unit_price) AS r FROM sales s "
                 "JOIN products p ON p.id=s.product_id WHERE s.sold_on>=%s GROUP BY p.name ORDER BY q DESC LIMIT 6", (since7,))
    lines.append("TOP SELLERS (7d): " + "; ".join("%s %d units ৳%d" % (r["name"], r["q"], round(float(r["r"]))) for r in top))
    w = db.one("SELECT SUM(cost_loss) AS c, SUM(kg) AS k FROM waste_log WHERE logged_on>=%s", (since30,)) or {}
    wp = db.all("SELECT p.name, SUM(w.cost_loss) AS c FROM waste_log w JOIN products p ON p.id=w.product_id "
                "WHERE w.logged_on>=%s GROUP BY p.name ORDER BY c DESC LIMIT 5", (since30,))
    lines.append("WASTE (30d): ৳%d lost, %.1f kg. Worst: %s" % (
        round(float(w.get("c") or 0)), float(w.get("k") or 0), "; ".join("%s ৳%d" % (r["name"], round(float(r["c"]))) for r in wp)))
    d = db.one("SELECT SUM(kg) AS k, SUM(meals) AS m FROM donations WHERE donated_on>=%s", (since30,)) or {}
    lines.append("DONATIONS (30d): %.1f kg, %d meals." % (float(d.get("k") or 0), int(d.get("m") or 0)))
    lines.append("BATCHES AT RISK (product | batch | days left | qty | forecast sold | at risk | current discount | engine advice):")
    for b in risky:
        r = b["rec"] or {}
        lines.append("- %s | %s | %d | %d | %s | %d | %d%% | %s %s" % (
            b["product_name"], b["batch_code"], b["days_left"], b["qty_remaining"], b["proj_sold"], b["at_risk"],
            float(b.get("discount_pct") or 0), r.get("action_type", "none"), ("%d%%" % r["discount_pct"]) if r.get("discount_pct") else ""))
    lines.append("INVENTORY & REORDER (product | status | stock | daily demand | days cover | suggested order | order cost | excess):")
    for r in plan:
        lines.append("- %s | %s | %d | %s | %s | %d | ৳%s | %d" % (
            r["name"], r["status"], r["stock"], r["daily"], r["cover"], r["suggest"], round(r["order_cost"]), r["excess"]))
    return "\n".join(lines)


def admin_system(context):
    return ("You are the AI operations assistant for the manager of FoodWasteZero, a grocery shop focused on cutting food "
            "waste. Answer questions about the current situation (stock, expiring batches, risk, sales, waste, "
            "donations, reordering) using ONLY the live data below; never invent figures. Give a direct answer first, "
            "then at most a few concrete recommended actions naming products and quantities. Be concise; use short "
            "bullet lists when listing items. If the data doesn't cover the question, say so. Reply in the manager's "
            "language (English or Bangla).\n\nLIVE STORE DATA:\n" + context)


ADMIN_BN = [("TODAY:", "আজ:"), ("Currency ৳.", "মুদ্রা ৳।"), ("TOTALS:", "মোট:"), ("active batches", "সক্রিয় ব্যাচ"),
            ("units at risk (cost value", "ইউনিট ঝুঁকিতে (খরচ মূল্য"), ("batches expiring within 3 days", "ব্যাচের মেয়াদ ৩ দিনের মধ্যে"),
            ("pending AI actions", "এআই পদক্ষেপ অপেক্ষমাণ"), ("LAST 7 DAYS SALES:", "শেষ ৭ দিনের বিক্রি:"), ("revenue", "আয়"),
            ("units", "ইউনিট"), ("TOP SELLERS (7d):", "সেরা বিক্রিত (৭ দিন):"), ("WASTE (30d):", "অপচয় (৩০ দিন):"),
            ("lost", "ক্ষতি"), ("Worst:", "সবচেয়ে বেশি:"), ("DONATIONS (30d):", "দান (৩০ দিন):"), ("meals", "বেলার খাবার")]


def admin_fallback(context, lang="en"):
    keep = [l for l in context.splitlines() if l.startswith(("TODAY", "TOTALS", "LAST 7", "TOP SELLERS", "WASTE", "DONATIONS"))]
    if lang == "bn":
        out = []
        for l in keep:
            for a, b in ADMIN_BN:
                l = l.replace(a, b)
            out.append("• " + i18n.tr(l))
        return "(এআই সেবা পাওয়া যাচ্ছে না — তার বদলে তথ্যের সারাংশ দেখানো হচ্ছে)\n" + "\n".join(out)
    return ("(AI service unreachable — showing a data summary instead)\n" + "\n".join("• " + l for l in keep))


# ---------------------------------------------------------------- shared
_hits = {}


def rate_ok(key, limit=20, per=60):
    now = time.time()
    q = [t for t in _hits.get(key, []) if now - t < per]
    if len(q) >= limit:
        _hits[key] = q
        return False
    q.append(now)
    _hits[key] = q
    return True


def clean_history(raw, max_turns=10, max_len=500):
    out = []
    for m in (raw or [])[-max_turns:]:
        if not isinstance(m, dict):
            continue
        role = "user" if m.get("role") == "user" else "bot"
        text = str(m.get("text", ""))[:max_len].strip()
        if text:
            out.append({"role": role, "text": text})
    while out and out[0]["role"] != "user":
        out.pop(0)
    return out
