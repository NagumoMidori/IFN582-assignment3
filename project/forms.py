import re

from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, TextAreaField, SubmitField, RadioField,
    SelectField, IntegerField, DecimalField, DateField, BooleanField,
    HiddenField, URLField
)
from wtforms.validators import (
    DataRequired, InputRequired, Email, Length, Optional, NumberRange,
    EqualTo, AnyOf, ValidationError
)



class CheckoutForm(FlaskForm):
    # Contact
    firstname = StringField("First Name", validators=[InputRequired(), Length(max=100)])
    surname   = StringField("Surname",    validators=[InputRequired(), Length(max=100)])
    email     = StringField("Email",      validators=[InputRequired(), Email(), Length(max=100)])
    phone     = StringField("Phone",      validators=[InputRequired(), Length(max=20)])

    # Delivery (REQUIRED)
    del_streetNumber = StringField("Street number", validators=[InputRequired(), Length(max=20)])
    del_streetName   = StringField("Street name",   validators=[InputRequired(), Length(max=100)])
    del_city         = StringField("City",          validators=[InputRequired(), Length(max=50)])
    del_state        = StringField("State",         validators=[InputRequired(), Length(max=50)])
    del_postcode     = StringField("Postcode",      validators=[InputRequired(), Length(max=10)])
    del_country      = StringField("Country",       validators=[InputRequired(), Length(max=100)])

    # Billing (REQUIRED unless user clicks “Same as delivery” first)
    bill_streetNumber = StringField("Street number", validators=[Length(max=20)])
    bill_streetName   = StringField("Street name",   validators=[Length(max=100)])
    bill_city         = StringField("City",          validators=[Length(max=50)])
    bill_state        = StringField("State",         validators=[Length(max=50)])
    bill_postcode     = StringField("Postcode",      validators=[Length(max=10)])
    bill_country      = StringField("Country",       validators=[Length(max=100)])

    # Payment (selection handled via template CSS for now)
    payment_method   = RadioField(
        "Payment method",
        choices=[
            ("card",   "Credit / Debit Card"),
            ("paypal", "PayPal"),
            ("wallet", "Digital Wallet")
        ],
        default="card",
        validators=[InputRequired()]
    )
    card_name        = StringField("Name on card", validators=[Optional(), Length(max=100)])
    card_number      = StringField("Card number", validators=[Optional(), Length(min=12, max=19)])
    card_expiry      = StringField("Expiry (MM/YY)", validators=[Optional(), Length(max=7)])
    card_cvv         = StringField("Security code", validators=[Optional(), Length(min=3, max=4)])

    paypal_email     = StringField("PayPal email", validators=[Optional(), Email(), Length(max=100)])

    wallet_provider  = StringField("Wallet provider", validators=[Optional(), Length(max=50)])
    wallet_reference = StringField("Wallet reference", validators=[Optional(), Length(max=100)])

    # Buttons
    copy_delivery = SubmitField("Same as delivery")
    submit        = SubmitField("Place order")

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators=extra_validators)
        if not ok:
            return False

        method = (self.payment_method.data or '').lower()
        if method == 'card':
            required = {
                'card_name': self.card_name.data,
                'card_number': self.card_number.data,
                'card_expiry': self.card_expiry.data,
                'card_cvv': self.card_cvv.data,
            }
            missing = False
            for field, value in required.items():
                if not (value or '').strip():
                    getattr(self, field).errors.append("Required for card payments.")
                    missing = True
            card_number_clean = re.sub(r"\s+", "", self.card_number.data or "")
            if card_number_clean:
                if not card_number_clean.isdigit():
                    self.card_number.errors.append("Card number must contain digits only.")
                    missing = True
                elif not (12 <= len(card_number_clean) <= 19):
                    self.card_number.errors.append("Card number must be between 12 and 19 digits.")
                    missing = True
            if self.card_cvv.data:
                if not self.card_cvv.data.isdigit():
                    self.card_cvv.errors.append("CVV must contain digits only.")
                    missing = True
                elif len(self.card_cvv.data) not in (3, 4):
                    self.card_cvv.errors.append("CVV must be 3 or 4 digits.")
                    missing = True
            if self.card_expiry.data:
                expiry = self.card_expiry.data.strip()
                if not re.match(r"^(0[1-9]|1[0-2])\/\d{2}$", expiry):
                    self.card_expiry.errors.append("Use MM/YY format.")
                    missing = True
            if missing:
                return False

        elif method == 'paypal':
            if not (self.paypal_email.data or '').strip():
                self.paypal_email.errors.append("PayPal email is required.")
                return False

        elif method == 'wallet':
            missing = False
            if not (self.wallet_provider.data or '').strip():
                self.wallet_provider.errors.append("Provider is required for digital wallets.")
                missing = True
            if not (self.wallet_reference.data or '').strip():
                self.wallet_reference.errors.append("Reference is required for digital wallets.")
                missing = True
            if missing:
                return False
        else:
            self.payment_method.errors.append("Please choose a payment method.")
            return False

        return True


class LoginForm(FlaskForm):
    username     = StringField("Username or Email", validators=[InputRequired()])
    password     = PasswordField("Password", validators=[InputRequired()])
    # Only show customer/vendor; admin is handled server-side regardless of selection
    account_type = RadioField(
        "Sign in as",
        choices=[("customer", "Customer"), ("vendor", "Vendor")],
        default="customer",
        validators=[AnyOf(["customer", "vendor"])]
    )
    submit       = SubmitField("Login")






class RegisterForm(FlaskForm):
    # Choose account type (NO admin option)
    account_type = HiddenField(
        "Account type",
        validators=[InputRequired(), AnyOf(["customer", "vendor"])]
    )

    # Common identity + contact
    firstname = StringField("First name", validators=[InputRequired(), Length(max=100)])
    surname   = StringField("Last name",  validators=[InputRequired(), Length(max=100)])
    email     = StringField("Email",      validators=[InputRequired(), Email(), Length(max=100)])
    phone     = StringField("Phone",      validators=[InputRequired(), Length(max=20)])

    # Password
    password  = PasswordField("Password", validators=[InputRequired(), Length(min=6, max=255)])
    confirm   = PasswordField("Confirm password", validators=[InputRequired(), EqualTo("password")])

    # Required address
    streetNumber = StringField("Street number", validators=[InputRequired(), Length(max=20)])
    streetName   = StringField("Street name",   validators=[InputRequired(), Length(max=100)])
    city         = StringField("City",          validators=[InputRequired(), Length(max=50)])
    state        = StringField("State",         validators=[InputRequired(), Length(max=50)])
    postcode     = StringField("Postcode",      validators=[InputRequired(), Length(max=10)])
    country      = StringField("Country",       validators=[InputRequired(), Length(max=100)], default="Australia")

    # Customer-only
    newsletterSubscription = BooleanField("Subscribe to newsletter")

    # Vendor-only fields (required for vendors)
    artisticName       = StringField("Artistic / Studio name", validators=[Length(max=100)])
    bio                = TextAreaField("Short bio")
    profilePictureLink = StringField("Profile picture", validators=[Length(max=255)])

    submit = SubmitField("Create account")

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators=extra_validators)
        if not ok:
            return False
        if self.account_type.data == "vendor":
            errors = False
            if not self.artisticName.data:
                self.artisticName.errors.append("Required for vendors."); errors = True
            if not self.bio.data:
                self.bio.errors.append("Required for vendors."); errors = True
            if not self.profilePictureLink.data:
                self.profilePictureLink.errors.append("Required for vendors."); errors = True
            if errors:
                return False
        return True
    

class AddToCartForm(FlaskForm):
    durationPreset = RadioField(
        "Duration option",
        choices=[("standard", "Standard - 1 week"), ("custom", "Custom duration")],
        default="standard",
        validators=[InputRequired()],
    )
    weeks = IntegerField(
        "Weeks",
        validators=[Optional(), NumberRange(min=2, max=50, message="Custom duration must be between 2 and 50 weeks.")],
        render_kw={"min": 2, "max": 50, "placeholder": "Week"},
    )
    quantity = IntegerField(
        "Quantity",
        validators=[InputRequired(), NumberRange(min=1)],
        default=1,
        render_kw={"min": 1},
    )
    postcode = StringField(
        "Delivery postcode",
        validators=[Optional(), Length(max=10)],
    )


class VendorForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=100)])
    phone = StringField("Phone", validators=[DataRequired(), Length(max=20)])
    vendor_password = PasswordField("Password", validators=[DataRequired(), Length(min=6, max=255)])
    firstName = StringField("First name", validators=[DataRequired(), Length(max=100)])
    lastName = StringField("Last name", validators=[DataRequired(), Length(max=100)])
    address_id = SelectField("Address (optional)", coerce=int, validators=[Optional()])  
    artisticName = StringField("Artistic name", validators=[DataRequired(), Length(max=100)])
    bio = TextAreaField("Bio", validators=[DataRequired()])
    profilePictureLink = StringField("Profile picture", validators=[DataRequired(), Length(max=255)])
    submit = SubmitField("Create Vendor")

class ArtworkForm(FlaskForm):
    vendor_id   = SelectField("Vendor", coerce=int, validators=[DataRequired()])          
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])  
    title       = StringField("Title", validators=[DataRequired(), Length(max=100)])
    itemDescription = TextAreaField("Description", validators=[DataRequired()])
    pricePerWeek    = DecimalField("Price per week (AUD)", places=2, validators=[DataRequired(), NumberRange(min=0)])
    imageLink       = StringField("Image", validators=[DataRequired(), Length(max=255)])
    availabilityStartDate = DateField("Available from", validators=[Optional()], format="%Y-%m-%d",
                                      render_kw={"type": "date"})
    availabilityEndDate   = DateField("Available until", validators=[Optional()], format="%Y-%m-%d",
                                      render_kw={"type": "date"})
    maxQuantity     = IntegerField("Max quantity", validators=[DataRequired(), NumberRange(min=1)])
    availabilityStatus = SelectField(
        "Availability status",
        choices=[('Listed','Listed'), ('Leased','Leased'), ('Unlisted','Unlisted')],
        validators=[DataRequired()]
    )
    submit = SubmitField("Publish Artwork")

    def validate_availabilityEndDate(self, field):
            start = self.availabilityStartDate.data
            end   = field.data
            # Only validate if both dates are present
            if start and end and end < start:
                raise ValidationError("Available until must be on or after 'Available from'.")
