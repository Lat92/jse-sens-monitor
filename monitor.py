import requests, json, re, os
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import yfinance as yf

STATE_FILE = "state.json"
SENS_FEED_URL = "https://www.moneyweb.co.za/tools-and-data/sens/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"seen": []}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def get_sens_links():
    r = requests.get(SENS_FEED_URL, headers=HEADERS)
    soup = BeautifulSoup(r.text, "lxml")
    articles = soup.select(".article-summary a")
    links = ["https://www.moneyweb.co.za" + a['href'] for a in articles if "dealings in securities" in a.text.lower()]
    return links

def parse_sens(url):
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "lxml")
    text = soup.get_text().lower()

    if "dealing in securities" not in text:
        return None

    name_match = re.search(r"name[s]?:\s*(.*?)(\n|$)", text)
    price_match = re.search(r"price[s]?:\s*([0-9.,]+)", text)
    value_match = re.search(r"value[s]?:\s*([0-9.,]+)", text)
    trade_type = "buy" if "purchase" in text or "acquire" in text else "sell"
    on_market = "on-market" if "on market" in text else "off-market"
    scheme = "yes" if "incentive" in text or "scheme" in text else "no"

    return {
        "name": name_match.group(1).strip() if name_match else "Unknown",
        "price": price_match.group(1) if price_match else "Unknown",
        "value": value_match.group(1) if value_match else "Unknown",
        "trade_type": trade_type,
        "on_market": on_market,
        "scheme": scheme,
        "url": url
    }

def get_price_change(ticker):
    try:
        stock = yf.Ticker(ticker + ".JO")
        hist = stock.history(period="1y")
        if hist.empty:
            return {"3m": "N/A", "6m": "N/A", "12m": "N/A"}

        today = hist.index[-1]

        def get_return(days):
            past = today - timedelta(days=days)
            old = hist[hist.index <= past]
            if old.empty:
                return "N/A"
            old_price = old["Close"][-1]
            return f"{round((hist['Close'][-1] - old_price) / old_price * 100, 2)}%"

        return {
            "3m": get_return(90),
            "6m": get_return(180),
            "12m": get_return(365),
        }
    except Exception:
        return {"3m": "N/A", "6m": "N/A", "12m": "N/A"}

def main():
    state = load_state()
    seen = set(state["seen"])
    new_links = [l for l in get_sens_links() if l not in seen]

    for link in new_links:
        data = parse_sens(link)
        if not data:
            continue

        ticker_match = re.search(r"/sens/.*?-(\w+)-", link)
        ticker = ticker_match.group(1) if ticker_match else "Unknown"

        perf = get_price_change(ticker) if ticker != "Unknown" else {"3m": "N/A", "6m": "N/A", "12m": "N/A"}

        print("----------------------------------------------------")
        print(f"📢 Insider Deal Detected")
        print(f"🔗 Link: {link}")
        print(f"👤 Name: {data['name']}")
        print(f"💰 Price: {data['price']}")
        print(f"💸 Value: {data['value']}")
        print(f"📈 Type: {data['trade_type']} ({data['on_market']})")
        print(f"🎯 Incentive scheme? {data['scheme']}")
        print(f"📊 Stock perf (3m/6m/12m): {perf['3m']} / {perf['6m']} / {perf['12m']}")
        print("----------------------------------------------------\n")

        seen.add(link)

    save_state({"seen": list(seen)})

    if not new_links:
        print("✅ No new insider dealings found.")

if __name__ == "__main__":
    main()
