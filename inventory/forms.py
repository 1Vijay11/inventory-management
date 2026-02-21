from django import forms
from .models import Product, Category, SubCategory

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'
        widgets = {
            'categories': forms.CheckboxSelectMultiple() # just here to make the category select prettier 
        }
 
class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = '__all__'

class SubCategoryForm(forms.ModelForm):
    class Meta:
        model = SubCategory
        fields  = '__all__'