"""The "AI" core of FoodWasteZero: demand forecasting + expiry-risk + action recommendation.

How it works (all explainable, no black box):
1. Baseline demand per product = recent average daily sales (discount-normalised),
   shaped by a smoothed day-of-week pattern learned from the last 28 days.
2. For each batch (earliest expiry first, FIFO) we forecast how many units can still be
   sold before the expiry date. Units that cannot be sold are "at risk".
3. A price-elasticity model (each 1% discount lifts demand ~4%) tells us what discount
   would clear the batch. If the discount needed is too deep, we recommend donation
   (or a final markdown for non-donatable items such as raw meat/fish).
"""
import math
from datetime import timedelta

import config

E = config.DEMAND_ELASTICITY
MAX_DISCOUNT = 30   # deepest "normal" markdown (%); beyond this the AI suggests donation / final markdown


def mult(pct):
    """Demand multiplier produced by a discount of `pct` percent."""
    return 1.0 + E * float(pct or 0)


# ------------------------------------------------------------------ demand profile
def demand_profile(db, product_id, today, window=28):
    start = today - timedelta(days=window)
    rows = db.all(
        "SELECT sold_on, SUM(quantity / (1 + %s * discount_pct)) AS q FROM sales "
        "WHERE product_id=%s AND sold_on>=%s AND sold_on<%s GROUP BY sold_on",
        (E, product_id, start.isoformat(), today.isoformat()))
    by_day = {r["sold_on"]: float(r["q"]) for r in rows}
    series = [(start + timedelta(days=i), by_day.get(start + timedelta(days=i), 0.0)) for i in range(window)]

    recent = [q for _, q in series[-14:]]
    base = sum(recent) / len(recent) if recent else 0.0
    overall = sum(q for _, q in series) / window if window else 0.0

    factors = []
    for wd in range(7):
        vals = [q for d, q in series if d.weekday() == wd]
        raw = (sum(vals) / len(vals)) / overall if vals and overall > 0 else 1.0
        raw = min(1.8, max(0.5, raw))
        factors.append(0.5 * raw + 0.5)          # shrink towards 1.0 to avoid over-fitting
    return {"base": base, "factors": factors, "history": series}


def day_forecast(prof, d):
    return prof["base"] * prof["factors"][d.weekday()]


def cum_forecast(prof, today, upto):
    """Expected base-price demand from now until `upto` (inclusive); today counts half."""
    total, d = 0.0, today
    while d <= upto:
        total += day_forecast(prof, d) * (0.5 if d == today else 1.0)
        d += timedelta(days=1)
    return total


# ------------------------------------------------------------------ batch assessment
def assess_batches(batches, prof, today, overrides=None):
    """batches: list of dicts for ONE product. overrides: {batch_id: discount_pct} for what-if.
    Returns {batch_id: assessment}."""
    overrides = overrides or {}
    consumed = 0.0
    result = {}
    for b in sorted(batches, key=lambda x: (x["expires_on"], x["id"])):
        pct = overrides.get(b["id"], b.get("discount_pct") or 0)
        m = mult(pct)
        rem = int(b["qty_remaining"])
        days_left = (b["expires_on"] - today).days
        if days_left < 0:
            avail, sold = 0.0, 0.0
        else:
            avail = max(0.0, cum_forecast(prof, today, b["expires_on"]) - consumed)
            sold = min(float(rem), avail * m)
            consumed += sold / m
        at_risk = max(0.0, rem - sold)
        if rem <= 0 or avail <= 0:
            pct_needed = None
        else:
            need = rem / avail
            pct_needed = 0.0 if need <= 1 else (need - 1) / E
        result[b["id"]] = {
            "days_left": days_left,
            "proj_sold": round(sold, 1),
            "at_risk": int(math.floor(at_risk + 0.5)),
            "risk_ratio": round(at_risk / rem, 3) if rem else 0.0,
            "avail": avail,
            "pct_needed": pct_needed,
        }
    return result


def recommend(b, a):
    """b: batch row joined with product/category. a: its assessment. Returns dict or None."""
    units = a["at_risk"]
    if units < 1 or a["days_left"] < 0:
        return None
    days_left = a["days_left"]
    pn = a["pct_needed"]
    price, kg = float(b["unit_price"]), float(b["kg_per_unit"])
    rem = int(b["qty_remaining"])
    urgency = "critical" if days_left <= 1 else "high" if days_left <= 3 else "medium"
    why = ("Forecast sells ~%.0f of %d units before expiry (%d day%s left); %d at risk."
           % (a["proj_sold"], rem, days_left, "" if days_left == 1 else "s", units))

    if pn is not None and pn <= MAX_DISCOUNT:
        pct = max(10, int(math.ceil(pn / 5.0) * 5))
        value = units * price * (1 - pct / 100.0)
        return {"action_type": "discount", "discount_pct": pct, "qty_affected": units, "urgency": urgency,
                "rationale": why + " A %d%% markdown should clear the batch." % pct, "est_value": round(value, 2)}
    if b["donatable"]:
        meals = math.ceil(units * kg / config.KG_PER_MEAL)
        return {"action_type": "donate", "discount_pct": 0, "qty_affected": units, "urgency": urgency,
                "rationale": why + " Discount alone is not enough: donate ~%d meals." % meals,
                "est_value": round(units * float(b["unit_cost"]), 2)}
    value = units * price * 0.4
    return {"action_type": "markdown", "discount_pct": 60, "qty_affected": units, "urgency": urgency,
            "rationale": why + " Not donatable: apply a 60% final markdown.", "est_value": round(value, 2)}


# ------------------------------------------------------------------ whole-store scan
BATCH_SQL = (
    "SELECT b.*, p.name AS product_name, p.sku, p.unit, p.unit_cost, p.unit_price, p.kg_per_unit, "
    "c.name AS category_name, c.donatable "
    "FROM batches b JOIN products p ON p.id=b.product_id JOIN categories c ON c.id=p.category_id "
    "WHERE b.qty_remaining>0 AND p.active=1")


def load_assessments(db, today, product_id=None):
    sql, params = BATCH_SQL, []
    if product_id:
        sql += " AND p.id=%s"
        params.append(product_id)
    rows = db.all(sql + " ORDER BY b.expires_on, b.id", params)
    by_product = {}
    for r in rows:
        by_product.setdefault(r["product_id"], []).append(r)
    out = []
    for pid, batches in by_product.items():
        prof = demand_profile(db, pid, today)
        res = assess_batches(batches, prof, today)
        for b in batches:
            a = res[b["id"]]
            b.update(a)
            b["rec"] = recommend(b, a)
            out.append(b)
    out.sort(key=lambda x: (x["days_left"], -x["at_risk"]))
    return out


# ------------------------------------------------------------------ smart reorder
def reorder_plan(db, today):
    """For every active product: how much stock do we need, and should we order more or hold off?"""
    products = db.all("SELECT p.*, c.name AS category_name FROM products p JOIN categories c ON c.id=p.category_id "
                      "WHERE p.active=1 ORDER BY p.name")
    stock = {r["product_id"]: int(r["q"]) for r in db.all(
        "SELECT product_id, SUM(qty_remaining) AS q FROM batches WHERE qty_remaining>0 AND expires_on>=%s "
        "GROUP BY product_id", (today.isoformat(),))}
    out = []
    for p in products:
        prof = demand_profile(db, p["id"], today)
        horizon = max(3, min(7, p["shelf_life_days"]))          # how far ahead we plan an order
        life = min(p["shelf_life_days"], 30)                    # how much stock can ever be sold in time
        need = sum(day_forecast(prof, today + timedelta(days=i)) for i in range(horizon))
        cap = sum(day_forecast(prof, today + timedelta(days=i)) for i in range(life))
        have = stock.get(p["id"], 0)
        suggest = max(0, int(math.ceil(need * config.REORDER_BUFFER - have))) if have < need else 0   # only reorder when stock will run short
        base = prof["base"]
        cover = round(have / base, 1) if base > 0 else None
        if have == 0 and base > 0:
            status = "out"
        elif suggest > 0:
            status = "reorder"
        elif have > cap * 1.3 and have - cap > 3:
            status = "overstock"
        else:
            status = "ok"
        out.append({"id": p["id"], "name": p["name"], "sku": p["sku"], "category_name": p["category_name"], "unit": p["unit"],
                    "stock": have, "daily": round(base, 1), "cover": cover, "horizon": horizon, "need": int(round(need)),
                    "suggest": suggest, "order_cost": round(suggest * float(p["unit_cost"]), 2), "status": status,
                    "excess": max(0, int(have - cap)) if status == "overstock" else 0})
    order = {"out": 0, "reorder": 1, "overstock": 2, "ok": 3}
    out.sort(key=lambda r: (order[r["status"]], -r["order_cost"]))
    return out
