from django import forms
from .models import Product, Category, SubCategory, PatternFile, Market,Sale,MarketExpense
from django.db.models import Max # this is used when i query the max sku so i can sugest the next best sku
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class ProductForm(forms.ModelForm):
    subCategory = forms.ModelChoiceField(
        queryset=SubCategory.objects.all(),
        required=False,
        empty_label="No subcategory",
        widget=forms.Select())
    
    class Meta:
        model = Product
        fields = [
            'sku', 'name', 'price', 'stock_quantity',
            'categories', 'subCategory', 'discontinued',
            'image', 'description','patternDescription',
        ]
        widgets = {
            'categories': forms.CheckboxSelectMultiple(),
            'discontinued': forms.CheckboxInput(attrs={'class': 'toggle-input'}),
        }
    # ... rest stays the same
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user:
            self.fields['categories'].queryset = Category.objects.filter(user=user)
            self.fields['subCategory'].queryset = SubCategory.objects.filter(user=user)
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
        qs = Product.objects.filter(sku=sku, user=self.user)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            max_sku = Product.objects.filter(user=self.user).aggregate(m=Max('sku'))['m'] or 0
            raise forms.ValidationError(
                f"SKU {sku} is already taken. Next available: {max_sku + 1}"
            )
        return sku

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user  # store for scoped duplicate check

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()

        if len(name) < 3:
            raise forms.ValidationError("Category name must be at least 3 characters.")

        # Case insensitive duplicate check
        if Category.objects.filter(name__iexact=name, user=self.user).exists():
            raise forms.ValidationError(f'"{name}" already exists as a category.')

        return name.title() # title() for prettyness

class SubCategoryForm(forms.ModelForm):
    class Meta:
        model = SubCategory
        fields  = ['name']
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user  # store for scoped duplicate check
    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()

        if len(name) < 3:
            raise forms.ValidationError("Subcategory name must be at least 3 characters.")

        if SubCategory.objects.filter(name__iexact=name, user=self.user).exists():
            raise forms.ValidationError(f'"{name}" already exists as a subcategory.')

        return name.title()
class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]



class ProductEditForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['sku', 'name', 'price', 'stock_quantity', 'categories', 'subCategory', 'discontinued']
        # removed both 'image' and 'description'
        widgets = {
            'categories': forms.CheckboxSelectMultiple(),
            'discontinued': forms.CheckboxInput(attrs={'class': 'toggle-input'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user:
            self.fields['categories'].queryset = Category.objects.filter(user=user)
            self.fields['subCategory'].queryset = SubCategory.objects.filter(user=user)

    # reuse all the same clean methods from ProductForm
    clean_name = ProductForm.clean_name
    clean_stock_quantity = ProductForm.clean_stock_quantity
    clean_price = ProductForm.clean_price
    clean_sku = ProductForm.clean_sku

class PatternFileForm(forms.ModelForm):
    class Meta:
        model = PatternFile
        fields = ['name', 'file']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Main pattern...'}),
        }

# =================================
# Phase 2 Market Mode
#======================================
class MarketForm(forms.ModelForm):
    class Meta:
        model = Market
        fields = ['name', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Location, event details...'}),
        }

class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ['payment_method', 'customer_type', 'discount_amount', 'tip_amount']
        widgets = {
            'payment_method': forms.Select(),
            'customer_type': forms.Select(),
            'discount_amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'value': '0'}),
            'tip_amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'value': '0'}),
        }

class MarketExpenseForm(forms.ModelForm):
    class Meta:
        model = MarketExpense
        fields = ['description', 'amount']
        widgets = {
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }