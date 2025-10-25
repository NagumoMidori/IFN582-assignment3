from hashlib import sha256
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, Tuple, List, Dict
from uuid import uuid4
from . import mysql
from project.models import Category, Artwork, Vendor, Order, OrderStatus
from project.forms import ArtworkForm



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
            c.categoryName                          
        FROM artworks a
        LEFT JOIN categories c ON c.category_id = a.category_id   
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
        sql += " AND a.category_id=%s"; params.append(category_id)
    if vendor_id is not None:
        sql += " AND a.vendor_id=%s"; params.append(vendor_id)
    if min_price is not None:
        sql += " AND a.pricePerWeek >= %s"; params.append(min_price)
    if max_price is not None:
        sql += " AND a.pricePerWeek <= %s"; params.append(max_price)
    if availability:
        sql += " AND a.availabilityStatus=%s"; params.append(availability)
    if q:
        like = f"%{q}%"
        sql += " AND (a.title LIKE %s OR a.itemDescription LIKE %s OR c.categoryName LIKE %s OR v.artisticName LIKE %s)"; params.extend([like, like, like, like])
    order_by = "a.artwork_id DESC"
    sort_map = {
        "latest": "a.artwork_id DESC",
        "oldest": "a.artwork_id ASC",
        "price_asc": "a.pricePerWeek ASC, a.artwork_id DESC",
        "price_desc": "a.pricePerWeek DESC, a.artwork_id DESC",
        "title": "a.title ASC"
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
            a.maxQuantity,              
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
        order.deliveryAddressID,
        
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

def get_latest_artworks(limit: Optional[int] = None, category_id: Optional[int] = None) -> List[dict]:
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

def delete_artwork(artwork_id: int, vendor_id: int) -> None:
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM artworks WHERE artwork_id=%s AND vendor_id=%s;", (artwork_id, vendor_id,))
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
        "customers_count":  int(sales.get("customersCnt") or 0),  
        "revenue":          Decimal(str(sales.get("revenue") or 0))
    }


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


def email_phone_in_use(role: str, email: str, phone: str) -> Tuple[bool, bool]:
    """
    Return (email_exists, phone_exists) for the target table only.
    role: 'customer' / 'vendor'
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



def get_listed_artworks_for_category_with_details(category_id: int) -> List[dict]:
    
    cur = mysql.connection.cursor()
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
    return items

def get_customer_postcode(customer_id: int) -> Optional[str]:
    
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT a.postcode
        FROM customers c
        LEFT JOIN addresses a ON a.address_id = c.address_id
        WHERE c.customer_id = %s
        LIMIT 1
    """, (int(customer_id),))
    row = cur.fetchone()
    cur.close()
    if row:
        return row.get('postcode')
    return None

def get_customer_address_details(customer_id: int) -> Optional[dict]:
    
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT a.streetNumber, a.streetName, a.city, a.state, a.postcode, a.country
          FROM customers c
          LEFT JOIN addresses a ON a.address_id = c.address_id
         WHERE c.customer_id = %s
         LIMIT 1
    """, (customer_id,))
    row = cur.fetchone()
    cur.close()
    return row

def get_artworks_for_vendor_gallery(vendor_id: int) -> List[dict]:
  
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
    return items

def add_artwork_from_form(form: ArtworkForm) -> None:
    
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

def admin_get_orders(order_id: Optional[int] = None) -> List[dict]:
    
    where = "WHERE o.order_id=%s" if order_id else ""
    params = (order_id,) if order_id else ()
    
    cur = mysql.connection.cursor()
    cur.execute(f"""
        SELECT o.order_id, o.customer_id, o.orderStatus, o.orderDate,
               o.billingAddressID, o.deliveryAddressID,
               c.firstName, c.lastName, c.email, c.phone
          FROM orders o
          LEFT JOIN customers c ON c.customer_id = o.customer_id
          {where}
         ORDER BY o.orderDate DESC, o.order_id DESC
    """, params)
    orders = cur.fetchall()
    cur.close()
    return orders

def admin_get_order_items(order_id: Optional[int] = None) -> List[dict]:
    
    where_items = "WHERE oi.order_id=%s" if order_id else ""
    params = (order_id,) if order_id else ()

    cur = mysql.connection.cursor()
    cur.execute(f"""
        SELECT
          oi.orderItem_id AS order_item_id,   
          oi.order_id,
          oi.artwork_id,
          oi.quantity,
          oi.rentalDuration,
          oi.unitPrice,
          a.title AS artworkTitle
        FROM order_item oi
        LEFT JOIN artworks a ON a.artwork_id = oi.artwork_id
        {where_items}
        ORDER BY oi.order_id DESC, oi.orderItem_id ASC
    """, params)
    order_items = cur.fetchall()
    cur.close()
    return order_items

def admin_get_order_statuses() -> List[str]:
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT DISTINCT orderStatus FROM orders ORDER BY orderStatus")
    statuses = [r['orderStatus'] for r in cur.fetchall()]
    cur.close()
    return statuses

def admin_update_order(order_id: int, cols: dict) -> None:
    
    sets, params = [], []
    for k, v in cols.items():
        if v is not None and v != '':
            sets.append(f"{k}=%s")
            params.append(v)
    if sets:
        params.append(order_id)
        cur = mysql.connection.cursor()
        cur.execute(f"UPDATE orders SET {', '.join(sets)} WHERE order_id=%s", tuple(params))
        mysql.connection.commit()
        cur.close()

def admin_update_order_item(order_item_id: int, cols: dict) -> None:
    
    sets, params = [], []
    for k, v in cols.items():
        if v is not None and v != '':
            sets.append(f"{k}=%s")
            params.append(v)
    if sets:
        params.append(order_item_id)
        cur = mysql.connection.cursor()
        cur.execute(f"UPDATE order_item SET {', '.join(sets)} WHERE orderItem_id=%s", tuple(params))
        mysql.connection.commit()
        cur.close()

def get_vendor_artwork(artwork_id: int, vendor_id: int) -> Optional[dict]:
    
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT artwork_id, vendor_id, category_id, title, itemDescription, pricePerWeek,
               imageLink, availabilityStartDate, availabilityEndDate, maxQuantity, availabilityStatus
        FROM artworks
        WHERE artwork_id=%s AND vendor_id=%s
        LIMIT 1
    """, (artwork_id, vendor_id))
    row = cur.fetchone()
    cur.close()
    return row

def update_artwork_from_form(form: ArtworkForm, artwork_id: int, vendor_id: int) -> None:
    
    category_id = form.category_id.data if form.category_id.data != 0 else None
    cur = mysql.connection.cursor()
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

def _get_artwork_constraints(artwork_id: int) -> Optional[dict]:
    """Fetch maxQuantity + availability window + status for a single artwork."""
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT maxQuantity, availabilityStartDate, availabilityEndDate, availabilityStatus
          FROM artworks
         WHERE artwork_id = %s
         LIMIT 1
    """, (artwork_id,))
    row = cur.fetchone()
    cur.close()
    return row or None

def quantity_within_max(artwork_id: int, requested_qty: int) -> Tuple[bool, int]:
    """
    True if requested_qty <= maxQuantity for the artwork.
    Returns (ok, maxQuantity).
    """
    info = _get_artwork_constraints(artwork_id)
    if not info:
        return (False, 0)
    max_q = int(info.get("maxQuantity") or 0)
    return (requested_qty <= max_q, max_q)

def weeks_within_availability(artwork_id: int, weeks: int, start: Optional[date] = None) -> Tuple[bool, date, Optional[date]]:
    """
    True if (start or today) + weeks <= availabilityEndDate.
    Returns (ok, start_date_used, availabilityEndDate).
    If availabilityEndDate is NULL, we treat it as 'no upper limit' => ok=True.
    """
    info = _get_artwork_constraints(artwork_id)
    if not info:
        return (False, start or date.today(), None)

    start_date = start or date.today()
    end_limit = info.get("availabilityEndDate")  # may be None
    if end_limit is None:
        return (True, start_date, None)

    # compute the date the rental would end
    end_date = start_date + timedelta(weeks=max(1, int(weeks or 1)))
    return (end_date <= end_limit, start_date, end_limit)

def can_fulfill_request(artwork_id: int, qty: int, weeks: int) -> Tuple[bool, str]:
    """
    Combined guard: the artwork must be Listed, qty <= max, and duration within availabilityEndDate.
    Returns (ok, human_message_if_not_ok).
    """
    info = _get_artwork_constraints(artwork_id)
    if not info:
        return (False, "This item no longer exists.")
    if (info.get("availabilityStatus") or "").lower() != "listed":
        return (False, "This item is not currently listed.")

    ok_qty, max_q = quantity_within_max(artwork_id, int(qty or 1))
    if not ok_qty:
        return (False, f"Only {max_q} available for this item.")

    ok_weeks, start_used, end_limit = weeks_within_availability(artwork_id, int(weeks or 1))
    if not ok_weeks:
        # end_limit may be None, but if we got here it's not
        return (False, f"Selected duration exceeds availability (available until {end_limit:%Y-%m-%d}).")

    return (True, "")
