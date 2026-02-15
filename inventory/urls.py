from django.urls import path
from .views import home_page, create, product_edit, change_stock
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', home_page, name='home_page'), # mainpage / default path
    path("add/", create, name="product_add"),
    path("edit/<int:sku>/", product_edit, name="product_edit"),
    path("change_stock/<int:sku>/", change_stock, name="change_stock")
] 
