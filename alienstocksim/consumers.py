import json
import asyncio
import requests
import random
import time
from channels.generic.websocket import AsyncWebsocketConsumer
from alienstocksim.views import generate_headline_batch
from alienstocksim.pricing import set_last_price, TRADE_COMPANY, get_last_price
from alienstocksim.models import NewsItem, PriceCache, StockEntry
from django.db.models import Sum

COMPANY_MAP = {
    "AAPL": "Pear",
    "GOOG": "Googlin",
    "FOXA": "Fire Rage Inc.",
    "COST": "BenefitCo",
}

class StockConsumer(AsyncWebsocketConsumer):
    connected_count = 0
    headline_task = None
    stock_task = None
    headline_queue = []
    news_impact = {}

    # Connecting to the websocket
    async def connect(self):
        await self.accept()
        self.running = True
        await self.channel_layer.group_add("news_feed", self.channel_name)
        StockConsumer.connected_count += 1
        if StockConsumer.headline_task == None:
            StockConsumer.headline_task = asyncio.create_task(self.send_headline_data())

        cache = await asyncio.to_thread(
            lambda: PriceCache.objects.filter(company=TRADE_COMPANY).first()
        )
        if cache and cache.datapoints:
            recent_points = cache.datapoints[-10:] # Gets the last 20 points
            if recent_points:
                await self.send(text_data=json.dumps({
                    "type": "price_history",
                    "datapoints": recent_points
                }))

        recent_headlines = await asyncio.to_thread(lambda: list(NewsItem.objects.order_by('id')[:20]))
        recent_headlines.reverse()

        for item in recent_headlines:
            await self.send(text_data=json.dumps({
                "type": "news_headline",
                "headline": {
                    "company": item.company,
                    "headline": item.headline,
                    "blurb": item.blurb,
                    "direction": item.direction,
                    "severity": str(item.severity)
                }
            }))

        # Start the chart
        if StockConsumer.stock_task is None:
            StockConsumer.stock_task = asyncio.create_task(self.send_stock_data())


    # Disconnecting to the websocket
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("news_feed", self.channel_name)
        StockConsumer.connected_count -= 1
        self.running = False

    async def send_stock_data(self, interval=5):
        prices = {
            name: await asyncio.to_thread(get_last_price, name)
            for name in COMPANY_MAP.values()
        }
        last_total = await asyncio.to_thread(self._get_total_shares)
        last_api_call = 0
        ticks_to_spread = 20  # spread the API change over this many ticks
        remaining_pcts = {name: 0.0 for name in COMPANY_MAP.values()}  # tracks leftover pct to apply

        while True:
            now = time.time()
            if now - last_api_call >= 21600:
                for symbol, name in COMPANY_MAP.items():
                    try:
                        total_pct = await self.get_stock_price(symbol)
                        # Divide the full change into equal slices
                        # Multiplied so the user can actually see the change
                        remaining_pcts[name] = total_pct / ticks_to_spread 
                    except:
                        remaining_pcts[name] = 0
                last_api_call = now

            current_total = await asyncio.to_thread(self._get_total_shares)
            delta = current_total - last_total
            last_total = current_total

            for symbol, name in COMPANY_MAP.items():
                noise = random.uniform(-0.005, 0.005)
                holdings_pct = (delta * 0.001) if name == TRADE_COMPANY else 0
                news_pct = StockConsumer.news_impact.pop(name, 0)
                total_pct = remaining_pcts[name] + holdings_pct + noise + news_pct
                prices[name] = round(prices[name] * (1 + total_pct), 2)

                print(news_pct)

                await asyncio.to_thread(self._append_to_cache, name, prices[name])
                await asyncio.to_thread(set_last_price, name, prices[name])
                await self.channel_layer.group_send(
                    "news_feed",
                    {
                        "type": "broadcast_price",
                        "company": name,
                        "price": prices[name]
                    }
                )

            await asyncio.sleep(interval)

    # Gets the total number of shares held
    @staticmethod
    def _get_total_shares():
        result = StockEntry.objects.filter(company=TRADE_COMPANY).aggregate(
            total=Sum("quantity")
        )
        return result["total"] or 0

    # Gets the data to the cache
    @staticmethod
    def _append_to_cache(company, price):
        cache, _ = PriceCache.objects.get_or_create(company=company)
        cache.datapoints.append({"t": int(time.time()), "p": int(price * 100)})
        cache.datapoints = cache.datapoints[-20:]  # Keeps only 20 data points
        cache.save()

    # Returns Real Stock Data
    async def get_stock_price(self, symbol):
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": "D1PBWCAD52UWQ786"
        }
        response = await asyncio.to_thread(requests.get, url, params=params)
        data = response.json()
        pct_str = data["Global Quote"]["10. change percent"]
        return float(pct_str.strip("%"))
    
    async def broadcast_price(self, event):
        await self.send(text_data=json.dumps({
            "type": "stock_price",
            "company": event["company"],
            "price": event["price"]
        }))

    async def receive(self, text_data):
        msg = json.loads(text_data)
        if msg.get("type") == "switch_company":
            await self.send_company_cache(msg["company"])

    async def send_company_cache(self, company):
        cache = await asyncio.to_thread(
            lambda: PriceCache.objects.filter(company=company).first()
        )
        if cache and cache.datapoints:
            await self.send(text_data=json.dumps({
                "type": "price_history",
                "datapoints": cache.datapoints[-10:]
            }))
        else:
            # Send empty history so the chart clears cleanly
            await self.send(text_data=json.dumps({
                "type": "price_history",
                "datapoints": []
            }))

    async def send_headline_data(self):
        while True:
            await asyncio.sleep(60)
            try:
                if not StockConsumer.headline_queue:
                    print("fetching new headlines")
                    StockConsumer.headline_queue = await asyncio.to_thread(generate_headline_batch)
                    print(f"Batch fetched: {len(StockConsumer.headline_queue)} headlines")

                headline = StockConsumer.headline_queue.pop()

                # Calculating the impact of the headline
                impact_value = {1: 0.05, 2: 0.1, 3: 0.2}.get(int(headline["severity"]), 0)
                impact_value = impact_value if headline["direction"] == "up" else -impact_value
                StockConsumer.news_impact[headline["company"]] = impact_value

                newHeadline = NewsItem(
                    company=headline["company"],
                    headline=headline["headline"],
                    blurb=headline["blurb"],
                    direction=headline["direction"],
                    severity=int(headline["severity"])
                )

                await asyncio.to_thread(newHeadline.save)

                await self.channel_layer.group_send(
                    "news_feed",
                    {
                        "type": "broadcast_headline",
                        "headline": headline
                    }
                )
                print("Headline sent:", headline)
            except Exception as e:
                print(f"Headline generation failed with error: {e}")
                #pray we dont get here...

    async def broadcast_headline(self, event):
        await self.send(text_data=json.dumps({
            "type": "news_headline",
            "headline": event["headline"]
        }))