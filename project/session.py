from flask import session
from project.db import get_artwork, can_fulfill_request
from project.models import Cart, CartItem, Order, OrderItem, OrderStatus
from decimal import Decimal

def get_user_dict():
    return session.get('user')


def get_cart() -> Cart:
    data = session.get('cart') or {'items': []}
    cart = Cart(cart_id=None, cartToken=0, customer_id=None)
    for row in data.get('items', []):
        artwork_id = row.get('artwork_id')
        if artwork_id is None:
            continue
        artwork = get_artwork(int(artwork_id))
        if not artwork:
            continue
        cart.items.append(CartItem(
            cartItem_id=row.get('id'),
            cart_id=0,
            artwork_id=artwork.artwork_id,
            quantity=row.get('quantity', 1) or 1,
            rentalDuration=row.get('rentalDuration') or 1,
            artwork=artwork
        ))
    _attach_cart_item_ids(cart)    
    return cart


def _save_cart(cart: Cart) -> None:
    session['cart'] = {
        'items': [{
            'id': item.cartItem_id,
            'artwork_id': item.artwork_id,
            'quantity': item.quantity,
            'rentalDuration': item.rentalDuration
        } for item in cart.items]
    }
    session.modified = True

def add_to_cart(artwork_id: int, quantity: int, weeks: int) -> bool:
    #Only add the item to the cart if it passes the validation
    q = max(1, int(quantity or 1))
    w = max(1, int(weeks or 1))

    data = session.get("cart") or {"items": []}
    items = data.setdefault("items", [])

    # find existing line with same artwork + same duration
    idx = -1
    for i, row in enumerate(items):
        rid = row.get("artwork_id")
        rw  = row.get("rentalDuration") or row.get("weeks")  # tolerate older key name
        if rid == artwork_id and int(rw or 0) == w:
            idx = i
            break

    if idx >= 0:
        # validate AFTER-MERGE quantity
        new_qty = int(items[idx].get("quantity", 1)) + q
        ok, msg = can_fulfill_request(artwork_id, new_qty, w)
        if not ok:
            _flash_safe(msg or "Requested quantity exceeds availability.", "warning")
            return False
        items[idx]["quantity"] = new_qty
    else:
        # validate for new line, flashes any errors
        ok, msg = can_fulfill_request(artwork_id, q, w)
        if not ok:
            _flash_safe(msg or "This item can't be added with the selected quantity/duration.", "warning")
            return False
        # write a simple dict; get_cart() will rehydrate to CartItem
        items.append({
            "artwork_id": artwork_id,
            "quantity": q,
            "rentalDuration": w,  # prefer this key going forward
        })

    # persist back to session
    session["cart"] = data
    session.modified = True
    return True

def _attach_cart_item_ids(cart):
    """
    It gives every cart row a stable ID (its list position) 
    so templates and routes know exactly which line item to update or remove.
    """
    raw_items = None
    try:
        from flask import session as _s
        raw_items = (_s.get("cart") or {}).get("items", None)
    except Exception:
        pass

    for idx, li in enumerate(getattr(cart, "items", []) or []):
        # attribute for object access
        try:
            setattr(li, "cartItem_id", idx)
        except Exception:
            pass

        # keep dict key in the raw session too (Jinja also treats dict keys as attributes)
        if isinstance(raw_items, list):
            try:
                row = raw_items[idx]
                if isinstance(row, dict):
                    row["cartItem_id"] = idx
            except Exception:
                pass

    # mark session modified if we touched raw dicts (safe no-op if not)
    try:
        from flask import session as _s
        _s.modified = True
    except Exception:
        pass


def _flash_safe(message: str, category: str = "warning"):
    # Fail safe in case the flash function fails inside the add to cart function
    try:
        from flask import flash
        flash(message, category)
    except Exception:
        # no request context; just skip flashing
        pass


def remove_from_cart(item_id: int) -> bool:
    cart = get_cart()
    original_len = len(cart.items)
    cart.items = [item for item in cart.items if item.cartItem_id != int(item_id)]
    if len(cart.items) == original_len:
        return False
    _save_cart(cart)
    return True


def update_cart_item(item_id: int, quantity: int) -> bool:
    cart = get_cart()
    for item in cart.items:
        if item.cartItem_id == int(item_id):
            item.quantity = max(1, quantity or 1)
            _save_cart(cart)
            return True
    return False


def empty_cart() -> None:
    session['cart'] = {'items': []}
    session.modified = True


def convert_cart_to_order(cart: Cart) -> Order:
    user = get_user_dict() or {}
    customer_id = int(user.get('id') or 0)
    order = Order(
        order_id=None,
        customer_id=customer_id,
        orderStatus=OrderStatus.PENDING if customer_id else OrderStatus.PENDING,
        orderDate=None,
        billingAddressID=None,
        deliveryAddressID=None,
        items=[]
    )
    for cart_item in cart.items:
        unit_price = None
        if cart_item.artwork and cart_item.artwork.pricePerWeek is not None:
            unit_price = cart_item.artwork.pricePerWeek
        order.items.append(OrderItem(
            orderItem_id=None,
            order_id=0,
            artwork_id=cart_item.artwork_id,
            quantity=cart_item.quantity,
            rentalDuration=cart_item.rentalDuration,
            unitPrice=unit_price,
            artwork=cart_item.artwork
        ))
    return order
def _delivery_cost_for_postcode(value) -> Decimal:
    #Return delivery cost as Decimal based on AU postcode bands.
    try:
        pc = int(str(value).strip())
    except Exception:
        return Decimal("0")  # default when missing/invalid

    if   0    < pc <=  999:  return Decimal("40")
    elif 1000 <= pc <= 2999:  return Decimal("10")
    elif 3000 <= pc <= 3999:  return Decimal("15")
    elif 4000 <= pc <= 4999:  return Decimal("5")
    elif 5000 <= pc <= 5999:  return Decimal("25")
    elif 6000 <= pc <= 6999:  return Decimal("30")
    elif 7000 <= pc <= 7999:  return Decimal("20")
    elif 8000 <= pc <= 8999:  return Decimal("15")
    elif 9000 <= pc <= 9999:  return Decimal("5")
    else:                     return Decimal("150")

def delivery_cost_from_session() -> Decimal:
    #Reads the user's chosen/remembered postcode and returns the cost.
    return _delivery_cost_for_postcode(session.get("checkout_postcode"))