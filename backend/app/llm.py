"""
LLM service (Groq API, OpenAI-compatible — model: openai/gpt-oss-120b).

PRD §7 — the LLM handles:
  transaction understanding, merchant extraction, categorization,
  ambiguous interpretations, pattern analysis, anomaly ID, forecast,
  recommendations, natural-language explanations.

PRD §8 — numbers are computed in Python/SQL; the LLM only *reasons*
over the summaries we send it.

If GROQ_API_KEY is empty and LLM_FALLBACK_TO_RULES=True, a deterministic
rule-based parser is used so the app works offline (great for demos).
"""
import json
import re
import httpx

from .config import settings
from .schemas import CATEGORIES

CATEGORY_LIST = ", ".join(CATEGORIES)

PARSE_SYSTEM = f"""You are an expense parser for an Indian spending tracker.
Given a raw transaction description (often messy UPI/bank text) and amount,
extract:
- merchant: short clean merchant name (e.g. "Uber", "Swiggy", "Amazon", "IRCTC")
- category: exactly ONE of [{CATEGORY_LIST}]
- amount: the numeric amount passed in

Category hints:
Food: swiggy, zomato, restaurant, cafe, dhaba, pizza, biryani
Transportation: uber, ola, rapido, metro, petrol, fastag, parking
Shopping: amazon, flipkart, myntra, decathlon, dmarts, reliance retail
Bills: electricity, water, gas, mobile recharge, jio, airtel, broadband, rent, emi
Entertainment: bookmyshow, pvr, inox, netflix, spotify, hotstar, games
Healthcare: apollo, pharmacy, doctor, hospital, medplus, lab
Education: udemy, coursera, college fees, books, byjus
Travel: irctc, indigo, spicejet, makemytrip, oyo, hotel, flight
Investment: zerodha, groww, sip, mutual fund, stocks, nps
Other: anything unclear, transfers, atm, cash withdrawal

Reply with ONLY valid JSON: {{"merchant": "...", "category": "...", "amount": <number>}}"""

INSIGHT_SYSTEM = """You are a friendly personal-finance analyst for Indian users.
You receive PRE-COMPUTED spending summaries (totals, category breakdowns,
monthly trends, top merchants). Never recompute precise sums — use the numbers given.
Reply with ONLY valid JSON, no markdown fences, no prose, exactly this shape:
{"bullets": [{"title": "<2-4 word heading>", "text": "<one concise line, ₹ for amounts>"}]}
Write 4-6 bullets covering: overall pattern / month-over-month change, largest
categories and drivers, any unusual spike or drop, one practical saving suggestion.
Rules: never suggest cutting healthcare/pharmacy spending. Routine monthly
subscriptions (Netflix etc.) are normal — do not call them wasteful."""


def _has_key() -> bool:
    key = (settings.GROQ_API_KEY or "").strip()
    if not key:
        return False
    lowered = key.lower()
    # Reject untouched placeholders from .env.example
    return not any(p in lowered for p in ("your-", "changeme", "here", "paste-"))


def _upstream_error_detail(resp: httpx.Response) -> str:
    """Extract the human-readable error message from a Groq error response."""
    try:
        data = resp.json()
        err = data.get("error", data)
        if isinstance(err, dict):
            return str(err.get("message", resp.text))[:300]
        return str(err)[:300]
    except Exception:
        return (resp.text or "no response body")[:300]


def _chat(messages: list[dict], temperature: float = 0.3, max_tokens: int = 800) -> str:
    """Call Groq chat-completions endpoint (OpenAI-compatible)."""
    url = settings.GROQ_BASE_URL.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=settings.GROQ_TIMEOUT) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        detail = _upstream_error_detail(e.response)
        if status == 401:
            raise RuntimeError(
                "Groq error 401 (invalid API key). Check GROQ_API_KEY in .env — "
                "get a key at https://console.groq.com/keys (starts with 'gsk_')."
            )
        if status == 404:
            raise RuntimeError(
                f"Groq error 404 (model not found: '{settings.GROQ_MODEL}'). "
                f"Upstream: {detail} Check active model IDs at https://console.groq.com/docs/models "
                "or via GET /openai/v1/models."
            )
        if status == 429:
            raise RuntimeError(
                f"Groq error 429 (rate limit — free tier is RPM/TPD capped). {detail} "
                "Wait a minute and retry."
            )
        raise RuntimeError(f"Groq error {status}: {detail}")
    except httpx.TimeoutException:
        raise RuntimeError(f"Groq request timed out after {settings.GROQ_TIMEOUT}s. Retry once.")
    except httpx.RequestError as e:
        raise RuntimeError(f"Could not reach Groq API ({e}). Check internet / GROQ_BASE_URL.")
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(f"Unexpected Groq response shape: {str(data)[:300]}")


def _chat_json(messages: list[dict], temperature: float = 0.4, max_tokens: int = 800) -> tuple[dict | None, str]:
    """Chat + extract the first {...} JSON block.

    Returns (parsed_dict_or_None, raw_text). API errors still raise;
    a non-JSON reply returns (None, raw) so callers can degrade gracefully.
    """
    raw = _chat(messages, temperature=temperature, max_tokens=max_tokens)
    fenced = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    m = re.search(r"\{.*\}", fenced, flags=re.DOTALL)
    try:
        data = json.loads(m.group(0) if m else fenced)
    except json.JSONDecodeError:
        return None, raw
    return (data if isinstance(data, dict) else None), raw


# ---------------------------------------------------------------- rule fallback
_RULES: list[tuple[str, str, str]] = [
    # (keyword regex, merchant, category)
    (r"uber|ola|rapido|metro|fastag|petrol|fuel|parking|cab", "Uber" , "Transportation"),
    (r"swiggy|zomato|dominos|pizza|biryani|cafe|restaurant|dhaba|food", "Swiggy", "Food"),
    (r"amazon|flipkart|myntra|decathlon|dmart|reliance|mall|store|shopping", "Amazon", "Shopping"),
    (r"electricity|water bill|gas bill|recharge|jio|airtel|broadband|rent|emi|bill", "Bills", "Bills"),
    (r"bookmyshow|pvr|inox|netflix|spotify|hotstar|movie|game|concert", "BookMyShow", "Entertainment"),
    (r"apollo|pharmacy|doctor|hospital|medplus|clinic|lab|medicine", "Apollo Pharmacy", "Healthcare"),
    (r"udemy|coursera|college|school|fees|books|tuition|course", "Udemy", "Education"),
    (r"irctc|indigo|spicejet|makemytrip|oyo|hotel|flight|train|travel|trip", "IRCTC", "Travel"),
    (r"zerodha|groww|sip|mutual|stock|nps|invest", "Zerodha", "Investment"),
]


def rule_based_parse(description: str, amount: float) -> dict:
    text = (description or "").lower()
    for pattern, merchant, category in _RULES:
        if re.search(pattern, text):
            # Try to pick a nicer merchant from the raw text
            m = re.search(r"(uber|ola|swiggy|zomato|amazon|flipkart|irctc|netflix|apollo|zerodha|jio|airtel|pvr|indigo|oyo|myntra)",
                          text)
            if m:
                merchant = m.group(1).capitalize()
                if merchant == "Irctc":
                    merchant = "IRCTC"
                if merchant == "Pvr":
                    merchant = "PVR"
            return {"merchant": merchant, "category": category, "amount": amount}
    # Unknown → prettify first token as merchant
    first = re.split(r"[-_\s/]+", (description or "Unknown").strip())
    merchant = first[1].capitalize() if len(first) > 1 and first[0].upper() == "UPI" else first[0].capitalize()
    return {"merchant": merchant[:30] or "Unknown", "category": "Other", "amount": amount}


# ---------------------------------------------------------------- public API
def parse_transaction(description: str, amount: float) -> dict:
    """PRD §4B/4C — LLM extracts merchant + category. Falls back to rules offline."""
    if not _has_key():
        if settings.LLM_FALLBACK_TO_RULES:
            return rule_based_parse(description, amount)
        raise RuntimeError("GROQ_API_KEY is not set. Add it to .env (see .env.example).")

    raw = _chat(
        [
            {"role": "system", "content": PARSE_SYSTEM},
            {"role": "user", "content": f"Description: {description}\nAmount: {amount}"},
        ],
        temperature=0.1,
        max_tokens=200,
    )
    # gpt-oss is a reasoning model: it may wrap JSON in fences or prose,
    # so extract the first {...} block instead of parsing the raw reply.
    fenced = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    m = re.search(r"\{.*\}", fenced, flags=re.DOTALL)
    try:
        data = json.loads(m.group(0) if m else fenced)
    except json.JSONDecodeError:
        return rule_based_parse(description, amount)

    category = str(data.get("category", "Other")).strip().capitalize()
    # Normalise to allowed list
    match = next((c for c in CATEGORIES if c.lower() == category.lower()), "Other")
    return {
        "merchant": str(data.get("merchant", "Unknown"))[:60] or "Unknown",
        "category": match,
        "amount": float(data.get("amount", amount) or amount),
    }


def generate_spending_insights(summary_text: str) -> dict:
    """PRD §4E — LLM reasons over pre-computed summary stats.

    Returns {"bullets": [{"title": str, "text": str}, ...]} for card rendering.
    """
    if not _has_key():
        if settings.LLM_FALLBACK_TO_RULES:
            return {"bullets": [
                {"title": "Offline mode",
                 "text": "Add GROQ_API_KEY to .env for AI insights. Meanwhile: cap your largest category with a monthly budget."},
                {"title": "Your summary", "text": summary_text.replace("\n", " ")[:400]},
            ]}
        raise RuntimeError("GROQ_API_KEY is not set.")
    data, raw = _chat_json(
        [
            {"role": "system", "content": INSIGHT_SYSTEM},
            {"role": "user", "content": f"Here is the user's pre-computed spending summary:\n{summary_text}\n\nGive insights."},
        ],
        temperature=0.5,
    )
    bullets = (data or {}).get("bullets")
    if not isinstance(bullets, list) or not bullets:
        return {"bullets": [{"title": "Overview", "text": raw[:800]}]}
    clean = [
        {"title": str(b.get("title", "Insight"))[:40], "text": str(b.get("text", ""))[:400]}
        for b in bullets if isinstance(b, dict) and b.get("text")
    ][:8]
    return {"bullets": clean or [{"title": "Overview", "text": raw[:800]}]}


def detect_anomalies(summary_text: str) -> dict:
    """PRD §4F — LLM flags unusual transactions from stats (no ML training).

    Returns {"flagged": [{"transaction": str, "reason": str}], "note": str}
    for table rendering.
    """
    if not _has_key():
        return {"flagged": [], "note": "(Offline mode) Anomaly detection needs GROQ_API_KEY. Heuristic: any transaction > 3× your average is worth reviewing."}
    data, raw = _chat_json(
        [
            {"role": "system", "content": (
                "You are a fraud-aware spending analyst. Given transaction stats and recent "
                "transactions, reply with ONLY valid JSON, no markdown fences, exactly:\n"
                '{"flagged": [{"transaction": "<amount – merchant (category)>", "reason": "<why, cite the >3x rule>"}], '
                '"note": "<one closing line>"}\n'
                "Flag ONLY genuine outliers: a single transaction >3x the user's average or "
                ">3x that category's typical spend. Do NOT flag routine monthly bills, standard "
                "subscriptions, or small everyday purchases. Do NOT allege duplicates without "
                "evidence (same merchant + same amount + same/adjacent date). If nothing is "
                'unusual: {"flagged": [], "note": "<say so plainly>"}. Use ₹.'
            )},
            {"role": "user", "content": summary_text},
        ],
        temperature=0.3,
    )
    flagged = (data or {}).get("flagged")
    if not isinstance(flagged, list):
        return {"flagged": [], "note": raw[:800]}
    clean = [
        {"transaction": str(f.get("transaction", ""))[:80], "reason": str(f.get("reason", ""))[:200]}
        for f in flagged if isinstance(f, dict) and f.get("transaction")
    ][:10]
    note = str((data or {}).get("note", ""))[:400] or "All other transactions fall within normal ranges."
    return {"flagged": clean, "note": note}


def forecast_spending(monthly_text: str) -> dict:
    """PRD §4G — AI estimate of next month's range from monthly totals.

    Returns {"baseline_low": float|None, "baseline_high": float|None,
             "one_off": str, "reasoning": str} for hero-card rendering.
    """
    if not _has_key():
        return {"baseline_low": None, "baseline_high": None, "one_off": "",
                "reasoning": "(Offline mode) Forecast needs GROQ_API_KEY. Rough estimate: expect next month ≈ average of last 3 months."}
    data, raw = _chat_json(
        [
            {"role": "system", "content": (
                "You estimate next month's RECURRING baseline spending from past monthly totals. "
                "Reply with ONLY valid JSON, no markdown fences, exactly: "
                '{"baseline_low": <number INR>, "baseline_high": <number INR>, '
                '"one_off": "<month + amount + likely cause, or empty string>", '
                '"reasoning": "<max 2 lines>"}. '
                "Steps: 1) spot one-off spikes (a month inflated by single purchases >3x the "
                "average, e.g. a phone/laptop) and EXCLUDE them to find the true monthly baseline; "
                "2) give the baseline as a range; 3) name the one-offs separately. "
                "Never forecast by blindly averaging a normal month with a spike month. "
                "This is an AI estimate, not financial advice."
            )},
            {"role": "user", "content": f"Monthly totals:\n{monthly_text}"},
        ],
        temperature=0.4,
    )
    try:
        low = float((data or {})["baseline_low"])
        high = float((data or {})["baseline_high"])
    except (KeyError, TypeError, ValueError):
        return {"baseline_low": None, "baseline_high": None, "one_off": "", "reasoning": raw[:600]}
    return {"baseline_low": low, "baseline_high": high,
            "one_off": str((data or {}).get("one_off", ""))[:300],
            "reasoning": str((data or {}).get("reasoning", ""))[:600]}
