from flask import session
from project.db import get_artwork
from project.models import Cart, CartItem, Order, OrderItem, OrderStatus

def get_user_dict():
    return session.get('user')

def get_cart() -> Cart:
    data = session.get('cart') or {'items': []}
    cart = Cart(cart_id=None, cartToken=0, customer_id=None)
    for row in data['items']:
        aw = get_artwork(int(row['artwork_id']))
        if aw:
            cart.items.append(CartItem(
                cartItem_id=row['id'], cart_id=0, artwork_id=aw.artwork_id,
                quantity=row['quantity'], rentalDuration=row.get('rentalDuration') or 1,
                artwork=aw
            ))
    return cart

def _save_cart(cart: Cart):
    session['cart'] = {
        'items': [{
            'id': item.cartItem_id,
            'artwork_id': item.artwork_id,
            'quantity': item.quantity,
            'rentalDuration': item.rentalDuration
        } for item in cart.items]
    }

def add_to_cart(artwork_id: int, quantity: int = 1, rentalDuration: int = 1):
    cart = get_cart()
    next_id = (max([i.cartItem_id for i in cart.items], default=0) or 0) + 1
    aw = get_artwork(artwork_id)
    if aw:
        cart.items.append(CartItem(
            cartItem_id=next_id, cart_id=0,
            artwork_id=aw.artwork_id, quantity=quantity,
            rentalDuration=rentalDuration, artwork=aw
        ))
        _save_cart(cart)

def remove_from_cart(item_id: int):
    cart = get_cart()
    cart.items = [i for i in cart.items if i.cartItem_id != int(item_id)]
    _save_cart(cart)

def empty_cart():
    session['cart'] = {'items': []}

def convert_cart_to_order(cart: Cart) -> Order:
    user = get_user_dict() or {}
    customer_id = int(user.get('id') or 0)
    order = Order(
        order_id=None, customer_id=customer_id,
        orderStatus=OrderStatus.CONFIRMED if customer_id else OrderStatus.PENDING,
        orderDate=None, billingAddressID=None, deliveryAddressID=None, items=[]
    )
    for li in cart.items:
        order.items.append(OrderItem(
            orderItem_id=None, order_id=0, artwork_id=li.artwork_id,
            quantity=li.quantity, rentalDuration=li.rentalDuration, unitPrice=None
        ))
    return order
