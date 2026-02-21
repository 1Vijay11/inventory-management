from django.db import models
from django.db.models import CheckConstraint, Q
from django.db.models import Min, Max

# Create your models here.

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    
    def __str__(self):
        return self.name 
class SubCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    @property 
    def total_value(self):
        products = self.products.all() # products being the related name we have in class Product

        total = 0
        for product in products :
            total += product.total_value
        return total
    @property
    def price(self):
        price = self.products.aggregate(min_price=Min("price"))
        return price["min_price"]
    @property
    def sku(self):
        sku = self.products.aggregate(sku=Min("sku"))
        return sku["sku"]
    @property
    def total_stock(self):
        total_stock = 0 
        products = self.products.all()
        for product in products:
            total_stock += product.stock_quantity
        return total_stock
    @property
    def price_display(self):
        prices = self.products.aggregate( # returns dicitionary 
            min_price=Min("price"),
            max_price=Max("price")
        )

        min_price = prices["min_price"] # retrives min a max price from dictionary 
        max_price = prices["max_price"]

        if min_price is None:
            return None  # no products

        if min_price == max_price:
            return min_price

        return f"{min_price} - {max_price}" # shows price range of teh category in case someone give multiple prices 
    def __str__(self):
        return self.name
    
class Product(models.Model):
    sku = models.IntegerField(unique=True)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    stock_quantity = models.IntegerField(default=0)

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

        ]

