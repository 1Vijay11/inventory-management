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
