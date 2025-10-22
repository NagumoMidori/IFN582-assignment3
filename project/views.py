from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session, abort
)

from project.db import (
    get_categories, get_category, get_artwork,
    get_orders, get_vendor, get_vendor_items, get_all_vendors, get_latest_artworks,
    filter_items, generate_kpi, publish_artwork, mysql
)

from project.session import (
    add_to_cart, empty_cart, remove_from_cart,
    update_cart_item
)

from project.forms import (
    AddToCartForm, ArtworkForm, LoginForm
)

from project.wrappers import (
    only_admins, only_vendors, only_guests_or_customers, only_guests
)


bp = Blueprint('main', __name__)  


@bp.route('/')
def index():
    items = filter_items(
        category_id=request.args.get('category_id', type=int),
        min_price=request.args.get('min', type=float),
        max_price=request.args.get('max', type=float),
        q=request.args.get('q')
    )
    active_category = request.args.get('category_id', type=int)
    vendors = get_all_vendors(limit=12)
    artworks = get_latest_artworks(limit=12, category_id=active_category)
    categories = get_categories()
    return render_template(
        'index.html',
        vendors=vendors,
        artworks=artworks,
        categories=categories,
        active_category=active_category
    )

# Category listing
@bp.route('/category/<int:category_id>/')
def category_items(category_id):
    from flask import render_template, abort
    from project.db import mysql

    cur = mysql.connection.cursor()

    cur.execute(
        "SELECT category_id, categoryName FROM categories WHERE category_id=%s LIMIT 1",
        (category_id,),
    )
    category = cur.fetchone()
    if not category:
        cur.close()
        abort(404)

    #Explicit columns,the image column to `image`
    cur.execute("""
        SELECT
            a.artwork_id,
            a.title,
            a.itemDescription,
            a.pricePerWeek,
            a.vendor_id,
            a.category_id,
            a.availabilityStatus,
            a.imageLink AS image,         
            v.artisticName AS artisticName,
            c.categoryName
        FROM artworks a
        LEFT JOIN vendors    v ON v.vendor_id   = a.vendor_id
        LEFT JOIN categories c ON c.category_id = a.category_id
        WHERE a.category_id = %s
          AND a.availabilityStatus = 'Listed'
        ORDER BY a.artwork_id DESC
    """, (category_id,))
    items = cur.fetchall()
    cur.close()

    return render_template('category_items.html', category=category, items=items)


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
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT a.postcode
            FROM customers c
            LEFT JOIN addresses a ON a.address_id = c.address_id
            WHERE c.customer_id = %s
            LIMIT 1
        """, (int(u['id']),))
        row = cur.fetchone()
        cur.close()
        if row:
            default_postcode = row.get('postcode')

    form = AddToCartForm()
    if request.method == 'POST' and form.validate_on_submit():
        add_to_cart(artwork_id, form.quantity.data or 1, form.weeks.data or 1)
        flash('Added to cart.')
        return redirect(url_for('main.cart'))
    return render_template('item_details.html', item=item, vendor=vendor, category=category, 
                           form=form, default_postcode=default_postcode)


#  Vendor gallery (public profile + items)
@bp.route('/vendor/<int:vendor_id>/')
def vendor_gallery(vendor_id):
    from flask import render_template, abort
    from project.db import mysql, get_vendor

    vendor = get_vendor(vendor_id)
    if not vendor:
        abort(404)

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT a.*, c.categoryName
          FROM artworks a
          LEFT JOIN categories c ON c.category_id = a.category_id
         WHERE a.vendor_id = %s
         ORDER BY
           CASE a.availabilityStatus
             WHEN 'Listed' THEN 0
             WHEN 'Leased' THEN 1
             ELSE 2
           END,
           a.artwork_id DESC
    """, (vendor_id,))
    items = cur.fetchall()
    cur.close()

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
        category_id = form.category_id.data if form.category_id.data != 0 else None
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO artworks (
                vendor_id, category_id, title, itemDescription, pricePerWeek,
                imageLink, availabilityStartDate, availabilityEndDate,
                maxQuantity, availabilityStatus
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            form.vendor_id.data, category_id, form.title.data, form.itemDescription.data,
            str(form.pricePerWeek.data), form.imageLink.data,
            form.availabilityStartDate.data, form.availabilityEndDate.data,
            form.maxQuantity.data, form.availabilityStatus.data
        ))
        mysql.connection.commit()
        cur.close()
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
    from flask import render_template, session
    from project.session import get_cart, delivery_cost_from_session
    from project.db import mysql

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
            cur = mysql.connection.cursor()
            cur.execute("""
                SELECT a.postcode
                  FROM customers c
             LEFT JOIN addresses a ON a.address_id = c.address_id
                 WHERE c.customer_id = %s
                 LIMIT 1
            """, (cust_id,))
            row = cur.fetchone()
            cur.close()
            if row and row.get('postcode'):
                session['checkout_postcode'] = str(row['postcode'])

    # Compute delivery using the same logic everywhere (reads session['checkout_postcode'])
    delivery_cost = delivery_cost_from_session()

    return render_template('cart.html', cart=c, delivery_cost=float(delivery_cost))



@bp.post('/cart/add/<int:artwork_id>/')
@only_guests_or_customers
def cart_add(artwork_id):
    from flask import request, session, redirect, url_for
    from project.session import add_to_cart   

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
    direction = request.form.get('direction')
    quantity = request.form.get('quantity', type=int)

    if direction in ('increase', 'decrease'):
        base = quantity if quantity and quantity > 0 else 1
        quantity = base + (1 if direction == 'increase' else -1)

    if quantity is not None:
        quantity = max(1, min(quantity, 99))
    
    if quantity is None or quantity < 1:
        flash('Invalid quantity. Please enter a valid number.', 'error')
        return redirect(url_for('main.cart'))
    
    if update_cart_item(item_id, quantity):
        flash('Cart updated successfully.')
    else:
        flash('Item not found in cart.', 'error')
    
    return redirect(url_for('main.cart'))

@bp.post('/cart/remove/<int:item_id>/')
@only_guests_or_customers
def cart_remove(item_id):
    if remove_from_cart(item_id):
        flash('Item removed from cart.')
    else:
        flash('Item not found in cart.', 'error')
    return redirect(url_for('main.cart'))

# Checkout
@bp.route('/checkout/', methods=['GET', 'POST'])
@only_guests_or_customers
def checkout():
    from flask import render_template, request, session, flash, redirect, url_for
    from project.forms import CheckoutForm
    from project.session import get_cart, empty_cart, convert_cart_to_order
    from project.db import add_order, ensure_address, mysql, get_artwork

    form = CheckoutForm()
    cart = get_cart()

    # Helpers
    def _get_customer_id(u: dict | None):
        """Find a customer id regardless of key naming."""
        u = u or {}
        for k in ('id', 'customer_id', 'customerID', 'customerId'):
            v = u.get(k)
            if v not in (None, ''):
                try:
                    return int(v)
                except Exception:
                    pass
        return None

    def _from_user(u: dict, *keys):
        """Pick the first non-empty value for common contact key variants."""
        for k in keys:
            v = u.get(k)
            if v:
                return v
        return None

    # Copy Delivery to Billing (no validation, just re-render)
    if request.method == 'POST' and 'copy_delivery' in request.form:
        form.bill_streetNumber.data = (form.del_streetNumber.data or '').strip()
        form.bill_streetName.data   = (form.del_streetName.data or '').strip()
        form.bill_city.data         = (form.del_city.data or '').strip()
        form.bill_state.data        = (form.del_state.data or '').strip()
        form.bill_postcode.data     = (form.del_postcode.data or '').strip()
        form.bill_country.data      = (form.del_country.data or '').strip()
        flash('Copied delivery address into billing.', 'info')
        return render_template('checkout.html', form=form, cart=cart)

    if request.method == 'POST':
        if form.validate_on_submit():
            # Block empty cart
            if not cart.items or len(cart.items) == 0:
                flash('Your cart is empty. Please add items before checking out.', 'error')
                return render_template('checkout.html', form=form, cart=cart)

            # Guests cannot place orders redirect them to register with full prefill
            u = session.get('user') or {}
            if u.get('role') != 'customer':
                session['checkout_prefill'] = {
                    'firstname': form.firstname.data or '',
                    'surname':   form.surname.data or '',
                    'email':     form.email.data or '',
                    'phone':     form.phone.data or '',
                    # delivery
                    'del_streetNumber': form.del_streetNumber.data or '',
                    'del_streetName':   form.del_streetName.data or '',
                    'del_city':         form.del_city.data or '',
                    'del_state':        form.del_state.data or '',
                    'del_postcode':     form.del_postcode.data or '',
                    'del_country':      form.del_country.data or '',
                    # billing
                    'bill_streetNumber': form.bill_streetNumber.data or '',
                    'bill_streetName':   form.bill_streetName.data or '',
                    'bill_city':         form.bill_city.data or '',
                    'bill_state':        form.bill_state.data or '',
                    'bill_postcode':     form.bill_postcode.data or '',
                    'bill_country':      form.bill_country.data or '',
                }
                session['register_prefill'] = {
                    'firstname': form.firstname.data or '',
                    'surname':   form.surname.data or '',
                    'email':     form.email.data or '',
                    'phone':     form.phone.data or '',
                }
                session['next_after_register'] = url_for('main.checkout')
                flash('Please register as a customer to place your order. We saved your details.', 'info')
                return redirect(url_for('main.register', next='checkout'))

            # Billing must be present (customer still must complete these)
            billing_required = [
                form.bill_streetNumber.data, form.bill_streetName.data,
                form.bill_city.data, form.bill_state.data,
                form.bill_postcode.data, form.bill_country.data
            ]
            if not all((v or '').strip() for v in billing_required):
                flash('Please provide your billing address or click "Same as delivery".', 'error')
                return render_template('checkout.html', form=form, cart=cart)

            # Ensure only Listed items can be checked out
            bad = []
            for li in (cart.items or []):
                art = get_artwork(li.artwork_id)
                if (not art) or art.availabilityStatus != 'Listed':
                    bad.append(li.artwork_id)
            if bad:
                flash('One or more items are no longer available (Unlisted/Leased). Please review your cart.', 'error')
                return redirect(url_for('main.cart'))

            # Deduplicate & attach addresses
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

            # Build and persist order
            order = convert_cart_to_order(cart)
            cust_id = _get_customer_id(u)
            if not getattr(order, 'customer_id', None) and cust_id:
                order.customer_id = cust_id
            order.deliveryAddressID = deliv_id
            order.billingAddressID  = bill_id

            add_order(order)
            empty_cart()
            session.pop('checkout_prefill', None)
            session.pop('checkout_postcode', None)
            flash('Thank you! Your order is being processed.')
            return redirect(url_for('main.index'))

        # Validation failed
        flash('Please correct the form and try again.', 'error')

    else:
        # GET: contact + delivery prefill for logged-in customers
        u = session.get('user') or {}

        # 1) Contact from session (handles different key names)
        if not (form.firstname.data or '').strip():
            form.firstname.data = _from_user(u, 'firstname', 'first_name', 'firstName', 'given_name', 'givenName') or ''
        if not (form.surname.data or '').strip():
            form.surname.data   = _from_user(u, 'surname', 'last_name', 'lastName', 'family_name', 'familyName') or ''
        if not (form.email.data or '').strip():
            form.email.data     = _from_user(u, 'email', 'emailAddress', 'mail') or ''
        if not (form.phone.data or '').strip():
            form.phone.data     = _from_user(u, 'phone', 'phoneNumber', 'mobile', 'mobile_phone') or ''

        # 2) Delivery address from DB for logged-in customers
        cust_id = _get_customer_id(u)
        is_customer = (u.get('role') == 'customer' or u.get('type') == 'customer')
        if is_customer and cust_id:
            try:
                cur = mysql.connection.cursor()
                cur.execute("""
                    SELECT a.streetNumber, a.streetName, a.city, a.state, a.postcode, a.country
                      FROM customers c
                      LEFT JOIN addresses a ON a.address_id = c.address_id
                     WHERE c.customer_id = %s
                     LIMIT 1
                """, (cust_id,))
                row = cur.fetchone()
                cur.close()
                if row:
                    form.del_streetNumber.data = row.get('streetNumber') or ''
                    form.del_streetName.data   = row.get('streetName')   or ''
                    form.del_city.data         = row.get('city')         or ''
                    form.del_state.data        = row.get('state')        or ''
                    form.del_postcode.data     = row.get('postcode')     or ''
                    form.del_country.data      = row.get('country')      or ''
            except Exception:
                pass

        # 3) Overlay any saved inputs from a previous attempt (guest -> register -> back)
        pf = session.get('checkout_prefill') or {}
        if pf:
            # contact
            if pf.get('firstname'):        form.firstname.data        = pf['firstname']
            if pf.get('surname'):          form.surname.data          = pf['surname']
            if pf.get('email'):            form.email.data            = pf['email']
            if pf.get('phone'):            form.phone.data            = pf['phone']
            # delivery
            if pf.get('del_streetNumber'): form.del_streetNumber.data = pf['del_streetNumber']
            if pf.get('del_streetName'):   form.del_streetName.data   = pf['del_streetName']
            if pf.get('del_city'):         form.del_city.data         = pf['del_city']
            if pf.get('del_state'):        form.del_state.data        = pf['del_state']
            if pf.get('del_postcode'):     form.del_postcode.data     = pf['del_postcode']
            if pf.get('del_country'):      form.del_country.data      = pf['del_country']
            # billing (optional to re-show)
            if pf.get('bill_streetNumber'): form.bill_streetNumber.data = pf['bill_streetNumber']
            if pf.get('bill_streetName'):   form.bill_streetName.data   = pf['bill_streetName']
            if pf.get('bill_city'):         form.bill_city.data         = pf['bill_city']
            if pf.get('bill_state'):        form.bill_state.data        = pf['bill_state']
            if pf.get('bill_postcode'):     form.bill_postcode.data     = pf['bill_postcode']
            if pf.get('bill_country'):      form.bill_country.data      = pf['bill_country']

        # 4) Apply postcode hint LAST so it overrides DB prefill (if present)
        pc_hint = (session.get('checkout_postcode') or '').strip()
        if pc_hint:
            form.del_postcode.data = pc_hint

    return render_template('checkout.html', form=form, cart=cart)

# Authentication
@bp.route('/register/', methods=['GET', 'POST'])
@only_guests
def register():
    from flask import render_template, request, session, flash, redirect, url_for
    from project.forms import RegisterForm
    from project.db import register_account, mysql

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
        table = 'customers' if role == 'customer' else 'vendors'

        # Pre-check uniqueness in the selected table
        email = (form.email.data or '').strip()
        phone = (form.phone.data or '').strip()

        cur = mysql.connection.cursor()
        cur.execute(f"SELECT 1 FROM {table} WHERE email=%s LIMIT 1", (email,))
        email_exists = cur.fetchone() is not None
        cur.execute(f"SELECT 1 FROM {table} WHERE phone=%s LIMIT 1", (phone,))
        phone_exists = cur.fetchone() is not None
        cur.close()

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
    from project.db import check_for_user_with_hint
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
        return redirect(url_for('main.index'))
    return render_template('login.html', form=form)



@bp.route('/logout/')
def logout():
    session.pop('user', None)
    session.pop('logged_in', None)
    session.pop('checkout_postcode', None)
    empty_cart()
    flash('You have been logged out.')
    return redirect(url_for('main.index'))

# Admin (orders overview) TO BE DEVELOPPED
@bp.route('/manage/')
@only_admins
def manage():
    orders = get_orders()
    return render_template('manage.html', orders=orders)


@bp.post('/vendor/artwork/<int:artwork_id>/publish/')
@only_vendors
def vendor_publish_artwork(artwork_id):
    publish_artwork(artwork_id)
    flash('Artwork published.', 'success')
    return redirect(url_for('main.vendor_manage'))


@bp.route('/vendor/artwork/<int:artwork_id>/edit/', methods=['GET', 'POST'], endpoint='vendor_edit_artwork')
@only_vendors
def vendor_edit_artwork(artwork_id):
    user = session.get('user', {})
    vendor_id = int(user.get('id'))

    # Load the artwork and ensure it belongs to this vendor
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT artwork_id, vendor_id, category_id, title, itemDescription, pricePerWeek,
               imageLink, availabilityStartDate, availabilityEndDate, maxQuantity, availabilityStatus
        FROM artworks
        WHERE artwork_id=%s AND vendor_id=%s
        LIMIT 1
    """, (artwork_id, vendor_id))
    row = cur.fetchone()
    if not row:
        cur.close()
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
        cur.close()
        return render_template('edit_artwork.html', form=form, artwork=row, categories=cats)

    # POST
    if form.validate_on_submit():
        category_id = form.category_id.data if form.category_id.data != 0 else None
        cur.execute("""
            UPDATE artworks
               SET category_id=%s,
                   title=%s,
                   itemDescription=%s,
                   pricePerWeek=%s,
                   imageLink=%s,
                   availabilityStartDate=%s,
                   availabilityEndDate=%s,
                   maxQuantity=%s,
                   availabilityStatus=%s
             WHERE artwork_id=%s AND vendor_id=%s
        """, (
            category_id,
            form.title.data,
            form.itemDescription.data,
            str(form.pricePerWeek.data),
            form.imageLink.data,
            form.availabilityStartDate.data,
            form.availabilityEndDate.data,
            form.maxQuantity.data,
            form.availabilityStatus.data,
            artwork_id, vendor_id
        ))
        mysql.connection.commit()
        cur.close()
        flash('Artwork updated!', 'success')
        return redirect(url_for('main.vendor_manage'))

    cur.close()
    return render_template('edit_artwork.html', form=form, artwork=row, categories=cats)
