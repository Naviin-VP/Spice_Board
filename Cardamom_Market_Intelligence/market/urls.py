from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("api/auction-data/", views.auction_data_api, name="auction_data_api"),
    path("api/auction-records/", views.auction_records_api, name="auction_records_api"),
    path("api/market-insights/", views.market_insights_api, name="market_insights_api"),
    path("api/forecast/", views.forecast_api, name="forecast_api"),
    path("api/export-intelligence/", views.export_intelligence_api, name="export_intelligence_api"),
    path("api/market-analytics/", views.market_analytics_api, name="market_analytics_api"),
]
