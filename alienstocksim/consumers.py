import json
import asyncio
import requests
import random
from channels.generic.websocket import AsyncWebsocketConsumer

class StockConsumer(AsyncWebsocketConsumer):
    # Connecting to the websocket
    async def connect(self):
        await self.accept()
        self.running = True
        asyncio.create_task(self.send_stock_data())

    # Disconnecting to the websocket
    async def disconnect(self, close_code):
        self.running = False

    # Waits for the stock price then send it
    async def send_stock_data(self):
        while self.running:
            price = await self.get_stock_price()
            await self.send(text_data=json.dumps({
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