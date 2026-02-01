from django.shortcuts import render, redirect, get_object_or_404
from .forms import ProductForm, CategoryForm
from .models import Product, Category
from django.db.models import Q # used for adding and/or/not in more advanced wher clauses

# Create your views here.

def home_page(request):
    #   Defining tables
    products = Product.objects.all() # retuns a list of .all() products inside products table (product.objects)
    categorys = Category.objects.all()

    #   search logic
    search = request.GET.get('search', '')
    if search:
        products = products.filter(Q(name__icontains=search) | Q(sku=search)) # __icontains is a looking for a case insensitive partial max
        # Q is need for any clauses that require multiple arguments -> use of OR

    #   sort Logic
    sort_key = request.GET.get('sort', 'name') # gets the sort from main.html and if nothing is selected automatically sorts by name
    cateogory_sort = request.GET.get('category_sort', "")
    if cateogory_sort :
        products = products.filter(categories__name__iexact=cateogory_sort)
    
    products = products.order_by(sort_key)

    #   zero stock logic
    show_zero = request.GET.get('show_zero_stock')
    if show_zero == "hide_empty_stock":
        products = products.filter(stock_quantity__gt=0) # gt = greater than

    #   return 
    return render( request, 'inventory/main.html', {"products" : products,'categorys' : categorys , 'current_sort': sort_key, 'current_search': search, 'current_category_sort' : cateogory_sort ,'show_zero': show_zero})

def product_create(request):
    if request.method == "POST": # form being sumbited 
        form = ProductForm(request.POST) #reciving data from the form
        if form.is_valid(): # django making sure everything is good with the new info given
            form.save() # writes and savs to databse 
            return redirect('home_page') # redirects to whatever url is named inventory_list
    else:
        form = ProductForm() # occurs when form is blank

    return render(request, 'inventory/add_product.html', {'form': form})

def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == "POST":
        action = request.POST.get("action") # checking the name 

        # EDITING LOGIC
        form = ProductForm(request.POST, instance=product) # instance=product is telling djang ot update that instance of product not create a new one
        if action == "save":
            if form.is_valid():
                form.save()
                return redirect('home_page')
            
        # DELETING LOGIC
        if action == "delete":
            product.delete()
            return redirect("home_page")

    else:
        form = ProductForm(instance=product) #instance=product just auto fills the form with the past instance of the product

    return render(request, 'inventory/edit_product.html', {
        'form': form,
        'product': product
    })

def category_create(request):
    if request.method == "POST": # form being sumbited 
        form = CategoryForm(request.POST) #reciving data from the form
        if form.is_valid(): # django making sure everything is good with the new info given
            form.save() # writes and savs to databse 
            return redirect('home_page') # redirects to whatever url is named inventory_list
    else:
        form = CategoryForm() # occurs when form is blank

    return render(request, 'inventory/add_category.html', {'form': form})
