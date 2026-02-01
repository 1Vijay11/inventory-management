from django.contrib import admin
from .models import Product, Category

# Register your models here.
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('sku', 'name', 'price', 'stock_quantity')
    search_fields = ('sku', 'name')
    list_editable = ('price', 'stock_quantity')
    filter_horizontal = ('categories',)

