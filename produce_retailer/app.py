from flask import Flask, request, render_template, redirect, url_for, flash, session
import pymongo
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import os
import re
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
from datetime import datetime

load_dotenv()

app = Flask(__name__)

# Load secret key and session lifetime from .env
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# Connect to MongoDB
mongo_uri = os.getenv("MONGO_URI")
client = pymongo.MongoClient(mongo_uri)
db = client["greeners"]
users_collection = db['users']
records_collection=db['sales']
expenditures_collection = db['expenditures']

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    return render_template('home.html')

@app.route('/enter_records_home')
def enter_records_home():
    return render_template('navig/enter_records_home.html')

@app.route('/view_details')
def view_details():
    return render_template('navig/view_details.html')

@app.route('/search_by_date')
def search_by_date():
    return render_template('search_by_date.html')

@app.route('/search_by_item', methods=['GET', 'POST'])
def search_by_item():
    if request.method == 'POST':
        item_name = request.form['itemName'].lower().strip()  # Convert input to lowercase and remove leading/trailing spaces

        # Debugging: Print the item name to check if it's correct
        print(f"Searching for item: {item_name}")

        # If no item name is provided, show an error
        if not item_name:
            return render_template('navig/search_by_item.html', error="Please enter an item name.")

        try:
            # Retrieve records matching the item name from MongoDB (case-insensitive search)
            records = list(db.sales.find({'item_name': {'$regex': item_name, '$options': 'i'}}))

            # Debugging: Print the number of records found
            print(f"Number of records found: {len(records)}")

            # If no records found
            if not records:
                return render_template('navig/search_by_item.html', error="No records found for this item.")

            # Aggregating total weight and total bill for the item
            total_weight = sum(record['weight'] for record in records)
            total_bill = sum(record['total_bill'] for record in records)

            # Number of items
            number_of_items = len(records)

            # Create summary
            summary = {
                'total_weight': total_weight,
                'total_bill': total_bill,
                'number_of_items': number_of_items,
                'item_name': item_name
            }

            # Render template with records and summary
            return render_template('navig/search_by_item.html', summary=summary, records=records)

        except Exception as e:
            # Handle any exceptions that occur during the database query
            print(f"Error occurred while querying MongoDB: {e}")
            return render_template('navig/search_by_item.html', error="An error occurred while processing your request. Please try again.")

    # If GET request, show the form to search for an item
    return render_template('navig/search_by_item.html')


@app.route('/search_by_vendor', methods=['GET', 'POST'])
def search_by_vendor():
    if request.method == 'POST':
        vendor_name = request.form['vendorName'].lower().strip()  # Convert to lowercase and strip spaces

        # Debugging: Print the vendor name to check if it's correct
        print(f"Searching for vendor: {vendor_name}")

        # Retrieve records matching the vendor name from MongoDB (case-insensitive search)
        records = list(db.sales.find({'vendor_name': {'$regex': vendor_name, '$options': 'i'}}))

        # If no records found
        if not records:
            return render_template('navig/search_by_vendor.html', error="No records found for this vendor.")

        # Aggregating total weight, total bill, and due for the vendor
        total_weight = sum(record['weight'] for record in records)
        total_bill = sum(record['total_bill'] for record in records)
        total_due = sum(record['due'] for record in records)

        # Create summary
        summary = {
            'total_weight': total_weight,
            'total_bill': total_bill,
            'total_due': total_due,
            'vendor_name': vendor_name
        }

        # Render template with records and summary
        return render_template('navig/search_by_vendor.html', summary=summary, records=records)

    # If GET request, render the empty search form
    return render_template('navig/search_by_vendor.html')


@app.route('/dues', methods=['GET'])
def dues():
    # Retrieve all records with due > 0 from MongoDB
    records = list(db.sales.find({'due': {'$gt': 0}}))  # Only records where due is greater than 0

    # If no records with due > 0
    if not records:
        return render_template('navig/dues.html', error="No dues available.")

    # Aggregating total dues across all records
    total_due = sum(record['due'] for record in records)

    # Create summary for dues
    summary = {
        'total_due': total_due
    }

    # Render template with records and dues summary
    return render_template('navig/dues.html', summary=summary, records=records)



@app.route('/profit_till_today')
def profit_today():
    return render_template('profit_today.html')

@app.route('/enter_records', methods=['GET', 'POST'])
def enter_records():
    if request.method == 'POST':
        try:
            # Get data from the form
            vendor_name = request.form.get('vendorName')
            item_name = request.form.get('itemName')
            weight = request.form.get('weight')
            cost_per_kg = request.form.get('costPerKg')
            amount_paid = request.form.get('amountPaid')

            # Check if any of the fields are missing
            if not vendor_name or not item_name or not weight or not cost_per_kg or not amount_paid:
                error_message = "All fields are required. Please fill out the entire form."
                return render_template('navig/enter_records.html', error=error_message)

            # Convert values to float and calculate total bill
            weight = float(weight)
            cost_per_kg = float(cost_per_kg)
            total_bill = weight * cost_per_kg
            amount_paid = float(amount_paid)

            # Check if amount_paid exceeds total_bill
            if amount_paid > total_bill:
                error_message = "Amount paid cannot be greater than the total bill."
                return render_template('navig/enter_records.html', error=error_message)

            # Retrieve date from the form or assign the current date
            record_date = request.form.get('recordDate')
            if not record_date:
                from datetime import datetime
                record_date = datetime.now().strftime('%Y-%m-%d')  # Default to the current date in 'YYYY-MM-DD' format

            # Calculate the due amount (Total bill - Amount paid)
            due = total_bill - amount_paid

            # Insert data into MongoDB with dues and date field
            result = db.sales.insert_one({
                'vendor_name': vendor_name,
                'item_name': item_name,
                'weight': weight,
                'cost_per_kg': cost_per_kg,
                'total_bill': total_bill,
                'amount_paid': amount_paid,
                'due': due,  # Store dues as the difference
                'date': record_date  # Store the date
            })

            # Debugging: Print result of insertion
            print(f"Record inserted with ID: {result.inserted_id}")
            print(f"Connected to database: {db.name}")

            # Redirect to success page
            return redirect(url_for('success'))

        except ValueError as ve:
            error_message = "Invalid input. Please ensure numeric fields are filled correctly."
            print(f"ValueError: {ve}")
            return render_template('navig/enter_records.html', error=error_message)

        except Exception as e:
            error_message = "There was an error processing your form. Please try again."
            print(f"Error occurred: {e}")
            return render_template('navig/enter_records.html', error=error_message)

    # Render the form for GET requests
    return render_template('navig/enter_records.html')



@app.route('/success')
def success():
    return render_template('navig/success.html')


@app.route('/enter_expenditures', methods=['GET', 'POST'])
def enter_expenditures():
    if request.method == 'POST':
        try:
            # Get data from the form
            description = request.form['description']
            amount_spent = float(request.form['amountSpent'])
            record_date = datetime.now().strftime('%Y-%m-%d')  # Capture current date

            # Insert data into the expenditures collection
            result = expenditures_collection.insert_one({
                'description': description,
                'amount_spent': amount_spent,
                'date': record_date,
            })

            # Debugging: Print result of insertion
            print(f"Expenditure inserted with ID: {result.inserted_id}")

            # Redirect to success page or another page
            return redirect(url_for('success'))

        except Exception as e:
            print(f"Error occurred: {e}")
            return render_template('navig/enter_expenditures.html', error="There was an error processing your form. Please try again.")

    return render_template('navig/enter_expenditures.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user_id' in session:
        user = users_collection.find_one({"_id": ObjectId(session['user_id'])})
        return redirect(url_for('home', username=user['username']))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        phone_number = request.form['phone_number']
        email = request.form['email']

        # Debugging output
        print("Form data received:", request.form)
        print(f"Attempting to sign up with username: {username}, email: {email}")

        # Validate email format
        if not validate_email(email):
            flash("Invalid email format.", "error")
            return render_template('signup.html')

        # Validate phone number format
        if not validate_phone_number(phone_number):
            flash("Invalid phone number format. It should be a 10-digit number.", "error")
            return render_template('signup.html')

        # Convert to lowercase for case-insensitive matching
        username = username.lower()
        email = email.lower()

        # Check if username already exists
        print("Checking for existing user by username:", username)
        existing_user_by_username = users_collection.find_one({"username": username})
        print("User found by username:", existing_user_by_username)

        if existing_user_by_username:
            flash("Username already exists. Please choose another.", "error")
            return render_template('signup.html')

        # Check if email already exists
        print("Checking for existing user by email:", email)
        existing_user_by_email = users_collection.find_one({"email": email})
        print("User found by email:", existing_user_by_email)

        if existing_user_by_email:
            flash("Email already exists. Please use another.", "error")
            return render_template('signup.html')

        # Hash password before storing it
        hashed_password = generate_password_hash(password)

        # Create a new user document
        user = {
            "username": username,
            "password": hashed_password,
            "phone_number": phone_number,
            "email": email
        }

        # Insert user into the database
        result = users_collection.insert_one(user)
        print("User inserted with ID:", result.inserted_id)
        print("Users in the database:", list(users_collection.find()))

        flash("User registered successfully!", "success")
        return redirect(url_for('login'))

    return render_template('signup.html')


@app.route('/login', methods=['POST', 'GET'])
def login():
    if 'user_id' in session:
        user = users_collection.find_one({"_id": ObjectId(session['user_id'])})
        print(f"User already logged in: {user}")  # Debug print
        return redirect(url_for('home'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = users_collection.find_one({"email": email})

        if user:
            print(f"User found: {user['email']}")  # Debug print
            print(f"Password in DB: {user['password']}")  # Debug print
            if check_password_hash(user['password'], password):
                flash("Login successful!", "success")
                session.permanent = True
                session['user_id'] = str(user['_id'])
                print(f"User session set: {session['user_id']}")  # Debug print
                return redirect(url_for('home'))
            else:
                flash("Invalid credentials. Please try again.", "error")
        else:
            flash("User not found.", "error")
        
        return render_template('login.html')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

# Validation functions
def validate_email(email):
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(email_regex, email) is not None

def validate_phone_number(phone):
    phone_regex = r'^\d{10}$'
    return re.match(phone_regex, phone) is not None

if __name__ == '__main__':
    app.run(debug=True, port=5001)
