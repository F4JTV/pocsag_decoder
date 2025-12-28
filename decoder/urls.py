# decoder/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('messages/', views.get_messages, name='get_messages'),
    path('status/', views.get_status, name='get_status'),
]
