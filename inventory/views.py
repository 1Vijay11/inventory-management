from django.shortcuts import render, redirect, get_object_or_404
from .forms import ProductForm, CategoryForm
from .models import Product, Category
from django.db.models import Q # used for adding and/or/not in more advanced wher clauses
from csv import DictWriter, DictReader
import csv
import io
from django.contrib import messages # usefull when creting errors
import decimal #used for turning values into devimal instead of float, for the databse
# Create your views here.

def home_page(request):
    #   Defining tables
    products = Product.objects.all() # retuns a list of .all() products inside products table (product.objects)
    categorys = Category.objects.all()

    #   search logic
    search = request.GET.get('search', '')
    if search:
        products = products.filter(Q(name__icontains=search)) # __icontains is a looking for a case insensitive partial max
        # Q is need for any clauses that require multiple arguments -> use of OR

    #   sort Logic
    sort_key = request.GET.get('sort', 'name') # gets the sort from main.html and if nothing is selected automatically sorts by name
    cateogory_sort = request.GET.get('category_sort', "")
    if cateogory_sort :
        products = products.filter(categories__name__iexact=cateogory_sort)
    
    products = products.order_by(sort_key)

    #   zero stock logic
    current_show_zero_stock = request.GET.get('show_zero_stock', "")
    show_zero = current_show_zero_stock == "hide_empty_stock" # returns true or false depnign if eqaution is eqaul
    if show_zero :
        products = products.filter(stock_quantity__gt=0) # gt = greater than
    
    #   return render
    return render( request, 'inventory/main.html', {"products" : products,'categorys' : categorys , 'current_sort': sort_key, 'current_search': search, 'current_category_sort' : cateogory_sort ,'current_show_zero_stock': current_show_zero_stock , 'show_zero': show_zero})

def change_stock(request, sku):




    # FOR LATER PLEASE ADD A CHECK REQUIRMENTS WHERE IT WILL STOP STOCK FROM GOING NEGATIVE




    
    if request.method == "POST":
        action = request.POST.get("action") # checking the name and returning the value
        product = Product.objects.get(sku=sku)
        if action == "add" :
            product.stock_quantity += 1
        elif action == "minus" :
            product.stock_quantity -= 1
        product.save()

    return redirect("home_page")

def create(request):
    products = Product.objects.all() # retuns a list of .all() products inside products table (product.objects)

    #\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\         add product logic           \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\

    if request.method == "POST": # form being sumbited 
        form = ProductForm(request.POST) #reciving data from the form
        if form.is_valid(): # django making sure everything is good with the new info given        
            form.save() # writes and savs to databse 
            return redirect('home_page') # redirects to whatever url is named inventory_list
    else:
        form = ProductForm() # occurs when form is blank

    # \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\               add category logic           \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\
    if request.method == "POST" and "add-category" in request.POST :
        form = CategoryForm(request.POST) #reciving data from the form
        if form.is_valid(): # django making sure everything is good with the new info given
            form.save() # writes and savs to databse 
            return redirect('home_page') # redirects to whatever url is named inventory_list
        else:
            form = CategoryForm() # occurs when form is blank

#\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\            uploading csv logic         \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\
    if request.method == "POST" and "upload_csv" in request.POST:
        csv_file = request.FILES.get("csv_file")
        # Read file
        decoded_file = csv_file.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(decoded_file))

        for row in reader :
            sku = row["sku"]
            try :
                if int(row["price"]) > 0 and int(row["stock"]) :                
                    new_product, created = Product.objects.update_or_create( # note that created is not used just her for reading purposes, as a tuple is reutnred
                        #updateOrCreate requires a lookip field and a update field
                        sku=row["sku"].strip(),   # LOOKUP FIELD - what django searches to see if it exists
                        defaults={               # FIELDS TO UPDATE- what to update
                            "name": row["name"].strip(),
                            "price": int(row["price"]),
                            "stock_quantity": int(row["stock"]),
                        }
                    )

                    new_product.categories.clear() # simply removes all the categorys of the product so that all new ones can be added
                    category_names = row["category"].split(",")
                    
                    for category_name in category_names:
                        # will reaturn a tuple : categoy, if created TRUE else FALSE
                        category_name = category_name.strip()
                        if category_name :
                            category_name = category_name.title()

                            category, got_created = Category.objects.get_or_create(name=category_name)# note that created is not used just her for reading purposes, as a tuple is reutnred
                            new_product.categories.add(category)
                else :
                    if int(row["price"]) < 0 :
                        print (f'price must be greater then 0 for the row with the sku number : {row["sku"]}')
                    else :
                        print (f"stock must be greater then 0 for the row with the sku number : {row["sku"]}")
            except Exception as ex:
                print(ex)
                continue

        return redirect("home_page")

    return render(request, 'inventory/add_product.html', {'form': form})


def product_edit(request, sku):
    product = get_object_or_404(Product, sku=sku)

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

