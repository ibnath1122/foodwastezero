"""Demo data: 7 categories, 24 products, 45 days of sales history, live batches
(some deliberately overstocked so the AI has something to catch), donation partners
and a few weeks of waste/donation history for the charts.
"""
import math
import random
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

CATEGORIES = [
    ("Bakery", 1), ("Dairy", 1), ("Fresh Produce", 1), ("Meat & Fish", 0),
    ("Ready Meals", 1), ("Beverages", 1), ("Packaged Foods", 1),
]

# name, sku, category, unit, cost, price, kg/unit, shelf-life days, avg daily demand
PRODUCTS = [
    ("Sandwich Bread", "BAK-001", "Bakery", "loaf", 45, 65, 0.40, 4, 22),
    ("Pau Bun (6 pack)", "BAK-002", "Bakery", "pack", 30, 48, 0.30, 3, 14),
    ("Chocolate Muffin", "BAK-003", "Bakery", "pc", 22, 40, 0.12, 3, 16),
    ("Pasteurized Milk 1L", "DAI-001", "Dairy", "pc", 88, 110, 1.03, 6, 30),
    ("Sweet Yogurt (Doi) 500g", "DAI-002", "Dairy", "cup", 70, 105, 0.50, 7, 12),
    ("Eggs (dozen)", "DAI-003", "Dairy", "dozen", 125, 160, 0.70, 14, 18),
    ("Paneer Block 200g", "DAI-004", "Dairy", "pc", 95, 140, 0.20, 9, 6),
    ("Bananas (dozen)", "PRO-001", "Fresh Produce", "dozen", 45, 75, 1.20, 4, 15),
    ("Tomato 1kg", "PRO-002", "Fresh Produce", "kg", 40, 65, 1.00, 5, 20),
    ("Spinach (Palong) bunch", "PRO-003", "Fresh Produce", "bunch", 12, 25, 0.25, 3, 26),
    ("Green Chili 250g", "PRO-004", "Fresh Produce", "pack", 15, 30, 0.25, 5, 12),
    ("Broiler Chicken 1kg", "MEA-001", "Meat & Fish", "kg", 210, 280, 1.00, 3, 16),
    ("Rui Fish 1kg", "MEA-002", "Meat & Fish", "kg", 300, 390, 1.00, 2, 8),
    ("Beef Mince 500g", "MEA-003", "Meat & Fish", "pack", 330, 420, 0.50, 3, 6),
    ("Chicken Biryani Box", "RDY-001", "Ready Meals", "box", 120, 220, 0.45, 2, 20),
    ("Vegetable Samosa (6)", "RDY-002", "Ready Meals", "pack", 35, 70, 0.30, 2, 17),
    ("Paratha Pack (5)", "RDY-003", "Ready Meals", "pack", 55, 85, 0.40, 10, 14),
    ("Fresh Orange Juice 1L", "BEV-001", "Beverages", "bottle", 95, 160, 1.05, 5, 11),
    ("Lassi 250ml", "BEV-002", "Beverages", "bottle", 28, 50, 0.27, 8, 18),
    ("Mango Juice 1L", "BEV-003", "Beverages", "bottle", 70, 110, 1.05, 30, 9),
    ("Instant Noodles (4 pack)", "PKG-001", "Packaged Foods", "pack", 60, 85, 0.30, 90, 10),
    ("Biscuit Family Pack", "PKG-002", "Packaged Foods", "pack", 40, 60, 0.35, 120, 12),
    ("Cornflakes 500g", "PKG-003", "Packaged Foods", "box", 270, 340, 0.50, 150, 4),
    ("Chicken Soup Cup", "RDY-004", "Ready Meals", "cup", 45, 80, 0.30, 5, 7),
]

PARTNERS = [
    ("Ashulia Community Kitchen (demo)", "charity", "Ashulia", "01700-000001"),
    ("Dhaka Food Bank (demo)", "food_bank", "Dhaka", "01700-000002"),
    ("Mirpur Shelter Home (demo)", "shelter", "Mirpur", "01700-000003"),
    ("Savar Compost & Feed Farm (demo)", "compost", "Savar", "01700-000004"),
]


def seed(db, today=None):
    today = today or date.today()
    rnd = random.Random(2026)
    iso = lambda d: d.isoformat()

    db.execute("INSERT INTO users (username, password_hash, full_name) VALUES (%s,%s,%s)",
               ("admin", generate_password_hash("admin123"), "Store Manager"))

    cat_ids = {}
    for name, donatable in CATEGORIES:
        cat_ids[name] = db.execute("INSERT INTO categories (name, donatable) VALUES (%s,%s)", (name, donatable))

    for name, kind, area, phone in PARTNERS:
        db.execute("INSERT INTO partners (name, kind, area, phone) VALUES (%s,%s,%s,%s)", (name, kind, area, phone))

    product_ids = []
    for name, sku, cat, unit, cost, price, kg, life, demand in PRODUCTS:
        pid = db.execute(
            "INSERT INTO products (sku, name, category_id, unit, unit_cost, unit_price, kg_per_unit, shelf_life_days)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (sku, name, cat_ids[cat], unit, cost, price, kg, life))
        product_ids.append((pid, name, cost, price, kg, life, demand))

    # ---- 45 days of sales history (Fri/Sat are busier) ----
    weekday_boost = {0: 0.9, 1: 0.85, 2: 0.9, 3: 1.0, 4: 1.3, 5: 1.35, 6: 1.1}
    for pid, name, cost, price, kg, life, demand in product_ids:
        for back in range(45, 0, -1):
            d = today - timedelta(days=back)
            promo = rnd.random() < 0.08
            pct = 20 if promo else 0
            lam = demand * weekday_boost[d.weekday()] * (1 + 0.04 * pct) * rnd.uniform(0.75, 1.25)
            qty = max(0, int(round(lam)))
            if qty:
                db.execute("INSERT INTO sales (product_id, batch_id, quantity, unit_price, discount_pct, sold_on)"
                           " VALUES (%s,NULL,%s,%s,%s,%s)", (pid, qty, round(price * (1 - pct / 100), 2), pct, iso(d)))

    # ---- live batches: a mix of healthy stock and overstock that will not sell in time ----
    n = 0
    for pid, name, cost, price, kg, life, demand in product_ids:
        n += 1
        scenario = rnd.choices(["healthy", "overstock", "two"], weights=[45, 35, 20])[0]
        specs = []
        if scenario == "healthy":
            age = rnd.randint(0, max(0, life // 3))
            specs.append((age, int(demand * rnd.uniform(0.9, 1.0) * max(2, life - age))))
        elif scenario == "overstock":
            age = rnd.randint(max(0, life // 2 - 1), max(1, life - 2))
            left = max(1, life - age)
            specs.append((age, int(demand * rnd.uniform(1.8, 3.2) * left) + 4))
        else:
            specs.append((life - 1 if life > 1 else 0, int(demand * rnd.uniform(0.8, 1.6))))
            specs.append((0, int(demand * rnd.uniform(0.7, 1.0) * life)))
        for age, qty in specs:
            qty = max(qty, 6)
            received = today - timedelta(days=age)
            expires = received + timedelta(days=life)
            if expires < today:
                expires = today
            sold_share = rnd.uniform(0.05, 0.3) if age else 0
            remaining = max(3, int(qty * (1 - sold_share)))
            db.execute(
                "INSERT INTO batches (product_id, batch_code, qty_received, qty_remaining, received_on, expires_on)"
                " VALUES (%s,%s,%s,%s,%s,%s)",
                (pid, f"B{received:%y%m%d}-{pid:02d}{n % 10}", qty, remaining, iso(received), iso(expires)))

    # ---- past waste + donations so the report charts have history ----
    pcount = len(PARTNERS)
    for week in range(8, 0, -1):
        for _ in range(rnd.randint(2, 4)):
            pid, name, cost, price, kg, life, demand = rnd.choice(product_ids)
            d = today - timedelta(days=week * 7 - rnd.randint(0, 6))
            qty = rnd.randint(2, max(3, int(demand * 0.8) + 2))
            db.execute("INSERT INTO waste_log (product_id, batch_id, quantity, kg, cost_loss, reason, logged_on)"
                       " VALUES (%s,NULL,%s,%s,%s,'expired',%s)",
                       (pid, qty, round(qty * kg, 2), round(qty * cost, 2), iso(d)))
        for _ in range(rnd.randint(1, 2)):
            pid, name, cost, price, kg, life, demand = rnd.choice(product_ids)
            d = today - timedelta(days=week * 7 - rnd.randint(0, 6))
            qty = rnd.randint(5, max(6, int(demand * 1.2)))
            kgs = round(qty * kg, 2)
            db.execute("INSERT INTO donations (product_id, batch_id, partner_id, quantity, kg, meals, donated_on)"
                       " VALUES (%s,NULL,%s,%s,%s,%s,%s)",
                       (pid, rnd.randint(1, pcount - 1), qty, kgs, math.ceil(kgs / 0.4), iso(d)))
