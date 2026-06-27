from django.shortcuts import render, redirect  # render templates, redirect users, fetch objects safely
from django.http import HttpResponse, JsonResponse  # standard and JSON responses
from django.contrib.auth import login  # log users in after signup/login
from django.contrib.auth.decorators import login_required  # restrict views to authenticated users
from django.contrib import messages  # display success/error messages to users
from django.utils import timezone # auto add curent date on market start

# Database queries & ORM tools
from django.db.models.functions import Coalesce
from django.db.models import Q, Max, Sum, F, Min, Count, Value, DecimalField
from .models import Product, Category, SubCategory, PatternFile, Market, Sale, SaleItem, Cart, CartItem, StockSnapshot, MarketExpense
from django.forms import modelformset_factory
from django.shortcuts import render, redirect, get_object_or_404
# Forms
from .forms import ProductForm, CategoryForm, SubCategoryForm, CustomUserCreationForm, PatternFileForm, ProductEditForm, MarketForm, SaleForm, MarketExpenseForm
# CSV handling
import csv  
from csv import DictWriter, DictReader  # read/write CSVs as dictionaries
# Utilities
import io  # handle in-memory file operations (e.g., CSV export)
import json  # parse/generate JSON data
from django.urls import reverse

@login_required # this will be for changeing the base url redirect depending if theres a market - if no market then redirect to normal inventory page if market then go to current market fro easy sale tracking while current market active
def root_redirect(request):
    active = Market.objects.filter(user=request.user, is_active=True).first()
    if active:
        return redirect('market_detail', market_id=active.id)
    return redirect('home_page')

@login_required
def home_page(request):
    #|||||||||||||| Defining tables ||||||||||||||
    products = Product.objects.filter(user=request.user)
    categorys = Category.objects.filter(user=request.user)
    sub_categorys = SubCategory.objects.filter(user=request.user)


    #|||||||||||||| search logic ||||||||||||||
    search = request.GET.get('search', '')
    if search:
        products = products.filter(Q(name__icontains=search) | Q(sku__contains=search) |     Q(subCategory__name__icontains=search)) # __icontains is a looking for a case insensitive partial max
        # Q is need for any clauses that require multiple arguments -> use of OR

    #||||||||||||||   category sort Logic   ||||||||||||||
    cateogory_sort = request.GET.getlist('sort_by_category', "")

    if cateogory_sort :
        for category in cateogory_sort :
            products = products.filter(categories__name=category)


    # ||||||||||||||| Show zero stock / discontinued toggles |||||||||||||||||||
# If form was submitted, respect the checkbox state. Otherwise default to True.
    if 'form_submitted' in request.GET:
        show_zero = request.GET.get('show_zero_stock', '') == 'show_empty_stock'
    else:
        show_zero = True    
    show_discontinued = request.GET.get('show_discontinued', '') == 'show_discontinued'


    # ---- State filters (out of stock / discontinued) from dropdown ----
    state_filters = request.GET.getlist('filter_state', [])

    if 'out_of_stock' in state_filters:
        # User wants ONLY out of stock — override toggle, force-show them
        products = products.filter(stock_quantity=0)
        show_zero = True  # so the toggle UI reflects what we're showing
    elif not show_zero:
        products = products.filter(stock_quantity__gt=0)

    if 'discontinued' in state_filters:
        # User wants ONLY discontinued — override toggle
        products = products.filter(discontinued=True)
        show_discontinued = True
    elif not show_discontinued:
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

    filtered_sub_categorys = sub_categorys.filter(products__in=products_with_sub_category).distinct()

    for sub in filtered_sub_categorys:
        sub_products = products_with_sub_category.filter(subCategory=sub)
        if not sub_products.exists():
            continue

        # Compute totals from the FILTERED products only, not from sub's properties
        sub_totals = sub_products.aggregate(
            total_stock=Sum('stock_quantity'),
            total_value=Sum(F('price') * F('stock_quantity')),
            min_price=Min('price'),
            min_sku=Min('sku'),
        )

        combined_products.append({
            "type": "subcategory",
            "name": sub.name,
            "sku": sub_totals['min_sku'] or 0,
            "price": sub_totals['min_price'] or 0,
            "stock_quantity": sub_totals['total_stock'] or 0,
            "total_value": sub_totals['total_value'] or 0,
            "categories": "",
            "object": sub
        })
    #||||||||||||||   sorting logic  ||||||||||||||
    sort_key = request.GET.get('sort', 'price') # gets the sort from main.html and if nothing is selected automatically sorts by name
    if not sort_key:
        sort_key = 'price'
    reverse = False
    if sort_key.startswith("-"):
        reverse = True
        sort_key = sort_key[1:]

    combined_products = sorted(
        combined_products,
        key=lambda x: x[sort_key] if x[sort_key] is not None else 0,
        reverse=reverse
    )
    #|||||||||||||| Getting Derived Values ||||||||||||||
    active_products = Product.objects.filter(user=request.user, discontinued=False)
    products = products.filter(discontinued=False)

    # total_stock_value = products.aggregate(
    #     total=Sum(F('price') * F('stock_quantity'))
    # )['total'] or 0
    total_stock_value = 0
    for product in combined_products :
        total_stock_value += product["total_value"]

    total_stock_amount = 0
    for product in combined_products :
        total_stock_amount += product["stock_quantity"]

    # total_stock_amount = products.aggregate(
    #     total=Sum('stock_quantity')
    # )['total'] or 0

    products_without_sub_category = active_products.filter(subCategory__isnull=True)
    sub_categorys_with_products = SubCategory.objects.filter(
        user=request.user, 
        products__isnull=False).distinct()

    total_unique_items = products_without_sub_category.count() + sub_categorys_with_products.count()
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
                return JsonResponse({"error": "Cannot go below 0"}, status=400)
            product.stock_quantity -= 1

        product.save()

        subcategory_stock = None
        subcategory_total_value = None
        subcategory_sku = None
        if product.subCategory:
            subcategory_stock = product.subCategory.total_stock
            subcategory_total_value = float(product.subCategory.total_value)
            subcategory_sku = product.subCategory.sku

        return JsonResponse({
            "stock": product.stock_quantity,
            "total_value": float(product.total_value),
            "subcategory_stock": subcategory_stock,
            "subcategory_total_value": subcategory_total_value,
            "subcategory_sku": subcategory_sku,
        })
    
@login_required 
def create(request):
    products = Product.objects.filter(user=request.user)
    category = Category.objects.filter(user=request.user).order_by('name')
    sub_Category = SubCategory.objects.filter(user=request.user)

    product_form = ProductForm(user=request.user)
    category_form = CategoryForm(user=request.user)
    sub_category_form = SubCategoryForm(user=request.user)

    active_tab = 'manual' # track tab after refresh 

    #\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\         add product logic           \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\
    if request.method == "POST":

        if "add-product" in request.POST:
            product_form = ProductForm(request.POST, request.FILES, user=request.user)
            if product_form.is_valid():
                product = product_form.save(commit=False)
                product.user = request.user
                product.save()
                product_form.save_m2m()

                # ── Pattern files & links: zip them together by index ──
                pattern_names = request.POST.getlist('pattern_name')
                pattern_types = request.POST.getlist('pattern_type')
                pattern_urls  = request.POST.getlist('pattern_url')   # only link rows
                pattern_files = request.FILES.getlist('pattern_file') # only file rows

                # Walk both lists in parallel using separate cursors
                url_idx = 0
                file_idx = 0
                for i, ptype in enumerate(pattern_types):
                    name = pattern_names[i].strip() if i < len(pattern_names) else ''
                    if not name:
                        # still advance the cursor for whichever input this row used
                        if ptype == 'link': url_idx += 1
                        else: file_idx += 1
                        continue

                    if ptype == 'link':
                        url = pattern_urls[url_idx].strip() if url_idx < len(pattern_urls) else ''
                        url_idx += 1
                        if url:
                            PatternFile.objects.create(product=product, name=name, url=url)
                    else:
                        file = pattern_files[file_idx] if file_idx < len(pattern_files) else None
                        file_idx += 1
                        if file:
                            PatternFile.objects.create(product=product, name=name, file=file)

                messages.success(request, "Successfully Added New Product")
                return redirect('home_page')
            else:
                # Form invalid — fall through to render with errors
                messages.error(request, "Please fix the errors below")
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
def edit_category(request, cat_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    category = get_object_or_404(Category, id=cat_id, user=request.user)
    new_name = request.POST.get("name", "").strip()
    if len(new_name) < 3:
        return JsonResponse({"error": "Name must be at least 3 characters."}, status=400)
    if Category.objects.filter(name__iexact=new_name, user=request.user).exclude(pk=cat_id).exists():
        return JsonResponse({"error": f'"{new_name}" already exists.'}, status=400)
    category.name = new_name.title()
    category.save()
    return JsonResponse({"success": True, "name": category.name})

@login_required
def edit_subcategory(request, sub_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    sub = get_object_or_404(SubCategory, id=sub_id, user=request.user)
    new_name = request.POST.get("name", "").strip()
    if len(new_name) < 3:
        return JsonResponse({"error": "Name must be at least 3 characters."}, status=400)
    if SubCategory.objects.filter(name__iexact=new_name, user=request.user).exclude(pk=sub_id).exists():
        return JsonResponse({"error": f'"{new_name}" already exists.'}, status=400)
    sub.name = new_name.title()
    sub.save()
    return JsonResponse({"success": True, "name": sub.name})
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
    product = get_object_or_404(Product, sku=sku, user=request.user)
    form = ProductEditForm(instance=product, user=request.user)
        # note that i used asysnc for any forms that arent the main one, as i needed things like event listeners to auto update through different methods
    if request.method == "POST":
        action = request.POST.get("action")

        # ─── Main form: Save ───
        if action == "save":
            form = ProductEditForm(request.POST, request.FILES, instance=product, user=request.user)
            if form.is_valid():
                form.save()
                messages.success(request, "Product updated successfully")
                return redirect("home_page")
            # invalid → falls through to render with errors

        # ─── Main form: Delete  ───
        elif action == "delete":
            product.delete()
            return redirect("home_page")

        # ─── Async: upload/replace image ───
        elif action == "upload-image":
            image_file = request.FILES.get("image")
            if not image_file:
                return JsonResponse({"error": "No image provided"}, status=400)
            if product.image:
                product.image.delete(save=False)
            product.image = image_file
            product.save()
            return JsonResponse({"success": True, "image_url": product.image.url})

        # ─── Async: remove image ───
        elif action == "remove-image":
            if product.image:
                product.image.delete(save=False)
                product.image = None
                product.save()
            return JsonResponse({"success": True})

        # ─── Async: save description on blur ───
        elif action == "save-description":
            product.description = request.POST.get("description", "")
            product.save()
            return JsonResponse({"success": True})
        # ─── Async: save pattern description on blur ───
        elif action == "save-patternDescription":
            product.patternDescription = request.POST.get("patternDescription", "")
            product.save()
            return JsonResponse({"success": True})
        # ─── Async: add pattern file or link ───
        elif action == "add-pattern":
            name = request.POST.get("pattern_name", "").strip()
            pattern_type = request.POST.get("pattern_type", "file")
            
            if not name:
                return JsonResponse({"error": "Name is required"}, status=400)
            
            if pattern_type == "link":
                url = request.POST.get("pattern_url", "").strip()
                if not url:
                    return JsonResponse({"error": "URL is required"}, status=400)
                pattern = PatternFile.objects.create(product=product, name=name, url=url)
                return JsonResponse({
                    "success": True,
                    "pattern": {
                        "id": pattern.id,
                        "name": pattern.name,
                        "url": pattern.url,
                        "is_link": True,
                    },
                })
            else:
                pattern_file = request.FILES.get("pattern_file")
                if not pattern_file:
                    return JsonResponse({"error": "File is required"}, status=400)
                pattern = PatternFile.objects.create(product=product, name=name, file=pattern_file)
                return JsonResponse({
                    "success": True,
                    "pattern": {
                        "id": pattern.id,
                        "name": pattern.name,
                        "url": pattern.file.url,
                        "is_link": False,
                    },
                })

        # ─── Async: delete pattern file ───
        elif action == "delete-pattern":
            pattern_id = request.POST.get("pattern_id")
            PatternFile.objects.filter(id=pattern_id, product=product).delete()
            return JsonResponse({"success": True})

    return render(request, "inventory/edit_product.html", {"form": form, "product": product})
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    # ensure the pattern belongs to a product owned by this user
    pattern = get_object_or_404(
        PatternFile, 
        id=pattern_id, 
        product__sku=sku, 
        product__user=request.user
    )
    
    pattern.file.delete(save=False)  # delete the file from disk
    pattern.delete()
    
    return JsonResponse({"success": True})
# =========================
# Phase 2 - Market Mode Views
# =========================
@login_required
def market_dashboard(request):
    active_market = Market.objects.filter(user=request.user, is_active=True).first()
    return render (request, 'inventory/market_dashboard.html' ,
                   {
                       'active_market' : active_market
                   })
@login_required
def market_start(request):
    if Market.objects.filter(user=request.user, is_active=True).exists():
        messages.error(request, "You already have an active market. End it before starting a new one.")
        return redirect('market_dashboard')

    form = MarketForm()
    if request.method == 'POST':
        form = MarketForm(request.POST)
        if form.is_valid():
            market = form.save(commit=False)
            market.user = request.user
            market.is_active = True
            market.save()

            # Take a stock snapshot of all products at market start
            products = Product.objects.filter(user=request.user, discontinued=False)
            snapshots = [
                StockSnapshot(
                    market=market,
                    product=product,
                    product_name_snapshot=product.name,
                    product_sku_snapshot=product.sku,
                    stock_at_start=product.stock_quantity,
                )
                for product in products
            ]
            StockSnapshot.objects.bulk_create(snapshots)

            messages.success(request, f"'{market.name}' has started!")
            return redirect('market_detail', market_id=market.id)

    return render(request, 'inventory/market_start.html', {'form': form})
    
@login_required
def market_end(request, market_id):
    market = get_object_or_404(Market, id=market_id, user=request.user, is_active=True)
    if request.method == 'POST':
        market.ended_at = timezone.now()
        market.is_active = False
        market.save()
        messages.success(request, f"'{market.name}' has ended.")
        return redirect('market_dashboard')
    # GET with no modal: just bounce back to detail
    return redirect('market_detail', market_id=market_id)
@login_required
def sale_new(request):
    active_market = get_object_or_404(Market, user=request.user, is_active=True)

    cart, created = Cart.objects.get_or_create(
        market=active_market,
        user=request.user,
    )

    search = request.GET.get('search', '')
    search_results = []
    if search:
        search_results = Product.objects.filter(
            user=request.user,
            discontinued=False,
        ).filter(Q(name__icontains=search) | Q(sku__icontains=search))

    cart_items = cart.cart_items.select_related('product').all()
    sale_form = SaleForm()

    return render(request, 'inventory/sale_new.html', {
        'active_market': active_market,
        'cart': cart,
        'cart_items': cart_items,
        'search_results': search_results,
        'search': search,
        'sale_form': sale_form,
    })


@login_required
def sale_add_item(request, sku):
    if request.method != 'POST':
        return redirect('sale_new')

    active_market = get_object_or_404(Market, user=request.user, is_active=True)
    product = get_object_or_404(Product, sku=sku, user=request.user, discontinued=False)

    cart, created = Cart.objects.get_or_create(
        market=active_market,
        user=request.user,
    )

    # Increment if already in cart, otherwise create
    cart_item, item_created = CartItem.objects.get_or_create(cart=cart, product=product)
    if not item_created:
        cart_item.quantity += 1
        cart_item.save()

    return redirect(f"{reverse('sale_new')}?search={request.POST.get('search', '')}")


@login_required
def sale_remove_item(request, cart_item_id):
    if request.method != 'POST':
        return redirect('sale_new')

    cart_item = get_object_or_404(CartItem, id=cart_item_id, cart__user=request.user)
    
    if cart_item.quantity > 1:
        cart_item.quantity -= 1
        cart_item.save()
    else:
        cart_item.delete()

    return redirect('sale_new')

@login_required
def sale_complete(request):
    if request.method != 'POST':
        return redirect('sale_new')

    active_market = get_object_or_404(Market, user=request.user, is_active=True)
    cart = get_object_or_404(Cart, market=active_market, user=request.user)
    cart_items = cart.cart_items.select_related('product').all()

    if not cart_items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect('sale_new')

    form = SaleForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please fix the errors below.")
        return redirect('sale_new')

    payment_method = form.cleaned_data['payment_method']
    customer_type = form.cleaned_data['customer_type']
    discount_amount = form.cleaned_data['discount_amount'] or 0
    tip_amount = form.cleaned_data['tip_amount'] or 0

    subtotal = float(cart.subtotal)
    total = round(subtotal - float(discount_amount) + float(tip_amount), 2)

    sale = Sale.objects.create(
        market=active_market,
        payment_method=payment_method,
        customer_type=customer_type,
        subtotal=subtotal,
        discount_amount=discount_amount,
        tip_amount=tip_amount,
        total=total,
    )

    for item in cart_items:
        SaleItem.objects.create(
            sale=sale,
            product=item.product,
            product_name_snapshot=item.product.name,
            product_sku_snapshot=item.product.sku,
            unit_price_snapshot=item.product.price,
            quantity=item.quantity,
            line_total=float(item.line_total),
        )
        item.product.stock_quantity = max(0, item.product.stock_quantity - item.quantity)
        item.product.save()

    cart.delete()

    messages.success(request, f"Sale #{sale.id} completed — ${total}")
    return redirect('market_detail', market_id=active_market.id)

@login_required
def market_detail(request, market_id):
    market = get_object_or_404(Market, id=market_id, user=request.user)
    sales = market.sales.prefetch_related('items').order_by('-created_at')
    expenses = market.expenses.all()
    expense_form = MarketExpenseForm()

    if request.method == 'POST':
        action = request.POST.get('action')

        # ── Save notes ──
        if action == 'save_notes':
            market.notes = request.POST.get('notes', '')
            market.save()
            messages.success(request, "Notes saved.")
            return redirect('market_detail', market_id=market_id)

        # ── Add expense ──
        elif action == 'add_expense':
            expense_form = MarketExpenseForm(request.POST)
            if expense_form.is_valid():
                expense = expense_form.save(commit=False)
                expense.market = market
                expense.save()
                messages.success(request, "Expense added.")
                return redirect('market_detail', market_id=market_id)

        # ── Delete expense ──
        elif action == 'delete_expense':
            expense_id = request.POST.get('expense_id')
            MarketExpense.objects.filter(id=expense_id, market=market).delete()
            messages.success(request, "Expense removed.")
            return redirect('market_detail', market_id=market_id)

    # Stats
    total_revenue = sales.aggregate(t=Sum('total'))['t'] or 0
    total_tips = sales.aggregate(t=Sum('tip_amount'))['t'] or 0
    total_discounts = sales.aggregate(t=Sum('discount_amount'))['t'] or 0
    total_transactions = sales.count()
    cash_total = sales.filter(payment_method='cash').aggregate(t=Sum('total'))['t'] or 0
    card_total = sales.filter(payment_method='card').aggregate(t=Sum('total'))['t'] or 0
    avg_sale = round(float(total_revenue) / total_transactions, 2) if total_transactions else 0
    total_expenses = expenses.aggregate(t=Sum('amount'))['t'] or 0
    total_profit = round(float(total_revenue) - float(total_expenses), 2)
# Items sold
    total_items_sold = SaleItem.objects.filter(
        sale__market=market
    ).aggregate(t=Sum('quantity'))['t'] or 0

    # All items sold list
    items_sold = SaleItem.objects.filter(
        sale__market=market
    ).values('product_name_snapshot', 'product_sku_snapshot', 'unit_price_snapshot').annotate(
        total_qty=Sum('quantity'),
        total_revenue=Sum('line_total')
    ).order_by('-total_qty')

    # Customer type breakdown
    from django.db.models import Count
    customer_breakdown = sales.values('customer_type').annotate(
        count=Count('id'),
        total_spent=Sum('total')
    ).order_by('-count')

    # Category stats
    category_stats = Category.objects.filter(
        user=request.user
    ).annotate(
        total_qty=Sum(
            'products__sale_items__quantity',
            filter=Q(products__sale_items__sale__market=market)
        ),
        total_revenue=Sum(
            F('products__sale_items__line_total'),
            filter=Q(products__sale_items__sale__market=market)
        )
    ).filter(total_qty__isnull=False).order_by('-total_qty')

    # Per hour breakdown
    from collections import defaultdict
    hourly_stats = defaultdict(lambda: {'revenue': 0, 'items_sold': 0, 'sales': 0})
    for sale in sales:
        hour = timezone.localtime(sale.created_at).strftime('%I %p').lstrip('0') or '12 AM'
        hourly_stats[hour]['revenue'] += float(sale.total)
        hourly_stats[hour]['sales'] += 1
        for item in sale.items.all():
            hourly_stats[hour]['items_sold'] += item.quantity
    hourly_stats = dict(hourly_stats)

    # Colour stats
    colours = ['pink', 'purple', 'green', 'blue', 'yellow']
    colour_stats = []
    for colour in colours:
        qty = SaleItem.objects.filter(
            sale__market=market,
            product_name_snapshot__icontains=colour
        ).aggregate(t=Sum('quantity'))['t'] or 0
        revenue = SaleItem.objects.filter(
            sale__market=market,
            product_name_snapshot__icontains=colour
        ).aggregate(t=Sum('line_total'))['t'] or 0
        colour_stats.append({
            'colour': colour.title(),
            'qty': qty,
            'revenue': revenue,
        })
    colour_stats = sorted(colour_stats, key=lambda x: x['qty'], reverse=True)

    # Chart 1 — Revenue by hour
    from collections import defaultdict
    revenue_by_hour = defaultdict(float)
    for sale in sales:
        hour = timezone.localtime(sale.created_at).strftime('%I %p').lstrip('0') or '12 AM'
        revenue_by_hour[hour] += float(sale.total)
    revenue_hours = list(revenue_by_hour.keys())
    revenue_values = list(revenue_by_hour.values())

    # Chart 3 — Top products by quantity
    top_products = SaleItem.objects.filter(
        sale__market=market
    ).values('product_name_snapshot').annotate(
        total_qty=Sum('quantity')
    ).order_by('-total_qty')[:10]
    top_product_names = [p['product_name_snapshot'] for p in top_products]
    top_product_qtys = [p['total_qty'] for p in top_products]

    return render(request, 'inventory/market_detail.html', {
        'market': market,
        'sales': sales,
        'expenses': expenses,
        'expense_form': expense_form,
        'total_revenue': total_revenue,
        'total_tips': total_tips,
        'total_discounts': total_discounts,
        'total_transactions': total_transactions,
        'cash_total': cash_total,
        'card_total': card_total,
        'avg_sale': avg_sale,
        'total_expenses': total_expenses,
        'total_profit': total_profit,
        'revenue_hours': json.dumps(revenue_hours),
        'revenue_values': json.dumps(revenue_values),
        'cash_total_float': float(cash_total),
        'card_total_float': float(card_total),
        'top_product_names': json.dumps(top_product_names),
        'top_product_qtys': json.dumps(top_product_qtys),
        'total_items_sold': total_items_sold,
        'items_sold': items_sold,
        'customer_breakdown': customer_breakdown,
        'category_stats': category_stats,
        'hourly_stats': hourly_stats,
        'colour_stats': colour_stats,
    })
@login_required
def sale_edit(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id, market__user=request.user)
    items = sale.items.all()

    if request.method == 'POST':
        action = request.POST.get('action')

            # ===== Handle Delete =====
        if action == 'delete':
            # Restore stock for all items
            for item in items:
                if item.product:
                    item.product.stock_quantity += item.quantity
                    item.product.save()
            sale.delete()
            messages.success(request, f"Sale #{sale_id} deleted.")
            return redirect('market_detail', market_id=sale.market.id)

            # ===== Handle Remove Specific Item ====
        elif action == 'remove_item':
            if items.count() <= 1:
                messages.error(request, "Cannot remove the last item. Delete the whole sale instead.")
                return redirect('sale_edit', sale_id=sale_id)
            item_id = request.POST.get('item_id')
            item = get_object_or_404(SaleItem, id=item_id, sale=sale)
            # Restore stock for this item
            if item.product:
                item.product.stock_quantity += item.quantity
                item.product.save()
            item.delete()
            # Recalc subtotal and total after item removal
            sale.subtotal = sum(i.line_total for i in sale.items.all())
            sale.total = round(float(sale.subtotal) - float(sale.discount_amount) + float(sale.tip_amount), 2)
            sale.save()
            messages.success(request, "Item removed.")
            return redirect('sale_edit', sale_id=sale_id)

        # ===== Handle Form Save =====
        elif action == 'save':
            payment_method = request.POST.get('payment_method')
            if payment_method not in ('cash', 'card'):
                messages.error(request, "Invalid payment method.")
                return redirect('sale_edit', sale_id=sale_id)

            try:
                discount_amount = abs(round(float(request.POST.get('discount_amount', 0) or 0), 2))
                tip_amount = abs(round(float(request.POST.get('tip_amount', 0) or 0), 2))
            except ValueError:
                messages.error(request, "Invalid discount or tip amount.")
                return redirect('sale_edit', sale_id=sale_id)

            # Update quantities and adjust stock for the difference
            for item in items:
                qty_key = f'quantity_{item.id}'
                try:
                    new_qty = int(request.POST.get(qty_key, item.quantity))
                    if new_qty < 1:
                        new_qty = 1
                    old_qty = item.quantity
                    diff = new_qty - old_qty

                    # diff > 0 means more sold, reduce stock
                    # diff < 0 means less sold, restore stock
                    if diff != 0 and item.product:
                        item.product.stock_quantity = max(0, item.product.stock_quantity - diff)
                        item.product.save()

                    item.quantity = new_qty
                    item.line_total = round(float(item.unit_price_snapshot) * new_qty, 2)
                    item.save()
                except ValueError:
                    pass
                customer_type = request.POST.get('customer_type')
                if customer_type not in ('child', 'teen', 'young_adult', 'adult'):
                    messages.error(request, "Invalid customer type.")
                    return redirect('sale_edit', sale_id=sale_id)
                sale.customer_type = customer_type
            # Recalc totals
            subtotal = round(sum(float(i.line_total) for i in sale.items.all()), 2)
            total = round(subtotal - discount_amount + tip_amount, 2)

            sale.payment_method = payment_method
            sale.discount_amount = discount_amount
            sale.tip_amount = tip_amount
            sale.subtotal = subtotal
            sale.total = total
            sale.save()

            messages.success(request, f"Sale #{sale_id} updated.")
            return redirect('market_detail', market_id=sale.market.id)

    return render(request, 'inventory/sale_edit.html', {
        'sale': sale,
        'items': items,
    })
@login_required
def market_dashboard(request):
    from collections import defaultdict

    active_market = Market.objects.filter(user=request.user, is_active=True).first()

    # ── Past markets with per-market totals ──────────────────────────────────
    past_markets = Market.objects.filter(
        user=request.user, is_active=False
    ).order_by('-ended_at').annotate(
        total_revenue=Coalesce(
            Sum('sales__total'),
            Value(0),
            output_field=DecimalField(max_digits=10, decimal_places=2),
        ),
        transaction_count=Count('sales'),
    )

    all_past = list(past_markets)          # evaluated once, reused below
    market_count = len(all_past)

    # ── Global aggregate KPIs ────────────────────────────────────────────────
    all_sales = Sale.objects.filter(market__user=request.user, market__is_active=False)

    total_revenue_all   = all_sales.aggregate(t=Sum('total'))['t'] or 0
    total_tips_all      = all_sales.aggregate(t=Sum('tip_amount'))['t'] or 0
    total_transactions_all = all_sales.count()

    total_expenses_all = MarketExpense.objects.filter(
        market__user=request.user
    ).aggregate(t=Sum('amount'))['t'] or 0

    total_profit_all = round(float(total_revenue_all) - float(total_expenses_all), 2)

    avg_market_revenue     = round(float(total_revenue_all)      / market_count, 2) if market_count else 0
    avg_market_profit      = round(float(total_profit_all)       / market_count, 2) if market_count else 0
    avg_market_transactions = round(total_transactions_all       / market_count, 2) if market_count else 0
    avg_sale_value         = round(float(total_revenue_all) / total_transactions_all, 2) if total_transactions_all else 0

    # ── Best sellers (quantity mode only — clean, no broken percentage logic) ─
    best_sellers = list(
        SaleItem.objects.filter(
            sale__market__user=request.user,
            sale__market__is_active=False,
        ).values('product_sku_snapshot', 'product_name_snapshot').annotate(
            total_sold=Sum('quantity'),
            total_revenue=Sum('line_total'),
        ).order_by('-total_sold')
    )

    # ── Customer mix across all markets ──────────────────────────────────────
    customer_breakdown = all_sales.values('customer_type').annotate(
        count=Count('id'),
        total_spent=Sum('total'),
    ).order_by('-count')

    # ── Category stats across all markets ────────────────────────────────────
    category_stats = Category.objects.filter(
        user=request.user
    ).annotate(
        total_qty=Sum(
            'products__sale_items__quantity',
            filter=Q(
                products__sale_items__sale__market__user=request.user,
                products__sale_items__sale__market__is_active=False,
            )
        ),
        total_revenue=Sum(
            F('products__sale_items__line_total'),
            filter=Q(
                products__sale_items__sale__market__user=request.user,
                products__sale_items__sale__market__is_active=False,
            )
        )
    ).filter(total_qty__isnull=False).order_by('-total_qty')

    # ── Colour stats across all markets ──────────────────────────────────────
    colours = ['pink', 'purple', 'green', 'blue', 'yellow']
    colour_stats = []
    for colour in colours:
        qs = SaleItem.objects.filter(
            sale__market__user=request.user,
            sale__market__is_active=False,
            product_name_snapshot__icontains=colour,
        )
        qty     = qs.aggregate(t=Sum('quantity'))['t'] or 0
        revenue = qs.aggregate(t=Sum('line_total'))['t'] or 0
        colour_stats.append({'colour': colour.title(), 'qty': qty, 'revenue': revenue})
    colour_stats = sorted(colour_stats, key=lambda x: x['qty'], reverse=True)

    # ── Average hourly activity across all past markets ───────────────────────
    # Step 1: collect (revenue, items_sold) per hour-slot per market
    hour_market_revenue = defaultdict(lambda: defaultdict(float))
    hour_market_items   = defaultdict(lambda: defaultdict(int))

    all_sales_prefetched = Sale.objects.filter(
        market__user=request.user,
        market__is_active=False,
    ).prefetch_related('items')

    market_ids_seen = defaultdict(set)   # hour -> set of market_ids that had activity that hour

    for sale in all_sales_prefetched:
        local_dt = timezone.localtime(sale.created_at)          # ← converts, but...
        hour = timezone.localtime(sale.created_at).strftime('%I %p').lstrip('0') or '12 AM'
        mid  = sale.market_id
        hour_market_revenue[hour][mid] += float(sale.total)
        market_ids_seen[hour].add(mid)
        for item in sale.items.all():
            hour_market_items[hour][mid] += item.quantity

    # Step 2: average across however many markets had sales in that hour
    def _hour_sort_key(h):
        parts = h.split()
        num = int(parts[0])
        meridiem = parts[1] if len(parts) > 1 else 'AM'
        if meridiem == 'AM':
            return 0 if num == 12 else num        # 12 AM = midnight = 0
        else:
            return 12 if num == 12 else num + 12  # 12 PM = noon = 12, 1 PM = 13, etc.

    all_hours = sorted(set(hour_market_revenue.keys()), key=_hour_sort_key)
    avg_hourly_revenue = []
    avg_hourly_items   = []
    for hour in all_hours:
        mids = market_ids_seen[hour]
        n    = len(mids)
        avg_hourly_revenue.append(round(sum(hour_market_revenue[hour].values()) / n, 2))
        avg_hourly_items.append(round(sum(hour_market_items[hour].values())   / n, 1))

    return render(request, 'inventory/market_dashboard.html', {
        # nav
        'active_market': active_market,
        'past_markets':  past_markets,
        'market_count':  market_count,
        # global KPIs
        'avg_market_revenue':      avg_market_revenue,
        'avg_market_profit':       avg_market_profit,
        'avg_market_transactions': avg_market_transactions,
        'avg_sale_value':          avg_sale_value,
        'total_revenue_all':       total_revenue_all,
        'total_profit_all':        total_profit_all,
        # tables / charts
        'best_sellers':        best_sellers,
        'customer_breakdown':  customer_breakdown,
        'category_stats':      category_stats,
        'colour_stats':        colour_stats,
        # hourly chart data islands (JSON-safe)
        'avg_hour_labels':   json.dumps(all_hours),
        'avg_hour_revenue':  json.dumps(avg_hourly_revenue),
        'avg_hour_items':    json.dumps(avg_hourly_items),
    })
# =============================
#  Login Page View 
# ===========================

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