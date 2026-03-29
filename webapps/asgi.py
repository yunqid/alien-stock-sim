"""
ASGI config for webapps project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapps.settings')
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack
import alienstocksim.routing

# Tells the channels what to do based on connection
application = ProtocolTypeRouter({
    "http": get_asgi_application(), # Regular HTTP Requests
    # Websockets are passed through an authentication middleware
    # Then routed to the consumer
    "websocket": AuthMiddlewareStack(
        URLRouter(
            alienstocksim.routing.websocket_urlpatterns
        )
    ),
})