import re

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session, abort
)

from project.db import (
    get_categories, get_category, get_artwork,
    get_vendor, get_vendor_items, get_all_vendors, delete_artwork,
    filter_items, generate_kpi, publish_artwork, mysql,
    get_listed_artworks_for_category_with_details,
    get_customer_postcode,
    get_customer_address_details,
    get_artworks_for_vendor_gallery,
    add_artwork_from_form,
    admin_get_orders,
    admin_get_order_items,
    admin_get_order_statuses,
    admin_update_order,
    admin_update_order_item,
    get_vendor_artwork,
    update_artwork_from_form,
    email_phone_in_use,
    register_account,
    check_for_user_with_hint,
    add_order, 
    ensure_address, can_fulfill_request
)

from project.session import (
    add_to_cart, empty_cart, remove_from_cart,
    update_cart_item, get_cart, delivery_cost_from_session,
    convert_cart_to_order
)

from project.forms import (
    AddToCartForm, ArtworkForm, LoginForm, CheckoutForm, RegisterForm
)

from project.wrappers import (
    only_admins, only_vendors, only_guests_or_customers, only_guests, only_customers
)


bp = Blueprint('main', __name__)  


@bp.route('/')
def index():
    sort = request.args.get('sort', default='latest')
    min_price = request.args.get('min', type=float)
    max_price = request.args.get('max', type=float)
    q = request.args.get('q', default=None)
    category_id = request.args.get('category_id', type=int)

    if q:
        q = q.strip() or None

    allowed_sorts = {'latest', 'oldest', 'price_asc', 'price_desc', 'title'}
    if sort not in allowed_sorts:
        sort = 'latest'

    has_active_filters = any([
        category_id,
        min_price is not None,
        max_price is not None,
        q,
        sort != 'latest'
    ])

    artworks = filter_items(
        category_id=category_id,
        min_price=min_price,
        max_price=max_price,
        q=q,
        availability='Listed',
        sort=sort,
        limit=None 
    )

    vendors = get_all_vendors(limit=12)
    categories = get_categories()
    return render_template(
        'index.html',
        vendors=vendors,
        artworks=artworks,
        categories=categories,
        active_category=category_id,
        filters={
            'sort': sort,
            'min': min_price,
            'max': max_price,
            'category_id': category_id,
            'q': q
        },
        has_active_filters=has_active_filters
    )

# Category listing
@bp.route('/category/<int:category_id>/')
def category_items(category_id):
    category_obj = get_category(category_id)
    if not category_obj:
        abort(404)
    
    # Use the dict-like category from get_category
    category_dict = {
        'category_id': category_obj.category_id,
        'categoryName': category_obj.categoryName
    }

    items = get_listed_artworks_for_category_with_details(category_id)

    return render_template('category_items.html', category=category_dict, items=items)


# Item details (with AddToCart)
@bp.route('/item/<int:artwork_id>/', methods=['GET', 'POST'])
def item_details(artwork_id):
    item = get_artwork(artwork_id)
    if not item:
        flash("Item not found", "warning")
        return redirect(url_for('main.index'))
    
    vendor = get_vendor(item.vendor_id)
    category = get_category(item.category_id) if item.category_id else None
    
    default_postcode = None
    u = session.get('user') or {}
    if u.get('role') == 'customer' and u.get('id'):
        default_postcode = get_customer_postcode(int(u['id']))

    form = AddToCartForm()
    if request.method == 'GET' and default_postcode and not form.postcode.data:
        form.postcode.data = default_postcode

    if request.method == 'POST':
        extra_errors = False
        if form.validate_on_submit():
            preset = form.durationPreset.data or 'standard'
            quantity = form.quantity.data or 1
            weeks = 1 if preset == 'standard' else form.weeks.data

            if preset == 'custom':
                if weeks is None:
                    form.weeks.errors.append('Please enter the number of weeks.')
                    extra_errors = True
                elif weeks < 2 or weeks > 50:
                    form.weeks.errors.append('Custom duration must be between 2 and 50 weeks.')
                    extra_errors = True

            if not extra_errors:
                postcode = (form.postcode.data or '').strip()
                if postcode:
                    session['checkout_postcode'] = postcode

                if add_to_cart(artwork_id, quantity, weeks or 1):
                    flash('Added to cart.')
                return redirect(url_for('main.cart'))
        else:
            extra_errors = True

        if extra_errors:
            flash('Please correct the errors highlighted below.', 'error')

    return render_template('item_details.html', item=item, vendor=vendor, category=category, 
                           form=form, default_postcode=default_postcode)


#  Vendor gallery (public profile + items)
@bp.route('/vendor/<int:vendor_id>/')
def vendor_gallery(vendor_id):
    vendor = get_vendor(vendor_id)
    if not vendor:
        abort(404)

    items = get_artworks_for_vendor_gallery(vendor_id)

    return render_template('vendor_gallery.html', vendor=vendor, items=items)


#  Vendor management (list & publish artworks)
@bp.route('/vendor/self_gallery/')
@only_vendors
def vendor_self_view():
    user = session.get('user', {})
    vendor_id2 = int(user.get('id'))
    return redirect(url_for('main.vendor_gallery', vendor_id = vendor_id2))


@bp.route('/vendor/manage/', methods=['GET', 'POST'])
@only_vendors
def vendor_manage():
    user = session.get('user') or {}
    vendor_id = int(user.get('id'))

    vendor = get_vendor(vendor_id)
    categories = get_categories() or []
    items = get_vendor_items(vendor_id)  # keep unfiltered for management
    form = ArtworkForm()

    # Populate select choices (no blank option)
    form.vendor_id.choices = [(vendor_id, "Me")]
    form.category_id.choices = [(c.category_id, c.categoryName) for c in categories]

    if request.method == 'POST' and form.validate_on_submit():
        add_artwork_from_form(form)
        flash('Artwork published.')
        return redirect(url_for('main.vendor_manage'))

    # Refresh items if POST modified anything (safe even on GET)
    items = get_vendor_items(vendor_id)

    # Always compute KPI and pass it to the template
    kpi = generate_kpi(vendor_id) or {
        "revenue": 0, "items_leased": 0,
        "inventory_total": 0, "inventory_active": 0,
        "orders_count": 0
    }

    return render_template(
        'vendor_management.html',
        vendor=vendor,
        items=items,
        form=form,
        categories=categories,
        kpi=kpi,                   
    )

# Cart
@bp.route('/cart/', methods=['GET'])
@only_guests_or_customers
def cart():
    c = get_cart()

    # If no postcode stored yet, and a customer is logged in, pull it from DB
    if not (session.get('checkout_postcode') or '').strip():
        u = session.get('user') or {}
        is_customer = (u.get('role') == 'customer' or u.get('type') == 'customer')
        cust_id = u.get('id') or u.get('customer_id') or u.get('customerID') or u.get('customerId')
        try:
            cust_id = int(cust_id) if cust_id is not None else None
        except Exception:
            cust_id = None

        if is_customer and cust_id:
            postcode = get_customer_postcode(cust_id)
            if postcode:
                session['checkout_postcode'] = str(postcode)

    # Compute delivery using the same logic everywhere (reads session['checkout_postcode'])
    delivery_cost = delivery_cost_from_session()

    return render_template('cart.html', cart=c, delivery_cost=float(delivery_cost))



@bp.post('/cart/add/<int:artwork_id>/')
@only_guests_or_customers
def cart_add(artwork_id):
    qty   = request.form.get('quantity', type=int) or 1
    weeks = request.form.get('weeks', type=int) or 1
    pc    = (request.form.get('postcode') or '').strip()

    # If Item Details posted a postcode, remember it for delivery calc
    if pc:
        session['checkout_postcode'] = pc

    add_to_cart(artwork_id, qty, weeks)
    return redirect(url_for('main.cart'))

@bp.post('/cart/clear/')
def cart_clear():
    empty_cart()
    flash('Cart cleared.')
    return redirect(url_for('main.cart'))

@bp.post('/cart/update/<int:item_id>/')
@only_guests_or_customers
def cart_update(item_id):
    # Optional helper for safe "next" redirects
    def _next_url(default):
        nxt = (request.form.get('next') or '').strip()
        return nxt if (nxt.startswith('/') and not nxt.startswith('//')) else default

    direction = (request.form.get('direction') or '').strip()   # 'increase' / 'decrease'
    raw_qty   = request.form.get('quantity', type=int)

    cart = get_cart()
    line = next((li for li in cart.items if int(li.cartItem_id) == int(item_id)), None)
    if not line:
        flash('Item not found in cart.', 'error')
        return redirect(_next_url(url_for('main.cart')))

    # Decide target quantity
    if direction in ('increase', 'decrease'):
        base = raw_qty if (raw_qty and raw_qty > 0) else line.quantity
        desired = base + (1 if direction == 'increase' else -1)
    else:
        desired = raw_qty if (raw_qty and raw_qty > 0) else line.quantity

    # Clamp to a max range
    desired = max(1, min(int(desired), 99))

    # Validate against availability/status/max-qty + rental window
    ok, msg = can_fulfill_request(line.artwork_id, desired, line.rentalDuration)
    if not ok:
        flash(msg or 'Unable to set that quantity for this item.', 'warning')
        return redirect(_next_url(url_for('main.cart')))

    # Persist the new quantity
    if update_cart_item(item_id, desired):
        flash('Cart updated successfully.')
    else:
        flash('Item not found in cart.', 'error')

    return redirect(_next_url(url_for('main.cart')))


@bp.post('/cart/remove/<int:item_id>/')
@only_guests_or_customers
def cart_remove(item_id):
    if remove_from_cart(item_id):
        flash('Item removed from cart.')
    else:
        flash('Item not found in cart.', 'error')

    next_url = request.form.get('next', '').strip()
    if next_url.startswith('/') and not next_url.startswith('//'):
        return redirect(next_url)

    return redirect(url_for('main.cart'))

# Checkout
@bp.route('/checkout/', methods=['GET', 'POST'])
@only_customers
def checkout():
    form = CheckoutForm()
    cart = get_cart()

    # Copy Delivery to Billing (no validation, just reflect on page)
    if request.method == 'POST' and 'copy_delivery' in request.form:
        form.bill_streetNumber.data = (form.del_streetNumber.data or '').strip()
        form.bill_streetName.data   = (form.del_streetName.data   or '').strip()
        form.bill_city.data         = (form.del_city.data         or '').strip()
        form.bill_state.data        = (form.del_state.data        or '').strip()
        form.bill_postcode.data     = (form.del_postcode.data     or '').strip()
        form.bill_country.data      = (form.del_country.data      or '').strip()
        flash('Copied delivery address into billing.', 'info')
        return render_template('checkout.html', form=form, cart=cart)

    # POST: place order
    if request.method == 'POST':
        if form.validate_on_submit():
            # 1) Must have items
            if not cart.items:
                flash('Your cart is empty. Please add items before checking out.', 'error')
                return render_template('checkout.html', form=form, cart=cart)

            # 2) Validate each cart line (status, quantity, availability window)
            for li in cart.items:
                ok, msg = can_fulfill_request(li.artwork_id, li.quantity, li.rentalDuration)
                if not ok:
                    flash(msg or 'This item cannot be checked out at the requested quantity/duration.', 'error')
                    return redirect(url_for('main.cart'))

            # 3) Billing must be present (server-side, regardless of client validators)
            billing_required = {
                'Street number': (form.bill_streetNumber.data or '').strip(),
                'Street name':   (form.bill_streetName.data   or '').strip(),
                'City':          (form.bill_city.data         or '').strip(),
                'State':         (form.bill_state.data        or '').strip(),
                'Postcode':      (form.bill_postcode.data     or '').strip(),
                'Country':       (form.bill_country.data      or '').strip(),
            }
            missing = [label for label, val in billing_required.items() if not val]
            if missing:
                if len(missing) == 1:
                    flash(f'Please provide your billing address — missing: {missing[0]}.', 'error')
                else:
                    flash('Please provide your billing address — missing: ' +
                          ', '.join(missing[:-1]) + f' and {missing[-1]}.', 'error')
                return render_template('checkout.html', form=form, cart=cart)

            # 4) Create/dedup addresses
            deliv_id = ensure_address(
                (form.del_streetNumber.data or '').strip(),
                (form.del_streetName.data   or '').strip(),
                (form.del_city.data         or '').strip(),
                (form.del_state.data        or '').strip(),
                (form.del_postcode.data     or '').strip(),
                (form.del_country.data      or 'Australia').strip(),
            )
            same_as_delivery = (
                (form.bill_streetNumber.data or '').strip().lower() == (form.del_streetNumber.data or '').strip().lower() and
                (form.bill_streetName.data   or '').strip().lower() == (form.del_streetName.data   or '').strip().lower() and
                (form.bill_city.data         or '').strip().lower() == (form.del_city.data         or '').strip().lower() and
                (form.bill_state.data        or '').strip().lower() == (form.del_state.data        or '').strip().lower() and
                (form.bill_postcode.data     or '').strip().lower() == (form.del_postcode.data     or '').strip().lower() and
                ((form.bill_country.data or 'Australia').strip().lower() ==
                 (form.del_country.data  or 'Australia').strip().lower())
            )
            bill_id = deliv_id if same_as_delivery else ensure_address(
                (form.bill_streetNumber.data or '').strip(),
                (form.bill_streetName.data   or '').strip(),
                (form.bill_city.data         or '').strip(),
                (form.bill_state.data        or '').strip(),
                (form.bill_postcode.data     or '').strip(),
                (form.bill_country.data      or 'Australia').strip(),
            )

            # 5) Build and persist order
            order = convert_cart_to_order(cart)
            user  = session.get('user') or {}
            cust_id = int(user.get('id') or user.get('customer_id'))
            if not getattr(order, 'customer_id', None):
                order.customer_id = cust_id
            order.deliveryAddressID = deliv_id
            order.billingAddressID  = bill_id

            add_order(order)
            empty_cart()
            flash('Thank you! Your order is being processed.', 'success')
            return redirect(url_for('main.index'))

        # Form didn’t validate, surface first field error clearly
        first_err = None
        for field, errs in form.errors.items():
            if errs:
                first_err = f"{field.replace('_',' ').title()}: {errs[0]}"
                break
        flash(first_err or 'Please correct the form and try again.', 'error')

    # GET: prefill
    else:
        u = session.get('user') or {}
        # Contact from session 
        form.firstname.data = u.get('firstname') or form.firstname.data
        form.surname.data   = u.get('surname')   or form.surname.data
        form.email.data     = u.get('email')     or form.email.data
        form.phone.data     = u.get('phone')     or form.phone.data

        # Delivery from DB (customer’s saved address)
        try:
            cust_id = int(u.get('id') or u.get('customer_id'))
            row = get_customer_address_details(cust_id)
            if row:
                form.del_streetNumber.data = row.get('streetNumber') or ''
                form.del_streetName.data   = row.get('streetName')   or ''
                form.del_city.data         = row.get('city')         or ''
                form.del_state.data        = row.get('state')        or ''
                form.del_postcode.data     = row.get('postcode')     or ''
                form.del_country.data      = row.get('country')      or ''
        except Exception:
            pass

        # Optional: postcode hint override
        pc_hint = (session.get('checkout_postcode') or '').strip()
        if pc_hint:
            form.del_postcode.data = pc_hint

    return render_template('checkout.html', form=form, cart=cart)


# Authentication
@bp.route('/register/', methods=['GET', 'POST'])
@only_guests
def register():
    form = RegisterForm()

    # Keep the toggle working 
    if request.method == 'GET':
        selected = (request.args.get('type') or 'customer').lower()
        if selected not in ('customer', 'vendor'):
            selected = 'customer'
        form.account_type.data = selected  # makes the hidden fields

        # Prefill identity/address if you stored them from checkout
        pf_checkout = session.get('checkout_prefill') or {}
        def fill_if_empty(field, value):
            if hasattr(form, field) and value and not (getattr(form, field).data or ''):
                getattr(form, field).data = value

        for f in ('firstname', 'surname', 'email', 'phone'):
            fill_if_empty(f, pf_checkout.get(f))

        # Prefill address from the BILLING section saved by checkout
        billing_map = {
            'streetNumber': pf_checkout.get('bill_streetNumber'),
            'streetName':   pf_checkout.get('bill_streetName'),
            'city':         pf_checkout.get('bill_city'),
            'state':        pf_checkout.get('bill_state'),
            'postcode':     pf_checkout.get('bill_postcode'),
            'country':      pf_checkout.get('bill_country'),
        }
        for name, value in billing_map.items():
            fill_if_empty(name, value)

    if form.validate_on_submit():
        role = (form.account_type.data or 'customer').lower()
        if role not in ('customer', 'vendor'):
            role = 'customer'

        # Pre-check uniqueness in the selected table
        email = (form.email.data or '').strip()
        phone = (form.phone.data or '').strip()

        email_exists, phone_exists = email_phone_in_use(role, email, phone)

        had_error = False
        if email_exists:
            form.email.errors.append(f"This email is already registered as a {role}. Please log in instead or use a different email.")
            had_error = True
        if phone_exists:
            form.phone.errors.append(f"This phone number is already registered as a {role}.")
            had_error = True
        if had_error:
            # Re-render the same page
            return render_template('register.html', form=form)

        # Create the account (address + customer/vendor; never admins)
        try:
            register_account(form)
        except Exception as e:
            # Catch MySQL duplicate key
            msg = str(e)
            code = getattr(e, "args", [None])[0]
            if ("Duplicate entry" in msg) or (code == 1062):
                if "email" in msg:
                    form.email.errors.append("That email is already registered. Please use another email or log in.")
                if "phone" in msg:
                    form.phone.errors.append("That phone number is already registered.")
                try:
                    mysql.connection.rollback()
                except Exception:
                    pass
                return render_template('register.html', form=form)
            raise  # unknown error

        flash(f"Registration successful as {role.title()}! You can now log in.", "success")
        return redirect(url_for('main.login'))

    return render_template('register.html', form=form)



@bp.route('/login/', methods=['GET', 'POST'])
@only_guests
def login():
    form = LoginForm()
    if request.method == 'POST' and form.validate_on_submit():
        role_hint = form.account_type.data or "customer"  # 'customer' or 'vendor'
        res = check_for_user_with_hint(form.username.data, form.password.data, role_hint)
        if not res:
            flash('Invalid credentials', 'error')
            return redirect(url_for('main.login'))

        role, info = res
        session['user'] = {
            'id': info['id'],
            'firstname': info.get('firstname'),
            'surname': info.get('surname'),
            'email': info.get('email'),
            'phone': info.get('phone'),
            'role': role,
            'is_admin': (role == 'admin')
        }
        session['logged_in'] = True
        flash('Login successful!')
        
        # Redirect back to checkout if that's where they came from
        next_url = session.pop('next_after_register', None)
        if next_url:
            return redirect(next_url)
        return redirect(url_for('main.index'))
    return render_template('login.html', form=form)



@bp.route('/logout/')
def logout():
    session.pop('user', None)
    session.pop('logged_in', None)
    session.pop('checkout_postcode', None)
    session.pop('checkout_prefill', None) # Clear prefill on logout
    session.pop('next_after_register', None) # Clear redirect hint
    empty_cart()
    flash('You have been logged out.')
    return redirect(url_for('main.index'))

# Admin (orders overview) 
@bp.route('/manage/', methods=['GET'])
@only_admins
def manage():
    #Admin: list all orders and order items
    oid = request.args.get('order_id', type=int)

    orders = admin_get_orders(oid)
    order_items = admin_get_order_items(oid)

    # Status choices
    try:
        from project.models import OrderStatus
        statuses = [s.value for s in OrderStatus]
    except Exception:
        statuses = admin_get_order_statuses()

    return render_template(
        'manage.html',
        orders=orders,
        order_items=order_items,
        statuses=statuses,
        filter_order_id=oid
    )


@bp.route('/manage/update/', methods=['POST'])
@only_admins
def manage_update():
    # Admin updater for 'orders' and 'order_item'.
    
    entity = (request.form.get('entity') or '').strip()

    if entity == 'order':
        order_id = request.form.get('order_id', type=int)
        # Editable columns in 'orders'
        cols = {
            'customer_id':       request.form.get('customer_id', type=int),
            'orderStatus':       request.form.get('orderStatus') or None,
            'orderDate':         request.form.get('orderDate') or None,
            'billingAddressID':  request.form.get('billingAddressID', type=int),
            'deliveryAddressID': request.form.get('deliveryAddressID', type=int),
        }
        admin_update_order(order_id, cols)
        flash(f"Order {order_id} updated.", "success")

    elif entity == 'order_item':
        oi_id = request.form.get('order_item_id', type=int)  # template posts 'order_item_id'
        # Editable columns in 'order_item'
        cols = {
            'order_id':       request.form.get('order_id', type=int),
            'artwork_id':     request.form.get('artwork_id', type=int),
            'quantity':       request.form.get('quantity', type=int),
            'rentalDuration': request.form.get('rentalDuration', type=int),
            'unitPrice':      request.form.get('unitPrice') or None,  # let MySQL cast
        }
        admin_update_order_item(oi_id, cols)
        flash(f"Order item {oi_id} updated.", "success")

    else:
        flash("Unknown entity.", "warning")

    return redirect(url_for('main.manage', order_id=request.form.get('persist_order_filter', type=int)))


@bp.post('/vendor/artwork/<int:artwork_id>/publish/')
@only_vendors
def vendor_publish_artwork(artwork_id):
    publish_artwork(artwork_id)
    flash('Artwork published.', 'success')
    return redirect(url_for('main.vendor_manage'))


@bp.post('/vendor/artwork/<int:artwork_id>/delete/')
@only_vendors
def vendor_delete_artwork(artwork_id):
    user = session.get('user', {})
    vendor_id = int(user.get('id'))
    delete_artwork(artwork_id, vendor_id)
    flash('Artwork deleted.', 'success')
    # If artwork is in order_item table it wont delete and render a error 500 on purpose
    return redirect(url_for('main.vendor_manage'))


@bp.route('/vendor/artwork/<int:artwork_id>/edit/', methods=['GET', 'POST'], endpoint='vendor_edit_artwork')
@only_vendors
def vendor_edit_artwork(artwork_id):
    user = session.get('user', {})
    vendor_id = int(user.get('id'))

    # Load the artwork and ensure it belongs to this vendor
    row = get_vendor_artwork(artwork_id, vendor_id)
    if not row:
        abort(404)

    # Build form + choices
    form = ArtworkForm()
    form.vendor_id.choices = [(vendor_id, "Me")]
    cats = get_categories() or []
    form.category_id.choices = [(0, "— No category —")] + [(c.category_id, c.categoryName) for c in cats]

    if request.method == 'GET':
        # Pre-fill fields
        form.vendor_id.data           = vendor_id
        form.category_id.data         = row['category_id'] or 0
        form.title.data               = row['title']
        form.itemDescription.data     = row['itemDescription']
        form.pricePerWeek.data        = row['pricePerWeek']
        form.imageLink.data           = row['imageLink']
        form.availabilityStartDate.data = row['availabilityStartDate']  # should be date or None
        form.availabilityEndDate.data   = row['availabilityEndDate']
        form.maxQuantity.data         = row['maxQuantity']
        form.availabilityStatus.data  = row['availabilityStatus'] or 'Unlisted'
        return render_template('edit_artwork.html', form=form, artwork=row, categories=cats)

    # POST
    if form.validate_on_submit():
        update_artwork_from_form(form, artwork_id, vendor_id)
        flash('Artwork updated!', 'success')
        return redirect(url_for('main.vendor_manage'))

    return render_template('edit_artwork.html', form=form, artwork=row, categories=cats)