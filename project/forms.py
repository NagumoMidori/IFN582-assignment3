from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, TextAreaField, SubmitField, RadioField,
    SelectField, IntegerField, DecimalField, DateField, DateTimeLocalField, 
)
from wtforms.validators import DataRequired, InputRequired, Email, Length, Optional, NumberRange, URL

class CheckoutForm(FlaskForm):
    firstname = StringField("First name", validators=[InputRequired()])
    surname   = StringField("Surname", validators=[InputRequired()])
    email     = StringField("Email", validators=[InputRequired(), Email()])
    phone     = StringField("Phone", validators=[InputRequired()])
    submit    = SubmitField("Place Order")

class LoginForm(FlaskForm):
    username  = StringField("Username or Email", validators=[InputRequired()])
    password  = PasswordField("Password", validators=[InputRequired()])
    submit    = SubmitField("Login")

class RegisterForm(FlaskForm):
    email     = StringField("Email", validators=[InputRequired(), Email()])
    password  = PasswordField("Password", validators=[InputRequired()])
    firstname = StringField("First name", validators=[InputRequired()])
    surname   = StringField("Surname", validators=[InputRequired()])
    phone     = StringField("Phone", validators=[InputRequired()])
    submit    = SubmitField("Create Account")

class AddToCartForm(FlaskForm):
    quantity = IntegerField("Quantity", validators=[InputRequired(), NumberRange(min=1)], default=1)
    weeks    = IntegerField("Weeks", validators=[Optional(), NumberRange(min=1)], default=1)


class VendorForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=100)])
    phone = StringField("Phone", validators=[DataRequired(), Length(max=20)])
    vendor_password = PasswordField("Password", validators=[DataRequired(), Length(min=6, max=255)])
    firstName = StringField("First name", validators=[DataRequired(), Length(max=100)])
    lastName = StringField("Last name", validators=[DataRequired(), Length(max=100)])
    address_id = SelectField("Address (optional)", coerce=int, validators=[Optional()])  # choices set in view
    artisticName = StringField("Artistic name", validators=[DataRequired(), Length(max=100)])
    bio = TextAreaField("Bio", validators=[DataRequired()])
    profilePictureLink = StringField("Profile picture URL", validators=[DataRequired(), URL(), Length(max=255)])
    submit = SubmitField("Create Vendor")

class ArtworkForm(FlaskForm):
    vendor_id = SelectField("Vendor", coerce=int, validators=[DataRequired()])           # set choices in view
    category_id = SelectField("Category (optional)", coerce=int, validators=[Optional()])# set choices in view
    title = StringField("Title", validators=[DataRequired(), Length(max=100)])
    itemDescription = TextAreaField("Description", validators=[DataRequired()])
    pricePerWeek = DecimalField("Price per week (AUD)", places=2,
                                validators=[DataRequired(), NumberRange(min=0)])
    imageLink = StringField("Image URL", validators=[DataRequired(), URL(), Length(max=255)])
    availabilityStartDate = DateField("Available from", validators=[Optional()], format="%Y-%m-%d")
    availabilityEndDate = DateField("Available until", validators=[Optional()], format="%Y-%m-%d")
    maxQuantity = IntegerField("Max quantity", validators=[DataRequired(), NumberRange(min=1)])
    availabilityStatus = SelectField(
        "Availability status",
        choices=[('Listed','Listed'), ('Leased','Leased'), ('Unlisted','Unlisted')],
        validators=[DataRequired()]
    )
    submit = SubmitField("Publish Artwork")
