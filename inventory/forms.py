from django import forms
from .models import Product, Category, SubCategory
from django.db.models import Max # this is used when i query the max sku so i can sugest the next best sku

class ProductForm(forms.ModelForm):
    subCategory = forms.ModelChoiceField( # this is used to give a drop down and a single select for subcategory 
        queryset=SubCategory.objects.all(),
        required=False,
        empty_label="No subcategory",
        widget=forms.Select())
    
    class Meta:
        model = Product
        fields = ['sku', 'name', 'price', 'stock_quantity', 'categories', 'subCategory']
        widgets = {
            'categories': forms.CheckboxSelectMultiple(), # just here to make the category select prettier ,
        }
    
    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()

        if len(name) < 3:
            raise forms.ValidationError("Product name must be at least 3 characters.")

        if len(name) > 255:
            raise forms.ValidationError("Product name must be under 255 characters.")

        return name
    def clean_stock_quantity(self):
        stock = self.cleaned_data.get('stock_quantity')

        if stock is None:
            raise forms.ValidationError("Stock quantity is required.")

        if stock < 0:
            raise forms.ValidationError("Stock quantity must be 0 or greater.")

        return stock
    def clean_price(self):
        price = self.cleaned_data.get('price')

        if price is None:
            raise forms.ValidationError("Price is required.")

        if price < 0:
            raise forms.ValidationError("Price must be 0 or greater.")

        if price > 9999.99:
            raise forms.ValidationError("Price cannot exceed $9,999.99.")

        return price
    def clean_sku(self):
        sku = self.cleaned_data.get('sku')

        if sku is None:
            raise forms.ValidationError("SKU is required.")

        if sku < 0:
            raise forms.ValidationError("SKU must be 0 or greater.")

        # Exclude the current product when editing so its own SKU doesn't trigger duplicate error
        qs = Product.objects.filter(sku=sku)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            max_sku = Product.objects.aggregate(m=Max('sku'))['m'] or 0
            raise forms.ValidationError(
                f"SKU {sku} is already taken. Next available: {max_sku + 1}"
            )

        return sku

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = '__all__'

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()

        if len(name) < 3:
            raise forms.ValidationError("Category name must be at least 3 characters.")

        # Case insensitive duplicate check
        if Category.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError(f'"{name}" already exists as a category.')

        return name.title() # title() for prettyness

class SubCategoryForm(forms.ModelForm):
    class Meta:
        model = SubCategory
        fields  = '__all__'
    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()

        if len(name) < 3:
            raise forms.ValidationError("Subcategory name must be at least 3 characters.")

        if SubCategory.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError(f'"{name}" already exists as a subcategory.')

        return name.title()