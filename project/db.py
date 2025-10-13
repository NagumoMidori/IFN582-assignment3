from hashlib import sha256
from datetime import datetime
from decimal import Decimal
from typing import Optional, Tuple, List
from typing import List, Optional
from uuid import uuid4
from . import mysql
from project.models import *


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

def get_artworks_for_category(category_id: int) -> List[Artwork]:
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT artwork_id, vendor_id, category_id, title, itemDescription,
               pricePerWeek, imageLink, availabilityStartDate, availabilityEndDate,
               maxQuantity, availabilityStatus
        FROM artworks
        WHERE category_id=%s
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
        SELECT artwork_id, vendor_id, category_id, title, itemDescription,
               pricePerWeek, imageLink, availabilityStartDate, availabilityEndDate,
               maxQuantity, availabilityStatus
        FROM artworks WHERE artwork_id=%s;
    """, (artwork_id,))
    r = cur.fetchone()
    cur.close()
    if not r:
        return None
    return Artwork(
        artwork_id=r['artwork_id'], vendor_id=r['vendor_id'], category_id=r['category_id'],
        title=r['title'], itemDescription=r['itemDescription'],
        pricePerWeek=Decimal(str(r['pricePerWeek'])), image=r['imageLink'],
        availabilityStartDate=r['availabilityStartDate'], availabilityEndDate=r['availabilityEndDate'],
        maxQuantity=r['maxQuantity'], availabilityStatus=r['availabilityStatus']
    )

def filter_items(
    category_id: int | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    q: str | None = None,
    vendor_id: int | None = None,
    availability: str | None = None  # 'active'|'unlisted'|'leased'
) -> list[dict]:
    """+filterItems(): flexible catalog filtering for UI."""
    sql = """
      SELECT artwork_id, vendor_id, category_id, title, itemDescription, pricePerWeek, imageLink,
             availabilityStartDate, availabilityEndDate, maxQuantity, availabilityStatus
      FROM artworks WHERE 1=1
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
        sql += " AND (title LIKE %s OR itemDescription LIKE %s)"; params.extend([like, like])
    sql += " ORDER BY title;"
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
        SELECT a.artwork_id, a.vendor_id, a.category_id, a.title, a.itemDescription,
               a.pricePerWeek, a.imageLink, a.availabilityStartDate, a.availabilityEndDate,
               a.maxQuantity, a.availabilityStatus,
               c.categoryName
        FROM artworks a
        LEFT JOIN categories c ON c.category_id = a.category_id
        WHERE a.vendor_id=%s
        ORDER BY a.title;
    """, (vendor_id,))
    rows = cur.fetchall()
    cur.close()
    items = []
    for r in rows:
        aw = Artwork(
            artwork_id=r['artwork_id'], vendor_id=r['vendor_id'], category_id=r['category_id'],
            title=r['title'], itemDescription=r['itemDescription'],
            pricePerWeek=Decimal(str(r['pricePerWeek'])), image=r['imageLink'],
            availabilityStartDate=r['availabilityStartDate'], availabilityEndDate=r['availabilityEndDate'],
            maxQuantity=r['maxQuantity'], availabilityStatus=r['availabilityStatus']
        )
    
        aw.categoryName = r['categoryName']
        items.append(aw)
    return items

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

def update_profile():
    pass

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

def arrange_delivery():
    pass

def edit_order():
    pass


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
    """
    params = []
    if category_id:
        sql += " WHERE category_id = %s"
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
    cur.execute("SELECT COUNT(*) AS totalItems, SUM(availabilityStatus='Listed') AS activeItems FROM artworks WHERE vendor_id=%s;", (vendor_id,))
    inv = cur.fetchone() or {"totalItems":0,"activeItems":0}

    # Orders and revenue for this vendor (joining vendor's artworks)
    cur.execute("""
        SELECT COUNT(DISTINCT oi.order_id) AS ordersCnt,
               COALESCE(SUM(oi.unitPrice * oi.quantity * COALESCE(oi.rentalDuration,1)),0) AS revenue
        FROM order_item oi
        JOIN artworks a ON a.artwork_id = oi.artwork_id
        WHERE a.vendor_id=%s
    """, (vendor_id,))
    sales = cur.fetchone() or {"ordersCnt":0,"revenue":0}
    cur.close()
    return {
        "inventory_total": int(inv["totalItems"] or 0),
        "inventory_active": int(inv["activeItems"] or 0),
        "orders_count": int(sales["ordersCnt"] or 0),
        "revenue": str(sales["revenue"] or 0),
    }


def validate_address():
    pass

def select_default_address(customer_id: int, address_id: int) -> None:
    cur = mysql.connection.cursor()
    cur.execute("UPDATE customers SET address_id=%s WHERE customer_id=%s;", (address_id, customer_id))
    mysql.connection.commit(); cur.close()


def ensure_customer():
    pass
def update_artwork_details():
    pass

def get_categories ():
    pass