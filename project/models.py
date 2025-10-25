from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict



class AvailabilityStatus(str, Enum):
    LISTED = "Listed"
    LEASED = "Leased"
    UNLISTED = "Unlisted"

class CartStatus(str, Enum):
    ACTIVE = "Active"
    ABANDONED = "Abandoned"
    CONVERTED = "Converted"

class OrderStatus(str, Enum):
    PENDING = "Pending"
    CONFIRMED = "Confirmed"
    CANCELLED = "Cancelled"

@dataclass
class Address:
    address_id: Optional[int]
    streetNumber: str
    streetName: str
    city: str
    state: str
    postcode: str
    country: str

@dataclass
class Category:
    category_id: Optional[int]
    categoryName: str

@dataclass
class Customer:
    customer_id: Optional[int]
    email: str
    phone: str
    customer_password: str
    firstName: str
    lastName: str
    address_id: Optional[int] = None
    address: Optional[Address] = None

@dataclass
class Vendor:
    vendor_id: Optional[int]
    email: str
    phone: str
    vendor_password: str
    firstName: str
    lastName: str
    address_id: Optional[int] = None
    artisticName: str = ""
    bio: str = ""
    image: str = 'foobar.png'
    address: Optional[Address] = None

@dataclass
class Artwork:
    artwork_id: Optional[int]
    vendor_id: int
    category_id: Optional[int]
    title: str
    itemDescription: str
    pricePerWeek: Decimal
    image: str = 'foobar.png'
    availabilityStartDate: Optional[date] = None
    availabilityEndDate: Optional[date] = None
    maxQuantity: int = 1
    availabilityStatus: AvailabilityStatus = AvailabilityStatus.UNLISTED
    vendor: Optional[Vendor] = None
    category: Optional[Category] = None


@dataclass
class Cart:
    cart_id: Optional[int]
    cartToken: int
    customer_id: Optional[int] = None
    cart_status: CartStatus = CartStatus.ACTIVE
    deliveryAddressID: Optional[int] = None
    customer: Optional[Customer] = None
    deliveryAddress: Optional[Address] = None
    items: List["CartItem"] = field(default_factory=list)

    def total_using_current_prices(self) -> Decimal:
        try:
            from project.session import delivery_cost_from_session
            delivery = delivery_cost_from_session()
        except Exception:
            # if we're outside a request context or the import fails, don't crash totals
            delivery = Decimal("0.00")

        total = Decimal("0.00")
        for li in self.items:
            if li.artwork and li.artwork.pricePerWeek is not None:
                total += (
                    Decimal(str(li.artwork.pricePerWeek))
                    * Decimal(li.rentalDuration or 1)
                    * Decimal(li.quantity or 1)
                )

        return (total + delivery).quantize(Decimal("0.01"))


@dataclass
class CartItem:
    cartItem_id: Optional[int]
    cart_id: int
    artwork_id: int
    quantity: int
    rentalDuration: int
    cart: Optional[Cart] = None
    artwork: Optional[Artwork] = None

@dataclass
class Order:
    order_id: Optional[int]
    customer_id: int
    orderStatus: OrderStatus = OrderStatus.PENDING
    orderDate: Optional[datetime] = None
    billingAddressID: Optional[int] = None
    deliveryAddressID: Optional[int] = None
    customer: Optional[Customer] = None
    billingAddress: Optional[Address] = None
    deliveryAddress: Optional[Address] = None
    items: List["OrderItem"] = field(default_factory=list)
    paymentMethod: Optional[str] = None
    paymentDetails: Dict[str, str] = field(default_factory=dict)

    def total(self) -> Decimal:
        total = Decimal("0.00")
        for li in self.items:
            total += li.line_total()
        return total.quantize(Decimal("0.01"))
    
@dataclass
class OrderItem:
    orderItem_id: Optional[int]
    order_id: int
    artwork_id: int
    quantity: int = 1
    rentalDuration: Optional[int] = None
    unitPrice: Optional[Decimal] = None
    order: Optional[Order] = None
    artwork: Optional[Artwork] = None

    def line_total(self) -> Decimal:
        if self.unitPrice is None:
            return Decimal("0.00")
        return (Decimal(str(self.unitPrice)) * (self.quantity or 1) * (self.rentalDuration or 1)).quantize(Decimal("0.01"))