from hashlib import sha256
from datetime import datetime
from decimal import Decimal
from typing import Optional, Tuple, List
from uuid import uuid4
from . import mysql
from project.models import Category, Artwork, Vendor, Order, OrderStatus


# Catalog
def get_categories() -> List[Category]:
    cur = mysql.connection.cursor()
    cur.execute("SELECT category_id, categoryName FROM categories ORDER BY categoryName;")
    rows = cur.fetchall()
    cur.close()
    return [Category(r['category_id'], r['categoryName']) for r in rows]

def get_category(category_id: int) -> Optional[Category]:
    cur = mysql.connection.cursor()
    cur.execute("SELECT category_id, categoryName FROM categories WHERE category_id=%s;", (category_id,))
    row = cur.fetchone()
    cur.close()
    return Category(row['category_id'], row['categoryName']) if row else None

def get_artworks_for_category(category_id: int):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT artwork_id, vendor_id, category_id, title, itemDescription,
               pricePerWeek, imageLink, availabilityStartDate, availabilityEndDate,
               maxQuantity, availabilityStatus
        FROM artworks
        WHERE category_id=%s AND availabilityStatus='Listed'
        ORDER BY title;
    """, (category_id,))
    rows = cur.fetchall()
    cur.close()
    return [Artwork(
        artwork_id=r['artwork_id'], vendor_id=r['vendor_id'], category_id=r['category_id'],
        title=r['title'], itemDescription=r['itemDescription'],
        pricePerWeek=Decimal(str(r['pricePerWeek'])), image=r['imageLink'],
        availabilityStartDate=r['availabilityStartDate'], availabilityEndDate=r['availabilityEndDate'],
        maxQuantity=r['maxQuantity'], availabilityStatus=r['availabilityStatus']
    ) for r in rows]


def get_artwork(artwork_id: int) -> Optional[Artwork]:
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT
            a.artwork_id, a.vendor_id, a.category_id, a.title, a.itemDescription,
            a.pricePerWeek, a.imageLink, a.availabilityStartDate, a.availabilityEndDate,
            a.maxQuantity, a.availabilityStatus,
            c.categoryName                          -- NEW
        FROM artworks a
        LEFT JOIN categories c ON c.category_id = a.category_id   -- NEW
        WHERE a.artwork_id = %s;
    """, (artwork_id,))
    r = cur.fetchone()
    cur.close()
    if not r:
        return None

    aw = Artwork(
        artwork_id=r['artwork_id'], vendor_id=r['vendor_id'], category_id=r['category_id'],
        title=r['title'], itemDescription=r['itemDescription'],
        pricePerWeek=Decimal(str(r['pricePerWeek'])), image=r['imageLink'],
        availabilityStartDate=r['availabilityStartDate'], availabilityEndDate=r['availabilityEndDate'],
        maxQuantity=r['maxQuantity'], availabilityStatus=r['availabilityStatus']
    )
    # Attach the readable name so templates can use it
    setattr(aw, 'categoryName', r.get('categoryName'))
    return aw


def filter_items(
    category_id: int | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    q: str | None = None,
    vendor_id: int | None = None,
    availability: str | None = None,  # 'Listed'/'Unlisted'/'Leased'
    sort: str | None = None,
    limit: int | None = None
) -> list[dict]:
    """+filterItems(): flexible catalog filtering for UI."""
    sql = """
      SELECT a.artwork_id, a.vendor_id, a.category_id, a.title, a.itemDescription, a.pricePerWeek, a.imageLink,
             a.availabilityStartDate, a.availabilityEndDate, a.maxQuantity, a.availabilityStatus,
             c.categoryName, v.artisticName
      FROM artworks a
      LEFT JOIN categories c ON c.category_id = a.category_id
      LEFT JOIN vendors v ON v.vendor_id = a.vendor_id
      WHERE 1=1
    """
    params = []
    if category_id is not None:
        sql += " AND category_id=%s"; params.append(category_id)
    if vendor_id is not None:
        sql += " AND vendor_id=%s"; params.append(vendor_id)
    if min_price is not None:
        sql += " AND pricePerWeek >= %s"; params.append(min_price)
    if max_price is not None:
        sql += " AND pricePerWeek <= %s"; params.append(max_price)
    if availability:
        sql += " AND availabilityStatus=%s"; params.append(availability)
    if q:
        like = f"%{q}%"
        sql += " AND (a.title LIKE %s OR a.itemDescription LIKE %s OR c.categoryName LIKE %s OR v.artisticName LIKE %s)"; params.extend([like, like, like, like])
    order_by = "artwork_id DESC"
    sort_map = {
        "latest": "artwork_id DESC",
        "oldest": "artwork_id ASC",
        "price_asc": "pricePerWeek ASC, artwork_id DESC",
        "price_desc": "pricePerWeek DESC, artwork_id DESC",
        "title": "title ASC"
    }
    if sort in sort_map:
        order_by = sort_map[sort]
    sql += f" ORDER BY {order_by}"
    if limit:
        sql += " LIMIT %s"; params.append(limit)
    cur = mysql.connection.cursor(); cur.execute(sql, tuple(params))
    rows = cur.fetchall(); cur.close()
    return rows
    
def get_vendor(vendor_id: int) -> Optional[Vendor]:
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT vendor_id, email, phone, vendor_password, firstName, lastName,
               address_id, artisticName, bio, profilePictureLink
        FROM vendors WHERE vendor_id=%s;
    """, (vendor_id,))
    r = cur.fetchone()
    cur.close()
    if not r:
        return None
    return Vendor(
        vendor_id=r['vendor_id'], email=r['email'], phone=r['phone'],
        vendor_password=r['vendor_password'], firstName=r['firstName'], lastName=r['lastName'],
        address_id=r['address_id'], artisticName=r['artisticName'], bio=r['bio'],
        image=r['profilePictureLink']
    )

def get_vendor_items(vendor_id: int):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT
            a.artwork_id,
            a.title,
            a.pricePerWeek,
            a.imageLink AS image,
            a.availabilityStatus,
            a.maxQuantity,              -
            a.availabilityEndDate,      
            a.category_id,
            c.categoryName
        FROM artworks a
        LEFT JOIN categories c ON c.category_id = a.category_id
        WHERE a.vendor_id = %s
        ORDER BY a.artwork_id DESC
    """, (vendor_id,))
    rows = cur.fetchall()
    cur.close()
    return rows



# Auth
def _hash(pw: str) -> str:
    return sha256(pw.encode()).hexdigest()

def check_for_user(credential: str, password_plain: str) -> Optional[Tuple[str, dict]]:
    pwd = _hash(password_plain)
    cur = mysql.connection.cursor()

    # Admin by username
    cur.execute("""
        SELECT admin_id AS id, username
        FROM admins
        WHERE username=%s AND admin_password=%s
    """, (credential, pwd))
    row = cur.fetchone()
    if row:
        cur.close()
        return "admin", {"id": row["id"], "firstname": "Admin", "surname": row["username"],
                         "email": None, "phone": None}

    # Customer by email
    cur.execute("""
        SELECT customer_id AS id, email, phone, customer_password, firstName, lastName
        FROM customers
        WHERE email=%s AND customer_password=%s
    """, (credential, pwd))
    row = cur.fetchone()
    if row:
        cur.close()
        return "customer", {"id": row["id"], "firstname": row["firstName"], "surname": row["lastName"],
                            "email": row["email"], "phone": row["phone"]}

    # Vendor by email
    cur.execute("""
        SELECT vendor_id AS id, email, phone, vendor_password, firstName, lastName
        FROM vendors
        WHERE email=%s AND vendor_password=%s
    """, (credential, pwd))
    row = cur.fetchone()
    cur.close()
    if row:
        return "vendor", {"id": row["id"], "firstname": row["firstName"], "surname": row["lastName"],
                          "email": row["email"], "phone": row["phone"]}
    return None

def check_for_user_with_role(credential: str, password_plain: str, role_hint: str | None = None) -> Optional[Tuple[str, dict]]:
    """
    Role-aware login. Admin is always checked first (by username), regardless of role_hint.
    role_hint: 'customer' / 'vendor' / 'admin' / 'auto' (or None)
    """
    pwd = _hash(password_plain)
    cur = mysql.connection.cursor()

    # 1) Admin first, regardless of the selected radio
    cur.execute("""
        SELECT admin_id AS id, username
        FROM admins
        WHERE username=%s AND admin_password=%s
    """, (credential, pwd))
    row = cur.fetchone()
    if row:
        cur.close()
        return "admin", {"id": row["id"], "firstname": "Admin", "surname": row["username"],
                         "email": None, "phone": None}

    # Normalize hint
    hint = (role_hint or "auto").lower()

    if hint == "admin":
        # If user explicitly chose Admin and we didn't match above, stop here.
        cur.close()
        return None

    if hint == "customer":
        # Customer only
        cur.execute("""
            SELECT customer_id AS id, email, phone, firstName, lastName
            FROM customers
            WHERE email=%s AND customer_password=%s
        """, (credential, pwd))
        row = cur.fetchone(); cur.close()
        if row:
            return "customer", {"id": row["id"], "firstname": row["firstName"], "surname": row["lastName"],
                                "email": row["email"], "phone": row["phone"]}
        return None

    if hint == "vendor":
        # Vendor only
        cur.execute("""
            SELECT vendor_id AS id, email, phone, firstName, lastName
            FROM vendors
            WHERE email=%s AND vendor_password=%s
        """, (credential, pwd))
        row = cur.fetchone(); cur.close()
        if row:
            return "vendor", {"id": row["id"], "firstname": row["firstName"], "surname": row["lastName"],
                              "email": row["email"], "phone": row["phone"]}
        return None

    # Auto: fall back to your existing order (customer / vendor)
    cur.execute("""
        SELECT customer_id AS id, email, phone, firstName, lastName
        FROM customers
        WHERE email=%s AND customer_password=%s
    """, (credential, pwd))
    row = cur.fetchone()
    if row:
        cur.close()
        return "customer", {"id": row["id"], "firstname": row["firstName"], "surname": row["lastName"],
                            "email": row["email"], "phone": row["phone"]}

    cur.execute("""
        SELECT vendor_id AS id, email, phone, firstName, lastName
        FROM vendors
        WHERE email=%s AND vendor_password=%s
    """, (credential, pwd))
    row = cur.fetchone(); cur.close()
    if row:
        return "vendor", {"id": row["id"], "firstname": row["firstName"], "surname": row["lastName"],
                          "email": row["email"], "phone": row["phone"]}
    return None


def check_for_user_with_hint(credential: str, password_plain: str, hint: str) -> Optional[Tuple[str, dict]]:
    """
    Try admin by username first (always allowed), then check ONLY the hinted role.
    hint: 'customer' or 'vendor'
    """
    pwd = _hash(password_plain)
    cur = mysql.connection.cursor()

    # 1) Admin (by username)
    cur.execute("""
        SELECT admin_id AS id, username
        FROM admins
        WHERE username=%s AND admin_password=%s
    """, (credential, pwd))
    row = cur.fetchone()
    if row:
        cur.close()
        return "admin", {
            "id": row["id"], "firstname": "Admin", "surname": row["username"],
            "email": None, "phone": None
        }

    # 2) Hinted role only
    if hint == "customer":
        cur.execute("""
            SELECT customer_id AS id, email, phone, firstName, lastName
            FROM customers
            WHERE email=%s AND customer_password=%s
        """, (credential, pwd))
        row = cur.fetchone()
        cur.close()
        if row:
            return "customer", {
                "id": row["id"], "firstname": row["firstName"], "surname": row["lastName"],
                "email": row["email"], "phone": row["phone"]
            }

    elif hint == "vendor":
        cur.execute("""
            SELECT vendor_id AS id, email, phone, firstName, lastName
            FROM vendors
            WHERE email=%s AND vendor_password=%s
        """, (credential, pwd))
        row = cur.fetchone()
        cur.close()
        if row:
            return "vendor", {
                "id": row["id"], "firstname": row["firstName"], "surname": row["lastName"],
                "email": row["email"], "phone": row["phone"]
            }

    # No match
    return None


def add_customer(form):
    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO customers (email, phone, customer_password, firstName, lastName, address_id)
        VALUES (%s, %s, %s, %s, %s, NULL)
    """, (form.email.data, form.phone.data, _hash(form.password.data), form.firstname.data, form.surname.data))
    mysql.connection.commit()
    cur.close()


def login(credential: str, password_plain: str):

    return check_for_user(credential, password_plain)  

def register(email: str, phone: str, password_plain: str, first: str, last: str, role: str = "customer") -> int:
    cur = mysql.connection.cursor()
    pw = _hash(password_plain)
    if role == "vendor":
        cur.execute("""
            INSERT INTO vendors (email, phone, vendor_password, firstName, lastName, address_id,
                         artisticName, bio, profilePictureLink)
            VALUES (%s,%s,%s,%s,%s,NULL, %s, %s, %s)
        """, (email, phone, pw, first, last,  '',  '',  ''))
        new_id = cur.lastrowid
    else:
        cur.execute("""
            INSERT INTO customers (email, phone, customer_password, firstName, lastName, address_id)
            VALUES (%s,%s,%s,%s,%s,NULL)
        """, (email, phone, pw, first, last))
        new_id = cur.lastrowid
    mysql.connection.commit(); cur.close()
    return new_id


def subscribe_to_newsletter(customer_id: int, subscribed: bool = True) -> None:
    cur = mysql.connection.cursor()
    cur.execute("UPDATE customers SET newsletterSubscription=%s WHERE customer_id=%s;", (1 if subscribed else 0, customer_id))
    mysql.connection.commit(); cur.close()

def deleteUser(role: str, user_id: int) -> None:
    table = "customers" if role == "customer" else "vendors"
    cur = mysql.connection.cursor()
    cur.execute(f"DELETE FROM {table} WHERE {role}_id=%s;", (user_id,))
    mysql.connection.commit(); cur.close()


# Orders
def add_order(order: Order):
    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO orders (customer_id, orderStatus, orderDate, billingAddressID, deliveryAddressID)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        order.customer_id,
        order.orderStatus.value if hasattr(order.orderStatus, "value") else str(order.orderStatus),
        order.orderDate or datetime.now(),
        order.billingAddressID,
        order.deliveryAddressID
    ))
    order_id = cur.lastrowid

    # Snapshot price from artworks into order_item.unitPrice
    for li in order.items:
        cur.execute("SELECT pricePerWeek FROM artworks WHERE artwork_id=%s;", (li.artwork_id,))
        r = cur.fetchone()
        unit = Decimal(str(r['pricePerWeek'])) if r else Decimal("0.00")
        cur.execute("""
            INSERT INTO order_item (order_id, artwork_id, quantity, rentalDuration, unitPrice)
            VALUES (%s, %s, %s, %s, %s)
        """, (order_id, li.artwork_id, li.quantity, li.rentalDuration, unit))

    mysql.connection.commit()
    cur.close()

def get_orders():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT o.order_id, o.customer_id, o.orderStatus, o.orderDate,
               o.billingAddressID, o.deliveryAddressID,
               c.firstName, c.lastName, c.email, c.phone
        FROM orders o
        JOIN customers c ON c.customer_id = o.customer_id
        ORDER BY o.orderDate DESC;
    """)
    rows = cur.fetchall()
    cur.close()
    results = []
    for r in rows:
        order = Order(
            order_id=r['order_id'], customer_id=r['customer_id'],
            orderStatus=OrderStatus(r['orderStatus']), orderDate=r['orderDate'],
            billingAddressID=r['billingAddressID'], deliveryAddressID=r['deliveryAddressID'],
            items=[]
        )
        results.append(order)
    return results

def view_orders(customer_id: int) -> list[dict]:
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT o.order_id, o.orderStatus, o.orderDate, o.billingAddressID, o.deliveryAddressID
        FROM orders o
        WHERE o.customer_id=%s
        ORDER BY o.orderDate DESC
    """, (customer_id,))
    rows = cur.fetchall(); cur.close()
    return rows

def calculate_totals(order_id: int) -> str:
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(oi.unitPrice * oi.quantity * COALESCE(oi.rentalDuration,1)),0) AS total
        FROM order_item oi WHERE oi.order_id=%s
    """, (order_id,))
    r = cur.fetchone(); cur.close()
    return str(r["total"] or 0)

def submit_order(cart_id: int, customer_id: int, billingAddressID: int | None, deliveryAddressID: int | None) -> int:
    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO orders (customer_id, orderStatus, orderDate, billingAddressID, deliveryAddressID)
        VALUES (%s,'Pending', NOW(), %s, %s)
    """, (customer_id, billingAddressID, deliveryAddressID))
    order_id = cur.lastrowid
    cur.execute("""
    SELECT ci.artwork_id, ci.quantity, ci.rentalDuration, a.pricePerWeek
    FROM cart_items ci
    JOIN artworks a ON a.artwork_id = ci.artwork_id
    WHERE ci.cart_id=%s
    """, (cart_id,))
    for r in cur.fetchall():
        cur.execute("""
           INSERT INTO order_item (order_id, artwork_id, quantity, rentalDuration, unitPrice)
           VALUES (%s,%s,%s,%s,%s)
        """, (order_id, r["artwork_id"], r["quantity"], r["rentalDuration"], r["pricePerWeek"]))

    # Mark cart converted
    cur.execute("UPDATE carts SET cart_status='Converted' WHERE cart_id=%s;", (cart_id,))
    mysql.connection.commit(); cur.close()
    return order_id

def confirm_payment(order_id: int) -> None:
    cur = mysql.connection.cursor()
    cur.execute("UPDATE orders SET orderStatus='Confirmed' WHERE order_id=%s;", (order_id,))
    mysql.connection.commit(); cur.close()




def get_all_vendors(limit: Optional[int] = None) -> List[dict]:
    cur = mysql.connection.cursor()
    sql = """
        SELECT vendor_id, artisticName, firstName, lastName, profilePictureLink
        FROM vendors
        ORDER BY artisticName IS NULL, artisticName, firstName, lastName
    """
    if limit:
        sql += " LIMIT %s"
        cur.execute(sql, (limit,))
    else:
        cur.execute(sql)
    rows = cur.fetchall()
    cur.close()
    return rows

def get_latest_artworks(limit: Optional[int] = 12, category_id: Optional[int] = None) -> List[dict]:
    cur = mysql.connection.cursor()
    sql = """
        SELECT artwork_id, vendor_id, category_id, title, itemDescription, pricePerWeek,
               imageLink, availabilityStartDate, availabilityEndDate, maxQuantity, availabilityStatus
        FROM artworks
        WHERE availabilityStatus='Listed'
    """
    params = []
    if category_id:
        sql += " AND category_id = %s"
        params.append(category_id)
    sql += " ORDER BY artwork_id DESC"
    if limit:
        sql += " LIMIT %s"
        params.append(limit)
    cur.execute(sql, tuple(params))
    rows = cur.fetchall()
    cur.close()
    return rows



def publish_artwork(artwork_id: int) -> None:
    cur = mysql.connection.cursor()
    cur.execute("UPDATE artworks SET availabilityStatus='Listed' WHERE artwork_id=%s;", (artwork_id,))
    mysql.connection.commit(); cur.close()

def update_artwork_details(artwork_id: int, patch: dict) -> None:
    allowed = {"title","itemDescription","pricePerWeek","imageLink","availabilityStartDate","availabilityEndDate","maxQuantity","category_id"}
    sets, params = [], []
    for k, v in patch.items():
        if k in allowed:
            sets.append(f"{k}=%s"); params.append(v)
    if not sets:
        return
    params.append(artwork_id)
    cur = mysql.connection.cursor()
    cur.execute(f"UPDATE artworks SET {', '.join(sets)} WHERE artwork_id=%s;", tuple(params))
    mysql.connection.commit(); cur.close()

def archive_artwork(artwork_id: int) -> None:
    cur = mysql.connection.cursor()
    cur.execute("UPDATE artworks SET availabilityStatus='Unlisted' WHERE artwork_id=%s;", (artwork_id,))
    mysql.connection.commit(); cur.close()

def generate_kpi(vendor_id: int) -> dict:
    cur = mysql.connection.cursor()

    # Inventory
    cur.execute("""
        SELECT
            COUNT(*) AS totalItems,
            COALESCE(SUM(availabilityStatus='Listed'), 0) AS activeItems
        FROM artworks
        WHERE vendor_id = %s
    """, (vendor_id,))
    inv = cur.fetchone() or {"totalItems": 0, "activeItems": 0}

    # Sales KPIs (Confirmed orders only) and distinct customers
    cur.execute("""
        SELECT
            COUNT(DISTINCT oi.order_id) AS ordersCnt,
            COUNT(DISTINCT o.customer_id) AS customersCnt,
            COALESCE(SUM(oi.quantity), 0) AS itemsLeased,
            COALESCE(SUM(oi.unitPrice * oi.quantity * COALESCE(oi.rentalDuration, 1)), 0) AS revenue
        FROM order_item oi
        JOIN artworks a ON a.artwork_id = oi.artwork_id
        JOIN orders   o ON o.order_id    = oi.order_id
        WHERE a.vendor_id = %s
          AND o.orderStatus = 'Confirmed'
          AND o.customer_id IS NOT NULL
    """, (vendor_id,))
    sales = cur.fetchone() or {"ordersCnt": 0, "customersCnt": 0, "itemsLeased": 0, "revenue": 0}
    cur.close()

    return {
        "inventory_total":  int(inv.get("totalItems") or 0),
        "inventory_active": int(inv.get("activeItems") or 0),
        "orders_count":     int(sales.get("ordersCnt") or 0),
        "items_leased":     int(sales.get("itemsLeased") or 0),
        "customers_count":  int(sales.get("customersCnt") or 0),   # 👈 NEW
        "revenue":          Decimal(str(sales.get("revenue") or 0))
    }


def select_default_address(customer_id: int, address_id: int) -> None:
    cur = mysql.connection.cursor()
    cur.execute("UPDATE customers SET address_id=%s WHERE customer_id=%s;", (address_id, customer_id))
    mysql.connection.commit(); cur.close()



def ensure_address(
    streetNumber: str,
    streetName: str,
    city: str,
    state: str,
    postcode: str,
    country: Optional[str] = None,
) -> int:
    country = (country or "Australia").strip()
    p = lambda s: (s or "").strip().lower()

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT address_id
          FROM addresses
         WHERE LOWER(TRIM(streetNumber))=%s
           AND LOWER(TRIM(streetName))=%s
           AND LOWER(TRIM(city))=%s
           AND LOWER(TRIM(state))=%s
           AND LOWER(TRIM(postcode))=%s
           AND LOWER(TRIM(country))=%s
         LIMIT 1
    """, (p(streetNumber), p(streetName), p(city), p(state), p(postcode), p(country)))
    row = cur.fetchone()
    if row:
        cur.close()
        return row["address_id"]

    cur.execute("""
        INSERT INTO addresses (streetNumber, streetName, city, state, postcode, country)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (streetNumber.strip(), streetName.strip(), city.strip(), state.strip(), postcode.strip(), country.strip()))
    mysql.connection.commit()
    addr_id = cur.lastrowid
    cur.close()
    return addr_id

def insert_address(streetNumber: str, streetName: str, city: str, state: str, postcode: str, country: str) -> int:
    # Backward-compatible
    return ensure_address(streetNumber, streetName, city, state, postcode, country)


def register_account(form) -> int:
    role = (form.account_type.data or "customer").strip().lower()
    if role not in ("customer", "vendor"):
        raise ValueError("Invalid account type")

    # 1) Address (required)
    addr_id = ensure_address(
        form.streetNumber.data.strip(),
        form.streetName.data.strip(),
        form.city.data.strip(),
        form.state.data.strip(),
        form.postcode.data.strip(),
        form.country.data.strip()
    )
    ...


    # 2) Person row
    cur = mysql.connection.cursor()
    pw = _hash(form.password.data)

    if role == "customer":
        cur.execute("""
            INSERT INTO customers (email, phone, customer_password, firstName, lastName, address_id, newsletterSubscription)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            form.email.data.strip(), form.phone.data.strip(), pw,
            form.firstname.data.strip(), form.surname.data.strip(), addr_id,
            1 if getattr(form, "newsletterSubscription", None) and form.newsletterSubscription.data else 0
        ))
        new_id = cur.lastrowid
    else:
        # Vendor requires artisticName, bio, profilePictureLink (validated in form)
        cur.execute("""
            INSERT INTO vendors (email, phone, vendor_password, firstName, lastName, address_id,
                                 artisticName, bio, profilePictureLink)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            form.email.data.strip(), form.phone.data.strip(), pw,
            form.firstname.data.strip(), form.surname.data.strip(), addr_id,
            form.artisticName.data.strip(), form.bio.data.strip(), form.profilePictureLink.data.strip()
        ))
        new_id = cur.lastrowid

    mysql.connection.commit()
    cur.close()
    return new_id

def ensure_customer(email: str, phone: str, first: str, last: str) -> int:
    cur = mysql.connection.cursor()
    cur.execute("SELECT customer_id FROM customers WHERE email=%s LIMIT 1;", (email,))
    row = cur.fetchone()
    if row:
        cur.close()
        return int(row["customer_id"])

    cur.execute("""
        INSERT INTO customers (email, phone, customer_password, firstName, lastName, address_id)
        VALUES (%s,%s,%s,%s,%s,NULL)
    """, (email, phone, _hash(uuid4().hex[:12]), first, last))
    new_id = cur.lastrowid
    mysql.connection.commit()
    cur.close()
    return new_id

def email_phone_in_use(role: str, email: str, phone: str) -> Tuple[bool, bool]:
    """
    Return (email_exists, phone_exists) for the target table only.
    role: 'customer' | 'vendor'
    """
    email = (email or "").strip()
    phone = (phone or "").strip()
    cur = mysql.connection.cursor()

    if role == "customer":
        cur.execute("SELECT 1 FROM customers WHERE email=%s LIMIT 1;", (email,))
        email_exists = bool(cur.fetchone())
        cur.execute("SELECT 1 FROM customers WHERE phone=%s LIMIT 1;", (phone,))
        phone_exists = bool(cur.fetchone())
    else:
        cur.execute("SELECT 1 FROM vendors WHERE email=%s LIMIT 1;", (email,))
        email_exists = bool(cur.fetchone())
        cur.execute("SELECT 1 FROM vendors WHERE phone=%s LIMIT 1;", (phone,))
        phone_exists = bool(cur.fetchone())

    cur.close()
    return email_exists, phone_exists

def arrange_delivery():
    pass

def edit_order():
    pass
