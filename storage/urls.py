from django.urls import path
from . import views

urlpatterns = [
    # Main start page
    path('', views.index, name='index'),

    # API endpoints
    path('api/customers/', views.customers_list, name='customers_list'),
    path('api/characteristics/', views.characteristics_list, name='characteristics_list'),
    path('api/demand-models/', views.demand_models_list, name='demand_models_list'),
    path('api/supply-models/', views.supply_models_list, name='supply_models_list'),
    path('api/studies/', views.create_study, name='create_study'),
    path('api/studies/<int:study_id>/process/', views.process_study, name='process_study'),
    path('api/studies/<int:study_id>/analysis/', views.run_analysis, name='run_analysis'),
    path('api/studies/<int:study_id>/boundaries.geojson', views.study_boundaries_geojson, name='study_boundaries_geojson'),
    path('api/studies/<int:study_id>/stores.geojson', views.study_stores_geojson, name='study_stores_geojson'),
    path('api/config/', views.get_config, name='get_config'),
]
