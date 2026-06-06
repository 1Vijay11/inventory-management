from django.contrib import admin
from .models import Product, Category, SubCategory

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

@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    search_fields = ('name',)

# =================================
#     Market Mode Backend
# =================================
from .models import Market, Sale, SaleItem, Cart, CartItem,StockSnapshot, MarketExpense

@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'is_active', 'started_at', 'ended_at')

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'market', 'payment_method', 'subtotal', 'discount_amount', 'tip_amount', 'total', 'created_at')

@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ('product_name_snapshot', 'product_sku_snapshot', 'unit_price_snapshot', 'quantity', 'line_total')

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'market', 'user', 'created_at')
@admin.register(CartItem)
class CartAdmin(admin.ModelAdmin):
    list_display = ('cart', 'product', 'quantity')

@admin.register(StockSnapshot)
class StockSnapshotAdmin(admin.ModelAdmin):
    list_display = ('product_name_snapshot', 'product_sku_snapshot', 'stock_at_start', 'market')

@admin.register(MarketExpense)
class MarketExpenseAdmin(admin.ModelAdmin):
    list_display = ('description', 'amount', 'market', 'created_at')