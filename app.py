import os
import json
import random
import smtplib
import urllib.parse
from threading import Thread
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS

# ----------------------------------------------------------------------
# Application Setup & Configurations
# ----------------------------------------------------------------------
app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'apascart-render-secret-key-prod-2026')
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'apascart-render-jwt-secret-prod-2026')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=30)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///ecommerce.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# File Paths for CSV Persistence
PRODUCTS_CSV_PATH = 'products.csv'
ORDERS_CSV_PATH = 'orders.csv'
PINCODES_CSV_PATH = 'serviceable_pincodes.csv'
DEMAND_CSV_PATH = 'pincode_demand.csv'

# Merchant UPI Setup
MERCHANT_UPI_VPA = os.environ.get('MERCHANT_UPI_VPA', 'yourupiid@okaxis')
MERCHANT_NAME = os.environ.get('MERCHANT_NAME', 'Apascart')

# SMTP Server Details (Load from Render Environment Variables)
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 465))
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "your-email@gmail.com")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "xxxx xxxx xxxx xxxx")

db = SQLAlchemy(app)
jwt = JWTManager(app)
CORS(app)

OTP_STORE = {}

def now_utc():
    return datetime.now(timezone.utc)

# ----------------------------------------------------------------------
# Pandas CSV Initialization Helpers
# ----------------------------------------------------------------------
def init_products_csv():
    if not os.path.exists(PRODUCTS_CSV_PATH):
        sample_data = [
            {"id": "p1", "name": "Alphonso Mango", "category": "seasonal", "emoji": "🥭", "unit": "1 kg (4-5 pcs)", "mrp": 520, "price": 449, "tag": "Bestseller", "image_url": "/static/images/mango.jpg"},
            {"id": "p2", "name": "Nagpur Orange", "category": "citrus", "emoji": "🍊", "unit": "1 kg", "mrp": 130, "price": 99, "tag": "Fresh", "image_url": "/static/images/orange.jpg"},
            {"id": "p3", "name": "Cavendish Banana", "category": "tropical", "emoji": "🍌", "unit": "6 pcs", "mrp": 60, "price": 49, "tag": "Daily Essential", "image_url": "/static/images/banana.jpg"},
            {"id": "p4", "name": "Kashmiri Apple", "category": "seasonal", "emoji": "🍎", "unit": "1 kg (5-6 pcs)", "mrp": 260, "price": 219, "tag": "Premium", "image_url": "/static/images/apple.jpg"},
            {"id": "p5", "name": "Thai Guava", "category": "tropical", "emoji": "🍐", "unit": "1 kg", "mrp": 110, "price": 89, "tag": "Organic", "image_url": "/static/images/guava.jpg"},
            {"id": "p6", "name": "Kiwi (NZ)", "category": "tropical", "emoji": "🥝", "unit": "4 pcs", "mrp": 199, "price": 159, "tag": "20% OFF", "image_url": "/static/images/kiwi.jpg"},
            {"id": "p7", "name": "Strawberry", "category": "berries", "emoji": "🍓", "unit": "200 g box", "mrp": 120, "price": 99, "tag": "In Season", "image_url": "/static/images/strawberry.jpg"},
            {"id": "p8", "name": "Black Grapes", "category": "berries", "emoji": "🍇", "unit": "500 g", "mrp": 100, "price": 79, "tag": "Fresh", "image_url": "/static/images/grapes.jpg"},
            {"id": "p9", "name": "Sweet Lime (Mosambi)", "category": "citrus", "emoji": "🍋", "unit": "1 kg", "mrp": 90, "price": 69, "tag": "Juicy", "image_url": "/static/images/sweetlime.jpg"},
            {"id": "p10", "name": "Dragon Fruit", "category": "tropical", "emoji": "🐉", "unit": "2 pcs", "mrp": 150, "price": 129, "tag": "Exotic", "image_url": "/static/images/dragonfruit.jpg"},
            {"id": "p11", "name": "Pomegranate", "category": "seasonal", "emoji": "🔴", "unit": "1 kg (3-4 pcs)", "mrp": 220, "price": 189, "tag": "14% OFF", "image_url": "/static/images/pomegranate.jpg"},
            
            # Wholesale Bulk Fruit Boxes
            {"id": "p12", "name": "Hass Avocado Box", "category": "boxes", "emoji": "🥑", "unit": "20 pcs Box", "mrp": 1600, "price": 1300, "tag": "Wholesale Box", "image_url": "/static/images/avocado_box.jpg"},
            {"id": "p13", "name": "Kashmiri Apple Crate", "category": "boxes", "emoji": "🍎", "unit": "120 pcs Bulk Box", "mrp": 3000, "price": 2500, "tag": "Bulk Deal", "image_url": "/static/images/apple_box.jpg"},
            {"id": "p14", "name": "Alphonso Mango Crate", "category": "boxes", "emoji": "🥭", "unit": "24 pcs (5 kg Box)", "mrp": 2400, "price": 1950, "tag": "Farm Bulk Box", "image_url": "/static/images/mango_box.jpg"},
            {"id": "p15", "name": "Nagpur Orange Crate", "category": "boxes", "emoji": "🍊", "unit": "50 pcs (10 kg Box)", "mrp": 1200, "price": 950, "tag": "Wholesale Box", "image_url": "/static/images/orange_box.jpg"},

            # Farm Vegetables
            {"id": "p16", "name": "Fresh Tomatoes", "category": "vegetables", "emoji": "🍅", "unit": "1 kg", "mrp": 40, "price": 28, "tag": "Fresh Veggies", "image_url": "/static/images/tomato.jpg"},
            {"id": "p17", "name": "Potato (Aloo)", "category": "vegetables", "emoji": "🥔", "unit": "1 kg", "mrp": 35, "price": 24, "tag": "Daily Veggies", "image_url": "/static/images/potato.jpg"},
            {"id": "p18", "name": "Onion (Pyaz)", "category": "vegetables", "emoji": "🧅", "unit": "1 kg", "mrp": 45, "price": 32, "tag": "Essential", "image_url": "/static/images/onion.jpg"}
        ]
        df = pd.DataFrame(sample_data)
        df.to_csv(PRODUCTS_CSV_PATH, index=False)

def init_serviceable_pincodes_csv():
    if not os.path.exists(PINCODES_CSV_PATH):
        sample_pins = [
            {"pincode": "500033", "area_name": "Jubilee Hills", "city": "Hyderabad", "is_active": True},
            {"pincode": "500081", "area_name": "Madhapur / HITECH City", "city": "Hyderabad", "is_active": True},
            {"pincode": "500034", "area_name": "Banjara Hills", "city": "Hyderabad", "is_active": True},
            {"pincode": "500084", "area_name": "Kondapur", "city": "Hyderabad", "is_active": True},
            {"pincode": "500032", "area_name": "Gachibowli", "city": "Hyderabad", "is_active": True},
            {"pincode": "500072", "area_name": "Kukatpally", "city": "Hyderabad", "is_active": True}
        ]
        df = pd.DataFrame(sample_pins)
        df.to_csv(PINCODES_CSV_PATH, index=False)

def init_demand_csv():
    if not os.path.exists(DEMAND_CSV_PATH):
        df = pd.DataFrame(columns=['Pincode', 'City', 'Requests_Count', 'Last_Requested'])
        df.to_csv(DEMAND_CSV_PATH, index=False)

def log_unserviceable_pincode(pincode, city='Unknown'):
    try:
        init_demand_csv()
        df = pd.read_csv(DEMAND_CSV_PATH, dtype={'Pincode': str})
        pincode_str = str(pincode).strip()
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if pincode_str in df['Pincode'].values:
            df.loc[df['Pincode'] == pincode_str, 'Requests_Count'] += 1
            df.loc[df['Pincode'] == pincode_str, 'Last_Requested'] = now_str
        else:
            new_row = pd.DataFrame([{
                'Pincode': pincode_str,
                'City': city,
                'Requests_Count': 1,
                'Last_Requested': now_str
            }])
            df = pd.concat([df, new_row], ignore_index=True)
            
        df.to_csv(DEMAND_CSV_PATH, index=False)
    except Exception as e:
        print(f"[Demand Log Error] {e}")

def init_orders_csv():
    if not os.path.exists(ORDERS_CSV_PATH):
        df = pd.DataFrame(columns=[
            'Order Code', 'Payment Transaction ID', 'Order Date', 'Customer Name', 'Customer Phone/Email',
            'Recipient Name', 'Contact Phone', 'Delivery Address', 'City', 'Pincode',
            'Items Breakdown', 'Subtotal (INR)', 'Delivery Fee (INR)', 'Grand Total (INR)',
            'Payment Method', 'Payment Status', 'Order Status'
        ])
        df.to_csv(ORDERS_CSV_PATH, index=False)

def append_order_to_csv(order_data):
    try:
        init_orders_csv()
        df = pd.DataFrame([order_data])
        df.to_csv(ORDERS_CSV_PATH, mode='a', header=False, index=False)
    except Exception as e:
        print(f"[Pandas Error] {e}")

def update_order_payment_in_csv(order_code, payment_tx_id, payment_method, payment_status):
    try:
        if os.path.exists(ORDERS_CSV_PATH):
            df = pd.read_csv(ORDERS_CSV_PATH, dtype={'Order Code': str})
            mask = df['Order Code'] == str(order_code)
            if mask.any():
                df.loc[mask, 'Payment Transaction ID'] = payment_tx_id
                df.loc[mask, 'Payment Method'] = payment_method
                df.loc[mask, 'Payment Status'] = payment_status
                df.to_csv(ORDERS_CSV_PATH, index=False)
    except Exception as e:
        print(f"[CSV Update Error] {e}")

# ----------------------------------------------------------------------
# SMTP Email Dispatcher
# ----------------------------------------------------------------------
def send_email_task(receiver_email, subject, body_html):
    if not receiver_email or "@" not in receiver_email:
        return
    if not SENDER_EMAIL or not SENDER_PASSWORD or "xxxx" in SENDER_PASSWORD:
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = receiver_email
    msg.set_content("Please view this email in an HTML-compatible client.")
    msg.add_alternative(body_html, subtype="html")

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=15) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"[SMTP Error] {e}")

def dispatch_async_email(receiver_email, subject, body_html):
    Thread(target=send_email_task, args=(receiver_email, subject, body_html)).start()

def send_otp_email(recipient_email, otp_code):
    subject = f"{otp_code} is your Apascart verification code"
    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 24px; border: 1px solid #e4e9f6; border-radius: 14px; background-color: #ffffff;">
        <div style="text-align: center; margin-bottom: 20px;">
            <h1 style="color: #1E3A8A; margin: 0; font-size: 26px;">apascart</h1>
            <p style="color: #5E6B8C; font-size: 13px; margin-top: 4px;">Fresh Fruit & Vegetables, Delivered</p>
        </div>
        <p style="color: #131A2E; font-size: 15px;">Hello,</p>
        <p style="color: #5E6B8C; font-size: 14px; line-height: 1.5;">Use the verification code below to complete your login. It is valid for <strong>5 minutes</strong>.</p>
        <div style="text-align: center; margin: 24px 0;">
            <span style="display: inline-block; background-color: #E9EEFB; color: #1E3A8A; font-size: 28px; font-weight: 800; letter-spacing: 6px; padding: 14px 28px; border-radius: 10px; border: 1px dashed #4169E1;">
                {otp_code}
            </span>
        </div>
        <p style="color: #8C98A9; font-size: 12px;">If you did not request this code, you can safely ignore this email.</p>
    </div>
    """
    dispatch_async_email(recipient_email, subject, body_html)

def send_order_receipt_email(user_email, order_code, payment_id, subtotal, delivery_fee, total_amount, items_summary, address, payment_method, payment_status):
    subject = f"Order Confirmation #{order_code} — Apascart"
    
    items_rows = ""
    for item in items_summary:
        items_rows += f"""
        <tr>
            <td style="padding: 8px 0; color: #131A2E; border-bottom: 1px solid #E4E9F6;">
                {item['name']} ({item.get('unit', '')}) &times; {item['qty']}
            </td>
            <td style="padding: 8px 0; color: #131A2E; text-align: right; border-bottom: 1px solid #E4E9F6;">
                ₹{float(item['total']):.2f}
            </td>
        </tr>
        """

    addr_text = f"{address.name}<br>{address.line1}"
    if address.line2:
        addr_text += f", {address.line2}"
    addr_text += f"<br>{address.city} — {address.pin}<br>Phone: {address.phone}"

    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 24px; border: 1px solid #e4e9f6; border-radius: 14px; background-color: #ffffff;">
        <div style="text-align: center; margin-bottom: 20px;">
            <h1 style="color: #1E3A8A; margin: 0; font-size: 26px;">apascart</h1>
            <p style="color: #0E9F6E; font-weight: bold; margin-top: 4px;">✓ Order Placed ({payment_method} - {payment_status})</p>
        </div>
        
        <div style="background-color: #F5F7FC; border-radius: 8px; padding: 12px; margin-bottom: 16px; font-size: 13px;">
            <div><strong>Order ID:</strong> #{order_code}</div>
            <div><strong>Payment / Txn ID:</strong> <span style="font-family: monospace; color: #1E3A8A;">{payment_id}</span></div>
            <div><strong>Status:</strong> <span style="color: #0E9F6E; font-weight: bold;">{payment_status}</span></div>
        </div>

        <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
            <thead>
                <tr style="color: #5E6B8C; font-size: 12px; text-align: left;">
                    <th style="padding-bottom: 8px;">ITEM</th>
                    <th style="padding-bottom: 8px; text-align: right;">PRICE</th>
                </tr>
            </thead>
            <tbody>
                {items_rows}
            </tbody>
        </table>

        <div style="margin-top: 15px; padding-top: 10px; border-top: 2px solid #1E3A8A;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 13px;">
                <span>Subtotal:</span>
                <span>₹{subtotal:.2f}</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 13px;">
                <span>Delivery Fee:</span>
                <span>₹{delivery_fee:.2f}</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-weight: bold; font-size: 16px; color: #1E3A8A; margin-top: 8px;">
                <span>Total Amount:</span>
                <span>₹{total_amount:.2f}</span>
            </div>
        </div>

        <div style="margin-top: 20px; background-color: #F5F7FC; padding: 12px; border-radius: 8px; font-size: 12px; color: #5E6B8C; line-height: 1.4;">
            <strong style="color: #131A2E;">Delivery Address:</strong><br>
            {addr_text}
        </div>
    </div>
    """
    dispatch_async_email(user_email, subject, body_html)

# ----------------------------------------------------------------------
# Database Schema
# ----------------------------------------------------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=True)
    contact_phone = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=now_utc)
    addresses = db.relationship('Address', backref='user', lazy=True, cascade="all, delete-orphan")
    orders = db.relationship('Order', backref='user', lazy=True)

class Address(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    line1 = db.Column(db.Text, nullable=False)
    line2 = db.Column(db.Text, nullable=True)
    city = db.Column(db.String(100), nullable=False)
    pin = db.Column(db.String(10), nullable=False)
    type = db.Column(db.String(20), default='Home')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_code = db.Column(db.String(50), unique=True, nullable=False)
    merchant_transaction_id = db.Column(db.String(100), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    address_id = db.Column(db.Integer, db.ForeignKey('address.id'), nullable=True)
    subtotal = db.Column(db.Float, nullable=False)
    delivery_fee = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), default='ONLINE')
    payment_status = db.Column(db.String(50), default='PENDING')
    order_status = db.Column(db.String(50), default='Order Placed')
    items_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=now_utc)

    address = db.relationship('Address')

# ----------------------------------------------------------------------
# Core API Routes
# ----------------------------------------------------------------------
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/delivery/check-pincode', methods=['POST'])
def check_pincode():
    init_serviceable_pincodes_csv()
    data = request.get_json() or {}
    pincode = str(data.get('pincode', '')).strip()

    if not pincode or len(pincode) != 6:
        return jsonify({"serviceable": False, "message": "Enter a valid 6-digit Pincode"}), 400

    try:
        df = pd.read_csv(PINCODES_CSV_PATH, dtype={'pincode': str})
        match = df[(df['pincode'] == pincode) & (df['is_active'] == True)]
        
        if not match.empty:
            area_name = match.iloc[0]['area_name']
            city = match.iloc[0]['city']
            return jsonify({
                "serviceable": True,
                "pincode": pincode,
                "area_name": area_name,
                "city": city,
                "message": f"Delivery Available in {area_name}, {city}!"
            }), 200
        else:
            log_unserviceable_pincode(pincode, data.get('city', 'Unknown'))
            return jsonify({
                "serviceable": False,
                "pincode": pincode,
                "message": f"Sorry! We do not deliver to Pincode {pincode} yet. Demand noted for expansion."
            }), 200
    except Exception as e:
        return jsonify({"serviceable": False, "message": f"Error checking pincode: {e}"}), 500

@app.route('/api/user/profile', methods=['GET', 'PUT'])
@jwt_required()
def user_profile():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"message": "User not found. Please log in again."}), 401

    if request.method == 'GET':
        return jsonify({
            "id": user.id,
            "email_or_phone": user.phone,
            "name": user.name or "",
            "contact_phone": user.contact_phone or ""
        }), 200

    if request.method == 'PUT':
        data = request.get_json() or {}
        if 'name' in data:
            user.name = data['name'].strip()
        if 'contact_phone' in data:
            user.contact_phone = data['contact_phone'].strip()
        db.session.commit()
        return jsonify({"message": "Profile updated successfully", "name": user.name, "contact_phone": user.contact_phone}), 200

@app.route('/api/orders/my-orders', methods=['GET'])
@jwt_required()
def get_my_orders():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user:
        return jsonify([]), 200

    orders = Order.query.filter_by(user_id=user_id).order_by(Order.created_at.desc()).all()
    out = []
    for o in orders:
        addr = o.address
        addr_str = f"{addr.line1}, {addr.line2 + ', ' if addr.line2 else ''}{addr.city} — {addr.pin}" if addr else "Address Unavailable"
        
        now_dt = datetime.now(timezone.utc)
        order_dt = o.created_at
        if order_dt.tzinfo is None:
            order_dt = order_dt.replace(tzinfo=timezone.utc)
        elapsed_mins = int((now_dt - order_dt).total_seconds() / 60)
        
        status = o.order_status
        if status == 'Order Placed' and elapsed_mins > 5:
            status = 'Packed'
        if elapsed_mins > 15 and status in ['Order Placed', 'Packed']:
            status = 'Out for Delivery'

        out.append({
            "id": o.id,
            "order_code": o.order_code,
            "merchant_transaction_id": o.merchant_transaction_id,
            "date": o.created_at.strftime('%d %b %Y, %I:%M %p'),
            "total_amount": o.total_amount,
            "subtotal": o.subtotal,
            "delivery_fee": o.delivery_fee,
            "payment_method": o.payment_method,
            "payment_status": o.payment_status,
            "order_status": status,
            "items": json.loads(o.items_json) if o.items_json else [],
            "delivery_address": addr_str,
            "recipient_name": addr.name if addr else "",
            "contact_phone": addr.phone if addr else ""
        })
    return jsonify(out), 200

@app.route('/api/auth/send-email-otp', methods=['POST'])
def send_email_otp():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    if not email or '@' not in email:
        return jsonify({"message": "Please provide a valid email address"}), 400

    otp_code = f"{random.randint(100000, 999999)}"
    OTP_STORE[email] = {"otp": otp_code, "expires_at": now_utc() + timedelta(minutes=5)}
    send_otp_email(email, otp_code)
    return jsonify({"success": True, "message": f"Verification code sent to {email}"}), 200

@app.route('/api/auth/verify-email-otp', methods=['POST'])
def verify_email_otp():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    otp_input = data.get('otp', '').strip()

    record = OTP_STORE.get(email)
    if not record or now_utc() > record['expires_at'] or record['otp'] != otp_input:
        return jsonify({"message": "Invalid or expired verification code"}), 400

    del OTP_STORE[email]
    user = User.query.filter_by(phone=email).first()
    if not user:
        derived_name = email.split('@')[0].capitalize()
        user = User(phone=email, name=derived_name)
        db.session.add(user)
        db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify({
        "success": True,
        "token": token,
        "user": {"id": user.id, "phone": user.phone, "name": user.name}
    }), 200

@app.route('/api/products', methods=['GET'])
def get_products():
    init_products_csv()
    try:
        df = pd.read_csv(PRODUCTS_CSV_PATH).fillna('')
        products_list = df.to_dict(orient='records')
        for p in products_list:
            mrp = float(p.get('mrp', 0) or 0)
            price = float(p.get('price', 0) or 0)
            if mrp > price and not p.get('off'):
                p['off'] = f"{int(((mrp - price) / mrp) * 100)}% OFF"
        return jsonify(products_list), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/api/addresses', methods=['GET', 'POST'])
@jwt_required()
def handle_addresses():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"message": "User session expired"}), 401

    if request.method == 'GET':
        addresses = Address.query.filter_by(user_id=user_id).all()
        return jsonify([{
            "id": a.id, "name": a.name, "phone": a.phone,
            "line1": a.line1, "line2": a.line2 or '', "city": a.city, "pin": a.pin, "type": a.type
        } for a in addresses]), 200

    data = request.get_json() or {}
    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    line1 = data.get('line1', '').strip()
    city = data.get('city', '').strip()
    pin = str(data.get('pin', '')).strip()

    if not name or not phone or not line1 or not city or len(pin) != 6:
        return jsonify({"message": "All fields are required and pincode must be 6 digits"}), 400

    addr = Address(
        user_id=user_id,
        name=name,
        phone=phone,
        line1=line1,
        line2=data.get('line2', '').strip(),
        city=city,
        pin=pin,
        type=data.get('type', 'Home')
    )
    db.session.add(addr)
    db.session.commit()

    return jsonify({
        "id": addr.id,
        "name": addr.name,
        "phone": addr.phone,
        "line1": addr.line1,
        "line2": addr.line2,
        "city": addr.city,
        "pin": addr.pin,
        "type": addr.type
    }), 201

@app.route('/api/addresses/<int:addr_id>', methods=['PUT', 'DELETE'])
@jwt_required()
def modify_address(addr_id):
    user_id = int(get_jwt_identity())
    addr = Address.query.filter_by(id=addr_id, user_id=user_id).first()
    if not addr:
        return jsonify({"message": "Address not found"}), 404

    if request.method == 'DELETE':
        db.session.delete(addr)
        db.session.commit()
        return jsonify({"success": True, "message": "Address deleted successfully"}), 200

    if request.method == 'PUT':
        data = request.get_json() or {}
        name = data.get('name', '').strip()
        phone = data.get('phone', '').strip()
        line1 = data.get('line1', '').strip()
        city = data.get('city', '').strip()
        pin = str(data.get('pin', '')).strip()

        if not name or not phone or not line1 or not city or len(pin) != 6:
            return jsonify({"message": "All fields are required and pincode must be 6 digits"}), 400

        addr.name = name
        addr.phone = phone
        addr.line1 = line1
        addr.line2 = data.get('line2', '').strip()
        addr.city = city
        addr.pin = pin
        addr.type = data.get('type', addr.type)
        db.session.commit()

        return jsonify({
            "id": addr.id,
            "name": addr.name,
            "phone": addr.phone,
            "line1": addr.line1,
            "line2": addr.line2,
            "city": addr.city,
            "pin": addr.pin,
            "type": addr.type
        }), 200

@app.route('/api/user/order-status', methods=['GET'])
@jwt_required()
def user_order_status():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"order_count": 0, "cod_eligible": True, "orders_left_for_cod": 2}), 200

    count = Order.query.filter_by(user_id=user_id).count()
    return jsonify({"order_count": count, "cod_eligible": count < 2, "orders_left_for_cod": max(0, 2 - count)}), 200

# 1. CASH ON DELIVERY ORDER PLACEMENT
@app.route('/api/payment/cod', methods=['POST'])
@jwt_required()
def place_cod():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"message": "User session expired. Please log in again."}), 401

    data = request.get_json() or {}
    address_id = data.get('address_id')
    cart_items = data.get('cart', {})

    if not address_id or not cart_items:
        return jsonify({"message": "Address and Cart items are required"}), 400

    shipping_address = db.session.get(Address, int(address_id))
    if not shipping_address:
        return jsonify({"message": "Selected address not found"}), 400
    
    init_serviceable_pincodes_csv()
    df_pins = pd.read_csv(PINCODES_CSV_PATH, dtype={'pincode': str})
    if str(shipping_address.pin).strip() not in df_pins['pincode'].values:
        log_unserviceable_pincode(shipping_address.pin, shipping_address.city)
        return jsonify({"message": f"Cannot deliver to pincode {shipping_address.pin}. Please change address."}), 400

    df_products = pd.read_csv(PRODUCTS_CSV_PATH).set_index('id')
    subtotal = 0.0
    items_list = []
    items_breakdown_csv = []

    for pid, qty in cart_items.items():
        if pid in df_products.index and qty > 0:
            item_row = df_products.loc[pid]
            cost = float(item_row['price']) * qty
            subtotal += cost
            items_list.append({"name": item_row['name'], "qty": qty, "total": cost, "unit": item_row['unit']})
            items_breakdown_csv.append(f"{item_row['name']} x{qty}")

    if subtotal <= 0:
        return jsonify({"message": "Cart is empty"}), 400

    delivery_fee = 0.0 if subtotal >= 499 else 25.0
    grand_total = subtotal + delivery_fee
    
    ts = int(now_utc().timestamp())
    order_code = f"AP-{ts % 1000000:06d}"
    tx_id = f"COD-{ts}-{user_id}"

    new_order = Order(
        order_code=order_code, merchant_transaction_id=tx_id,
        user_id=user_id, address_id=int(address_id), subtotal=subtotal,
        delivery_fee=delivery_fee, total_amount=grand_total, payment_method='Cash on Delivery',
        payment_status='PENDING (COD)', order_status='Order Placed', items_json=json.dumps(items_list)
    )
    db.session.add(new_order)
    db.session.commit()

    append_order_to_csv({
        'Order Code': order_code, 'Payment Transaction ID': tx_id,
        'Order Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'Customer Name': user.name or 'Customer', 'Customer Phone/Email': user.phone,
        'Recipient Name': shipping_address.name, 'Contact Phone': shipping_address.phone,
        'Delivery Address': f"{shipping_address.line1}, {shipping_address.city} - {shipping_address.pin}",
        'City': shipping_address.city, 'Pincode': shipping_address.pin,
        'Items Breakdown': " | ".join(items_breakdown_csv), 'Subtotal (INR)': f"{subtotal:.2f}",
        'Delivery Fee (INR)': f"{delivery_fee:.2f}", 'Grand Total (INR)': f"{grand_total:.2f}",
        'Payment Method': 'Cash on Delivery', 'Payment Status': 'PENDING (COD)', 'Order Status': 'Order Placed'
    })

    if user.phone and "@" in user.phone:
        send_order_receipt_email(
            user.phone, order_code, tx_id, subtotal, delivery_fee, grand_total,
            items_list, shipping_address, "Cash on Delivery", "PENDING (COD)"
        )

    return jsonify({"success": True, "order_code": order_code, "payment_id": tx_id}), 200

# 2. INITIATE PAYMENT INTENT SESSION
@app.route('/api/payment/create-payment-intent', methods=['POST'])
@jwt_required()
def create_payment_intent():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"message": "User session expired"}), 401

    data = request.get_json() or {}
    address_id = data.get('address_id')
    cart_items = data.get('cart', {})
    chosen_app = data.get('app', 'generic')
    order_code_existing = data.get('order_code')

    if not address_id and not order_code_existing:
        return jsonify({"message": "Missing payment context"}), 400

    if order_code_existing:
        order = Order.query.filter_by(order_code=order_code_existing, user_id=user_id).first()
        if not order:
            return jsonify({"message": "Order not found"}), 404
        grand_total = order.total_amount
        order_code = order.order_code
    else:
        df_products = pd.read_csv(PRODUCTS_CSV_PATH).set_index('id')
        subtotal = 0.0
        for pid, qty in cart_items.items():
            if pid in df_products.index and qty > 0:
                subtotal += float(df_products.loc[pid]['price']) * qty
        if subtotal <= 0:
            return jsonify({"message": "Cart is empty"}), 400
        delivery_fee = 0.0 if subtotal >= 499 else 25.0
        grand_total = subtotal + delivery_fee
        order_code = f"AP-{int(now_utc().timestamp()) % 1000000:06d}"

    ts = int(now_utc().timestamp())
    tx_id = f"TXN-{ts}-{user_id}"

    upi_params = urllib.parse.urlencode({
        "pa": MERCHANT_UPI_VPA, "pn": MERCHANT_NAME,
        "tn": f"Order {order_code}", "am": f"{grand_total:.2f}", "cu": "INR", "tr": tx_id
    })
    
    schemes = {'gpay': 'gpay://upi/pay?', 'phonepe': 'phonepe://pay?', 'paytm': 'paytmmp://pay?'}
    intent_url = schemes.get(chosen_app, 'upi://pay?') + upi_params

    return jsonify({
        "success": True,
        "order_code": order_code,
        "payment_id": tx_id,
        "amount": grand_total,
        "intent_url": intent_url
    }), 200

# 3. VERIFY & COMPLETE ONLINE ORDER
@app.route('/api/payment/verify-and-complete', methods=['POST'])
@jwt_required()
def verify_and_complete():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"message": "User session expired"}), 401

    data = request.get_json() or {}
    order_code = data.get('order_code')
    payment_id = data.get('payment_id')
    address_id = data.get('address_id')
    cart_items = data.get('cart', {})
    chosen_app = data.get('app', 'UPI')
    is_cod_conversion = data.get('is_cod_conversion', False)

    if not payment_id or not order_code:
        return jsonify({"message": "Payment details missing"}), 400

    if is_cod_conversion:
        order = Order.query.filter_by(order_code=order_code, user_id=user_id).first()
        if not order:
            return jsonify({"message": "Order not found"}), 404
        
        order.payment_method = f'Online ({chosen_app.upper()})'
        order.payment_status = 'PAID'
        order.merchant_transaction_id = payment_id
        db.session.commit()

        update_order_payment_in_csv(order_code, payment_id, f'Online ({chosen_app.upper()})', 'PAID')

        shipping_address = order.address
        if user.phone and "@" in user.phone:
            send_order_receipt_email(
                user.phone, order.order_code, payment_id, order.subtotal, order.delivery_fee,
                order.total_amount, json.loads(order.items_json), shipping_address,
                f"Online ({chosen_app.upper()})", "PAID"
            )
        return jsonify({"success": True, "order_code": order.order_code, "payment_id": payment_id}), 200

    shipping_address = db.session.get(Address, int(address_id)) if address_id else None
    if not shipping_address:
        return jsonify({"message": "Delivery address missing"}), 400

    df_products = pd.read_csv(PRODUCTS_CSV_PATH).set_index('id')
    subtotal = 0.0
    items_list = []
    items_breakdown_csv = []

    for pid, qty in cart_items.items():
        if pid in df_products.index and qty > 0:
            item_row = df_products.loc[pid]
            cost = float(item_row['price']) * qty
            subtotal += cost
            items_list.append({"name": item_row['name'], "qty": qty, "total": cost, "unit": item_row['unit']})
            items_breakdown_csv.append(f"{item_row['name']} x{qty}")

    delivery_fee = 0.0 if subtotal >= 499 else 25.0
    grand_total = subtotal + delivery_fee

    new_order = Order(
        order_code=order_code, merchant_transaction_id=payment_id,
        user_id=user_id, address_id=int(address_id), subtotal=subtotal,
        delivery_fee=delivery_fee, total_amount=grand_total,
        payment_method=f'Online ({chosen_app.upper()})',
        payment_status='PAID', order_status='Order Placed', items_json=json.dumps(items_list)
    )
    db.session.add(new_order)
    db.session.commit()

    append_order_to_csv({
        'Order Code': order_code, 'Payment Transaction ID': payment_id,
        'Order Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'Customer Name': user.name or 'Customer', 'Customer Phone/Email': user.phone,
        'Recipient Name': shipping_address.name, 'Contact Phone': shipping_address.phone,
        'Delivery Address': f"{shipping_address.line1}, {shipping_address.city} - {shipping_address.pin}",
        'City': shipping_address.city, 'Pincode': shipping_address.pin,
        'Items Breakdown': " | ".join(items_breakdown_csv), 'Subtotal (INR)': f"{subtotal:.2f}",
        'Delivery Fee (INR)': f"{delivery_fee:.2f}", 'Grand Total (INR)': f"{grand_total:.2f}",
        'Payment Method': f'Online ({chosen_app.upper()})', 'Payment Status': 'PAID', 'Order Status': 'Order Placed'
    })

    if user.phone and "@" in user.phone:
        send_order_receipt_email(
            user.phone, order_code, payment_id, subtotal, delivery_fee, grand_total,
            items_list, shipping_address, f"Online ({chosen_app.upper()})", "PAID"
        )

    return jsonify({"success": True, "order_code": order_code, "payment_id": payment_id}), 200

# 4. ADMIN EXPORT APIS
@app.route('/api/admin/export-orders-csv')
def export_orders():
    init_orders_csv()
    return send_file(ORDERS_CSV_PATH, as_attachment=True, download_name="apascart_orders.csv")

@app.route('/api/admin/export-demand-csv')
def export_demand():
    init_demand_csv()
    return send_file(DEMAND_CSV_PATH, as_attachment=True, download_name="apascart_pincode_demand.csv")

# ----------------------------------------------------------------------
# Application Startup & Database Initialization (Runs under Gunicorn & CLI)
# ----------------------------------------------------------------------
with app.app_context():
    db.create_all()
    init_products_csv()
    init_serviceable_pincodes_csv()
    init_demand_csv()
    init_orders_csv()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)