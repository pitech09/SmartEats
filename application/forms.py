from flask_wtf import FlaskForm # type: ignore
from flask_wtf.file import FileField, FileAllowed # type: ignore
from wtforms import StringField, HiddenField,FloatField, PasswordField, SubmitField, BooleanField, TextAreaField,IntegerField,SelectField, RadioField, EmailField# type: ignore
from wtforms.validators import DataRequired, Length, Email # type: ignore

class PharmacyRegistrationForm(FlaskForm):
    pharmacy_name = StringField('Store Name', validators=[DataRequired()])
    email = EmailField('Email', validators=[DataRequired()])
    phone = StringField('Phone Number', validators=[DataRequired()])
    address = StringField('Address', validators=[DataRequired()])
    opening_hours_and_days = StringField('Opening Hours', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8, max=16)])
    submit = SubmitField('Register Store')

class emailform(FlaskForm):
    email = EmailField('Email', validators=[DataRequired()])
    submit = SubmitField('Send')

class resetpassword(FlaskForm):
    password= PasswordField('New password', validators=[DataRequired(), Length(min=8, max=16)])

class UpdateForm(FlaskForm):
    username = StringField("Username",
                           validators=[DataRequired(), Length(min=3, max=18)])
    lastName = StringField('Lastname',
                           validators=[DataRequired(),
                                       Length(min=2, max=16)])
    phonenumber = StringField('Phone Number', validators=[DataRequired(), Length(min=8, max=15)])

    residence = StringField('Place of Residence', validators=[DataRequired()])

    Email = EmailField('Email',
                        validators=[DataRequired(),
                                    Length(min=5, max=30)])
    submit = SubmitField('Update')

class Search(FlaskForm):
    keyword = StringField('keyword')
    submit = SubmitField('Search')


class RegistrationForm(FlaskForm):
    username = StringField("Username",
                           validators=[DataRequired(), Length(min=3, max=18)])
    lastName = StringField('Lastname',
                           validators=[DataRequired(),
                                       Length(min=2, max=16)])
    
    Email = EmailField('Email',
                        validators=[DataRequired(),
                                    Length(min=5, max=30)])

    Password = PasswordField('Password',
                             validators=[DataRequired(), Length(min=8, max=16)])

    submit = SubmitField('Register')

class Set_StoreForm(FlaskForm):
    store = SelectField('Choose Store', choices=[], coerce=int, validators=[DataRequired()], default=-1)
    submit = SubmitField('Continue')



class LoginForm(FlaskForm):
    email = EmailField('Email',
                        validators=[DataRequired(), Length(min=5, max=30)])
    password = PasswordField('Password',
                             validators=[DataRequired()])

    submit = SubmitField('Login')

class CartlistForm(FlaskForm):
    submit = SubmitField('AddtoCart')


class removefromcart(FlaskForm):
    submit = SubmitField("-")


class clearcart(FlaskForm):
    submit = SubmitField('Clear Cart')

class addmore(FlaskForm):
    submit = SubmitField("+")

class update(FlaskForm):
    newname = StringField("New Name")
    newprice = FloatField("New Price: ")
    quantity = IntegerField("Quantity")
    newdescription = StringField("New Description: ")
    picture = FileField('Upload Product Picture', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif'])])

    submit = SubmitField("Commit Update")


class confirmpurchase(FlaskForm):
    payment = SelectField("Payment Method", validators=[DataRequired()], choices=[('Mpesa', 'Mpesa'), ('Ecocash', 'Ecocash')])
    transid = StringField('Enter your Mpesa/Ecocash Transaction ID', render_kw={'placeholder': 'transxxxxxxx'})
    payment_number = StringField('Phone Number Used for payment', render_kw={'placeholder':'+266 5123 4456'})
    payment_screenshot = FileField('Upload Proof of Payment', validators=[FileAllowed(['jpg', 'jpeg', 'png'])])
    deliverymethod = RadioField('Choose Delivery Method', choices=[('agent', 'Use Delivery agent'), ('pickup', 'Customer pickup')])
    drop_address = StringField('Drop Location:',render_kw={'placeholder': "Library, Metlakaseng Sefalana Crossong etc"})
    submit = SubmitField("Buy Cart")

class upload_prescription(FlaskForm):
    file = FileField('Upload Prescription', validators=[FileAllowed(['jpg', 'jpeg', 'png'])])

class ProductForm(FlaskForm):
    product_name = StringField("Product Name", validators=[DataRequired()])
    product_description = StringField("Description", validators=[DataRequired()])
    product_price = FloatField("Price", validators=[DataRequired()])
    product_pictures = FileField('Upload Product Picture', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif'])])
    submit = SubmitField("Add Product")


class updatestatusform(FlaskForm):
    status = SelectField('Status', validators=[DataRequired()], choices=[('Approved', 'Approved'),
                                                                        ('Ready ', 'Ready'),
                                                                        ('Out for Deliver', 'Out for Delivery'), 
                                                                        ('Delivered', 'Delivered'),
                                                                        ('Cancelled', 'Cancelled')])
    submit = SubmitField('Update Status')

class updateorderpickup(FlaskForm):
    status = SelectField('Status', validators=[DataRequired()], choices=[('Appproved', 'Approved'),
                                                                            ('Ready ', 'Ready'), 
                                                                            ('Collected', 'Collected'),
                                                                            ('Cancelled', 'Cancelled')
                                                                            ])
    submit = SubmitField('Update')

class updatedeliveryform(FlaskForm):
    status = SelectField('Status', validators=[DataRequired()], choices=[ ('Delivered', 'Delivered'),
                                                                            ('Cancelled', 'Cancelled')])
    delivery_prove = FileField('Customer Photo With their Order',
                               validators=[FileAllowed(['jpg', 'jpeg', 'png'])])
    submit = SubmitField('Update Delivery Status')



class addstaffform(FlaskForm):
    names = StringField('Names:', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired()])
    role = SelectField('Assign Role', validators=[DataRequired()], choices=[('Manager', 'Manager'), ('Cashier', 'Cashier')])
    password = StringField('Password', validators=[DataRequired()])
    submit = SubmitField('Add Staff')

class UpdatePharmacyForm(FlaskForm):
    mpesacode = StringField("Mpesa Till No.", validators=[DataRequired()])
    ecocashcode = StringField("Ecocash Till No.", validators=[DataRequired()])
    submit = SubmitField('Save')

class deliveryregistrationform(FlaskForm):
    names = StringField('Fullnames', validators=[DataRequired()])
    email = StringField('Email Address', validators=[DataRequired()])
    phone = StringField('Phone Number', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8, max=16)])
    submit = SubmitField('Register Delivery Agent')


class update_password(FlaskForm):
    old_password = PasswordField('Old Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired()])
    confirm = SubmitField('Confirm')


