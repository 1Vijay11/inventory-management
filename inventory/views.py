from django.shortcuts import render, redirect  # render templates, redirect users, fetch objects safely
from django.http import HttpResponse, JsonResponse  # standard and JSON responses
from django.contrib.auth import login  # log users in after signup/login
from django.contrib.auth.decorators import login_required  # restrict views to authenticated users
from django.contrib import messages  # display success/error messages to users
# Database queries & ORM tools
from django.db.models import Q, Max, Sum, F  # advanced queries, aggregations, and field operations
from .models import Product, Category, SubCategory  # database tables for your app
# Forms
from .forms import (
    ProductForm,
    CategoryForm,
    SubCategoryForm,
    CustomUserCreationForm,
) 
# CSV handling
import csv  
from csv import DictWriter, DictReader  # read/write CSVs as dictionaries
# Utilities
import io  # handle in-memory file operations (e.g., CSV export)
import json  # parse/generate JSON data

@login_required
def home_page(request):
    #|||||||||||||| Defining tables ||||||||||||||
    products = Product.objects.filter(user=request.user)
    categorys = Category.objects.filter(user=request.user)
    sub_categorys = SubCategory.objects.filter(user=request.user)
    #|||||||||||||| Getting Dirived Values ||||||||||||||
    total_stock_value = 0
    total_stock_amount = 0
    for product in products :
        total_stock_value += product.total_value
        total_stock_amount += product.stock_quantity
    products_without_sub_category = products.filter(user=request.user, subCategory__isnull=True) 
    sub_categorys_with_products = SubCategory.objects.filter( user=request.user, products__isnull=False).distinct()
    total_unique_items = products_without_sub_category.count() + sub_categorys_with_products.count()

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
    show_zero = current_show_zero_stock == "show_empty_stock" # returns true or false depnign if eqaution is eqaul
    if not show_zero :
        products = products.filter(stock_quantity__gt=0) # gt = greater than
    
    #||||||||||||||    Discontinued logic   ||||||||||||||
    show_discontinued = request.GET.get('show_discontinued', "")
    if not show_discontinued :
        products = products.filter(discontinued=False) 
    
        # ||||||||||||||             SUBCATEGORY LOGIC               ||||||||||||||
    products_with_sub_category = products.filter(subCategory__isnull=False) # seperates products into 2 list 1with and 1 without subcategorys
    products = products.filter(subCategory__isnull=True)

    combined_products = []
    for product in products:
        combined_products.append({
            "type": "product",
            "name": product.name,
            "sku": product.sku,
            "price": product.price,
            "stock_quantity": product.stock_quantity,
            "total_value" : product.total_value,
            "categories": product.categories,
            "discontinued" : product.discontinued,
            "object" : product 
        })
    filtered_sub_categorys = sub_categorys.filter(products__in=products_with_sub_category).distinct() # applyign the filters, distint so there no reapeats *very inportant*
    for sub in filtered_sub_categorys:   
            sub_products = products_with_sub_category.filter(subCategory=sub)
            if not sub_products.exists():   
                continue        
            combined_products.append({
                "type": "subcategory",
                "name": sub.name,
                "sku": sub.sku,  # your Min("sku") property
                "price": sub.price,  # your Min("price")
                "stock_quantity": sub.total_stock,
                "total_value" : sub.total_value,
                "categories": "",
                "object" : sub 
            })
    #||||||||||||||   sorting logic  ||||||||||||||
    sort_key = request.GET.get('sort', 'name') # gets the sort from main.html and if nothing is selected automatically sorts by name
    if not sort_key:
        sort_key = 'name'
    reverse = False
    if sort_key.startswith("-"):
        reverse = True
        sort_key = sort_key[1:]

    combined_products = sorted(
        combined_products,
        key=lambda x: x[sort_key] if x[sort_key] is not None else 0,
        reverse=reverse
    )
    # |||||||||||||| defining base query ||||||||||||||
    #here to stop values from resseting after new from sumbits
    base_query = request.GET.copy()
    base_query.pop("sort", None) # gets rid of current sort, so when you add it back to <a> it doesnt duplicate itself
    base_query_string = base_query.urlencode()
    #\\\\\\\\\\\\\\\\\\\\\\\\\\\\    return render  /////////////////////////////////////////////////

    return render( request, 'inventory/main.html', 
                  {"products" : products,
                   'categorys' : categorys ,
                   "sub_categorys": sub_categorys,
                   "filtered_sub_category_list" : products_with_sub_category, # this has a list of all the products that have subcategorys that are also filtered properaly
                    'show_zero': show_zero,
                    "show_discontinued" : show_discontinued,
                    "base_query": base_query_string,
                    "current_category_sort_list":cateogory_sort,
                    "total_stock_value" : total_stock_value,
                    "total_stock_amount" : total_stock_amount,
                    "combined_products" : combined_products,
                    "total_unique_items": total_unique_items,
})
@login_required
def change_stock(request, sku):
    if request.method == "POST":
        data = json.loads(request.body)
        action = data.get("action")
        product = Product.objects.get(sku=sku, user=request.user)    

        if action == "add":
            product.stock_quantity += 1

        elif action == "minus":
            if product.stock_quantity <= 0:
                return JsonResponse({"error": "Cannot go below 0"}, status=400) # stops the stofk from going below 0
            product.stock_quantity -= 1

        product.save()

        #reset values without refreshing
        #derived values calculations
        products = Product.objects.filter(user=request.user)
        total_stock_value = 0
        total_stock_amount = 0
        for item in products :
            total_stock_value += item.total_value
            total_stock_amount += item.stock_quantity
        return JsonResponse({ # instead of refreshing page just return products only to our js
            "stock": product.stock_quantity,
            "total_stock_amount": total_stock_amount,
            "total_stock_value": total_stock_value,
        })
    
@login_required 
def create(request):
    products = Product.objects.filter(user=request.user)
    category = Category.objects.filter(user=request.user)
    sub_Category = SubCategory.objects.filter(user=request.user)

    product_form = ProductForm(user=request.user)
    category_form = CategoryForm(user=request.user)
    sub_category_form = SubCategoryForm(user=request.user)

    active_tab = 'manual' # track tab after refresh 

    #\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\         add product logic           \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\
    if request.method == "POST":

        if "add-product" in request.POST:
            product_form = ProductForm(request.POST, user=request.user) #reciving data from the form
            if product_form.is_valid(): # django making sure everything is good with the new info given        
                product = product_form.save(commit=False)  # don't save yet
                product.user = request.user        # assign logged-in user
                product.save()
                product_form.save_m2m()  # IMPORTANT for categories     
                messages.success(request, "Succesfully Added New Product")
                return redirect('home_page') # redirects to whatever url is named inventory_list
        # \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\               category logic           \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\
        elif "add-category" in request.POST :
            active_tab = 'categories'
            category_form = CategoryForm(request.POST, user=request.user) #reciving data from the form
            if category_form.is_valid(): # django making sure everything is good with the new info given
                
                category = category_form.save(commit=False)  # don't save yet
                category.user = request.user        # assign logged-in user
                category.save()
                category_form.save_m2m()  # IMPORTANT for categories                  messages.success(request, "Succesfully Added New Category")
                return redirect('product_add') # redirects to whatever url is named inventory_list

        # ── Delete Category ───────────────────────────
        elif "delete-category" in request.POST:
            cat_id = request.POST.get("delete-category")
            Category.objects.filter(id=cat_id, user=request.user).delete()
            messages.success(request, "Category deleted")
            active_tab = 'categories'

            # NO REDIRECT so you can continue deleting
        # \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\               Sub Category logic           \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\
        elif "add-sub-category" in request.POST:
            active_tab = 'subcategories'
            sub_category_form = SubCategoryForm(request.POST, user=request.user) #reciving data from the form
            if sub_category_form.is_valid(): # django making sure everything is good with the new info given
                sub_category = sub_category_form.save(commit=False)  # don't save yet
                sub_category.user = request.user        # assign logged-in user
                sub_category.save()
                sub_category_form.save_m2m()
                messages.success(request, "Succesfully Added New Sub Category")
                return redirect('product_add') # redirects to whatever url is named inventory_list
        # ── Delete Subcategory ────────────────────────
        elif "delete-subcategory" in request.POST:
            sub_id = request.POST.get("delete-subcategory")
            SubCategory.objects.filter(id=sub_id, user=request.user).delete()
            messages.success(request, "Subcategory deleted")
            active_tab = 'subcategories'
            # NO REDIRECT so you can continue deleting

    #\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\            uploading csv logic         \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\
        elif "upload_csv" in request.POST:
            csv_file = request.FILES.get("csv_file")
            # Read file
            decoded_file = csv_file.read().decode("utf-8")
            reader = csv.DictReader(io.StringIO(decoded_file))

            rows_skipped = []
            number_of_rows_skipped = 0
            number_of_rows_added = 0

            for row_number, row in enumerate(reader, start=2):  # start=2 accounts for header row  
                try :
                    # Discontinued Logic
                    raw_discontinued = row["discontinued"].strip().lower() 
                    if raw_discontinued in ["yes", "true", "discontinued"]:
                        discontinued = True
                    else: # if its not a valid true field it will default to no
                        discontinued = False
                    if float(row["price"]) >= 0 and int(row["stock"]) >= 0 :                
                        new_product, created = Product.objects.update_or_create( # note that created is not used just her for reading purposes, as a tuple is reutnred
                            #updateOrCreate requires a lookip field and a update field
                            sku=row["sku"].strip(),   # LOOKUP FIELD - what django searches to see if it exists
                            user=request.user,
                            defaults={               # FIELDS TO UPDATE- what to update
                                "name": row["name"].strip(),
                                "price": float(row["price"]),
                                "stock_quantity": int(row["stock"]),
                                "discontinued" : discontinued
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
                                category, got_created = Category.objects.get_or_create(name=category_name, user=request.user)# note that created is not used just her for reading purposes, as a tuple is reutnred
                                new_product.categories.add(category)
                                new_product.save()

                        # sub Category Logic, create or add subcategory
                        sub_category_name = row.get("subCategory", "").title().strip()
                        if sub_category_name:
                            sub_category, created = SubCategory.objects.get_or_create(name=sub_category_name, user=request.user)

                            new_product.subCategory = sub_category
                            new_product.save()
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
    # caclualte the sugested sku:
    max_sku = Product.objects.filter(user=request.user).aggregate(m=Max('sku'))['m'] or 0
    sugested_sku = int(max_sku) + 1

        #return render
    return render(request, 'inventory/add_product.html', {
        'form': product_form,
        'category_form': category_form,
        'sub_category_form': sub_category_form,
        'categorys': category,
        'sub_categorys': sub_Category,
        'products': products,
        'sugested_sku': sugested_sku,
        'active_tab': active_tab,

    })
@login_required
def export_products_csv(request):
    # Create response with CSV header
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="products.csv"'

    writer = csv.writer(response)

    writer.writerow([
        "name", "sku", "price", "stock", "category", "subCategory", "discontinued"
    ])

    products = Product.objects.filter(user=request.user)

    for product in products:
        categories = ", ".join(
            c.name for c in product.categories.all()
        )

        sub_category = product.subCategory.name if product.subCategory else ""

        writer.writerow([
            product.name,
            product.sku,
            product.price,
            product.stock_quantity,
            categories,
            sub_category,
            product.discontinued
        ])

    return response
@login_required
def product_edit(request, sku):
    product = Product.objects.get(sku=sku, user=request.user)

    if request.method == "POST":
        action = request.POST.get("action") # checking the name 

        # EDITING LOGIC
        form = ProductForm(request.POST, instance=product, user=request.user) # instance=product is telling djang ot update that instance of product not create a new one
        if action == "save":
            if form.is_valid():
                form.save()
                return redirect('home_page')
            
        # DELETING LOGIC
        if action == "delete":
            product.delete()
            return redirect("home_page")

    else:
        form = ProductForm(instance=product, user=request.user) #instance=product just auto fills the form with the past instance of the product

    return render(request, 'inventory/edit_product.html', {
        'form': form,
        'product': product
    })
# Login not required
def signup(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.email = form.cleaned_data["email"]
            user.save()
            login(request, user)  # auto login after signup
            messages.success(request, "Account created successfully!")
            return redirect("home_page")
    else:
        form = CustomUserCreationForm()

    return render(request, "inventory/signup.html", {"form": form})