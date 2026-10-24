# FoodWasteZero  ·  FoodSphere AI track
**International AI Builders Congress 2026 — challenge: "Food Waste Zero: demand-aligned inventory to cut spoilage and waste"**

An AI inventory assistant for grocery shops and supermarkets. It forecasts demand for every product, works out which
batches **will not sell before they expire**, and tells the manager exactly what to do: **discount**, **donate**, or do a
final **markdown**. It tracks the money saved, the food rescued, the meals donated and the CO2 avoided.

Stack: **Python (Flask) + HTML/CSS/JS + MySQL (XAMPP)**. Charts use Chart.js, bundled in `static/js` (works offline; only the web font needs internet).

---
## 1. Run it on Windows with XAMPP (5 minutes)

1. Install **Python 3.10+** from python.org (tick "Add Python to PATH").
2. Open **XAMPP Control Panel** and **Start MySQL** (Apache is not needed).
3. Open a terminal (Command Prompt) in this project folder and run:
   ```
   pip install -r requirements.txt
   python app.py
   ```
   On the first run `app.py` creates the `foodwastezero` database, tables and demo data automatically.
4. Open **http://127.0.0.1:5000** and log in with **admin / admin123**.

`setup_db.py` (also called automatically on first run) creates the `foodwastezero` database, all tables and demo data (24 products, 45 days of sales, live batches,
partners). Run `python setup_db.py` yourself any time to reset to fresh demo data. Use `python setup_db.py --empty` for a clean database.

**Prefer phpMyAdmin?** Open http://localhost/phpmyadmin → Import → choose `database/schema.sql`.
This creates empty tables only; run `python setup_db.py --empty` afterwards to add the admin user, or just run `python setup_db.py` for tables plus demo data.

**Different MySQL password or port?** Set environment variables before running, e.g. (Windows)
`set MYSQL_PASSWORD=yourpass` — or edit `config.py`.

No MySQL handy? Try it instantly with SQLite: `set FWZ_DB=sqlite` then `python setup_db.py` and `python app.py`.

## 2. How the AI works (explainable, no black box)
| Step | What happens |
|---|---|
| Demand profile | Average daily sales of the last 14 days (promotion effect removed), shaped by a smoothed day-of-week pattern from 28 days. |
| Expiry-risk | Batches are sold oldest-expiry first (FIFO). The model forecasts how many units sell before each batch's expiry; the rest are **at risk**. |
| Price elasticity | Each 1% discount lifts demand about 4%. This gives the discount needed to clear a batch. |
| Decision | Needed discount ≤ 30% → **Discount**. Larger → **Donate** (food-safe categories) or **60% final markdown** (raw meat/fish). |
| Urgency | critical ≤ 1 day, high ≤ 3 days, medium otherwise. |

Tunable constants (elasticity, kg per meal, CO2 factor, currency) are in `config.py`; `MAX_DISCOUNT` is in `forecast.py`.

## 3. Pages and features
Dashboard (KPIs and charts) · AI Actions (apply one, **apply all markdowns**, donate, dismiss) · Inventory (per-batch sell-through, write-off) ·
**Smart Reorder** (how much to order, and which products are overstocked) · Forecast (demand chart plus a **what-if markdown simulator**) ·
Sales (FIFO) · Donations and partners · Products · Impact report.

Every table has **search, filters, click-to-sort headers, Show all / Show less and CSV export**. Press `/` to jump to search.
Light / dark mode and orange / purple colour themes are switched in the sidebar (your choice is remembered).

## 4. Project layout
```
app.py            Flask routes
forecast.py       demand forecast, expiry risk, recommendation engine
db.py / config.py database layer / settings
setup_db.py       creates DB + loads demo data      seed.py  demo data generator
database/schema.sql   MySQL schema (import in phpMyAdmin)
templates/ static/    HTML, CSS, JS
```
Database tables: users, categories, products, batches, sales, partners, actions, donations, waste_log.

## 5. Ideas to extend (for the final pitch)
Barcode scanning on receive, SMS/WhatsApp alert to partners, weather and Eid/Ramadan demand factors, multi-store support,
a Bangla UI, replacing the forecast with Prophet/XGBoost (the `forecast.py` interface stays the same).

Note: partner names in the demo data are fictional placeholders.

## Public shop (customer view)
Run the app and open **http://127.0.0.1:5000/shop** — no login needed. It shows every in-stock, non-expired product with its
live price, rescue-deal discount (set by applying AI Actions), best-before date and stock, with filters for
All / Rescue deals / Regular price / Last chance, category, search and sorting. Each product has a detail page at `/shop/<id>`.
Staff see a "View public shop" link in the sidebar.

### Product images
Each seeded product has its own illustration in `static/img/products/<SKU>.svg`. To use a real photo instead, open
Products → Edit → *Product photo* and upload a JPG/PNG/WEBP (max 5 MB); it is saved as `static/uploads/p<id>.<ext>` and
replaces the illustration in the shop. Products with neither fall back to their category icon.

## Chatbots (Gemini + live data)
* **Customers** — "Ask us" button on every shop page (`/api/shop-chat`): price, discount, availability, best-before. Public, rate-limited (20 msgs/min per IP).
* **Admin** — sidebar **Ask AI** (`/assistant`): current situation, items needing action, reorder advice, sales, waste.
Replies are written by Gemini from live store data in the prompt; if Gemini is unreachable the bots fall back to a built-in answer from the same data.

## Design system
Theme tokens live in `static/css/theme.css` (leaf green + chili red sale tags + turmeric highlight; light/dark; alternative Mango and Plum themes via the sidebar dots).
Fonts are bundled in `static/fonts/` (Bricolage Grotesque for headings, Hind Siliguri for body — covers Bangla), so no internet is needed to load them.
