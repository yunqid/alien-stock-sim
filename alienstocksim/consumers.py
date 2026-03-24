import json
import asyncio
import requests
import random
from channels.generic.websocket import AsyncWebsocketConsumer
from alienstocksim.views import generate_headline_batch
from alienstocksim.models import NewsItem
from alienstocksim.pricing import set_last_price, TRADE_COMPANY

class StockConsumer(AsyncWebsocketConsumer):
    connected_count = 0
    headline_task = None
    headline_queue = []
    

    # Connecting to the websocket
    async def connect(self):
        await self.accept()
        self.running = True
        asyncio.create_task(self.send_stock_data())
        await self.channel_layer.group_add("news_feed", self.channel_name)
        StockConsumer.connected_count += 1
        if StockConsumer.headline_task == None:
            StockConsumer.headline_task = asyncio.create_task(self.send_headline_data())

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


    # Disconnecting to the websocket
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("news_feed", self.channel_name)
        StockConsumer.connected_count -= 1
        self.running = False

    # Waits for the stock price then send it
    async def send_stock_data(self):
        while self.running:
            price = await self.get_stock_price()
            await asyncio.to_thread(set_last_price, TRADE_COMPANY, price)
            await self.send(text_data=json.dumps({
                "type": "stock_price", #THIS LINE IS NEW FROM LEYUS CODE - davis
                "price": price
            }))
            await asyncio.sleep(5) # Rate limits how fast data is sent

    # Simulating the stock price
    async def get_stock_price(self):
        await asyncio.sleep(0) 
        return round(random.uniform(150, 200), 2)

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
    #     return data["Global Quote"]["05. price"]

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