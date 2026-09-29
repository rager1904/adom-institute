"""
ASGI config for adom project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'adom.settings')

# get_asgi_application() is what calls django.setup(). It has to run before the
# routing import below, because communication.routing imports consumers, and
# the consumers import model classes. Importing models before the app registry
# is populated raises:
#
#   File "communication/consumers.py", line 4, in <module>
#     from django.contrib.auth.models import AnonymousUser
#   django.core.exceptions.AppRegistryNotReady: Apps aren't loaded yet.
#
# which kills daphne on startup. Calling get_asgi_application() inline as the
# "http" value below happened too late -- the module-level import on the
# preceding line had already run. Setup first, then import, then route.
django_asgi_app = get_asgi_application()

from communication.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                websocket_urlpatterns
            )
        )
    ),
})
