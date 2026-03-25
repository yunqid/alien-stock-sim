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

class StockConsumer(AsyncWebsocketConsumer):
    connected_count = 0
    headline_task = None
    headline_queue = []

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
        asyncio.create_task(self.send_stock_data())


    # Disconnecting to the websocket
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("news_feed", self.channel_name)
        StockConsumer.connected_count -= 1
        self.running = False

    # Calculates the stock
    async def send_stock_data(self, interval=5):
        price = await asyncio.to_thread(get_last_price, TRADE_COMPANY)
        last_total = await asyncio.to_thread(self._get_total_shares)
        last_api_call = 0  # Timestamp of last API call

        while self.running:
            # Get the actual change in stock
            api_pct = 0
            # Rate limits the amount of time the api is called
            now = time.time()
            if now - last_api_call >= 10: # Change the value here to adjust frequency
                api_pct = await self.get_stock_price()
                last_api_call = now

            # Predicted change from change in shares held
            current_total = await asyncio.to_thread(self._get_total_shares)
            delta = current_total - last_total
            last_total = current_total
            holdings_pct = delta * 0.001

            # Combine the pcts
            # Adjust total_pct for more sophisticated calculations
            total_pct = (api_pct / 100) + holdings_pct
            price = round(price * (1 + total_pct), 2)

            # Adding data to both caches
            await asyncio.to_thread(self._append_to_cache, TRADE_COMPANY, price)
            await asyncio.to_thread(set_last_price, TRADE_COMPANY, price)
            await self.send(text_data=json.dumps({
                "type": "stock_price",
                "company": TRADE_COMPANY,
                "price": price
            }))

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

    # Simulating the stock price
    async def get_stock_price(self):
        await asyncio.sleep(0) 
        return round(random.uniform(-10, 10), 2)

    # This works now
    # async def get_stock_price(self):
    #     url = "https://www.alphavantage.co/query"
    #     params = {
    #         "function": "GLOBAL_QUOTE",
    #         "symbol": "AAPL",
    #         "apikey": "D1PBWCAD52UWQ786"
    #     }
    #     response = requests.get(url, params=params)
    #     data = response.json()
    #     pct_str = data["Global Quote"]["10. change percent"]
    #     return float(pct_str.strip("%"))

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