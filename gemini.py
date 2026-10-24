"""Gemini layer: turns the forecast engine's numbers into plain-language analysis.

The rule-based engine in forecast.py stays the source of truth for every number.
Gemini only reads those numbers and explains / prioritises them, so it cannot invent stock data.
Uses only the standard library (no extra dependency). Fails soft: callers get an error string.
"""
import json
import urllib.error
import urllib.request

import config

URL = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "headline": {"type": "STRING"},
        "summary": {"type": "STRING"},
        "priorities": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "product": {"type": "STRING"}, "action": {"type": "STRING"}, "why": {"type": "STRING"}}}},
        "reorder_advice": {"type": "ARRAY", "items": {"type": "STRING"}},
        "risks": {"type": "ARRAY", "items": {"type": "STRING"}},
        "quick_wins": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["headline", "summary", "priorities", "reorder_advice", "risks", "quick_wins"],
}


def enabled():
    return bool(config.GEMINI_API_KEY)


def analyze(context, timeout=45):
    """context: dict of facts from the forecast engine. Returns (result_dict, error_str)."""
    if not enabled():
        return None, "No GEMINI_API_KEY set. Add it to the .env file and restart."
    prompt = (
        "You are the operations analyst for a grocery shop in Bangladesh (currency ৳) whose goal is zero food waste. "
        "Below is JSON produced by the shop's forecasting engine. Use ONLY these numbers; never invent products or "
        "figures. Give a short, practical analysis for the store manager: what to act on today, which products to "
        "reorder or hold back, risks, and quick wins. Be concise and specific, name products and quantities.\n\n"
        + json.dumps(context, ensure_ascii=False, default=str))
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json",
                                 "responseSchema": SCHEMA}}
    req = urllib.request.Request(
        URL % config.GEMINI_MODEL, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": config.GEMINI_API_KEY})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text), None
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8"))["error"]["message"]
        except Exception:
            msg = e.reason
        return None, "Gemini API error %s: %s" % (e.code, msg)
    except Exception as e:  # network down, bad JSON, blocked response...
        return None, "Could not get an AI analysis (%s)." % e


def chat(system, history, timeout=40):
    """Multi-turn chat. history: [{"role": "user"|"bot", "text": str}, ...] ending with the user's message.
    Returns (reply_text, error_str)."""
    if not enabled():
        return None, "No GEMINI_API_KEY set."
    contents = [{"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["text"]}]} for m in history]
    body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents,
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 900}}
    req = urllib.request.Request(
        URL % config.GEMINI_MODEL, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": config.GEMINI_API_KEY})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts).strip()
        return (text, None) if text else (None, "Empty reply from Gemini.")
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8"))["error"]["message"]
        except Exception:
            msg = e.reason
        return None, "Gemini API error %s: %s" % (e.code, msg)
    except Exception as e:
        return None, "Could not reach Gemini (%s)." % e
