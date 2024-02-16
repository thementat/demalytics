from .views import *
from django.urls import path, include
from google import views as view

urlpatterns = [
   path('',view.home, name="home"),
   path('geocode',view.geocode, name="geocode"),
   path('map',view.map, name="map"),
]