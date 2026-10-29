"""English <-> Bangla (বাংলা) support for FoodWasteZero.

How it works (so the templates stay readable English and nothing has to be wrapped in _()):
  * The user picks a language with the EN | বাংলা switch (stored in the session + a cookie).
  * When Bangla is active, every HTML response passes through translate_html(), which translates the visible
    text, placeholders, tooltips and chart labels using the tables below and converts digits to Bangla numerals.
  * Form values, URLs, SKUs and batch codes are never touched, so filters, searches and forms keep working.
To translate a new sentence, add it to EXACT (fixed text) or PATTERNS (text with numbers in it).
Product names live in PRODUCT_BN; a product that is not listed there simply stays in English.
"""
import html as _html
import json
import re

LANGS = ("en", "bn")

# ------------------------------------------------------------------ digits / dates / units
BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
MONTHS = {"Jan": "জানু", "Feb": "ফেব্রু", "Mar": "মার্চ", "Apr": "এপ্রিল", "May": "মে", "Jun": "জুন",
          "Jul": "জুলাই", "Aug": "আগস্ট", "Sep": "সেপ্টেম্বর", "Oct": "অক্টোবর", "Nov": "নভেম্বর", "Dec": "ডিসেম্বর"}
WEEKDAYS = {"Mon": "সোম", "Tue": "মঙ্গল", "Wed": "বুধ", "Thu": "বৃহ", "Fri": "শুক্র", "Sat": "শনি", "Sun": "রবি"}
UNITS = {"pc": "পিস", "loaf": "লোফ", "pack": "প্যাক", "dozen": "ডজন", "kg": "কেজি", "cup": "কাপ", "bunch": "আঁটি",
         "box": "বক্স", "bottle": "বোতল", "unit": "ইউনিট", "units": "ইউনিট", "g": "গ্রাম", "l": "লিটার"}

# codes that must keep Latin digits: SKU, batch code, phone numbers, demo password
_CODE = r"\b[A-Z]{3}-\d{3}\b|\bB\d{6}-\d+\b|\b01\d{3}-\d{6}\b|\badmin123\b"
_CODE_OR_DIGIT = re.compile("(%s)|([0-9])" % _CODE)


def bn_digits(s):
    """Latin digits -> Bangla digits, except inside SKUs / batch codes / phone numbers."""
    return _CODE_OR_DIGIT.sub(lambda m: m.group(1) or m.group(2).translate(BN_DIGITS), s)


# ------------------------------------------------------------------ catalogue names
CATEGORY_BN = {
    "Bakery": "বেকারি", "Dairy": "দুগ্ধজাত", "Fresh Produce": "তাজা শাকসবজি ও ফল", "Meat & Fish": "মাছ ও মাংস",
    "Ready Meals": "রেডি খাবার", "Beverages": "পানীয়", "Packaged Foods": "প্যাকেটজাত খাবার", "Sweets": "মিষ্টি",
}
PRODUCT_BN = {
    "Sandwich Bread": "স্যান্ডউইচ পাউরুটি", "Bakorkhani (6 pcs)": "বাখরখানি (৬ পিস)", "Rosogolla (box of 12)": "রসগোল্লা (১২ পিসের বক্স)",
    "Pasteurized Milk 1L": "পাস্তুরিত দুধ ১ লিটার", "Sweet Yogurt (Doi) 500g": "মিষ্টি দই ৫০০ গ্রাম", "Eggs (dozen)": "ডিম (ডজন)",
    "Paneer Block 200g": "পনির ২০০ গ্রাম", "Bananas (dozen)": "কলা (ডজন)", "Tomato 1kg": "টমেটো ১ কেজি",
    "Spinach (Palong) bunch": "পালং শাক (আঁটি)", "Green Chili 250g": "কাঁচা মরিচ ২৫০ গ্রাম", "Broiler Chicken 1kg": "ব্রয়লার মুরগি ১ কেজি",
    "Rui Fish 1kg": "রুই মাছ ১ কেজি", "Beef Mince 500g": "গরুর কিমা ৫০০ গ্রাম", "Chicken Biryani Box": "চিকেন বিরিয়ানি বক্স",
    "Beguni (6 pcs)": "বেগুনি (৬ পিস)", "Paratha Pack (5)": "পরোটা প্যাক (৫ পিস)", "Fresh Orange Juice 1L": "তাজা কমলার জুস ১ লিটার",
    "Lassi 250ml": "লাচ্ছি ২৫০ মি.লি.", "Roshmalai (box of 6)": "রসমালাই (৬ পিসের বক্স)", "Biscuit Family Pack": "বিস্কুট ফ্যামিলি প্যাক",
    "Jilapi (500g)": "জিলাপি (৫০০ গ্রাম)", "Khichuri Box": "খিচুড়ি বক্স", "Haleem (cup)": "হালিম (কাপ)",
}
PARTNER_BN = {
    "Ashulia Community Kitchen (demo)": "আশুলিয়া কমিউনিটি কিচেন (ডেমো)", "Dhaka Food Bank (demo)": "ঢাকা ফুড ব্যাংক (ডেমো)",
    "Mirpur Shelter Home (demo)": "মিরপুর আশ্রয়কেন্দ্র (ডেমো)", "Savar Compost & Feed Farm (demo)": "সাভার কম্পোস্ট ও ফিড ফার্ম (ডেমো)",
}
AREA_BN = {"Ashulia": "আশুলিয়া", "Dhaka": "ঢাকা", "Mirpur": "মিরপুর", "Savar": "সাভার"}
KIND_BN = {"charity": "দাতব্য সংস্থা", "food bank": "ফুড ব্যাংক", "shelter": "আশ্রয়কেন্দ্র", "farm": "খামার", "compost": "কম্পোস্ট"}

# longest first so "Sweet Yogurt (Doi) 500g" wins over any shorter overlap
_NAMES = {}
for _d in (PRODUCT_BN, PARTNER_BN, CATEGORY_BN):
    _NAMES.update(_d)
_NAME_RX = re.compile("|".join(re.escape(k) for k in sorted(_NAMES, key=len, reverse=True)))
_AREA_RX = re.compile(r"\b(%s)\b" % "|".join(AREA_BN))

# ------------------------------------------------------------------ fixed text
EXACT = {
    # --- navigation / chrome
    "Dashboard": "ড্যাশবোর্ড", "AI Actions": "এআই পদক্ষেপ", "Ask AI": "এআইকে জিজ্ঞাসা", "AI Insights": "এআই বিশ্লেষণ",
    "Inventory": "ইনভেন্টরি (মজুত)", "Smart Reorder": "স্মার্ট রিঅর্ডার", "Sales": "বিক্রয়", "Donations": "দান",
    "Products": "পণ্য", "Impact Report": "প্রভাব প্রতিবেদন", "View public shop": "পাবলিক শপ দেখুন", "Sign out": "সাইন আউট",
    "Store Manager": "স্টোর ম্যানেজার", "Language": "ভাষা", "Switch light / dark mode": "লাইট / ডার্ক মোড বদলান", "Switch light or dark mode": "লাইট / ডার্ক মোড বদলান",
    "Green theme": "সবুজ থিম", "Mango theme": "আম থিম", "Plum theme": "বেগুনি থিম", "Purple theme": "বেগুনি থিম",
    "Staff login": "স্টাফ লগইন", "All products": "সব পণ্য", "Rescue deals": "রেসকিউ অফার", "Last chance": "শেষ সুযোগ",
    "Fresh · Fair · Zero waste": "তাজা · ন্যায্য · শূন্য অপচয়", "FoodSphere AI": "ফুডস্ফিয়ার এআই",
    # --- login
    "Welcome back": "স্বাগতম", "Username": "ইউজারনেম", "Password": "পাসওয়ার্ড", "Sign in": "সাইন ইন", "Demo login:": "ডেমো লগইন:",
    "Predict what won't sell. Rescue it before it expires.": "যা বিক্রি হবে না তা আগেই জানুন। মেয়াদ শেষ হওয়ার আগে বাঁচান।",
    "Zero waste. Full baskets.": "শূন্য অপচয়। ভরা ঝুড়ি।",
    "AI forecasts what will expire unsold and tells you whether to discount, donate or mark down.":
        "কোন পণ্য অবিক্রীত থেকে মেয়াদ পেরিয়ে যাবে এআই তা আগাম বলে দেয় এবং জানায় ছাড় দেবেন, দান করবেন নাকি দাম কমাবেন।",
    "Bread": "রুটি", "today": "আজ", "meals donated": "বেলার খাবার দান", "CO₂ avoided": "CO₂ এড়ানো গেছে",
    # --- dashboard
    "Save food before it expires.": "মেয়াদ শেষ হওয়ার আগেই খাবার বাঁচান।", "Review AI actions": "এআই পদক্ষেপ দেখুন", "Run AI scan": "এআই স্ক্যান চালান",
    "Re-run AI scan": "আবার এআই স্ক্যান চালান", "Stock value at risk": "ঝুঁকিতে থাকা স্টকের মূল্য", "Waste cost (30d)": "অপচয়ের খরচ (৩০ দিন)",
    "written off after expiry": "মেয়াদ শেষে বাতিল", "Food donated (30d)": "দান করা খাবার (৩০ দিন)", "rescued from the bin": "ফেলে দেওয়ার হাত থেকে বাঁচানো",
    "Value at risk by category": "ক্যাটাগরি অনুযায়ী ঝুঁকিতে থাকা মূল্য", "Nothing at risk right now.": "এখন কিছুই ঝুঁকিতে নেই।",
    "Most urgent batches": "সবচেয়ে জরুরি ব্যাচ", "Expires": "মেয়াদ শেষ", "At risk": "ঝুঁকিতে", "AI says": "এআই-এর পরামর্শ",
    "See all AI actions →": "সব এআই পদক্ষেপ দেখুন →", "All stock is on track to sell.": "সব স্টকই সময়মতো বিক্রি হওয়ার পথে।",
    "No pending recommendations. Stock is on track.": "কোনো অপেক্ষমাণ সুপারিশ নেই। স্টক ঠিক পথে আছে।",
    # --- AI actions
    "Recommendations to save stock before it expires. Apply a markdown, donate, or dismiss.": "মেয়াদ শেষ হওয়ার আগে স্টক বাঁচানোর সুপারিশ। ছাড় দিন, দান করুন অথবা বাতিল করুন।",
    "Apply": "প্রয়োগ করুন", "Dismiss": "বাতিল করুন", "Donate…": "দান করুন…", "Donate": "দান", "Discount": "ছাড়", "Markdown": "দাম কমানো",
    "Recent decisions": "সাম্প্রতিক সিদ্ধান্ত", "Status": "অবস্থা", "When": "কখন", "critical": "অতি জরুরি", "high": "উচ্চ", "medium": "মাঝারি",
    "Critical": "অতি জরুরি", "High": "উচ্চ", "Medium": "মাঝারি", "Applied": "প্রয়োগ হয়েছে", "Dismissed": "বাতিল", "Donated": "দান করা হয়েছে",
    "Urgency": "জরুরিত্ব", "Action": "পদক্ষেপ", "applied": "প্রয়োগ হয়েছে", "dismissed": "বাতিল", "donated": "দান করা হয়েছে",
    # --- inventory / batches
    "Every batch with its forecast sell-through before expiry. Click a column to sort.": "প্রতিটি ব্যাচ এবং মেয়াদের আগে তার পূর্বাভাসিত বিক্রি। সাজাতে কলামে ক্লিক করুন।",
    "Receive batch": "ব্যাচ গ্রহণ", "Product / batch": "পণ্য / ব্যাচ", "Stock": "স্টক", "Forecast sell-through": "পূর্বাভাসিত বিক্রি",
    "Forecast": "পূর্বাভাস", "Log a new delivery. The AI re-scores risk immediately.": "নতুন সরবরাহ লিখুন। এআই সঙ্গে সঙ্গে ঝুঁকি আবার হিসাব করবে।",
    "Quantity": "পরিমাণ", "Delivered on": "সরবরাহের তারিখ", "Expires on": "মেয়াদ শেষের তারিখ",
    "Auto-filled from the product's shelf life; edit if the label says otherwise.": "পণ্যের মেয়াদকাল থেকে নিজে থেকে বসেছে; লেবেলে অন্য তারিখ থাকলে বদলে নিন।",
    "Save batch": "ব্যাচ সংরক্ষণ", "Cancel": "বাতিল", "Write off this batch (damaged / lost)": "এই ব্যাচ বাতিল করুন (নষ্ট / হারিয়ে গেছে)",
    "Write off batch": "ব্যাচ বাতিল করুন", "On track": "ঠিক আছে", "Expiry": "মেয়াদ", "Batch": "ব্যাচ",
    # --- reorder
    "Stop overstocking at the source: order only what the forecast says will sell before it expires.": "অতিরিক্ত মজুত গোড়াতেই বন্ধ করুন: মেয়াদের আগে যতটুকু বিক্রি হবে বলে পূর্বাভাস, ততটুকুই অর্ডার করুন।",
    "Products to order": "অর্ডারযোগ্য পণ্য", "Estimated order cost": "আনুমানিক অর্ডার খরচ", "at current unit cost": "বর্তমান ইউনিট দামে",
    "Overstocked products": "অতিরিক্ত মজুত পণ্য", "do not reorder these": "এগুলো আবার অর্ডার করবেন না", "Cover (days)": "কভার (দিন)",
    "Need": "প্রয়োজন", "Order qty": "অর্ডারের পরিমাণ", "Out of stock": "স্টক শেষ", "Reorder": "রিঅর্ডার", "OK": "ঠিক আছে",
    "Overstocked": "অতিরিক্ত মজুত", "to download your purchase list.": "বোতামে কেনার তালিকা ডাউনলোড করুন।",
    "CSV": "CSV",
    # --- sales
    "Record a sale. Stock is taken from the batch expiring soonest (FIFO) at its current markdown.": "বিক্রি লিখুন। যে ব্যাচের মেয়াদ আগে শেষ হবে (FIFO) সেটি থেকেই, তার বর্তমান ছাড়ের দামে স্টক কাটা হবে।",
    "Record sale": "বিক্রি লিখুন", "Unit price": "একক দাম", "Total": "মোট", "Price": "দাম", "Discounted": "ছাড়যুক্ত", "Full price": "পূর্ণ দাম",
    # --- donations
    "Surplus food sent to partners instead of the bin.": "উদ্বৃত্ত খাবার ফেলে না দিয়ে সহযোগীদের কাছে পাঠানো হয়েছে।", "+ Log donation": "+ দান লিখুন",
    "Log donation": "দান লিখুন", "Recent donations": "সাম্প্রতিক দান", "Qty": "পরিমাণ", "Kg": "কেজি", "Meals": "বেলার খাবার",
    "No donations yet.": "এখনও কোনো দান নেই।", "Partners": "সহযোগী প্রতিষ্ঠান", "Add partner": "সহযোগী যোগ করুন", "Add": "যোগ করুন",
    "Name": "নাম", "Type": "ধরন", "Charity": "দাতব্য সংস্থা", "Food bank": "ফুড ব্যাংক", "Shelter": "আশ্রয়কেন্দ্র", "Farm": "খামার",
    "Compost": "কম্পোস্ট", "Area": "এলাকা", "Phone": "ফোন", "Partner": "সহযোগী", "Date": "তারিখ", "Estimated impact": "আনুমানিক প্রভাব",
    "Save donation": "দান সংরক্ষণ", "Stock is deducted from the batch and meals are estimated from weight.": "ব্যাচ থেকে স্টক কাটা হবে এবং ওজন থেকে খাবারের বেলা আনুমানিক হিসাব হবে।",
    # --- products
    "The catalogue the forecast model learns from.": "যে পণ্যতালিকা থেকে পূর্বাভাস মডেল শেখে।", "New product": "নতুন পণ্য", "Edit product": "পণ্য সম্পাদনা",
    "Cost": "খরচ", "Margin": "মার্জিন", "Shelf life": "মেয়াদকাল", "In stock": "মজুত আছে", "inactive": "নিষ্ক্রিয়", "Edit": "সম্পাদনা",
    "Active": "সক্রিয়", "Inactive": "নিষ্ক্রিয়", "SKU": "এসকেইউ", "Category": "ক্যাটাগরি", "Unit (pc, kg, loaf…)": "একক (পিস, কেজি, লোফ…)",
    "Unit cost (৳)": "একক খরচ (৳)", "Selling price (৳)": "বিক্রয়মূল্য (৳)", "Weight per unit (kg)": "প্রতি এককের ওজন (কেজি)", "Shelf life (days)": "মেয়াদকাল (দিন)",
    "Yes": "হ্যাঁ", "No": "না", "Save": "সংরক্ষণ", "Product photo (JPG / PNG / WEBP — shown in the shop and in the tables)": "পণ্যের ছবি (JPG / PNG / WEBP — শপ ও তালিকায় দেখানো হবে)",
    "Product": "পণ্য", "Batch code": "ব্যাচ কোড",
    # --- forecast
    "← Inventory": "← ইনভেন্টরি", "Weekday pattern": "সাপ্তাহিক ধরন", "What-if markdown simulator": "ছাড় দিলে কী হবে — সিমুলেটর",
    "Discount:": "ছাড়:", "Forecast units sold before expiry": "মেয়াদের আগে পূর্বাভাসিত বিক্রি (ইউনিট)", "Units still at risk": "এখনও ঝুঁকিতে থাকা ইউনিট",
    "No stock of this product.": "এই পণ্যের কোনো স্টক নেই।", "Actual": "প্রকৃত", "1.0 = average day. The model blends this pattern with the recent 14-day average.": "১.০ = গড় দিন। মডেল এই ধরনটিকে সাম্প্রতিক ১৪ দিনের গড়ের সাথে মেলায়।",
    # --- impact
    "Waste cost": "অপচয়ের খরচ", "Food wasted": "নষ্ট হওয়া খাবার", "expired unsold": "অবিক্রীত অবস্থায় মেয়াদোত্তীর্ণ", "from donated food": "দান করা খাবার থেকে",
    "CO₂e avoided": "CO₂e এড়ানো গেছে", "Markdown sales": "ছাড়ে বিক্রি", "Waste cost by category": "ক্যাটাগরি অনুযায়ী অপচয়ের খরচ", "No waste logged.": "কোনো অপচয় লেখা নেই।",
    "Top wasted products": "সবচেয়ে বেশি নষ্ট হওয়া পণ্য", "Loss": "ক্ষতি", "Nothing yet.": "এখনও কিছু নেই।", "Waste cost": "অপচয়ের খরচ",
    # --- AI insights / assistant
    "Gemini reads the forecast engine's numbers and writes a plain-language action plan. All figures come from your data.": "জেমিনি পূর্বাভাস ইঞ্জিনের সংখ্যাগুলো পড়ে সহজ ভাষায় কর্মপরিকল্পনা লেখে। সব সংখ্যা আপনার নিজের তথ্য থেকে আসে।",
    "Analyse my store": "আমার স্টোর বিশ্লেষণ করুন", "Re-analyse": "আবার বিশ্লেষণ করুন", "Do first": "আগে করুন", "Why": "কেন",
    "to generate today's AI briefing.": "চাপলে আজকের এআই ব্রিফিং তৈরি হবে।", "Press": "", "to the": "এই ফাইলে:", "file, then restart the app.": "— তারপর অ্যাপ আবার চালু করুন।",
    "Chat with your store data: stock, expiring batches, sales, waste, reordering.": "আপনার স্টোরের তথ্যের সাথে কথা বলুন: স্টক, মেয়াদ-শেষ হতে চলা ব্যাচ, বিক্রি, অপচয়, রিঅর্ডার।",
    "(Gemini key not set — you will get data summaries only.)": "(জেমিনি কী সেট করা নেই — শুধু তথ্যের সারাংশ পাবেন।)", "Send": "পাঠান",
    "Ask about your store…": "আপনার স্টোর সম্পর্কে জিজ্ঞাসা করুন…",
    "Hi! I can see your live inventory, sales and waste data. Ask me about the current situation or what to do next.": "নমস্কার! আমি আপনার লাইভ ইনভেন্টরি, বিক্রি ও অপচয়ের তথ্য দেখতে পাই। বর্তমান অবস্থা বা পরের করণীয় সম্পর্কে জিজ্ঞাসা করুন।",
    "What's the current situation?": "বর্তমান অবস্থা কী?", "Which items need action today?": "আজ কোন পণ্যে পদক্ষেপ নিতে হবে?", "What should I reorder?": "কী রিঅর্ডার করা উচিত?",
    "Which products are overstocked?": "কোন পণ্যগুলো অতিরিক্ত মজুত?", "What are the top sellers this week?": "এই সপ্তাহে সবচেয়ে বেশি কী বিক্রি হয়েছে?", "How much waste did we have this month?": "এই মাসে কত অপচয় হয়েছে?",
    # --- shop
    "Fresh food, priced to be eaten today.": "তাজা খাবার, আজই খাওয়ার মতো দামে।",
    "Everything here is on our shelves right now. Items close to their best-before date are marked down, so good food gets eaten instead of binned.": "এখানকার সবকিছুই এই মুহূর্তে আমাদের তাকে আছে। মেয়াদ ফুরিয়ে আসা পণ্যের দাম কমানো হয়েছে, যাতে ভালো খাবার ফেলা না গিয়ে খাওয়া হয়।",
    "products in stock": "পণ্য মজুত আছে", "on rescue deal": "রেসকিউ অফারে", "biggest discount today": "আজকের সর্বোচ্চ ছাড়",
    "Biggest deal today": "আজকের সেরা অফার", "Best before soonest": "সবচেয়ে আগে মেয়াদ শেষ হবে", "All": "সব", "Regular price": "নিয়মিত দাম",
    "All categories": "সব ক্যাটাগরি", "Search": "খুঁজুন", "Search products…": "পণ্য খুঁজুন…", "Search products": "পণ্য খুঁজুন", "Sort": "সাজান",
    "Biggest discount": "সর্বোচ্চ ছাড়", "Expiring soon": "শীঘ্রই মেয়াদ শেষ", "Price: low to high": "দাম: কম থেকে বেশি", "Price: high to low": "দাম: বেশি থেকে কম",
    "Best before today": "মেয়াদ আজই শেষ", "Best before tomorrow": "মেয়াদ কালই শেষ", "In stock": "মজুত আছে",
    "Nothing matches that search.": "এই অনুসন্ধানে কিছু মেলেনি।", "Show all products": "সব পণ্য দেখুন", "← All products": "← সব পণ্য",
    "Regular price. Fresh stock with plenty of shelf life left.": "নিয়মিত দাম। তাজা স্টক, মেয়াদ অনেক বাকি।",
    "This is a": "এটি একটি", "rescue deal": "রেসকিউ অফার",
    ": it is still fresh and safe to eat, but it is close to its best-before date, so we have marked it down to get it eaten instead of binned.": ": এটি এখনও তাজা ও খাওয়ার জন্য নিরাপদ, তবে মেয়াদ ফুরিয়ে আসছে। তাই ফেলে না দিয়ে যাতে খাওয়া হয় সেজন্য দাম কমানো হয়েছে।",
    "Best before": "মেয়াদ শেষ", "Availability": "প্রাপ্যতা", "Typical shelf life": "সাধারণ মেয়াদকাল", "Product code": "পণ্য কোড", "Impact": "প্রভাব",
    "Available lots": "বিদ্যমান লট", "Time left": "সময় বাকি", "Tomorrow": "আগামীকাল", "Today": "আজ", "tomorrow": "আগামীকাল",
    "Back to the shop": "শপে ফিরে যান", "This product is sold out or no longer available.": "এই পণ্য শেষ হয়ে গেছে অথবা আর পাওয়া যায় না।",
    "Prices and stock update live from the store's inventory. Discounted items are good to eat — we just want them eaten before their best-before date.": "দাম ও স্টক সরাসরি স্টোরের ইনভেন্টরি থেকে হালনাগাদ হয়। ছাড়ের পণ্য খাওয়ার জন্য ভালো — আমরা শুধু চাই মেয়াদ শেষ হওয়ার আগেই সেগুলো খাওয়া হোক।",
    "Visit the shop to buy.": "কিনতে দোকানে আসুন।", "Shop assistant": "শপ সহকারী", "Ask us": "আমাদের জিজ্ঞাসা করুন", "Close chat": "চ্যাট বন্ধ করুন", "Open chat assistant": "চ্যাট সহকারী খুলুন",
    "Ask about a product…": "কোনো পণ্য সম্পর্কে জিজ্ঞাসা করুন…", "Hi! Ask me the price or availability of any product, or what's on discount today.": "নমস্কার! যেকোনো পণ্যের দাম বা প্রাপ্যতা জিজ্ঞাসা করুন, অথবা আজ কিসে ছাড় আছে জানতে চান।",
    "What's on discount?": "কিসে ছাড় আছে?", "Is milk available?": "দুধ কি পাওয়া যাচ্ছে?", "Price of eggs": "ডিমের দাম কত?", "What expires soon?": "কোন পণ্যের মেয়াদ শীঘ্রই শেষ হবে?",
    "Shop": "শপ", "Not available": "পাওয়া যাচ্ছে না", "Basket of fresh food": "তাজা খাবারের ঝুড়ি",
    # --- JS-driven table UI (also used server-side for data-search / data-filters labels)
    "Search donations…": "দান খুঁজুন…", "Search name or SKU…": "নাম বা এসকেইউ খুঁজুন…", "Search product or SKU…": "পণ্য বা এসকেইউ খুঁজুন…",
    "Search product or batch…": "পণ্য বা ব্যাচ খুঁজুন…", "Search product, SKU or batch…": "পণ্য, এসকেইউ বা ব্যাচ খুঁজুন…", "Search sales…": "বিক্রি খুঁজুন…", "Search decisions…": "সিদ্ধান্ত খুঁজুন…",
    "Catalogue": "পণ্যতালিকা",
}

# ------------------------------------------------------------------ text with numbers in it
def _u(w):                      # unit word -> Bangla
    return UNITS.get(w, w)


def _plural_day(n):
    return "দিন"


PATTERNS = [
    # dashboard banner (split around the ৳ amount)
    (r"^(\d[\d,]*) units worth$", lambda m: "%sটি ইউনিট, মূল্য" % m[1]),
    (r"^([\d,.]+) are forecast to go unsold\. Review the AI's suggested discounts and donations\.$",
     lambda m: "%s — এগুলো অবিক্রীত থেকে যাওয়ার পূর্বাভাস আছে। এআই-এর প্রস্তাবিত ছাড় ও দান দেখে নিন।" % m[1]),
    (r"^Hello, (.+?) · (.+)$", lambda m: "নমস্কার, %s · %s" % (tr(m[1]), m[2])),
    (r"^([\d,]+) units may expire unsold$", lambda m: "%sটি ইউনিট অবিক্রীত থেকে মেয়াদোত্তীর্ণ হতে পারে" % m[1]),
    (r"^Expiring ≤ (\d+) days$", lambda m: "মেয়াদ ≤ %s দিনের মধ্যে" % m[1]),
    (r"^of (\d+) active batches$", lambda m: "মোট %sটি সক্রিয় ব্যাচের মধ্যে" % m[1]),
    (r"^Waste cost \((\d+)d\)$", lambda m: "অপচয়ের খরচ (%s দিন)" % m[1]),
    (r"^Weekly waste cost \((\d+) weeks\)$", lambda m: "সাপ্তাহিক অপচয়ের খরচ (%s সপ্তাহ)" % m[1]),
    (r"^Revenue, last (\d+) days$", lambda m: "আয়, শেষ %s দিন" % m[1]),
    (r"^Last (\d+) days: what waste cost you, and what you rescued\.$", lambda m: "শেষ %s দিন: অপচয়ে কত গেছে, আর কী বাঁচানো গেছে।" % m[1]),
    (r"^Latest (\d+) sales$", lambda m: "সর্বশেষ %sটি বিক্রি" % m[1]),
    (r"^Demand: last (\d+) days and next (\d+)$", lambda m: "চাহিদা: শেষ %s দিন ও পরবর্তী %s দিন" % (m[1], m[2])),
    (r"^(\d+)% higher than previous (\d+) days$", lambda m: "আগের %s দিনের চেয়ে %s%% বেশি" % (m[2], m[1])),
    (r"^(\d+)% lower than previous (\d+) days$", lambda m: "আগের %s দিনের চেয়ে %s%% কম" % (m[2], m[1])),
    (r"^([\d,]+) completely out of stock$", lambda m: "%sটি সম্পূর্ণ স্টকশূন্য" % m[1]),
    (r"^([\d,]+) units sold at a discount$", lambda m: "%sটি ইউনিট ছাড়ে বিক্রি হয়েছে" % m[1]),
    (r"^([\d,]+) donations · ≈ ([\d,]+) meals$", lambda m: "%sটি দান · ≈ %s বেলার খাবার" % (m[1], m[2])),
    (r"^([\d,]+) meals$", lambda m: "%s বেলার খাবার" % m[1]),
    (r"^Apply all markdowns \((\d+)\)$", lambda m: "সব ছাড় প্রয়োগ করুন (%s)" % m[1]),
    (r"^Overstocked \+(\d+)$", lambda m: "অতিরিক্ত মজুত +%s" % m[1]),
    (r"^([\d.,]+) / day$", lambda m: "%s / দিন" % m[1]),
    (r"^/ (\d+)d$", lambda m: "/ %s দিন" % m[1]),
    (r"^(\d+) d$", lambda m: "%s দিন" % m[1]),
    (r"^(\d+) days? left$", lambda m: "আর %s দিন বাকি" % m[1]),
    (r"^(\d+) days?$", lambda m: "%s দিন" % m[1]),
    (r"^(\d+) day left$", lambda m: "আর %s দিন বাকি" % m[1]),
    (r"^(\d+)\+ days$", lambda m: "%s+ দিন" % m[1]),
    (r"^(\d+)-(\d+) days$", lambda m: "%s-%s দিন" % (m[1], m[2])),
    (r"^Only (\d+) left$", lambda m: "মাত্র %sটি বাকি" % m[1]),
    (r"^(\d+) (\w+) in stock$", lambda m: "%s %s মজুত আছে" % (m[1], _u(m[2]))),
    (r"^Weight per (\w+)$", lambda m: "প্রতি %s ওজন" % _u(m[1])),
    (r"^per (\w+)$", lambda m: "প্রতি %s" % _u(m[1])),
    (r"^/ (\w+)$", lambda m: "/ %s" % _u(m[1])),
    (r"^More in (.+)$", lambda m: "%s-এর আরও পণ্য" % m[1]),
    (r"^Save (.+?)(\d[\d,.]*) · (\d+)% off$", lambda m: "সাশ্রয় %s%s · %s%% ছাড়" % (m[1], m[2], m[3])),
    (r"^(\d+)% off$", lambda m: "%s%% ছাড়" % m[1]),
    (r"^Discount (\d+)%$", lambda m: "ছাড় %s%%" % m[1]),
    (r"^Markdown (\d+)%$", lambda m: "দাম কমানো %s%%" % m[1]),
    (r"^Donate (\d+) (\w+)$", lambda m: "%s %s দান করুন" % (m[1], _u(m[2]))),
    (r"^(\d+)% markdown on (\d+) (\w+)$", lambda m: "%s %s-এ %s%% ছাড়" % (m[2], _u(m[3]), m[1])),
    (r"^Expires (.+)$", lambda m: "মেয়াদ শেষ %s" % m[1]),
    (r"^Recovers$", lambda m: "পুনরুদ্ধার"),
    (r"^Buying one saves ~([\d.]+) kg CO₂e$", lambda m: "একটি কিনলে ~%s কেজি CO₂e সাশ্রয় হয়" % m[1]),
    (r"^~([\d.]+) kg$", lambda m: "~%s কেজি" % m[1]),
    (r"^([\d.,]+) kg$", lambda m: "%s কেজি" % m[1]),
    (r"^~(\d+) of (\d+) will sell$", lambda m: "%s-এর মধ্যে ~%sটি বিক্রি হবে" % (m[2], m[1])),
    (r"^(.+?) · (\d+) left · (\d+)d to expiry$", lambda m: "%s · %sটি বাকি · মেয়াদ শেষ হতে %s দিন" % (m[1], m[2], m[3])),
    (r"^(.+?) · (.+?) · (\d+) (\w+) left · exp (.+)$", lambda m: "%s · %s · %s %s বাকি · মেয়াদ %s" % (m[1], m[2], m[3], _u(m[4]), m[5])),
    (r"^(.+?) · shelf life (\d+) days · price$", lambda m: "%s · মেয়াদকাল %s দিন · দাম" % (m[1], m[2])),
    (r"^([\d,.]+ )?· baseline ≈ ([\d.]+) (\w+)/day$", lambda m: "%s· গড় চাহিদা ≈ %s %s/দিন" % (m[1] or "", m[2], _u(m[3]))),
    (r"^Estimates: ([\d.]+) kg CO₂e avoided per kg donated; ([\d.]+) kg of food per meal\. Constants are editable in config\.py\.$",
     lambda m: "হিসাব: প্রতি কেজি দানে %s কেজি CO₂e এড়ানো যায়; প্রতি বেলার খাবারে %s কেজি খাদ্য। ধ্রুবকগুলো config.py-তে বদলানো যায়।" % (m[1], m[2])),
    (r"^Suggested order = forecast demand over the next few days \(up to the shelf life\) × ([\d.]+) safety margin − stock already on hand\.(?: Use)?$",
     lambda m: "প্রস্তাবিত অর্ডার = আগামী কয়েক দিনের (মেয়াদকাল পর্যন্ত) পূর্বাভাসিত চাহিদা × %s নিরাপত্তা মার্জিন − হাতে থাকা স্টক।" % m[1]),
    (r"^Generated by (.+?) from live store data\. Review before acting\.$", lambda m: "%s লাইভ স্টোর তথ্য থেকে তৈরি করেছে। পদক্ষেপ নেওয়ার আগে যাচাই করুন।" % m[1]),
    # forecast-engine rationale (stored in the database in English)
    (r"^Forecast sells ~(\d+) of (\d+) units before expiry \((\d+) days? left\); (\d+) at risk\. A (\d+)% markdown should clear the batch\.$",
     lambda m: "পূর্বাভাস: মেয়াদের আগে %s ইউনিটের মধ্যে ~%sটি বিক্রি হবে (আর %s দিন বাকি); %sটি ঝুঁকিতে। %s%% ছাড় দিলে ব্যাচটি শেষ হওয়া উচিত।" % (m[2], m[1], m[3], m[4], m[5])),
    (r"^Forecast sells ~(\d+) of (\d+) units before expiry \((\d+) days? left\); (\d+) at risk\. Discount alone is not enough: donate ~(\d+) meals\.$",
     lambda m: "পূর্বাভাস: মেয়াদের আগে %s ইউনিটের মধ্যে ~%sটি বিক্রি হবে (আর %s দিন বাকি); %sটি ঝুঁকিতে। শুধু ছাড়ে হবে না: ~%s বেলার খাবার দান করুন।" % (m[2], m[1], m[3], m[4], m[5])),
    (r"^Forecast sells ~(\d+) of (\d+) units before expiry \((\d+) days? left\); (\d+) at risk\. Not donatable: apply a (\d+)% final markdown\.$",
     lambda m: "পূর্বাভাস: মেয়াদের আগে %s ইউনিটের মধ্যে ~%sটি বিক্রি হবে (আর %s দিন বাকি); %sটি ঝুঁকিতে। দান করা যায় না: %s%% চূড়ান্ত ছাড় দিন।" % (m[2], m[1], m[3], m[4], m[5])),
    # flash messages
    (r"^Wrong username or password\.$", lambda m: "ইউজারনেম বা পাসওয়ার্ড ভুল।"),
    (r"^(\d+) expired batch\(es\) were written off automatically\.$", lambda m: "মেয়াদোত্তীর্ণ %sটি ব্যাচ নিজে থেকেই বাতিল হয়েছে।" % m[1]),
    (r"^Please check the form: quantity must be positive and expiry after delivery date\.$", lambda m: "ফর্মটি দেখুন: পরিমাণ শূন্যের বেশি হতে হবে এবং মেয়াদ সরবরাহের তারিখের পরে হতে হবে।"),
    (r"^Batch (\S+) received and risk re-scored\.$", lambda m: "ব্যাচ %s গ্রহণ করা হয়েছে এবং ঝুঁকি আবার হিসাব হয়েছে।" % m[1]),
    (r"^Please fill every field with valid values\.$", lambda m: "প্রতিটি ঘর সঠিক মান দিয়ে পূরণ করুন।"),
    (r"^That SKU already exists\.$", lambda m: "এই এসকেইউ আগে থেকেই আছে।"),
    (r"^Product saved\.$", lambda m: "পণ্য সংরক্ষিত হয়েছে।"),
    (r"^Photo must be a JPG, PNG, WEBP or GIF image\.$", lambda m: "ছবি অবশ্যই JPG, PNG, WEBP বা GIF হতে হবে।"),
    (r"^Enter a valid product, quantity and date\.$", lambda m: "সঠিক পণ্য, পরিমাণ ও তারিখ দিন।"),
    (r"^Not enough sellable stock for that quantity\.$", lambda m: "এই পরিমাণের জন্য বিক্রয়যোগ্য স্টক যথেষ্ট নেই।"),
    (r"^Sale recorded \(FIFO by expiry date\)\.$", lambda m: "বিক্রি লেখা হয়েছে (মেয়াদ অনুযায়ী FIFO)।"),
    (r"^AI scan complete: (\d+) recommendation\(s\) generated\.$", lambda m: "এআই স্ক্যান সম্পন্ন: %sটি সুপারিশ তৈরি হয়েছে।" % m[1]),
    (r"^That recommendation is no longer pending\.$", lambda m: "এই সুপারিশটি আর অপেক্ষমাণ নেই।"),
    (r"^Recommendation dismissed\.$", lambda m: "সুপারিশ বাতিল করা হয়েছে।"),
    (r"^(\d+)% markdown applied\. New sales of this batch use the lower price\.$", lambda m: "%s%% ছাড় প্রয়োগ হয়েছে। এই ব্যাচের নতুন বিক্রি কম দামে হবে।" % m[1]),
    (r"^Check the batch, partner and quantity \(cannot exceed remaining stock\)\.$", lambda m: "ব্যাচ, সহযোগী ও পরিমাণ দেখুন (বাকি স্টকের বেশি হতে পারবে না)।"),
    (r"^Donation logged: ([\d.]+) kg, about (\d+) meals\.$", lambda m: "দান লেখা হয়েছে: %s কেজি, প্রায় %s বেলার খাবার।" % (m[1], m[2])),
    (r"^Partner added\.$", lambda m: "সহযোগী যোগ করা হয়েছে।"),
    (r"^(\d+) markdown\(s\) applied in one go\.$", lambda m: "একসাথে %sটি ছাড় প্রয়োগ হয়েছে।" % m[1]),
    (r"^Batch (\S+) written off \((\d+) units\)\.$", lambda m: "ব্যাচ %s বাতিল হয়েছে (%sটি ইউনিট)।" % (m[1], m[2])),
]
_PATTERNS = [(re.compile(p), f) for p, f in PATTERNS]

_DATE_RX = re.compile(r"\b(\d{1,2}) (%s)(?: (\d{4}))?\b" % "|".join(MONTHS))
_UNIT_RX = re.compile(r"(?P<pre>(?<=\d )|(?<=/ )|(?<=per )|(?<=\())(?P<u>%s)\b" % "|".join(sorted(UNITS, key=len, reverse=True)))
_DAYS_RX = re.compile(r"\b(\d+) days?\b")
_KIND_RX = re.compile(r"\b(%s)\b" % "|".join(KIND_BN))
_URG_RX = re.compile(r"^(critical|high|medium)$")


def _general(s):
    """Last-resort replacements inside a string that matched no sentence rule."""
    s = _DATE_RX.sub(lambda m: "%s %s%s" % (m[1], MONTHS[m[2]], (" " + m[3]) if m[3] else ""), s)
    s = _DAYS_RX.sub(lambda m: "%s দিন" % m[1], s)
    s = _UNIT_RX.sub(lambda m: UNITS[m["u"]], s)
    s = re.sub(r"/day\b", "/দিন", s)
    return s


def _partner_line(core):
    """'charity · Ashulia · 01700-000001'"""
    parts = [p.strip() for p in core.split(" · ")]
    if len(parts) == 3 and parts[0].lower() in KIND_BN:
        return " · ".join([KIND_BN[parts[0].lower()], AREA_BN.get(parts[1], parts[1]), parts[2]])
    return None


def tr(text):
    """Translate one piece of visible text (no markup). Returns it unchanged if nothing applies."""
    if not text or not re.search(r"[A-Za-z]", text):
        return bn_digits(text) if text else text
    lead = text[: len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    core = re.sub(r"\s+", " ", text.strip())

    pl = _partner_line(core)
    if pl:
        return lead + bn_digits(pl) + trail
    # product / partner / category names first (longest first), then areas
    named = _NAME_RX.sub(lambda m: _NAMES[m[0]], core)
    named = _AREA_RX.sub(lambda m: AREA_BN[m[1]], named)
    out = None
    for cand in (named, core):
        if cand in EXACT:
            out = EXACT[cand]
            break
        for rx, fn in _PATTERNS:
            m = rx.match(cand)
            if m:
                r = fn(m)
                if r:
                    out = r
                    break
        if out:
            break
    if out is None and " · " in named:                      # "Bakery · B2610-01 · 3 days" etc.
        out = " · ".join(tr(p) for p in named.split(" · "))
    if out is None:
        out = named
    return lead + bn_digits(_general(out)) + trail


# ------------------------------------------------------------------ whole-page translation
_SCRIPT_STYLE = re.compile(r"(?is)(<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>)")
_TEXT = re.compile(r">([^<>]+)<")
_ATTR = re.compile(r'(\s(?:placeholder|title|aria-label|alt|data-hello|data-q|data-search)=)(")([^"]*)(")')
_FILTERS = re.compile(r'(\sdata-filters=")([^"]*)(")')
_DATAF = re.compile(r'\sdata-f-[a-z]+="([^"]*)"')
_JS_STR = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
_LABEL_RX = re.compile(r"^(\d{1,2}) (%s)$|^W-(\d)$|^This wk$" % "|".join(MONTHS))


def _text_node(m):
    raw = m.group(1)
    if not raw.strip():
        return m.group(0)
    return ">" + _html.escape(tr(_html.unescape(raw)), quote=False) + "<"


def _attr(m):
    return m.group(1) + m.group(2) + _html.escape(tr(_html.unescape(m.group(3))), quote=True) + m.group(4)


def _filters(m):
    segs = []
    for seg in m.group(2).split(","):
        k, _, label = seg.partition(":")
        segs.append("%s:%s" % (k, tr(label)) if label else seg)
    return m.group(1) + ",".join(segs) + m.group(3)


def _chart_label(s):
    m = _LABEL_RX.match(s)
    if m:
        if s == "This wk":
            return "এই সপ্তাহ"
        if s.startswith("W-"):
            return bn_digits("সপ্তাহ-%s" % m[3])
        return bn_digits("%s %s" % (m[1], MONTHS[m[2]]))
    if s in WEEKDAYS:
        return WEEKDAYS[s]
    if s in EXACT and len(s) < 40:
        return EXACT[s]
    if s in _NAMES:
        return _NAMES[s]
    return None


def _script(block):
    if block.lower().startswith("<style") or re.search(r"(?i)<script[^>]*\bsrc=", block.split(">", 1)[0] + ">"):
        return block

    def lit(sm):
        try:
            s = json.loads('"%s"' % sm.group(1))
        except ValueError:
            return sm.group(0)
        t = _chart_label(s)
        return json.dumps(t, ensure_ascii=False) if t else sm.group(0)
    return _JS_STR.sub(lit, block)


def translate_html(page):
    """page: rendered HTML (str). Returns the Bangla version."""
    # values shown in the JS-built filter drop-downs (they come from data-f-* attributes)
    vals = {}
    for v in _DATAF.findall(page):
        v = _html.unescape(v)
        t = tr(v)
        if t != v:
            vals[v] = t
    parts = _SCRIPT_STYLE.split(page)
    for i, part in enumerate(parts):
        if i % 2:                                           # script / style block
            parts[i] = _script(part)
        else:
            part = _TEXT.sub(_text_node, part)
            part = _ATTR.sub(_attr, part)
            part = _FILTERS.sub(_filters, part)
            parts[i] = part
    out = "".join(parts)
    out = re.sub(r'<html lang="en"', '<html lang="bn"', out, count=1)
    inject = "<script>window.FWZ_VAL=%s;</script>" % json.dumps(vals, ensure_ascii=False)
    return out.replace("</head>", inject + "</head>", 1) if "</head>" in out else out


def lang_from(request_cookies, session, default="en"):
    v = session.get("lang") or request_cookies.get("fwz_lang") or default
    return v if v in LANGS else default
