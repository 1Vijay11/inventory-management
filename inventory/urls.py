from django.urls import path
from .views import home_page, product_create, product_edit, category_create

urlpatterns = [
    path('', home_page, name='home_page'), # mainpage / default path
    path("add/", product_create, name="product_add"),
    path("edit/<int:pk>/", product_edit, name="product_edit"),
    path("add-category/", category_create, name = "category_create")
]
