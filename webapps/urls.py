"""
URL configuration for webapps project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from alienstocksim import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.landing_action, name='landing'),
    path('home', views.home_action, name='home'),
    path('profile', views.profile_action, name='profile'),
    path('profile/<str:username>', views.profile_action, name='profile_user'),
    path('follow/', views.follow_toggle, name='follow_toggle'),
    path('messages/', views.messages_inbox, name='messages_inbox'),
    path('messages/<str:username>/', views.messages_thread, name='messages_thread'),
    path("trade/", views.trade_stock, name="trade_stock"),
    path("stock_stats/<str:company>/", views.stock_stats, name="stock_stats"),
    path("user_stats/<str:company>/", views.user_stats, name="user_stats"),
    path("api/leaderboard/", views.leaderboard_api, name="leaderboard_api"),
    path("accounts/", include('allauth.urls')),
    path('sw.js', views.serve_sw, name='sw'),
    path('unread_messages/', views.unread_message_count, name='unread_messages'),
    path('messages/<str:username>/poll/', views.messages_thread_poll, name='messages_thread_poll'),
]
