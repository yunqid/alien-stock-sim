from django.urls import re_path
from .consumers import StockConsumer

# url of the websocket, must match the one in home.js
websocket_urlpatterns = [
    re_path(r'ws/alienstocksim/$', StockConsumer.as_asgi()),
]