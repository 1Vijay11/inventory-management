from django.urls import path
from .views import (
    home_page, create, product_edit, change_stock, export_products_csv, edit_category, edit_subcategory,sale_edit,
    signup, market_dashboard, market_start, market_end,market_detail,
    sale_new, sale_add_item, sale_remove_item, sale_complete
)
from django.contrib.auth import views as auth_views


urlpatterns = [
    path("", home_page, name="home_page"),
    path("add/", create, name="product_add"),
    path("edit/<int:sku>/", product_edit, name="product_edit"),
    path("change_stock/<int:sku>/", change_stock, name="change_stock"),
    path("export-csv/", export_products_csv, name="export_csv"),
    path("edit-category/<int:cat_id>/", edit_category, name="edit_category"),
    path("edit-subcategory/<int:sub_id>/", edit_subcategory, name="edit_subcategory"),

    #Market mode
    path("market", market_dashboard, name="market_dashboard"),
    path("market/start", market_start, name= "market_start"),
    path("market/end/<int:market_id>/", market_end, name = "market_end"),

    path("market/sale/new/", sale_new, name="sale_new"),
    path("market/sale/add/<int:sku>/", sale_add_item, name="sale_add_item"),
    path("market/sale/remove/<int:cart_item_id>/", sale_remove_item, name="sale_remove_item"),
    path("market/sale/complete/", sale_complete, name="sale_complete"),

    path("market/<int:market_id>/", market_detail, name="market_detail"),
    path("market/sale/<int:sale_id>/edit/", sale_edit, name="sale_edit"),

    # AUTH
    path("login/", auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    path("signup/", signup, name="signup"),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
]
