from collections import defaultdict

from django.shortcuts import render, redirect  # render templates, redirect users, fetch objects safely
from django.http import HttpResponse, JsonResponse  # standard and JSON responses
from django.contrib.auth import login  # log users in after signup/login
from django.contrib.auth.decorators import login_required  # restrict views to authenticated users
from django.contrib import messages  # display success/error messages to users
from django.utils import timezone # auto add curent date on market start
from urllib.parse import urlencode # For saving the url across pages 
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

# GET parameter names that count as inventory filters.
# Persisted to session on form submit, restored when returning to a bare URL.
INVENTORY_FILTER_KEYS = (
    'search',
    'sort_by_category',
    'show_zero_stock',
    'show_discontinued',
    'filter_state',
    'sort',
    'form_submitted',
)
@login_required # this will be for changeing the base url redirect depending if theres a market - if no market then redirect to normal inventory page if market then go to current market fro easy sale tracking while current market active
def root_redirect(request):
    active = Market.objects.filter(user=request.user, is_active=True).first()
    if active:
        return redirect('market_detail', market_id=active.id)
    return redirect('home_page')

@login_required
def home_page(request):
    # ── Filter persistence via Django session ──

    # If the filter form was submitted, save the current filters to session
    if 'form_submitted' in request.GET:
        saved_filters = {}
        for key in INVENTORY_FILTER_KEYS:
            values = request.GET.getlist(key)
            if values:
                saved_filters[key] = values
        request.session['inventory_filters'] = saved_filters

    # Otherwise, if URL has no filters and we have saved ones, redirect to apply them
    else:
        url_has_filters = any(key in request.GET for key in INVENTORY_FILTER_KEYS)
        saved_filters = request.session.get('inventory_filters')
        if saved_filters and not url_has_filters:
            return redirect(f"{request.path}?{urlencode(saved_filters, doseq=True)}")

    #|||||||||||||| Defining tables ||||||||||||||
    products = Product.objects.filter(user=request.user)
    categorys = Category.objects.filter(user=request.user)
    sub_categorys = SubCategory.objects.filter(user=request.user)

    #|||||||||||||| search logic ||||||||||||||
    searches = request.GET.get('search', '').strip().split()
    

    if searches:
        for search in searches: 
            products = products.filter(Q(name__icontains=search) | Q(sku__contains=search) |  Q(subCategory__name__icontains=search)) # __icontains is a looking for a case insensitive partial max
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
        active_market = Market.objects.filter(user=request.user, is_active=True).first()

        if action == "add":
            product.stock_quantity += 1
            if active_market:
                snapshot, _ = StockSnapshot.objects.get_or_create(
                    market=active_market,
                    product=product,
                    defaults={
                        'product_name_snapshot': product.name,
                        'product_sku_snapshot': product.sku,
                        'stock_at_start': 0,
                    }
                )
                snapshot.stock_at_start += 1
                snapshot.save()
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
    searches = search.strip().split()
    search_results = []
    if len(searches) > 0:
        search_results = Product.objects.filter(
            user=request.user,
            discontinued=False,
        )
        for search_word in searches:
            search_results = search_results.filter(Q(name__icontains=search_word) | Q(sku__icontains=search_word) |  Q(subCategory__name__icontains=search_word))

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
    # Step 2: get all sales for this market, newest first, pre-loading their items
    sales = market.sales.prefetch_related('items').order_by('-created_at')
    # Step 3: get all expenses logged for this market
    expenses = market.expenses.all()
    # Step 4: set up a blank expense form for the page (gets replaced below if invalid)
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

    # ── Overall totals ──
    # Step 1: total revenue across all sales in this market
    total_revenue = sales.aggregate(t=Sum('total'))['t'] or 0
    # Step 2: total tips collected
    total_tips = sales.aggregate(t=Sum('tip_amount'))['t'] or 0
    # Step 3: total discounts given
    total_discounts = sales.aggregate(t=Sum('discount_amount'))['t'] or 0
    # Step 4: how many separate sales happened
    total_transactions = sales.count()
    # Step 5: revenue that came in as cash
    cash_total = sales.filter(payment_method='cash').aggregate(t=Sum('total'))['t'] or 0
    # Step 6: revenue that came in as card
    card_total = sales.filter(payment_method='card').aggregate(t=Sum('total'))['t'] or 0
    # Step 7: average amount per sale (guard against divide-by-zero if there were no sales)
    avg_sale = round(float(total_revenue) / total_transactions, 2) if total_transactions else 0
    # Step 8: total money spent on expenses for this market
    total_expenses = expenses.aggregate(t=Sum('amount'))['t'] or 0
    # Step 9: revenue minus expenses
    total_profit = round(float(total_revenue) - float(total_expenses), 2)

    # ── Items sold (total count) ──
    # Step 1: get every sale item that belongs to a sale in this market
    market_sale_items = SaleItem.objects.filter(sale__market=market)
    # Step 2: add up the quantity column across all of them
    total_items_sold = market_sale_items.aggregate(t=Sum('quantity'))['t'] or 0

    # ── Items sold (breakdown by product) ──
    # Step 1: start from the same market sale items
    # Step 2: group them by product (name/sku/price identify a distinct product)
    # Step 3: within each group, total the quantity and the revenue
    # Step 4: order so the best-selling product is first
    items_sold = (
        market_sale_items
        .values('product_name_snapshot', 'product_sku_snapshot', 'unit_price_snapshot') # we take any item that has the same sku name nad price meaning that has to be a unique item
        .annotate(
            total_qty=Sum('quantity'),
            total_revenue=Sum('line_total'),
        )
        .order_by('-total_qty')
    )
    # example ouput
# <QuerySet [ // rreturns list of dictionaty
#     {
            # first it sorts by these 3 values
#         'product_name_snapshot': 'Kirby Luffy', 
#         'product_sku_snapshot': 41, 
#         'unit_price_snapshot': Decimal('35.00'), 
            # then annotate runs and dirives these valeus and appens them to list 
#         'total_qty': 12, 
#         'total_revenue': Decimal('420.00')
#     },
#     {
#         'product_name_snapshot': 'Pink Whale', 
#         'product_sku_snapshot': 20, 
#         'unit_price_snapshot': Decimal('6.00'), 
#         'total_qty': 5, 
#         'total_revenue': Decimal('30.00')
#     }
# ]>
    # ── Customer type breakdown ──
    # Step 1: group this market's sales by customer_type
    # Step 2: count how many sales came from each type
    # Step 3: total how much each type spent
    # Step 4: order so the most common customer type is first
    customer_breakdown = (
        sales
        .values('customer_type')
        .annotate(
            count=Count('id'),
            total_spent=Sum('total'),
        )
        .order_by('-count')
    )

    # ── Category stats ──
    # Step 1: start from every category this user owns
    # Step 2: for each category, only look at sale items from THIS market
    # Step 3: total the quantity and revenue for that category, in this market
    # Step 4: drop categories that had no sales at this market
    # Step 5: order so the best-selling category is first

    #Each caterogry we look and each product that relate to that category then we lloke at which all sales items that reference those products then each sale taht those sale items re in and finally the market that has those - ultiamtly filtering out all 
    category_stats = (
        Category.objects
        .filter(user=request.user)
        .annotate(
            total_qty=Sum('products__sale_items__quantity', filter=Q(products__sale_items__sale__market=market)),
            total_revenue=Sum(F('products__sale_items__line_total'), filter=Q(products__sale_items__sale__market=market)),
        )
        .filter(total_qty__isnull=False)
        .order_by('-total_qty')
    )

    # ── Per-hour breakdown (used for both the table and the revenue chart) ──
    # Step 1: set up an empty bucket for each hour, so we don't need to check "does this hour exist yet"
    hourly_stats = defaultdict(lambda: {'revenue': 0, 'items_sold': 0, 'sales': 0})
    # Step 2: walk through every sale in this market once
    for sale in sales:
        # Step 2a: figure out which hour bucket this sale belongs to (in local time, not UTC)
        hour = timezone.localtime(sale.created_at).strftime('%I %p').lstrip('0') or '12 AM'
        # Step 2b: add this sale's revenue and count into that hour's bucket
        hourly_stats[hour]['revenue'] += float(sale.total)
        hourly_stats[hour]['sales'] += 1
        # Step 2c: add up how many items were part of this sale, into the same bucket
        for item in sale.items.all():
            hourly_stats[hour]['items_sold'] += item.quantity
    # Step 3: convert back to a plain dict now that we're done adding to it
    hourly_stats = dict(hourly_stats)

    # ── Colour stats ──
    colours = ['pink', 'purple', 'green', 'blue', 'yellow']
    colour_stats = []
    for colour in colours:
        # Step 1: find sale items in this market whose product name mentions this colour
        colour_items = SaleItem.objects.filter(
            sale__market=market,
            product_name_snapshot__icontains=colour,
        )
        # Step 2: total the quantity AND revenue in one query instead of two
        colour_totals = colour_items.aggregate(qty=Sum('quantity'), revenue=Sum('line_total'))
        # Step 3: save this colour's totals to the list
        colour_stats.append({
            'colour': colour.title(),
            'qty': colour_totals['qty'] or 0,
            'revenue': colour_totals['revenue'] or 0,
        })
    # Step 4: order so the most-sold colour is first
    colour_stats = sorted(colour_stats, key=lambda x: x['qty'], reverse=True)

    # ── Chart 1 — Revenue by hour ──
    # Step 1: reuse hourly_stats instead of looping over sales a second time
    revenue_hours = list(hourly_stats.keys())
    revenue_values = [bucket['revenue'] for bucket in hourly_stats.values()]

    # ── Chart 3 — Top products by quantity ──

    #------------- TOP PRODUCTS BY QUANTITY / REVENU -----------
    # ---- Subcategory seperation logic ------
    per_product_stats = list(
        market_sale_items
        .values(
            'product_sku_snapshot',
            'product_name_snapshot',
            'unit_price_snapshot',
            'product__subCategory__id',
            'product__subCategory__name',
        )
        .annotate(
            total_qty=Sum('quantity'),
            total_revenue=Sum('line_total'),
        )
    )

    # Step 2: split into standalone products vs subcategory buckets — same shape as home_page.
    standalone_products = []
    subcategory_groups = {}  # keyed by subcategory id

    for row in per_product_stats:
        sub_id = row['product__subCategory__id']

        if sub_id is None:
            standalone_products.append({
                'type': 'product',
                'name': row['product_name_snapshot'],
                'sku': row['product_sku_snapshot'],
                'total_qty': row['total_qty'],
                'total_revenue': float(row['total_revenue']),
            })
        else:
            # Step 2a: first time seeing this subcategory, set up its bucket
            if sub_id not in subcategory_groups:
                subcategory_groups[sub_id] = {
                    'type': 'subcategory',
                    'name': row['product__subCategory__name'],
                    'sku': sub_id,          # used as the expand/collapse key in the template
                    'total_qty': 0,
                    'total_revenue': 0.0,
                    'children': [],
                }
            # Step 2b: fold this product's totals into the subcategory bucket
            bucket = subcategory_groups[sub_id]
            bucket['total_qty'] += row['total_qty']
            bucket['total_revenue'] += float(row['total_revenue'])
            bucket['children'].append({
                'name': row['product_name_snapshot'],
                'sku': row['product_sku_snapshot'],
                'total_qty': row['total_qty'],
                'total_revenue': float(row['total_revenue']),
            })

    # Step 3: the combined list is what home_page calls combined_products — same idea.
    combined_top_products = standalone_products + list(subcategory_groups.values())

    # Step 4: produce two sorted views. We copy each subcategory dict so the two views can
    #         sort their children by different metrics without stepping on each other
    #         (both views share the same underlying dicts otherwise, and the second sort
    #         of children would silently overwrite the first).
    def _sorted_view(combined, sort_key):
        result = []
        for item in combined:
            if item['type'] == 'subcategory':
                item = {**item, 'children': sorted(item['children'], key=lambda c: c[sort_key], reverse=True)}
            result.append(item)
        return sorted(result, key=lambda x: x[sort_key], reverse=True)[:10]

    top_products_grouped_by_qty = _sorted_view(combined_top_products, 'total_qty')
    top_products_grouped_by_revenue = _sorted_view(combined_top_products, 'total_revenue')

    # -------- Top product by perctage sold ----------------
    #total quantiy by perctage sold - total sold of that product / snapshot of stock before{unless == 0} * 100
    # ── Top products by percentage sold ──

    # Step 1: get how many of each product sold at this market 
    qty_sold_per_product = (
        market_sale_items
        .values('product_name_snapshot', 'product_sku_snapshot')
        .annotate(total_qty=Sum('quantity'))
    )
    # Step 2: get the starting stock for every product snapshot taken at this market
    stock_snapshots = StockSnapshot.objects.filter(market=market)
    # Step 3: turn the snapshots into a lookup dict, keyed by SKU, so step 4 can find them fast
    stock_at_start_by_sku = {
        snapshot.product_sku_snapshot: snapshot.stock_at_start
        for snapshot in stock_snapshots
    }

    # Step 4: for each product sold, calculate what percentage of its starting stock got sold
    top_products_by_percentage_sold = []
    for product in qty_sold_per_product:
        sku = product['product_sku_snapshot']
        starting_stock = stock_at_start_by_sku.get(sku)
        # Step 4a: skip this product if we have no snapshot for it, or it started at 0 (avoid divide-by-zero)
        if not starting_stock:
            continue

        percentage_sold = round((product['total_qty'] / starting_stock) * 100, 1)
        top_products_by_percentage_sold.append({
            'product_name': product['product_name_snapshot'],
            'qty_sold': product['total_qty'],
            'starting_stock': starting_stock,
            'percentage_sold': percentage_sold,
        })
    # Step 5: sort so the highest percentage sold is first, and keep only the top 10
    top_products_by_percentage_sold = sorted(
        top_products_by_percentage_sold,
        key=lambda p: p['percentage_sold'],
        reverse=True
    )[:10]

    top_products = (
        market_sale_items
        .values('product_name_snapshot')
        .annotate(total_qty=Sum('quantity'))
        .order_by('-total_qty')[:10]
    )

    top_products_by_total_made = (
        market_sale_items
        .values('product_name_snapshot')
        .annotate(total_revenue=Sum('line_total'))
        .order_by('-total_revenue')[:10]
    )
    # ---------- Combined Inventory Sold list — grouped by subcategory, home_page style --------------
    standalone_items = []
    subcategory_item_groups = {}

    for row in per_product_stats:
        sub_id = row['product__subCategory__id']

        if sub_id is None:
            standalone_items.append({
                'type': 'product',
                'name': row['product_name_snapshot'],
                'sku': row['product_sku_snapshot'],
                'unit_price': row['unit_price_snapshot'],
                'total_qty': row['total_qty'],
                'total_revenue': float(row['total_revenue']),
            })
        else:
            if sub_id not in subcategory_item_groups:
                subcategory_item_groups[sub_id] = {
                    'type': 'subcategory',
                    'name': row['product__subCategory__name'],
                    'sku': sub_id,                               # used as unique collapse key
                    'min_price': row['unit_price_snapshot'],     # cheapest child
                    'total_qty': 0,
                    'total_revenue': 0.0,
                    'children': [],
                }
            bucket = subcategory_item_groups[sub_id]
            bucket['total_qty'] += row['total_qty']
            bucket['total_revenue'] += float(row['total_revenue'])
            if row['unit_price_snapshot'] < bucket['min_price']:
                bucket['min_price'] = row['unit_price_snapshot']
            bucket['children'].append({
                'name': row['product_name_snapshot'],
                'sku': row['product_sku_snapshot'],
                'unit_price': row['unit_price_snapshot'],
                'total_qty': row['total_qty'],
                'total_revenue': float(row['total_revenue']),
            })

    # Sort children inside each group by qty (biggest colour first)
    for group in subcategory_item_groups.values():
        group['children'] = sorted(group['children'], key=lambda c: c['total_qty'], reverse=True)

    # Full combined list, sorted by qty like items_sold was
    combined_items_sold = sorted(
        standalone_items + list(subcategory_item_groups.values()),
        key=lambda x: x['total_qty'],
        reverse=True,
    )
    # Step 5: pull the names and quantities out into two separate lists for Chart.js
    top_product_names = [p['product_name_snapshot'] for p in top_products]
    top_product_qtys = [p['total_qty'] for p in top_products]

    # ------------ Records panel: search + sort ------------------

    # Step 1: which table is being searched, and what was typed — both come from the URL
    search_target = request.GET.get('target', 'history')   # 'history' or 'inventory'
    search_query = request.GET.get('q', '').strip()

    # Step 2: which column Sale History should be sorted by (defaults to newest sale first)
    sale_sort = request.GET.get('sale_sort', '-created_at')
    valid_sale_sort_fields = {'created_at', 'payment_method', 'subtotal', 'discount_amount', 'tip_amount', 'total'}
    if sale_sort.lstrip('-') not in valid_sale_sort_fields:
        sale_sort = '-created_at'

    # Step 3: apply the sort — this is just an ORDER BY, so it's fine to do at the database level
    sorted_sales = sales.order_by(sale_sort)

    # Step 4: start with everything unfiltered — only the table matching search_target gets narrowed
    filtered_sales = sorted_sales
    filtered_items_sold = items_sold

    if search_query and search_target == 'history':
        # Step 4a: parse "10" as hour-only, or "10:05" as hour + minute
        query = search_query.lower()
        hour_query, _, minute_query = query.partition(':')
        hour_query = hour_query.strip()
        minute_query = minute_query.strip() if minute_query else None

        # Step 4b: check each sale — time has to run in Python since it compares against the
        # LOCAL 12-hour clock display, not the raw UTC value stored in the database
        matching_sales = []
        for sale in sorted_sales:
            local_dt = timezone.localtime(sale.created_at)
            sale_hour = int(local_dt.strftime('%I'))    # 1–12
            sale_minute = int(local_dt.strftime('%M'))  # 0–59

            is_time_match = (
                hour_query.isdigit()
                and int(hour_query) == sale_hour
                and (minute_query is None or (minute_query.isdigit() and int(minute_query) == sale_minute))
            )
            is_payment_match = query in sale.get_payment_method_display().lower()
            is_id_match = query.lstrip('#') == str(sale.id)

            if is_time_match or is_payment_match or is_id_match:
                matching_sales.append(sale)
        filtered_sales = matching_sales

    elif search_query and search_target == 'inventory':
        searches = search_query.lower().split()

        def _matches_all_words(name, sku, sub_name=''):
            # Every search word must appear in at least one of the three fields (AND across words, OR across fields)
            name_lower = (name or '').lower()
            sku_lower = str(sku or '').lower()
            sub_lower = (sub_name or '').lower()
            for word in searches:
                if word not in name_lower and word not in sku_lower and word not in sub_lower:
                    return False
            return True

        filtered_combined = []
        for item in combined_items_sold:
            if item['type'] == 'product':
                if _matches_all_words(item['name'], item['sku']):
                    filtered_combined.append(item)
            else:
                # Subcategory: if the group name matches, keep all children.
                # Otherwise check each child — a child inherits its parent's subcategory name for matching.
                if _matches_all_words('', '', item['name']):
                    filtered_combined.append(item)
                else:
                    matching_children = [
                        child for child in item['children']
                        if _matches_all_words(child['name'], child['sku'], item['name'])
                    ]
                    if matching_children:
                        filtered_combined.append({**item, 'children': matching_children})

        filtered_combined_items_sold = filtered_combined
    else:
        filtered_combined_items_sold = combined_items_sold
    base_query = request.GET.copy()
    base_query.pop('sale_sort', None)
    base_query_string = base_query.urlencode()


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
        'top_products_by_total_made': top_products_by_total_made,
        'top_products_by_percentage_sold': top_products_by_percentage_sold,
        'search_query':          search_query,
        'search_query':        search_query,
        'search_target':       search_target,
        'sale_sort':           sale_sort,
        'base_query':          base_query_string,
        'filtered_sales':      filtered_sales,
        'filtered_items_sold': filtered_items_sold,
        'top_products_grouped_by_qty': top_products_grouped_by_qty,
    'top_products_grouped_by_revenue': top_products_grouped_by_revenue,
    'filtered_combined_items_sold': filtered_combined_items_sold,
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
    active_market = Market.objects.filter(user=request.user, is_active=True).first()

    # ── Past markets with per-market totals ──
    # Step 1: get every market this user has already ended, most recently ended first
    past_markets = Market.objects.filter(user=request.user, is_active=False).order_by('-ended_at')
    # Step 2: attach each market's total revenue and sale count directly onto the queryset
    #         Coalesce swaps in 0 whenever a market has zero sales (Sum alone would give None there)
    past_markets = past_markets.annotate(
        total_revenue=Coalesce(
            Sum('sales__total'),
            Value(0),
            output_field=DecimalField(max_digits=10, decimal_places=2),
        ),
        transaction_count=Count('sales'),
    )
    # Step 3: run the query once, keep it as a list — market_count below reuses this instead of a second query
    all_past = list(past_markets)
    market_count = len(all_past)

    # ── Global aggregate  (across every past market) ──
    # Step 1: every sale that belongs to one of this user's past (ended) markets
    all_sales = Sale.objects.filter(market__user=request.user, market__is_active=False)
    # Step 2: total revenue, tips, and how many sales happened, across all of those
    total_revenue_all = all_sales.aggregate(t=Sum('total'))['t'] or 0
    total_tips_all = all_sales.aggregate(t=Sum('tip_amount'))['t'] or 0
    total_transactions_all = all_sales.count()

    # Step 3: total expenses logged across all of this user's markets
    total_expenses_all = MarketExpense.objects.filter(
        market__user=request.user,
        market__is_active=False,
    ).aggregate(t=Sum('amount'))['t'] or 0
    # Step 4: overall profit = revenue minus expenses
    total_profit_all = round(float(total_revenue_all) - float(total_expenses_all), 2)
    # Step 5: per-market and per-sale averages, guarded against divide-by-zero
    avg_market_revenue = round(float(total_revenue_all) / market_count, 2) if market_count else 0
    avg_market_profit = round(float(total_profit_all) / market_count, 2) if market_count else 0
    avg_market_transactions = round(total_transactions_all / market_count, 2) if market_count else 0
    avg_sale_value = round(float(total_revenue_all) / total_transactions_all, 2) if total_transactions_all else 0


    # ── Best sellers grouped by subcategory — same pattern as market_detail ──
    # Difference from market_detail: source spans EVERY ended market, not just one.

    # Step 1: per-product totals across all past markets, tagged with subcategory info
    per_product_stats_all = list(
        SaleItem.objects
        .filter(sale__market__user=request.user, sale__market__is_active=False)
        .values(
            'product_sku_snapshot',
            'product_name_snapshot',
            'product__subCategory__id',
            'product__subCategory__name',
        )
        .annotate(
            total_qty=Sum('quantity'),
            total_revenue=Sum('line_total'),
        )
    )

    # Step 2: split into standalone products vs subcategory buckets
    standalone_bs = []
    subcategory_bs_groups = {}  # keyed by subcategory id

    for row in per_product_stats_all:
        sub_id = row['product__subCategory__id']

        if sub_id is None:
            standalone_bs.append({
                'type': 'product',
                'name': row['product_name_snapshot'],
                'sku': row['product_sku_snapshot'],
                'total_qty': row['total_qty'],
                'total_revenue': float(row['total_revenue']),
            })
        else:
            if sub_id not in subcategory_bs_groups:
                subcategory_bs_groups[sub_id] = {
                    'type': 'subcategory',
                    'name': row['product__subCategory__name'],
                    'sku': sub_id,
                    'total_qty': 0,
                    'total_revenue': 0.0,
                    'children': [],
                }
            bucket = subcategory_bs_groups[sub_id]
            bucket['total_qty'] += row['total_qty']
            bucket['total_revenue'] += float(row['total_revenue'])
            bucket['children'].append({
                'name': row['product_name_snapshot'],
                'sku': row['product_sku_snapshot'],
                'total_qty': row['total_qty'],
                'total_revenue': float(row['total_revenue']),
            })

    combined_best_sellers = standalone_bs + list(subcategory_bs_groups.values())

    # Step 3: two sorted views. Each subcategory dict is copied so the two views
    #         can sort their children by different metrics without stepping on each other
    #         (both views share the same underlying dicts otherwise, and the second sort
    #         of children would silently overwrite the first).
    def _sorted_bs_view(combined, sort_key):
        result = []
        for item in combined:
            if item['type'] == 'subcategory':
                item = {**item, 'children': sorted(item['children'], key=lambda c: c[sort_key], reverse=True)}
            result.append(item)
        return sorted(result, key=lambda x: x[sort_key], reverse=True)[:10]

    best_sellers_grouped_by_qty = _sorted_bs_view(combined_best_sellers, 'total_qty')
    best_sellers_grouped_by_revenue = _sorted_bs_view(combined_best_sellers, 'total_revenue')
    # ── Best sellers by percentage sold — averaged across every market it appeared in ──
    # Goal: work out what % of starting stock sold AT EACH market a product appeared in,
    #       then average those percentages — so one lucky/unlucky market doesn't skew things,
    #       and a slow-seller isn't punished just because it took many markets to finally sell out.

    # Step 1: every stock snapshot from this user's past markets — one row per (market, product)
    past_snapshots = StockSnapshot.objects.filter(
        market__user=request.user,
        market__is_active=False,
    ).values('market_id', 'product_sku_snapshot', 'product_name_snapshot', 'stock_at_start')

    # Step 2: quantity sold per (market, product) — same grouping shape as the snapshots above
    qty_sold_per_market_product = (
        SaleItem.objects
        .filter(sale__market__user=request.user, sale__market__is_active=False)
        .values('sale__market_id', 'product_sku_snapshot')
        .annotate(total_qty=Sum('quantity'))
    )
    # Step 3: turn that into a lookup dict keyed by (market_id, sku), so step 4 can find it fast
    qty_sold_lookup = {
        (row['sale__market_id'], row['product_sku_snapshot']): row['total_qty']
        for row in qty_sold_per_market_product
    }

    # Step 4: walk through every snapshot and bucket its numbers by product (sku)
    product_market_data = defaultdict(lambda: {'name': '', 'percentages': [], 'stock_totals': [], 'qty_totals': []})
    for snapshot in past_snapshots:
        sku = snapshot['product_sku_snapshot']
        stock_at_start = snapshot['stock_at_start']

        # Step 4a: skip markets where this product started with 0 stock (can't divide by 0)
        if not stock_at_start:
            continue

        qty_sold_this_market = qty_sold_lookup.get((snapshot['market_id'], sku), 0)
        this_market_percentage = (qty_sold_this_market / stock_at_start) * 100

        bucket = product_market_data[sku]
        bucket['name'] = snapshot['product_name_snapshot']
        bucket['percentages'].append(this_market_percentage)
        bucket['stock_totals'].append(stock_at_start)
        bucket['qty_totals'].append(qty_sold_this_market)

    # Step 5: average each product's numbers across however many markets it appeared in
    best_sellers_by_percentage_sold = []
    for sku, data in product_market_data.items():
        markets_counted = len(data['percentages'])
        best_sellers_by_percentage_sold.append({
            'product_name':   data['name'],
            'percentage_sold': round(sum(data['percentages']) / markets_counted, 1),
            'avg_stock_made':  round(sum(data['stock_totals']) / markets_counted, 1),
            'avg_qty_sold':    round(sum(data['qty_totals']) / markets_counted, 1),
            'markets_counted': markets_counted,
        })

    # Step 6: order so the highest average percentage is first, keep the top 10
    best_sellers_by_percentage_sold = sorted(
        best_sellers_by_percentage_sold,
        key=lambda p: p['percentage_sold'],
        reverse=True
    )[:10]
    # ── Customer mix across all past markets ──
    # Step 1: group all_sales by customer_type
    # Step 2: count sales and total spend per type
    # Step 3: order so the most common type is first
    customer_breakdown = (
        all_sales
        .values('customer_type')
        .annotate(count=Count('id'), total_spent=Sum('total'))
        .order_by('-count')
    )

    # ── Category stats across all past markets ──
    # Step 1: build the "belongs to one of this user's ended markets" condition once, reused below
    # Step 2: for every category, total the quantity + revenue from sale items tied to those markets
    # Step 3: drop categories that had no sales at all
    # Step 4: order so the best-selling category is first
    category_stats = (
        Category.objects
        .filter(user=request.user)
        .annotate(
            total_qty=Sum('products__sale_items__quantity', filter=Q(products__sale_items__sale__market__user=request.user,products__sale_items__sale__market__is_active=False,)),
            total_revenue=Sum('products__sale_items__line_total', filter=Q(products__sale_items__sale__market__user=request.user,products__sale_items__sale__market__is_active=False,)),
        )
        .filter(total_qty__isnull=False)
        .order_by('-total_qty')
    )

    # ── Colour stats across all past markets ──
    colours = ['pink', 'purple', 'green', 'blue', 'yellow']
    colour_stats = []
    for colour in colours:
        # Step 1: sale items from past markets whose product name mentions this colour
        colour_items = SaleItem.objects.filter(
            sale__market__user=request.user,
            sale__market__is_active=False,
            product_name_snapshot__icontains=colour,
        )
        # Step 2: total quantity AND revenue in one query instead of two
        colour_totals = colour_items.aggregate(qty=Sum('quantity'), revenue=Sum('line_total'))
        colour_stats.append({
            'colour': colour.title(),
            'qty': colour_totals['qty'] or 0,
            'revenue': colour_totals['revenue'] or 0,
        })
    # Step 3: order so the most-sold colour is first
    colour_stats = sorted(colour_stats, key=lambda x: x['qty'], reverse=True)

    # ── Average hourly activity across all past markets ──
    # Goal: for each hour slot (9 AM, 10 AM, ...), show the AVERAGE revenue/items per market
    #       during that hour — not the total, since not every market had activity every hour.

    # Step 1: pull every sale from past markets, with its items preloaded
    all_sales_prefetched = Sale.objects.filter(
        market__user=request.user,
        market__is_active=False,
    ).prefetch_related('items')

    # Step 2: empty per-hour, per-market buckets (outer key = hour, inner key = market id)
    hour_market_revenue = defaultdict(lambda: defaultdict(float))
    hour_market_items = defaultdict(lambda: defaultdict(int))
    # Step 3: track which markets actually had a sale in each hour, so we know what to divide by later
    market_ids_seen_per_hour = defaultdict(set)

    # Step 4: walk through every sale once, filing it into the right hour + market bucket
    for sale in all_sales_prefetched:
        hour = timezone.localtime(sale.created_at).strftime('%I %p').lstrip('0') or '12 AM'
        market_id = sale.market_id

        hour_market_revenue[hour][market_id] += float(sale.total)
        market_ids_seen_per_hour[hour].add(market_id)

        for item in sale.items.all():
            hour_market_items[hour][market_id] += item.quantity

    # Step 5: sort hours into real clock order (alphabetical would put "10 AM" before "9 AM")
    def _hour_sort_key(hour_label):
        number, meridiem = hour_label.split()
        number = int(number)
        if meridiem == 'AM':
            return 0 if number == 12 else number
        return 12 if number == 12 else number + 12

    all_hours = sorted(hour_market_revenue.keys(), key=_hour_sort_key)

    # Step 6: for each hour, average its totals across however many markets had activity that hour
    avg_hourly_revenue = []
    avg_hourly_items = []
    for hour in all_hours:
        markets_active_this_hour = len(market_ids_seen_per_hour[hour])
        total_revenue_this_hour = sum(hour_market_revenue[hour].values())
        total_items_this_hour = sum(hour_market_items[hour].values())

        avg_hourly_revenue.append(round(total_revenue_this_hour / markets_active_this_hour, 2))
        avg_hourly_items.append(round(total_items_this_hour / markets_active_this_hour, 1))

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
        'best_sellers_by_percentage_sold':  best_sellers_by_percentage_sold,
        'best_sellers_grouped_by_qty': best_sellers_grouped_by_qty,
'best_sellers_grouped_by_revenue': best_sellers_grouped_by_revenue,
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