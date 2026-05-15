from django.urls import path
from .views import home_page, create, product_edit, change_stock, export_products_csv,signup, update_product_image, update_product_description, add_pattern_file, delete_pattern_file
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', home_page, name='home_page'), # mainpage / default path
    path("add/", create, name="product_add"),
    path("edit/<int:sku>/", product_edit, name="product_edit"),
    path("change_stock/<int:sku>/", change_stock, name="change_stock"),
    path('export-csv/', export_products_csv, name='export_csv'),
    # AUTH
    path("login/", auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    path('signup/', signup, name='signup'),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),

    # ADDING THESE MAY CHANGE LATER 
    path("product/<int:sku>/update-image/", update_product_image, name="update_product_image"),
    path("product/<int:sku>/update-description/", update_product_description, name="update_product_description"),
    path("product/<int:sku>/add-pattern/", add_pattern_file, name="add_pattern_file"),
    path("product/<int:sku>/delete-pattern/<int:pattern_id>/", delete_pattern_file, name="delete_pattern_file"),
] 
