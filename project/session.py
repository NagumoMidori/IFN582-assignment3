from flask import session

from project.db import get_artwork
from project.models import Cart, CartItem, Order, OrderItem, OrderStatus


def get_user_dict():
    return session.get('user')


def get_cart() -> Cart:
    """Rehydrate the cart stored in the session into a Cart dataclass."""
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


def add_to_cart(artwork_id: int, quantity: int = 1, rental_duration: int = 1) -> bool:
    cart = get_cart()
    artwork = get_artwork(artwork_id)
    if not artwork:
        return False

    quantity = max(1, quantity or 1)
    rental_duration = max(1, rental_duration or 1)
    next_id = max((item.cartItem_id or 0 for item in cart.items), default=0) + 1

    cart.items.append(CartItem(
        cartItem_id=next_id,
        cart_id=0,
        artwork_id=artwork.artwork_id,
        quantity=quantity,
        rentalDuration=rental_duration,
        artwork=artwork
    ))
    _save_cart(cart)
    return True


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
        orderStatus=OrderStatus.CONFIRMED if customer_id else OrderStatus.PENDING,
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
