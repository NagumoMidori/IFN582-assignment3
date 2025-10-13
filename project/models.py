from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from uuid import uuid4

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
class Admin:
    admin_id: Optional[int]
    username: str
    admin_password: str

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

    def is_available_on(self, d: date) -> bool:
        pass
    
    def checkAvailability(self, start_date: date, weeks: int, qty: int = 1) -> bool:
        pass
    def calculateCustomPrice(self, qty: int, weeks: int, discount: Decimal | float = 0) -> Decimal:
        base = Decimal(str(self.pricePerWeek)) * Decimal(qty) * Decimal(weeks)
        if discount:
            base = base * (Decimal("1.00") - Decimal(str(discount)))
        return base.quantize(Decimal("0.01"))

    def getArtworkDetails(self) -> dict:
        return {
            "artwork_id": self.artwork_id,
            "title": self.title,
            "pricePerWeek": str(self.pricePerWeek),
            "availability": self.availabilityStatus.value,
            "maxQuantity": self.maxQuantity,
        }


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
        total = Decimal("0.00")
        for li in self.items:
            if li.artwork and li.artwork.pricePerWeek is not None:
                total += Decimal(str(li.artwork.pricePerWeek)) * (li.rentalDuration or 1) * (li.quantity or 1)
        return total.quantize(Decimal("0.01"))

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

    def total(self) -> Decimal:
        total = Decimal("0.00")
        for li in self.items:
            total += li.line_total()
        return total.quantize(Decimal("0.01"))
    
    def calculateTotals(self) -> Decimal:
        return self.total()

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
    
    def calculateLineTotal(self) -> Decimal:
        return self.line_total()