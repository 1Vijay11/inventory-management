from django.db import models
from django.db.models import CheckConstraint, Q
# Create your models here.

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    
    def __str__(self):
        return self.name
    

class Product(models.Model):
    sku = models.IntegerField(unique=True)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=4, decimal_places=2)
    stock_quantity = models.IntegerField(default=0)

    # creating a many to many relationship, blank = true => alows products to have no category
    categories = models.ManyToManyField(Category, blank=True, related_name="products")

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
