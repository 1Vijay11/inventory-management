from django.urls import path
from .views import home_page, create, product_edit, change_stock
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', home_page, name='home_page'), # mainpage / default path
    path("add/", create, name="product_add"),
    path("edit/<int:sku>/", product_edit, name="product_edit"),
    path("change_stock/<int:sku>/", change_stock, name="change_stock"),

    # AUTH
    path("login/", auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
] 
