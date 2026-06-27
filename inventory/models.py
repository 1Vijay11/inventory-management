from django.db import models
from django.db.models import CheckConstraint, Q
from django.db.models import Q, Max, Min, Sum, F  # advanced queries, aggregations, and field operations
from django.contrib.auth.models import User
# Create your models here.

class Category(models.Model):
    name = models.CharField(max_length=100)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    class Meta:
        unique_together = ('user', 'name')
        ordering = ['name']  
    def __str__(self):
        return self.name 
class SubCategory(models.Model):
    name = models.CharField(max_length=100)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    class Meta:
        unique_together = ('user', 'name')
    @property 
    def total_value(self):
        from django.db.models import Sum, F
        result = self.products.filter(
            user=self.user, 
            discontinued=False
        ).aggregate(
            total=Sum(F('price') * F('stock_quantity'))
        )['total']
        return result or 0

    @property
    def price(self):
        return self.products.filter(user=self.user).aggregate(
            min_price=Min("price")
        )["min_price"]

    @property
    def sku(self):
        return self.products.filter(user=self.user).aggregate(
            sku=Min("sku")
        )["sku"] or 0

    @property
    def total_stock(self):
        return self.products.filter(
            user=self.user,
            discontinued=False
        ).aggregate(
            total=Sum('stock_quantity')
        )['total'] or 0

    @property
    def price_display(self):
        prices = self.products.filter(user=self.user).aggregate(
            min_price=Min("price"),
            max_price=Max("price")
        )

        min_price = prices["min_price"]
        max_price = prices["max_price"]

        if min_price is None:
            return None

        if min_price == max_price:
            return min_price

        return f"{min_price} - {max_price}"
    def __str__(self):
        return self.name
    
def product_image_path(instance, filename):
    return f'products/{instance.user.id}/{instance.sku}/image/{filename}'

def product_pattern_path(instance, filename):
    return f'products/{instance.product.user.id}/{instance.product.sku}/patterns/{filename}'

class Product(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)

    sku = models.IntegerField()
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    stock_quantity = models.IntegerField(default=0)
    discontinued = models.BooleanField(default=False) # items just being added are normally not discontinued

    #for the editpage info
    image = models.ImageField(upload_to=product_image_path, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    patternDescription = models.TextField(null=True, blank=True)

    # creating a many to many relationship, blank = true => alows products to have no category
    categories = models.ManyToManyField(Category, blank=True, related_name="products")

    #creating many to 1 relationship with sub category
    subCategory = models.ForeignKey(SubCategory, on_delete=models.CASCADE, related_name="products", blank=True, null=True)

    #adding derived values below
    @property 
    def total_value(self):
        return self.price * self.stock_quantity

    def __str__(self): # here for when your trying to treat product like a string, {{ product }} would return { name sku }
        return f"{self.name} ({self.sku})"
    
    class Meta :
        constraints = [
            CheckConstraint(condition=Q(price__gte=0), name="price_must_be_gte_0"),
            CheckConstraint(condition=Q(stock_quantity__gte=0), name="stock_must_be_gte_0"),
            CheckConstraint(condition=Q(sku__gte=0), name="sku_must_be_gte_0"),
        ]
        unique_together = ('user', 'sku')

class PatternFile(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='patterns')
    file = models.FileField(upload_to=product_pattern_path, null=True, blank=True)
    url = models.URLField(max_length=500, null=True, blank=True)
    name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_link(self):
        return bool(self.url)

    def __str__(self):
        return self.name


# ===============================================================
#           Phase 2 - Market Mode Backend Models
# ===============================================================
class Market(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Ended'})"

    class Meta:
        ordering = ['-started_at']


class Sale(models.Model):
    PAYMENT_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Card'),
    ]
    CUSTOMER_CHOICES = [
        ('child', 'Child'),
        ('teen', 'Teen'),
        ('young_adult', 'Young Adult'),
        ('adult', 'Adult'),
    ]
    market = models.ForeignKey(Market, on_delete=models.CASCADE, related_name='sales')
    created_at = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES)
    subtotal = models.DecimalField(max_digits=8, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    tip_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=8, decimal_places=2)
    customer_type = models.CharField(max_length=15, choices=CUSTOMER_CHOICES, default='young_adult')
    def __str__(self):
        return f"Sale #{self.id} — {self.market.name} (${self.total})"

    class Meta:
        ordering = ['-created_at']


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL, related_name='sale_items')

    # Historical snapshots — these never change after the sale is recorded
    product_name_snapshot = models.CharField(max_length=255)
    product_sku_snapshot = models.IntegerField()
    unit_price_snapshot = models.DecimalField(max_digits=6, decimal_places=2)

    quantity = models.IntegerField()
    line_total = models.DecimalField(max_digits=8, decimal_places=2)  # stored, not computed

    def __str__(self):
        return f"{self.product_name_snapshot} x{self.quantity} @ ${self.unit_price_snapshot}"
    
class Cart(models.Model):
    market = models.ForeignKey(Market, on_delete=models.CASCADE, related_name='cart')
    user = models.ForeignKey( User, on_delete=models.CASCADE )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Cart For {self.market.name}"
    
    @property
    def subtotal(self):
        return sum(item.line_total for item in self.cart_items.all())
    
class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='cart_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)

    @property
    def line_total(self):
        return self.product.price * self.quantity
    
    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
class StockSnapshot(models.Model):
    # must use a stocksnap shot at the start of the market so we can cross reference stock sold to intial stock - display populat items sold by percentage
    market = models.ForeignKey(Market, on_delete=models.CASCADE, related_name='stock_snapshots')
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL)
    product_name_snapshot = models.CharField(max_length=255)
    product_sku_snapshot = models.IntegerField()
    stock_at_start = models.IntegerField()

    def __str__(self):
        return f"{self.product_name_snapshot} — {self.stock_at_start} at start"

    class Meta:
        unique_together = ('market', 'product')


class MarketExpense(models.Model):
    market = models.ForeignKey(Market, on_delete=models.CASCADE, related_name='expenses')
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.description} — ${self.amount}"

    class Meta:
        ordering = ['created_at']