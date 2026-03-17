import json
import asyncio
import aiohttp
import random
from channels.generic.websocket import AsyncWebsocketConsumer

class StockConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.running = True
        asyncio.create_task(self.send_stock_data())

    async def disconnect(self, close_code):
        self.running = False

    async def send_stock_data(self):
        while self.running:
            price = await self.get_stock_price()
            await self.send(text_data=json.dumps({
                "price": price
            }))
            await asyncio.sleep(1)

    async def get_stock_price(self):
        await asyncio.sleep(0) 
        return round(random.uniform(150, 200), 2)

    # Note don't know if this works yet since the api is rate limited
    # Will test again past midnight tonight
    # async def get_stock_price(self):
    #     url = "https://www.alphavantage.co/query"
    #     params = {
    #         "function": "GLOBAL_QUOTE",
    #         "symbol": "AAPL",
    #         "apikey": "D1PBWCAD52UWQ786"
    #     }
    #     response = aiohttp.get(url, params=params)
    #     data = response.json()
    #     return data["Global Quote"]["05. price"]