from django.db import models

# Create your models here.

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    
    def __str__(self):
        return self.name
    

class Product(models.Model):
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    stock_quantity = models.IntegerField()

    # creating a many to many relationship, blank = true => alows products to have no category
    categories = models.ManyToManyField(Category, blank=True, related_name="products")

    #adding derived values below
    @property 
    def total_value(self):
        return self.price * self.stock_quantity

    def __str__(self): # here for when your trying to treat product like a string, {{ product }} would return { name sku }
        return f"{self.name} ({self.sku})"
    

