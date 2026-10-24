"""FoodWasteZero - AI inventory & surplus-food rescue for grocery shops.
Run:  python app.py   ->   http://127.0.0.1:5000   (login: admin / admin123)
"""
import math
import os
import random
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (Flask, flash, g, jsonify, redirect, render_template, request,
                   session, url_for)
from markupsafe import Markup
from werkzeug.security import check_password_hash

import config
import db as dbm
import forecast as fc
import chatbots
import gemini

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024   # 5 MB photo limit


# ---------------------------------------------------------------- plumbing
def get_db():
    if "db" not in g:
        g.db = dbm.DB(dbm.connect())
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    d = g.pop("db", None)
    if d:
        d.close()


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "uid" not in session:
            return redirect(url_for("login", next=request.path))
        return f(*a, **kw)
    return wrapper


@app.template_filter("money")
def money(v):
    return Markup('<span class="cur">%s</span>%s' % (config.CURRENCY, format(round(float(v or 0)), ",")))


@app.template_filter("num")
def num(v, digits=0):
    return format(round(float(v or 0), digits), ",.%df" % digits)


@app.template_filter("fdate")
def fdate(v):
    if isinstance(v, str) and len(v) >= 10:
        try:
            v = datetime.fromisoformat(v[:10])
        except ValueError:
            return v
    if isinstance(v, datetime):
        return v.strftime("%d %b %Y")
    if isinstance(v, date):
        return v.strftime("%d %b %Y")
    return str(v or "")


@app.context_processor
def inject_globals():
    pending = 0
    if "uid" in session:
        pending = get_db().scalar("SELECT COUNT(*) FROM actions WHERE status='pending'")
    return {"currency": config.CURRENCY, "today": date.today(), "pending_count": pending,
            "user_name": session.get("name", "")}


# ---------------------------------------------------------------- product images
# An uploaded photo (static/uploads/p<id>.<ext>) wins; otherwise the illustration for the SKU
# (static/img/products/<SKU>.svg); otherwise None (templates fall back to the category icon).
UPLOAD_DIR = os.path.join(app.static_folder, "uploads")
ALLOWED_IMG = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def product_image(pid, sku=""):
    for ext in sorted(ALLOWED_IMG):
        if os.path.exists(os.path.join(UPLOAD_DIR, "p%s%s" % (pid, ext))):
            f = "uploads/p%s%s" % (pid, ext)
            return {"url": url_for("static", filename=f,
                                   v=int(os.path.getmtime(os.path.join(app.static_folder, f)))), "photo": True}
    art = "img/products/%s.svg" % sku
    if sku and os.path.exists(os.path.join(app.static_folder, art)):
        return {"url": url_for("static", filename=art), "photo": False}
    return None


app.jinja_env.globals["product_image"] = product_image


def save_product_photo(pid, file):
    """Store an uploaded photo as p<id>.<ext>, replacing any previous one. Returns an error string or None."""
    if not file or not file.filename:
        return None
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_IMG:
        return "Photo must be a JPG, PNG, WEBP or GIF image."
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    for e in ALLOWED_IMG:
        old = os.path.join(UPLOAD_DIR, "p%s%s" % (pid, e))
        if os.path.exists(old):
            os.remove(old)
    file.save(os.path.join(UPLOAD_DIR, "p%s%s" % (pid, ext)))
    return None


def today():
    return date.today()


def sweep_expired(db):
    """Anything past its expiry date is written off into the waste log."""
    rows = db.all("SELECT b.id, b.product_id, b.qty_remaining, p.unit_cost, p.kg_per_unit "
                  "FROM batches b JOIN products p ON p.id=b.product_id "
                  "WHERE b.qty_remaining>0 AND b.expires_on<%s", (today().isoformat(),))
    for r in rows:
        q = int(r["qty_remaining"])
        db.execute("INSERT INTO waste_log (product_id,batch_id,quantity,kg,cost_loss,reason,logged_on) "
                   "VALUES (%s,%s,%s,%s,%s,'expired',%s)",
                   (r["product_id"], r["id"], q, round(q * r["kg_per_unit"], 2),
                    round(q * r["unit_cost"], 2), today().isoformat()))
        db.execute("UPDATE batches SET qty_remaining=0 WHERE id=%s", (r["id"],))
        db.execute("UPDATE actions SET status='dismissed', resolved_at=%s WHERE batch_id=%s AND status='pending'",
                   (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), r["id"]))
    return len(rows)


def run_scan(db):
    """Re-score every batch and refresh pending recommendations."""
    sweep_expired(db)
    items = fc.load_assessments(db, today())
    created = 0
    for b in items:
        db.execute("DELETE FROM actions WHERE batch_id=%s AND status='pending'", (b["id"],))
        r = b["rec"]
        if r:
            db.execute("INSERT INTO actions (batch_id,action_type,discount_pct,qty_affected,urgency,rationale,est_value) "
                       "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                       (b["id"], r["action_type"], r["discount_pct"], r["qty_affected"], r["urgency"],
                        r["rationale"], r["est_value"]))
            created += 1
    db.commit()
    return created


# ---------------------------------------------------------------- auth
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = get_db().one("SELECT * FROM users WHERE username=%s", (request.form.get("username", "").strip(),))
        if u and check_password_hash(u["password_hash"], request.form.get("password", "")):
            session["uid"], session["name"] = u["id"], u["full_name"]
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Wrong username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------- dashboard
@app.route("/")
@login_required
def dashboard():
    db = get_db()
    swept = sweep_expired(db)
    if swept:
        flash("%d expired batch(es) were written off automatically." % swept, "warn")
    if db.scalar("SELECT COUNT(*) FROM actions WHERE status='pending'") == 0 and \
            db.scalar("SELECT COUNT(*) FROM actions") == 0:
        run_scan(db)

    items = fc.load_assessments(db, today())
    risky = [b for b in items if b["at_risk"] > 0]
    value_at_risk = sum(b["at_risk"] * b["unit_cost"] for b in risky)
    since30 = (today() - timedelta(days=30)).isoformat()

    cat = {}
    for b in risky:
        cat[b["category_name"]] = cat.get(b["category_name"], 0) + b["at_risk"] * b["unit_cost"]
    cat_labels = sorted(cat, key=cat.get, reverse=True)

    waste_rows = db.all("SELECT logged_on, cost_loss FROM waste_log WHERE logged_on>=%s",
                        ((today() - timedelta(days=56)).isoformat(),))
    weeks = [0.0] * 8
    for r in waste_rows:
        idx = 7 - (today() - r["logged_on"]).days // 7
        if 0 <= idx < 8:
            weeks[idx] += r["cost_loss"]

    sales_rows = db.all("SELECT sold_on, SUM(quantity*unit_price) AS rev FROM sales WHERE sold_on>=%s GROUP BY sold_on",
                        ((today() - timedelta(days=13)).isoformat(),))
    rev = {r["sold_on"]: r["rev"] for r in sales_rows}
    days14 = [today() - timedelta(days=13 - i) for i in range(14)]

    top = sorted(risky, key=lambda b: (b["days_left"], -b["at_risk"] * b["unit_cost"]))[:8]
    kpi = {
        "active_batches": len(items),
        "units_at_risk": sum(b["at_risk"] for b in risky),
        "value_at_risk": value_at_risk,
        "expiring_3d": len([b for b in items if b["days_left"] <= 3]),
        "waste_30d": db.scalar("SELECT SUM(cost_loss) FROM waste_log WHERE logged_on>=%s", (since30,)),
        "kg_donated_30d": db.scalar("SELECT SUM(kg) FROM donations WHERE donated_on>=%s", (since30,)),
    }
    return render_template(
        "dashboard.html", kpi=kpi, top=top,
        cat_labels=cat_labels, cat_values=[round(cat[k]) for k in cat_labels],
        week_labels=["W-%d" % (7 - i) if i < 7 else "This wk" for i in range(8)],
        week_values=[round(w) for w in weeks],
        sales_labels=[d.strftime("%d %b") for d in days14],
        sales_values=[round(rev.get(d, 0)) for d in days14])


# ---------------------------------------------------------------- Gemini AI insights
def build_ai_context(db):
    items = fc.load_assessments(db, today())
    risky = sorted([b for b in items if b["at_risk"] > 0],
                   key=lambda b: (b["days_left"], -b["at_risk"] * float(b["unit_cost"])))[:15]
    plan = [r for r in fc.reorder_plan(db, today()) if r["status"] != "ok"][:15]
    since30 = (today() - timedelta(days=30)).isoformat()
    return {
        "today": today().isoformat(),
        "totals": {"active_batches": len(items),
                   "units_at_risk": sum(b["at_risk"] for b in items),
                   "value_at_risk": round(sum(b["at_risk"] * float(b["unit_cost"]) for b in items)),
                   "waste_cost_30d": float(db.scalar("SELECT SUM(cost_loss) FROM waste_log WHERE logged_on>=%s", (since30,)) or 0),
                   "kg_donated_30d": float(db.scalar("SELECT SUM(kg) FROM donations WHERE donated_on>=%s", (since30,)) or 0)},
        "batches_at_risk": [{"product": b["product_name"], "category": b["category_name"], "batch": b["batch_code"],
                             "days_left": b["days_left"], "qty_remaining": b["qty_remaining"],
                             "forecast_sold": b["proj_sold"], "at_risk_units": b["at_risk"],
                             "current_discount_pct": float(b.get("discount_pct") or 0),
                             "engine_recommendation": (b["rec"] or {}).get("action_type"),
                             "engine_discount_pct": (b["rec"] or {}).get("discount_pct")} for b in risky],
        "reorder_plan": [{"product": r["name"], "status": r["status"], "stock": r["stock"],
                          "daily_demand": r["daily"], "days_cover": r["cover"],
                          "suggested_order": r["suggest"], "excess_units": r["excess"]} for r in plan],
    }


@app.route("/ai-insights", methods=["GET", "POST"])
@login_required
def ai_insights():
    result = error = None
    if request.method == "POST":
        result, error = gemini.analyze(build_ai_context(get_db()))
    return render_template("ai_insights.html", result=result, error=error, enabled=gemini.enabled(),
                           model=config.GEMINI_MODEL)


# ---------------------------------------------------------------- public shop (no login)
SHOP_SQL = (
    "SELECT b.id AS batch_id, b.batch_code, b.qty_remaining, b.expires_on, b.discount_pct, "
    "p.id, p.name, p.sku, p.unit, p.unit_price, p.kg_per_unit, p.shelf_life_days, c.name AS category_name "
    "FROM batches b JOIN products p ON p.id=b.product_id JOIN categories c ON c.id=p.category_id "
    "WHERE b.qty_remaining>0 AND p.active=1 AND b.expires_on>=%s ORDER BY b.expires_on, b.id")


def shop_catalog(db):
    """One entry per product, built only from lots that are in stock and not expired."""
    prods = {}
    for r in db.all(SHOP_SQL, (today().isoformat(),)):
        exp = r["expires_on"]
        if isinstance(exp, str):
            exp = date.fromisoformat(exp[:10])
        elif isinstance(exp, datetime):
            exp = exp.date()
        pct = float(r["discount_pct"] or 0)
        price = float(r["unit_price"])
        lot = {"code": r["batch_code"], "qty": int(r["qty_remaining"]), "expires": exp,
               "days_left": (exp - today()).days, "pct": pct, "price": round(price * (1 - pct / 100.0), 2)}
        p = prods.setdefault(r["id"], {
            "id": r["id"], "name": r["name"], "sku": r["sku"], "unit": r["unit"], "category": r["category_name"],
            "base": price, "kg": float(r["kg_per_unit"]), "shelf_life": r["shelf_life_days"], "lots": []})
        p["lots"].append(lot)
    out = []
    for p in prods.values():
        lots = p["lots"]
        p["qty"] = sum(l["qty"] for l in lots)
        p["price"] = min(l["price"] for l in lots)
        p["pct"] = max(l["pct"] for l in lots)
        p["expires"] = min(l["expires"] for l in lots)
        p["days_left"] = min(l["days_left"] for l in lots)
        p["kind"] = "deal" if p["pct"] > 0 else "fresh"
        p["save"] = round(p["base"] - p["price"], 2)
        out.append(p)
    return out


@app.route("/shop")
def shop():
    items = shop_catalog(get_db())
    cats = sorted({p["category"] for p in items})
    kind = request.args.get("type", "all")
    cat = request.args.get("category", "")
    q = request.args.get("q", "").strip().lower()
    sort = request.args.get("sort", "deals")
    counts = {"all": len(items), "deal": len([p for p in items if p["kind"] == "deal"]),
              "fresh": len([p for p in items if p["kind"] == "fresh"]),
              "last": len([p for p in items if p["days_left"] <= 1])}
    view = items
    if kind == "deal":
        view = [p for p in view if p["kind"] == "deal"]
    elif kind == "fresh":
        view = [p for p in view if p["kind"] == "fresh"]
    elif kind == "last":
        view = [p for p in view if p["days_left"] <= 1]
    if cat:
        view = [p for p in view if p["category"] == cat]
    if q:
        view = [p for p in view if q in p["name"].lower() or q in p["category"].lower()]
    keys = {"deals": lambda p: (-p["pct"], p["days_left"], p["name"]), "low": lambda p: (p["price"], p["name"]),
            "high": lambda p: (-p["price"], p["name"]), "expiry": lambda p: (p["days_left"], p["name"]),
            "name": lambda p: p["name"].lower()}
    view = sorted(view, key=keys.get(sort, keys["deals"]))
    deals = [p for p in items if p["pct"] > 0]
    stats = {"products": len(items), "deals": len(deals),
             "max_pct": int(max([p["pct"] for p in deals] or [0])),
             "kg": round(sum(l["qty"] * p["kg"] for p in deals for l in p["lots"] if l["pct"] > 0))}
    return render_template("shop.html", items=view, cats=cats, kind=kind, cat=cat, q=q, sort=sort,
                           counts=counts, stats=stats, shelf=sorted(items, key=lambda x: x["name"])[:16],
                           featured=(max(items, key=lambda x: (x["pct"], -x["days_left"])) if items and stats["deals"]
                                     else (min(items, key=lambda x: x["days_left"]) if items else None)))


@app.route("/shop/<int:pid>")
def shop_product(pid):
    items = shop_catalog(get_db())
    p = next((x for x in items if x["id"] == pid), None)
    if not p:
        return render_template("shop_missing.html"), 404
    related = [x for x in items if x["category"] == p["category"] and x["id"] != pid][:4]
    return render_template("shop_product.html", p=p, related=related,
                           co2=round(p["kg"] * config.CO2_PER_KG, 1))


# ---------------------------------------------------------------- chatbots
@app.route("/api/shop-chat", methods=["POST"])
def api_shop_chat():
    """Public customer assistant: prices / discounts / availability."""
    if not chatbots.rate_ok("shop:" + (request.remote_addr or "?")):
        return jsonify({"reply": "You're sending messages very quickly — please wait a moment and try again."}), 429
    hist = chatbots.clean_history((request.get_json(silent=True) or {}).get("messages"))
    if not hist or hist[-1]["role"] != "user":
        return jsonify({"reply": "Ask me about any product — for example \"price of milk\" or \"what's on discount?\""})
    catalog = shop_catalog(get_db())
    reply, err = gemini.chat(chatbots.shop_system(catalog, today()), hist)
    if err:
        reply = chatbots.shop_fallback(hist[-1]["text"], catalog)
    return jsonify({"reply": reply})


@app.route("/assistant")
@login_required
def assistant():
    return render_template("assistant.html", enabled=gemini.enabled())


@app.route("/api/admin-chat", methods=["POST"])
@login_required
def api_admin_chat():
    hist = chatbots.clean_history((request.get_json(silent=True) or {}).get("messages"), max_len=800)
    if not hist or hist[-1]["role"] != "user":
        return jsonify({"reply": "Ask me about stock, expiring batches, sales, waste or what to reorder."})
    ctx = chatbots.admin_context(get_db(), today(), fc)
    reply, err = gemini.chat(chatbots.admin_system(ctx), hist)
    if err:
        reply = chatbots.admin_fallback(ctx)
    return jsonify({"reply": reply})


# ---------------------------------------------------------------- inventory
@app.route("/inventory")
@login_required
def inventory():
    db = get_db()
    sweep_expired(db)
    items = fc.load_assessments(db, today())
    q = request.args.get("q", "").strip().lower()
    cat = request.args.get("category", "")
    risk = request.args.get("risk", "")
    if q:
        items = [b for b in items if q in b["product_name"].lower() or q in b["batch_code"].lower()]
    if cat:
        items = [b for b in items if b["category_name"] == cat]
    if risk == "at_risk":
        items = [b for b in items if b["at_risk"] > 0]
    elif risk == "expiring":
        items = [b for b in items if b["days_left"] <= 3]
    cats = [r["name"] for r in db.all("SELECT name FROM categories ORDER BY name")]
    return render_template("inventory.html", items=items, cats=cats, q=q, cat=cat, risk=risk)


@app.route("/batches/new", methods=["GET", "POST"])
@login_required
def batch_new():
    db = get_db()
    products = db.all("SELECT id, name, unit, shelf_life_days FROM products WHERE active=1 ORDER BY name")
    if request.method == "POST":
        try:
            pid = int(request.form["product_id"])
            qty = int(request.form["quantity"])
            received = date.fromisoformat(request.form["received_on"])
            expires = date.fromisoformat(request.form["expires_on"])
            assert qty > 0 and expires >= received
        except Exception:
            flash("Please check the form: quantity must be positive and expiry after delivery date.", "error")
            return render_template("batch_form.html", products=products, form=request.form), 400
        code = "B%s-%02d%03d" % (received.strftime("%y%m%d"), pid, random.randint(0, 999))
        db.execute("INSERT INTO batches (product_id,batch_code,qty_received,qty_remaining,received_on,expires_on) "
                   "VALUES (%s,%s,%s,%s,%s,%s)", (pid, code, qty, qty, received.isoformat(), expires.isoformat()))
        db.commit()
        run_scan(db)
        flash("Batch %s received and risk re-scored." % code, "ok")
        return redirect(url_for("inventory"))
    return render_template("batch_form.html", products=products, form={})


# ---------------------------------------------------------------- products
@app.route("/products")
@login_required
def products():
    rows = get_db().all(
        "SELECT p.*, c.name AS category_name, "
        "(SELECT COALESCE(SUM(qty_remaining),0) FROM batches b WHERE b.product_id=p.id) AS stock "
        "FROM products p JOIN categories c ON c.id=p.category_id ORDER BY c.name, p.name")
    return render_template("products.html", rows=rows)


def _product_form(pid=None):
    db = get_db()
    cats = db.all("SELECT * FROM categories ORDER BY name")
    row = db.one("SELECT * FROM products WHERE id=%s", (pid,)) if pid else None
    if request.method == "POST":
        f = request.form
        try:
            vals = (f["sku"].strip(), f["name"].strip(), int(f["category_id"]), f["unit"].strip() or "pc",
                    float(f["unit_cost"]), float(f["unit_price"]), float(f["kg_per_unit"]),
                    int(f["shelf_life_days"]), 1 if f.get("active") else 0)
            assert vals[0] and vals[1] and vals[7] > 0
        except Exception:
            flash("Please fill every field with valid values.", "error")
            return render_template("product_form.html", cats=cats, row=f, pid=pid), 400
        try:
            if pid:
                db.execute("UPDATE products SET sku=%s,name=%s,category_id=%s,unit=%s,unit_cost=%s,unit_price=%s,"
                           "kg_per_unit=%s,shelf_life_days=%s,active=%s WHERE id=%s", vals + (pid,))
            else:
                db.execute("INSERT INTO products (sku,name,category_id,unit,unit_cost,unit_price,kg_per_unit,"
                           "shelf_life_days,active) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", vals)
            db.commit()
            new_id = pid or db.scalar("SELECT id FROM products WHERE sku=%s", (vals[0],))
        except Exception:
            flash("That SKU already exists.", "error")
            return render_template("product_form.html", cats=cats, row=f, pid=pid), 400
        err = save_product_photo(new_id, request.files.get("photo"))
        flash(err or "Product saved.", "error" if err else "ok")
        return redirect(url_for("products"))
    return render_template("product_form.html", cats=cats, row=row or {"active": 1, "unit": "pc", "kg_per_unit": 0.5,
                                                                      "shelf_life_days": 7}, pid=pid)


@app.route("/products/new", methods=["GET", "POST"])
@login_required
def product_new():
    return _product_form()


@app.route("/products/<int:pid>/edit", methods=["GET", "POST"])
@login_required
def product_edit(pid):
    return _product_form(pid)


# ---------------------------------------------------------------- sales (FIFO)
@app.route("/sales", methods=["GET", "POST"])
@login_required
def sales():
    db = get_db()
    if request.method == "POST":
        try:
            pid = int(request.form["product_id"])
            qty = int(request.form["quantity"])
            sold_on = date.fromisoformat(request.form["sold_on"])
            assert qty > 0
        except Exception:
            flash("Enter a valid product, quantity and date.", "error")
            return redirect(url_for("sales"))
        batches = db.all("SELECT * FROM batches WHERE product_id=%s AND qty_remaining>0 AND expires_on>=%s "
                         "ORDER BY expires_on, id", (pid, sold_on.isoformat()))
        if sum(b["qty_remaining"] for b in batches) < qty:
            flash("Not enough sellable stock for that quantity.", "error")
            return redirect(url_for("sales"))
        price = db.scalar("SELECT unit_price FROM products WHERE id=%s", (pid,))
        left = qty
        for b in batches:                     # sell oldest-expiry first
            take = min(left, b["qty_remaining"])
            pct = b["discount_pct"] or 0
            db.execute("INSERT INTO sales (product_id,batch_id,quantity,unit_price,discount_pct,sold_on) "
                       "VALUES (%s,%s,%s,%s,%s,%s)",
                       (pid, b["id"], take, round(price * (1 - pct / 100.0), 2), pct, sold_on.isoformat()))
            db.execute("UPDATE batches SET qty_remaining=qty_remaining-%s WHERE id=%s", (take, b["id"]))
            left -= take
            if left == 0:
                break
        db.commit()
        flash("Sale recorded (FIFO by expiry date).", "ok")
        return redirect(url_for("sales"))
    products = db.all("SELECT id, name, unit_price FROM products WHERE active=1 ORDER BY name")
    history = db.all("SELECT s.*, p.name AS product_name FROM sales s JOIN products p ON p.id=s.product_id "
                     "ORDER BY s.sold_on DESC, s.id DESC LIMIT 30")
    return render_template("sales.html", products=products, history=history)


# ---------------------------------------------------------------- AI recommendations
@app.route("/recommendations")
@login_required
def recommendations():
    db = get_db()
    pending = db.all(
        "SELECT a.*, b.batch_code, b.expires_on, b.qty_remaining, p.name AS product_name, p.unit, p.unit_price, "
        "c.name AS category_name "
        "FROM actions a JOIN batches b ON b.id=a.batch_id JOIN products p ON p.id=b.product_id "
        "JOIN categories c ON c.id=p.category_id "
        "WHERE a.status='pending' "
        "ORDER BY CASE a.urgency WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END, a.est_value DESC")
    history = db.all(
        "SELECT a.*, b.batch_code, p.name AS product_name FROM actions a JOIN batches b ON b.id=a.batch_id "
        "JOIN products p ON p.id=b.product_id WHERE a.status<>'pending' ORDER BY a.resolved_at DESC, a.id DESC LIMIT 15")
    return render_template("recommendations.html", pending=pending, history=history)


@app.route("/scan", methods=["POST"])
@login_required
def scan():
    n = run_scan(get_db())
    flash("AI scan complete: %d recommendation(s) generated." % n, "ok")
    return redirect(url_for("recommendations"))


@app.route("/recommendations/<int:aid>/<verb>", methods=["POST"])
@login_required
def resolve_action(aid, verb):
    db = get_db()
    a = db.one("SELECT * FROM actions WHERE id=%s AND status='pending'", (aid,))
    if not a:
        flash("That recommendation is no longer pending.", "warn")
        return redirect(url_for("recommendations"))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if verb == "dismiss":
        db.execute("UPDATE actions SET status='dismissed', resolved_at=%s WHERE id=%s", (now, aid))
        db.commit()
        flash("Recommendation dismissed.", "ok")
    elif verb == "apply" and a["action_type"] in ("discount", "markdown"):
        db.execute("UPDATE batches SET discount_pct=%s WHERE id=%s", (a["discount_pct"], a["batch_id"]))
        db.execute("UPDATE actions SET status='applied', resolved_at=%s WHERE id=%s", (now, aid))
        db.commit()
        run_scan(db)
        flash("%d%% markdown applied. New sales of this batch use the lower price." % a["discount_pct"], "ok")
    elif verb == "apply" and a["action_type"] == "donate":
        return redirect(url_for("donation_new", batch_id=a["batch_id"], qty=a["qty_affected"], action_id=aid))
    return redirect(url_for("recommendations"))


# ---------------------------------------------------------------- donations
@app.route("/donations")
@login_required
def donations():
    db = get_db()
    rows = db.all("SELECT d.*, p.name AS product_name, pr.name AS partner_name FROM donations d "
                  "JOIN products p ON p.id=d.product_id JOIN partners pr ON pr.id=d.partner_id "
                  "ORDER BY d.donated_on DESC, d.id DESC LIMIT 40")
    partners = db.all("SELECT pr.*, (SELECT COALESCE(SUM(meals),0) FROM donations d WHERE d.partner_id=pr.id) AS meals "
                      "FROM partners pr ORDER BY pr.name")
    return render_template("donations.html", rows=rows, partners=partners)


@app.route("/donations/new", methods=["GET", "POST"])
@login_required
def donation_new():
    db = get_db()
    batches = db.all("SELECT b.id, b.batch_code, b.qty_remaining, b.expires_on, p.name AS product_name, p.kg_per_unit, "
                     "p.unit FROM batches b JOIN products p ON p.id=b.product_id WHERE b.qty_remaining>0 "
                     "AND b.expires_on>=%s ORDER BY b.expires_on", (today().isoformat(),))
    partners = db.all("SELECT * FROM partners ORDER BY name")
    if request.method == "POST":
        try:
            bid, part, qty = int(request.form["batch_id"]), int(request.form["partner_id"]), int(request.form["quantity"])
            on = date.fromisoformat(request.form["donated_on"])
            b = db.one("SELECT b.*, p.kg_per_unit FROM batches b JOIN products p ON p.id=b.product_id WHERE b.id=%s", (bid,))
            assert b and 0 < qty <= b["qty_remaining"]
        except Exception:
            flash("Check the batch, partner and quantity (cannot exceed remaining stock).", "error")
            return redirect(url_for("donation_new"))
        kg = round(qty * b["kg_per_unit"], 2)
        db.execute("INSERT INTO donations (product_id,batch_id,partner_id,quantity,kg,meals,donated_on) "
                   "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                   (b["product_id"], bid, part, qty, kg, math.ceil(kg / config.KG_PER_MEAL), on.isoformat()))
        db.execute("UPDATE batches SET qty_remaining=qty_remaining-%s WHERE id=%s", (qty, bid))
        aid = request.form.get("action_id")
        if aid:
            db.execute("UPDATE actions SET status='applied', resolved_at=%s WHERE id=%s",
                       (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), int(aid)))
        db.commit()
        run_scan(db)
        flash("Donation logged: %s kg, about %d meals." % (kg, math.ceil(kg / config.KG_PER_MEAL)), "ok")
        return redirect(url_for("donations"))
    return render_template("donation_form.html", batches=batches, partners=partners,
                           sel_batch=request.args.get("batch_id", type=int), qty=request.args.get("qty", ""),
                           action_id=request.args.get("action_id", ""))


@app.route("/partners/new", methods=["POST"])
@login_required
def partner_new():
    f = request.form
    if f.get("name", "").strip():
        get_db().execute("INSERT INTO partners (name,kind,area,phone) VALUES (%s,%s,%s,%s)",
                         (f["name"].strip(), f.get("kind", "charity"), f.get("area", ""), f.get("phone", "")))
        get_db().commit()
        flash("Partner added.", "ok")
    return redirect(url_for("donations"))


# ---------------------------------------------------------------- impact report
@app.route("/impact")
@login_required
def impact():
    db = get_db()
    t = today()
    d30, d60 = (t - timedelta(days=30)).isoformat(), (t - timedelta(days=60)).isoformat()
    waste_now = db.scalar("SELECT SUM(cost_loss) FROM waste_log WHERE logged_on>=%s", (d30,))
    waste_prev = db.scalar("SELECT SUM(cost_loss) FROM waste_log WHERE logged_on>=%s AND logged_on<%s", (d60, d30))
    kg_wasted = db.scalar("SELECT SUM(kg) FROM waste_log WHERE logged_on>=%s", (d30,))
    don = db.one("SELECT COALESCE(SUM(kg),0) AS kg, COALESCE(SUM(meals),0) AS meals, COUNT(*) AS n FROM donations "
                 "WHERE donated_on>=%s", (d30,))
    disc = db.one("SELECT COALESCE(SUM(quantity),0) AS units, COALESCE(SUM(quantity*unit_price),0) AS rev FROM sales "
                  "WHERE discount_pct>0 AND sold_on>=%s", (d30,))
    top_waste = db.all("SELECT p.name, SUM(w.cost_loss) AS loss, SUM(w.kg) AS kg FROM waste_log w "
                       "JOIN products p ON p.id=w.product_id WHERE w.logged_on>=%s GROUP BY p.id, p.name "
                       "ORDER BY loss DESC LIMIT 6", (d30,))
    by_cat = db.all("SELECT c.name, SUM(w.cost_loss) AS loss FROM waste_log w JOIN products p ON p.id=w.product_id "
                    "JOIN categories c ON c.id=p.category_id WHERE w.logged_on>=%s GROUP BY c.name ORDER BY loss DESC", (d30,))
    kg_saved = don["kg"]
    change = None if not waste_prev else round((waste_now - waste_prev) / waste_prev * 100)
    return render_template("impact.html", waste_now=waste_now, waste_prev=waste_prev, change=change,
                           kg_wasted=kg_wasted, don=don, disc=disc, top_waste=top_waste, by_cat=by_cat,
                           co2=round(kg_saved * config.CO2_PER_KG, 1))


# ---------------------------------------------------------------- forecast + what-if
@app.route("/forecast/<int:pid>")
@login_required
def forecast_page(pid):
    db = get_db()
    p = db.one("SELECT p.*, c.name AS category_name FROM products p JOIN categories c ON c.id=p.category_id "
               "WHERE p.id=%s", (pid,))
    if not p:
        return redirect(url_for("inventory"))
    prof = fc.demand_profile(db, pid, today())
    horizon = max(7, min(14, p["shelf_life_days"]))
    hist = [(d.strftime("%d %b"), round(q, 1)) for d, q in prof["history"]]
    fut = [((today() + timedelta(days=i)), round(fc.day_forecast(prof, today() + timedelta(days=i)), 1))
           for i in range(horizon)]
    batches = [b for b in fc.load_assessments(db, today(), pid)]
    return render_template("forecast.html", p=p, prof=prof, batches=batches,
                           labels=[h[0] for h in hist] + [d.strftime("%d %b") for d, _ in fut],
                           hist=[h[1] for h in hist] + [None] * horizon,
                           pred=[None] * (len(hist) - 1) + [hist[-1][1]] + [v for _, v in fut][:horizon],
                           weekdays=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                           factors=[round(f, 2) for f in prof["factors"]])


@app.route("/api/whatif")
@login_required
def api_whatif():
    db = get_db()
    bid = request.args.get("batch_id", type=int)
    pct = max(0.0, min(80.0, request.args.get("pct", 0, type=float)))
    b = db.one("SELECT product_id FROM batches WHERE id=%s", (bid,))
    if not b:
        return jsonify({"error": "batch not found"}), 404
    rows = [x for x in fc.load_assessments(db, today(), b["product_id"])]
    batches = db.all("SELECT * FROM batches WHERE product_id=%s AND qty_remaining>0", (b["product_id"],))
    prof = fc.demand_profile(db, b["product_id"], today())
    res = fc.assess_batches(batches, prof, today(), overrides={bid: pct})[bid]
    rem = next(x["qty_remaining"] for x in batches if x["id"] == bid)
    return jsonify({"proj_sold": res["proj_sold"], "at_risk": res["at_risk"], "remaining": rem,
                    "clear_pct": round(100 * res["proj_sold"] / rem) if rem else 0})


# ---------------------------------------------------------------- bulk actions, write-off, reorder
@app.route("/recommendations/apply-discounts", methods=["POST"])
@login_required
def apply_all_discounts():
    db = get_db()
    rows = db.all("SELECT * FROM actions WHERE status='pending' AND action_type IN ('discount','markdown')")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for a in rows:
        db.execute("UPDATE batches SET discount_pct=%s WHERE id=%s", (a["discount_pct"], a["batch_id"]))
        db.execute("UPDATE actions SET status='applied', resolved_at=%s WHERE id=%s", (now, a["id"]))
    db.commit()
    run_scan(db)
    flash("%d markdown(s) applied in one go." % len(rows), "ok")
    return redirect(url_for("recommendations"))


@app.route("/batches/<int:bid>/writeoff", methods=["POST"])
@login_required
def batch_writeoff(bid):
    db = get_db()
    b = db.one("SELECT b.*, p.unit_cost, p.kg_per_unit FROM batches b JOIN products p ON p.id=b.product_id WHERE b.id=%s", (bid,))
    if b and b["qty_remaining"] > 0:
        q = int(b["qty_remaining"])
        db.execute("INSERT INTO waste_log (product_id,batch_id,quantity,kg,cost_loss,reason,logged_on) VALUES (%s,%s,%s,%s,%s,'damaged',%s)",
                   (b["product_id"], bid, q, round(q * b["kg_per_unit"], 2), round(q * b["unit_cost"], 2), today().isoformat()))
        db.execute("UPDATE batches SET qty_remaining=0 WHERE id=%s", (bid,))
        db.execute("UPDATE actions SET status='dismissed', resolved_at=%s WHERE batch_id=%s AND status='pending'",
                   (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), bid))
        db.commit()
        flash("Batch %s written off (%d units)." % (b["batch_code"], q), "warn")
    return redirect(url_for("inventory"))


@app.route("/reorder")
@login_required
def reorder():
    plan = fc.reorder_plan(get_db(), today())
    kpi = {"to_order": len([r for r in plan if r["status"] in ("out", "reorder")]),
           "order_cost": sum(r["order_cost"] for r in plan),
           "over": len([r for r in plan if r["status"] == "overstock"]),
           "out": len([r for r in plan if r["status"] == "out"])}
    cats = sorted({r["category_name"] for r in plan})
    return render_template("reorder.html", plan=plan, kpi=kpi, cats=cats)


if __name__ == "__main__":
    import os
    import setup_db
    # Flask's reloader starts the script twice; only set up in the first (parent) process.
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true" and not setup_db.database_ready():
        print("First run: creating database '%s' with demo data ..." % config.MYSQL_DB)
        setup_db.main(empty=False)
    app.run(debug=True, host="127.0.0.1", port=5000)
