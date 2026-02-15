from django.shortcuts import render, redirect, get_object_or_404
from .forms import ProductForm, CategoryForm
from .models import Product, Category
from django.db.models import Q # used for adding and/or/not in more advanced wher clauses
from csv import DictWriter, DictReader
import csv
import io
from django.contrib import messages # usefull when creting errors
# Create your views here. 

def home_page(request):

    #|||||||||||||| Defining tables ||||||||||||||
    products = Product.objects.all() # retuns a list of .all() products inside products table (product.objects)
    categorys = Category.objects.all()

    #|||||||||||||| search logic ||||||||||||||
    search = request.GET.get('search', '')
    if search:
        products = products.filter(Q(name__icontains=search) | Q(sku__contains=search)) # __icontains is a looking for a case insensitive partial max
        # Q is need for any clauses that require multiple arguments -> use of OR

    #||||||||||||||   category sort Logic   ||||||||||||||
    cateogory_sort = request.GET.getlist('sort_by_category', "")

    if cateogory_sort :
        for category in cateogory_sort :
            products = products.filter(categories__name=category)


    #||||||||||||||   zero stock logic   ||||||||||||||
    current_show_zero_stock = request.GET.get('show_zero_stock', "")
    show_zero = current_show_zero_stock == "hide_empty_stock" # returns true or false depnign if eqaution is eqaul
    if show_zero :
        products = products.filter(stock_quantity__gt=0) # gt = greater than
    
    #||||||||||||||   sorting logic  ||||||||||||||
    sort_key = request.GET.get('sort', 'name') # gets the sort from main.html and if nothing is selected automatically sorts by name
    products = products.order_by(sort_key)

    # |||||||||||||| defining base query ||||||||||||||
    #here to stop values from resseting after new from sumbits
    base_query = request.GET.copy()
    base_query.pop("sort", None) # gets rid of current sort, so when you add it back to <a> it doesnt duplicate itself
    base_query_string = base_query.urlencode()

    #\\\\\\\\\\\\\\\\\\\\\\\\\\\\    return render  /////////////////////////////////////////////////

    return render( request, 'inventory/main.html', 
                  {"products" : products,
                   'categorys' : categorys ,
                    'show_zero': show_zero,
                    "base_query": base_query_string,
                    "current_sort" : sort_key,
                    "current_category_sort_list":cateogory_sort
})

def change_stock(request, sku):
    product = Product.objects.get(sku=sku)
    if request.method == "POST":
        action = request.POST.get("action") # checking the name and returning the value
        if action == "add" :
            product.stock_quantity += 1
        elif product.stock_quantity >= 1:
            if action == "minus" :
                product.stock_quantity -= 1
        else :
            messages.error(request, f"{product.name} stock is already at 0")
    product.save()
    return redirect(f"/?{request.GET.urlencode()}") # request.GET.urlencode() simply just gets the past parmaters and saves them as a string, for exmaple" search=&category_sort=&show_zero_stock=&sort=sku"

def create(request):
    products = Product.objects.all() # might use

    #\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\         add product logic           \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\

    if request.method == "POST": # form being sumbited 
        form = ProductForm(request.POST) #reciving data from the form
        if form.is_valid(): # django making sure everything is good with the new info given        
            form.save() # writes and savs to databse 
            messages.success(request, "Succesfully Added New Product")
            return redirect('home_page') # redirects to whatever url is named inventory_list
    else:
        form = ProductForm() # occurs when form is blank

    # \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\               add category logic           \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\
    if request.method == "POST" and "add-category" in request.POST :
        form = CategoryForm(request.POST) #reciving data from the form
        if form.is_valid(): # django making sure everything is good with the new info given
            form.save() # writes and savs to databse 
            messages.success(request, "Succesfully Added New Category")
            return redirect('home_page') # redirects to whatever url is named inventory_list
        else:
            form = CategoryForm() # occurs when form is blank

#\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\            uploading csv logic         \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\
    if request.method == "POST" and "upload_csv" in request.POST:
        csv_file = request.FILES.get("csv_file")
        # Read file
        decoded_file = csv_file.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(decoded_file))

        rows_skipped = []
        number_of_rows_skipped = 0
        number_of_rows_added = 0

        for row_number, row in enumerate(reader, start=2):  # start=2 accounts for header row  
            try :
                if float(row["price"]) > 0 and int(row["stock"]) > 0 :                
                    new_product, created = Product.objects.update_or_create( # note that created is not used just her for reading purposes, as a tuple is reutnred
                        #updateOrCreate requires a lookip field and a update field
                        sku=row["sku"].strip(),   # LOOKUP FIELD - what django searches to see if it exists
                        defaults={               # FIELDS TO UPDATE- what to update
                            "name": row["name"].strip(),
                            "price": float(row["price"]),
                            "stock_quantity": int(row["stock"]),
                        }
                    )
                    number_of_rows_added += 1
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
                        number_of_rows_skipped += 1
                        rows_skipped.append(row["sku"])
                        messages.error(
                            request,
                            f"Row {row_number}: has an invalid price. Price MUST be greater or eqaul to 0"
                        )

                    elif int(row["stock"]) < 0  :
                        number_of_rows_skipped += 1
                        rows_skipped.append(row["sku"])
                        messages.error(
                            request,
                            f"Row {row_number}: has an invalid Stock. Stock MUST be greater or eqaul to 0"
                        )
            except KeyError as e:
                messages.error(
                    request,
                    f"Row {row_number}: Missing column '{e.args[0]}'. "
                    f"Required headers: sku, name, price, stock, category"
                )
                continue
            except Exception as e:
                messages.error(
                    request,
                    f"Row {row_number}: Unexpected error — {str(e)}"
                )
                continue

                # PRINTING error logic 
        if number_of_rows_added > 0 :
            messages.success(request, f"Succesfully Updated or Created {number_of_rows_added} Rows")

        if number_of_rows_skipped > 0 :     
                messages.warning(request, f" SKIPPED {number_of_rows_skipped} rows")

        return redirect("home_page")
    
    #return render
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

