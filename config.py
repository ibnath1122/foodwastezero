"""FoodWasteZero configuration.

Defaults match a fresh XAMPP install (MySQL/MariaDB user "root", empty password).
Override anything with environment variables if your setup is different.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# "mysql" (XAMPP) is the real target. "sqlite" is only a zero-setup fallback for quick trials.
DB_ENGINE = os.getenv("FWZ_DB", "mysql")

MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DB = os.getenv("MYSQL_DB", "foodwastezero")

SQLITE_PATH = os.getenv("SQLITE_PATH", os.path.join(BASE_DIR, "foodwastezero.sqlite3"))

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key")

# ---- Forecast / impact model constants ----
CURRENCY = "৳"
DEMAND_ELASTICITY = 0.04   # each 1% discount lifts demand by ~4% (30% off -> 2.2x demand)
KG_PER_MEAL = 0.4          # ~0.4 kg of food per meal
CO2_PER_KG = 2.5           # ~2.5 kg CO2e avoided per kg of food kept out of waste
REORDER_BUFFER = 1.15      # order 15% above forecast demand as a safety margin

# ---- Gemini (AI analysis layer) ----
# Key is read from the environment or a local .env file (never hard-code it in source).
def _load_dotenv():
    path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
