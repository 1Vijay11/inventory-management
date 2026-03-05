from django import forms
from .models import Product, Category, SubCategory

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'
        widgets = {
            'categories': forms.CheckboxSelectMultiple(), # just here to make the category select prettier ,
        }
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if len(name) < 3:
            raise forms.ValidationError("Company name must be at least 3 characters long.")
        return name
    def clean_stock(self):  # CURENTLY DOESNT WORK PLEASE FIX LATER
        stock = self.cleaned_data.get('stock_quantity')
        if int(stock) < 0 :
            raise forms.ValidationError("Stock Most Be greater than 0")
        return stock
    def clean_price(self):
        price = self.cleaned_data.get('price')
        if float(price) < 0 :
            raise forms.ValidationError("price must be greater then 0")
        return price
class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = '__all__'
class SubCategoryForm(forms.ModelForm):
    class Meta:
        model = SubCategory
        fields  = '__all__'