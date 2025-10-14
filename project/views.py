from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from project.db import (
    get_categories, get_category, get_artworks_for_category, get_artwork,
    add_order, get_orders, check_for_user, add_customer,
    get_vendor, get_vendor_items,filter_items, _hash, publish_artwork, archive_artwork, update_artwork_details
)
from project.session import (
    get_cart, add_to_cart, empty_cart, remove_from_cart, convert_cart_to_order
)
from project.forms import (
    CheckoutForm, LoginForm, RegisterForm, AddToCartForm,
    VendorForm, ArtworkForm
)
from project.wrappers import only_admins, only_vendors
from . import mysql

bp = Blueprint('main', __name__)



@bp.route('/')
def index():
    items = filter_items(
        category_id=request.args.get('category_id', type=int),
        min_price=request.args.get('min', type=float),
        max_price=request.args.get('max', type=float),
        q=request.args.get('q')
    )
    from project.db import get_all_vendors, get_latest_artworks, get_categories
    active_category = request.args.get('category_id', type=int)
    vendors = get_all_vendors(limit=12)
    artworks = get_latest_artworks(limit=12, category_id=active_category)
    categories = get_categories()
    print('artworks are =>', artworks[0])
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
    cat = get_category(category_id)
    if not cat:
        flash("Category not found", "warning")
        return redirect(url_for('main.index'))
    items = get_artworks_for_category(category_id)
    return render_template('category_items.html', category=cat, items=items)

# Item details (with AddToCart)
@bp.route('/item/<int:artwork_id>/', methods=['GET', 'POST'])
def item_details(artwork_id):
    item = get_artwork(artwork_id)
    if not item:
        flash("Item not found", "warning")
        return redirect(url_for('main.index'))
    vendor = get_vendor(item.vendor_id)
    category = get_category(item.category_id) if item.category_id else None

    form = AddToCartForm()
    if request.method == 'POST' and form.validate_on_submit():
        add_to_cart(artwork_id, form.quantity.data or 1, form.weeks.data or 1)
        flash('Added to cart.')
        return redirect(url_for('main.cart'))
    return render_template('item_details.html', item=item, vendor=vendor, category=category, form=form)

#  Vendor gallery (public profile + items)
@bp.route('/vendor/<int:vendor_id>/')
def vendor_gallery(vendor_id):
    vendor = get_vendor(vendor_id)
    if not vendor:
        flash("Vendor not found", "warning")
        return redirect(url_for('main.index'))
    items = get_vendor_items(vendor_id)
    return render_template('vendor_gallery.html', vendor=vendor, items=items)

# Vendor registration
@bp.route('/vendor/register/', methods=['GET', 'POST'])
@only_admins
def vendor_register():
    pass

#  Vendor management (list & publish artworks) ----------
@bp.route('/vendor/self_gallery/')
@only_vendors
def vendor_self_view():
    user = session.get('user', {})
    vendor_id2 = int(user.get('id'))
    return redirect(url_for('main.vendor_gallery', vendor_id = vendor_id2))

@bp.route('/vendor/manage/', methods=['GET', 'POST'])
@only_vendors
def vendor_manage():
    user = session.get('user', {})
    vendor_id = int(user.get('id'))
    items = get_vendor_items(vendor_id)
    form = ArtworkForm()
    form.vendor_id.choices = [(vendor_id, "Me")]

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

    vendor = get_vendor(vendor_id)
    # Also pass categories for table chips if your template wants them
    return render_template('vendor_management.html',
                           vendor=vendor, items=items, form=form, categories=get_categories())

# Cart
@bp.route('/cart/', methods=['GET'])
def cart():
    a_id = request.args.get('artwork_id', type=int)
    qty = request.args.get('quantity', default=1, type=int)
    weeks = request.args.get('weeks', default=1, type=int)
    if a_id:
        add_to_cart(a_id, qty, weeks)
    c = get_cart()
    print('cart is =>', c)
    return render_template('cart.html', cart=c)

@bp.post('/cart/add/<int:artwork_id>/')
def cart_add(artwork_id):
    qty = request.form.get('quantity', type=int) or 1
    weeks = request.form.get('weeks', type=int) or 1
    add_to_cart(artwork_id, qty, weeks)
    return redirect(url_for('main.cart'))

@bp.post('/cart/remove/<int:item_id>/')
def cart_remove(item_id):
    remove_from_cart(item_id)
    return redirect(url_for('main.cart'))

@bp.post('/cart/clear/')
def cart_clear():
    empty_cart()
    flash('Cart cleared.')
    return redirect(url_for('main.cart'))

# Checkout
@bp.route('/checkout/', methods=['GET', 'POST'])
def checkout():
    form = CheckoutForm()
    cart = get_cart()
    if request.method == 'POST':
        if form.validate_on_submit():

            if 'user' not in session:
                # create or fetch a minimal customer row
                from project.db import ensure_customer
                cid = ensure_customer(
                    email=form.email.data.strip(),
                    phone=form.phone.data.strip(),
                    first=form.firstname.data.strip(),
                    last=form.surname.data.strip()
                )
                session['user'] = {
                    'id': cid,
                    'firstname': form.firstname.data,
                    'surname': form.surname.data,
                    'email': form.email.data,
                    'phone': form.phone.data,
                    'role': 'customer',
                    'is_admin': False
                }

            order = convert_cart_to_order(cart)
            add_order(order)
            empty_cart()
            flash('Thank you! Your order is being processed.')
            return redirect(url_for('main.index'))
        flash('Please correct the form and try again.', 'error')
    else:
        u = session.get('user')
        if u:
            form.firstname.data = u.get('firstname')
            form.surname.data = u.get('surname')
            form.email.data = u.get('email')
            form.phone.data = u.get('phone')
    return render_template('checkout.html', form=form, cart=cart)

# Authentication
@bp.route('/register/', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if request.method == 'POST' and form.validate_on_submit():
        add_customer(form)
        flash('Registration successful! You can now log in.')
        return redirect(url_for('main.login'))
    return render_template('register.html', form=form)

@bp.route('/login/', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if request.method == 'POST' and form.validate_on_submit():
        res = check_for_user(form.username.data, form.password.data)
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
    flash('You have been logged out.')
    return redirect(url_for('main.index'))

# Admin (orders overview)
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

@bp.post('/vendor/artwork/<int:artwork_id>/archive/')
@only_vendors
def vendor_archive_artwork(artwork_id):
    archive_artwork(artwork_id)
    flash('Artwork archived.', 'success')
    return redirect(url_for('main.vendor_manage'))


