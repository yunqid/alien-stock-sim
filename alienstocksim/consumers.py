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

# Getting the global channel layer
from channels.layers import get_channel_layer


channel_layer = get_channel_layer()

# Maps the stock ticker to the "fake" companies
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
        # Waiting to connect
        await self.accept()
        self.running = True

        # Subscribing to the news feed topic
        await self.channel_layer.group_add("news_feed", self.channel_name)
        StockConsumer.connected_count += 1
        # Start a background task to send headline data only if there isn't one
        if StockConsumer.headline_task == None:
            StockConsumer.headline_task = asyncio.create_task(self.send_headline_data())

        # Filters the cache for datapoint of the current companty
        cache = await asyncio.to_thread(
            lambda: PriceCache.objects.filter(company=TRADE_COMPANY).first()
        )
        if cache and cache.datapoints:
            recent_points = cache.datapoints[-10:] # Gets the last 10 points
            # Send data to frontend
            if recent_points:
                await self.send(text_data=json.dumps({
                    "type": "price_history",
                    "datapoints": recent_points
                }))

        # Get 20 headline from the database
        recent_headlines = await asyncio.to_thread(lambda: list(NewsItem.objects.order_by('id')[:20]))
        recent_headlines.reverse()

        # Send information about the headline
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


    # Disconnecting from the websocket
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("news_feed", self.channel_name)
        StockConsumer.connected_count -= 1
        self.running = False

    # Sending stock data
    async def send_stock_data(self, interval=10):
        # Gets the latest price for each company
        prices = {
            name: await asyncio.to_thread(get_last_price, name)
            for name in COMPANY_MAP.values()
        }

        # Gets the amount of shares left in the last update 
        last_total = await asyncio.to_thread(self._get_total_shares)

        # Gets the percentage change based on real stock data
        # Calculate spreading them across multiple updates
        last_api_call = 0
        ticks_to_spread = 20  # Number of updates to spread
        remaining_pcts = {name: 0.0 for name in COMPANY_MAP.values()}  # Tracks leftover pct to apply

        # Main loop for determining the change in stock price
        while True:
            now = time.time()
            # Only fetch real stock data every 6 hours
            # Pervents rate limiting
            if now - last_api_call >= 21600:
                for symbol, name in COMPANY_MAP.items():
                    try:
                        total_pct = await self.get_stock_price(symbol)
                        # Divide the full change into equal slices
                        # Multiplied so the user can actually see the change
                        remaining_pcts[name] = (total_pct / ticks_to_spread) * 10 
                    except:
                        remaining_pcts[name] = 0 # Just in case we get rate limited
                last_api_call = now

            # Getting the current amount of shares left
            current_total = await asyncio.to_thread(self._get_total_shares)
            delta = {
                name: current_total[name] - last_total.get(name, 0) # Using .get because it's safer for the first iteration
                for name in current_total
            }
            last_total = current_total

            # Cache + send stock changes for each company
            for symbol, name in COMPANY_MAP.items():
                # Noise from [-0.5%, 0.5%]
                noise = random.uniform(-0.005, 0.005)
                # Percent change caused by user action
                holdings_pct = delta[name] * 0.001
                # Percent change caused by the news headline
                news_pct = StockConsumer.news_impact.pop(name, 0)
                # Adding up the total change
                total_pct = remaining_pcts[name] + holdings_pct + noise + news_pct
                # Applying the change to the stock price
                prices[name] = round(prices[name] * (1 + total_pct), 2)
                # Applying a lowercap
                if prices[name] < 10: prices[name] = 10
                print(remaining_pcts[name])
                # Caching the new stock price
                await asyncio.to_thread(self._append_to_cache, name, prices[name])
                await asyncio.to_thread(set_last_price, name, prices[name])

                await channel_layer.group_send(
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
        result = {}
        # Gets the total share for each company
        for symbol, name in COMPANY_MAP.items():
            agg = StockEntry.objects.filter(company=name).aggregate(
                total=Sum("quantity")
            )
            result[name] = agg["total"] or 0
        return result

    # Caches the data
    @staticmethod
    def _append_to_cache(company, price):
        cache, _ = PriceCache.objects.get_or_create(company=company)
        cache.datapoints.append({"t": int(time.time()), "p": int(price * 100)})
        cache.datapoints = cache.datapoints[-20:]  # Keeps only 20 data points
        cache.save()

    # Returns Real Stock Data
    # The api in use if alpha vantage
    async def get_stock_price(self, symbol):
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": "D1PBWCAD52UWQ786"
        }
        response = await asyncio.to_thread(requests.get, url, params=params)
        data = response.json()
        pct_str = data["Global Quote"]["10. change percent"] # We only need the percent change
        return float(pct_str.strip("%"))
    
    # Sends stock price to the frontend
    async def broadcast_price(self, event):
        await self.send(text_data=json.dumps({
            "type": "stock_price",
            "company": event["company"],
            "price": event["price"]
        }))

    # Recieves msgs
    async def receive(self, text_data):
        msg = json.loads(text_data)
        # If the message is switch company, run send_company_cache with the new company
        if msg.get("type") == "switch_company":
            await self.send_company_cache(msg["company"])

    # Sends the datapoints of a specific company
    async def send_company_cache(self, company):
        # Filters the cache
        cache = await asyncio.to_thread(
            lambda: PriceCache.objects.filter(company=company).first()
        )
        if cache and cache.datapoints:
            await self.send(text_data=json.dumps({
                "type": "price_history",
                "datapoints": cache.datapoints[-10:] # Sending the last 10 points
            }))
        else:
            # Send empty history so the chart clears cleanly
            await self.send(text_data=json.dumps({
                "type": "price_history",
                "datapoints": []
            }))

    # Sends the headline
    async def send_headline_data(self):
        while True:
            await asyncio.sleep(60) # Sends a headline from the queue every minute
            try:
                # Generate a new patch of headlines if there isn't one
                if not StockConsumer.headline_queue:
                    print("fetching new headlines")
                    StockConsumer.headline_queue = await asyncio.to_thread(generate_headline_batch)
                    print(f"Batch fetched: {len(StockConsumer.headline_queue)} headlines")

                # Getting the latest headline
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

    # Sending the headline to the frontend
    async def broadcast_headline(self, event):
        await self.send(text_data=json.dumps({
            "type": "news_headline",
            "headline": event["headline"]
        }))
