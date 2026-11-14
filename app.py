import os
import json
import requests
import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from user_agents import parse
import time

# ==========================================
# APP & DATABASE CONFIGURATION
# ==========================================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'bronx_ultra_super_secret_key_123'

# Render.com Database setup
db_url = os.environ.get('DATABASE_URL', 'sqlite:///bronx.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ==========================================
# FAMPAY API CONFIGURATION
# ==========================================
FAMPAY_API_KEY = "KTSQ8XXAVQMWQMPFML0T"
FAMPAY_BASE_URL = "https://fampay-bronx-opop.onrender.com"

# ==========================================
# DDOS PROTECTION (Basic In-Memory Rate Limiter)
# ==========================================
ip_requests = {}
BAN_TIME = 300  # 5 minutes ban
MAX_REQUESTS = 60 # Max 60 requests per minute

def check_ddos(ip):
    now = time.time()
    if ip in ip_requests:
        reqs = [t for t in ip_requests[ip] if now - t < 60]
        ip_requests[ip] = reqs
        if len(reqs) > MAX_REQUESTS:
            return False # Banned
    else:
        ip_requests[ip] = []
    ip_requests[ip].append(now)
    return True

@app.before_request
def ddos_protection():
    ip = request.remote_addr
    if not check_ddos(ip):
        return "Access Denied: Too many requests. IP temporarily banned.", 429

# ==========================================
# DATABASE MODELS
# ==========================================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    
    # Hidden Info (Device & IP)
    ip_address = db.Column(db.String(50))
    browser_info = db.Column(db.String(200))
    os_info = db.Column(db.String(100))
    device_type = db.Column(db.String(50))
    
    # Prime Status
    is_prime = db.Column(db.Boolean, default=False)
    prime_expiry = db.Column(db.DateTime, nullable=True)
    prime_limit = db.Column(db.Integer, default=0)
    searches_used = db.Column(db.Integer, default=0)
    prime_plan_name = db.Column(db.String(50))
    
    # History
    history = db.relationship('SearchHistory', backref='user', lazy=True)

class Feature(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(50), default='fa-solid fa-magnifying-glass')
    api_url = db.Column(db.String(255), nullable=False)
    is_visible = db.Column(db.Boolean, default=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    plan_name = db.Column(db.String(50))
    status = db.Column(db.String(20), default='PENDING')
    order_id = db.Column(db.String(100), unique=True)
    utr = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class SearchHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    feature_name = db.Column(db.String(100))
    query = db.Column(db.String(200))
    result = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Broadcast(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# ==========================================
# PRIME PLANS (User Requested)
# ==========================================
PRIME_PLANS = {
    "1":  {"days": 1,  "price": 20,   "limit": 10,   "name": "1 Day Plan"},
    "5":  {"days": 5,  "price": 100,  "limit": 50,   "name": "5 Days Plan"},
    "10": {"days": 10, "price": 200,  "limit": 100,  "name": "10 Days Plan"},
    "15": {"days": 15, "price": 300,  "limit": 150,  "name": "15 Days Plan"},
    "20": {"days": 20, "price": 400,  "limit": 200,  "name": "20 Days Plan"},
    "30": {"days": 30, "price": 500,  "limit": 500,  "name": "30 Days Plan"},
    "40": {"days": 40, "price": 700,  "limit": 800,  "name": "40 Days Plan"},
    "60": {"days": 60, "price": 1199, "limit": 1500, "name": "60 Days Plan"},
    "100":{"days": 100,"price": 2999, "limit": 5000, "name": "100 Days Plan"},
    "180":{"days": 180,"price": 5999, "limit": 999999,"name": "180 Days Plan"}
}

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def get_client_info():
    ua_string = request.headers.get('User-Agent')
    user_agent = parse(ua_string)
    ip = request.remote_addr
    browser = f"{user_agent.browser.family} {user_agent.browser.version_string}"
    os = f"{user_agent.os.family} {user_agent.os.version_string}"
    
    if user_agent.is_mobile: device_type = "Mobile"
    elif user_agent.is_tablet: device_type = "Tablet"
    elif user_agent.is_pc: device_type = "Desktop"
    else: device_type = "Unknown"
        
    return ip, browser, os, device_type

# ==========================================
# USER ROUTES
# ==========================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if len(password) < 5 or len(password) > 12:
            flash('Password must be between 5 and 12 characters.', 'error')
            return redirect(url_for('register'))
            
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('Username or Email already exists.', 'error')
            return redirect(url_for('register'))
            
        ip, browser, os, device_type = get_client_info()
        
        new_user = User(
            name=name, username=username, email=email, password_hash=generate_password_hash(password),
            ip_address=ip, browser_info=browser, os_info=os, device_type=device_type
        )
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier')
        password = request.form.get('password')
        
        user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()
        
        if user and check_password_hash(user.password_hash, password):
            ip, browser, os, device_type = get_client_info()
            user.ip_address = ip
            user.browser_info = browser
            user.os_info = os
            user.device_type = device_type
            db.session.commit()
            
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials.', 'error')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_prime and current_user.prime_expiry and current_user.prime_expiry < datetime.datetime.utcnow():
        current_user.is_prime = False
        db.session.commit()
        
    features = Feature.query.filter_by(is_visible=True).all()
    broadcasts = Broadcast.query.order_by(Broadcast.created_at.desc()).limit(3).all()
    now = datetime.datetime.now()
    return render_template('dashboard.html', features=features, broadcasts=broadcasts, now=now)

@app.route('/account')
@login_required
def account():
    return render_template('account.html', plans=PRIME_PLANS)

@app.route('/history')
@login_required
def history():
    records = SearchHistory.query.filter_by(user_id=current_user.id).order_by(SearchHistory.timestamp.desc()).all()
    return render_template('history.html', records=records)

@app.route('/buy-prime')
@login_required
def buy_prime():
    return render_template('buy_prime.html', plans=PRIME_PLANS)

@app.route('/process-payment/<plan_key>')
@login_required
def process_payment(plan_key):
    if plan_key not in PRIME_PLANS: return redirect(url_for('buy_prime'))
        
    plan = PRIME_PLANS[plan_key]
    order_id = f"ORD{int(datetime.datetime.now().timestamp())}{current_user.id}"
    
    txn = Transaction(user_id=current_user.id, amount=plan['price'], plan_name=plan['name'], order_id=order_id, status='PENDING')
    db.session.add(txn)
    db.session.commit()
    
    payment_url = f"{FAMPAY_BASE_URL}/v2/fam/{FAMPAY_API_KEY}?qr={plan['price']}"
    return render_template('payment.html', plan=plan, plan_key=plan_key, order_id=order_id, payment_url=payment_url)

@app.route('/check-payment/<order_id>')
@login_required
def check_payment(order_id):
    txn = Transaction.query.filter_by(order_id=order_id, user_id=current_user.id).first()
    if not txn: return jsonify({"status": "ERROR"})
    if txn.status == 'PAID': return jsonify({"status": "PAID"})
        
    try:
        # FamPay Auto Check API
        check_url = f"{FAMPAY_BASE_URL}/api/v2/check/{FAMPAY_API_KEY}?order_id={order_id}"
        res = requests.get(check_url, timeout=10).json()
        
        if res.get('status') == 'PAID':
            txn.status = 'PAID'
            txn.utr = res.get('utr')
            
            plan_key = next((k for k, v in PRIME_PLANS.items() if v['price'] == txn.amount and v['name'] == txn.plan_name), None)
            if plan_key:
                plan = PRIME_PLANS[plan_key]
                current_user.is_prime = True
                current_user.prime_expiry = datetime.datetime.utcnow() + datetime.timedelta(days=plan['days'])
                current_user.prime_limit = plan['limit']
                current_user.searches_used = 0
                current_user.prime_plan_name = plan['name']
                
            db.session.commit()
            return jsonify({"status": "PAID"})
        return jsonify({"status": "PENDING"})
    except Exception as e:
        return jsonify({"status": "ERROR", "msg": str(e)})

@app.route('/feature/<int:feature_id>', methods=['GET', 'POST'])
@login_required
def feature(feature_id):
    feat = Feature.query.get_or_404(feature_id)
    
    if not current_user.is_prime or (current_user.prime_expiry and current_user.prime_expiry < datetime.datetime.utcnow()):
        flash('Active Prime subscription required.', 'error')
        return redirect(url_for('buy_prime'))
        
    if current_user.searches_used >= current_user.prime_limit:
        flash('Search limit reached. Please upgrade.', 'error')
        return redirect(url_for('buy_prime'))

    result = None
    error = None
    query = ""
    
    if request.method == 'POST':
        query = request.form.get('query')
        if query:
            api_url = feat.api_url.replace('{p}', query)
            try:
                response = requests.get(api_url, timeout=15)
                # JSON to Text Formatter
                try:
                    data = response.json()
                    result = json.dumps(data, indent=4)
                    if not data or "error" in str(data).lower() or "not found" in str(data).lower():
                        error = "Result not found or API error. (No limit deducted)"
                    else:
                        current_user.searches_used += 1
                        # Save to History
                        hist = SearchHistory(user_id=current_user.id, feature_name=feat.name, query=query, result=result)
                        db.session.add(hist)
                        db.session.commit()
                except ValueError:
                    if response.text:
                        result = response.text
                        current_user.searches_used += 1
                        hist = SearchHistory(user_id=current_user.id, feature_name=feat.name, query=query, result=result)
                        db.session.add(hist)
                        db.session.commit()
                    else:
                        error = "Empty response."
            except Exception as e:
                error = f"Failed to fetch data."

    remaining = current_user.prime_limit - current_user.searches_used if current_user.is_prime else 0
    return render_template('features.html', feature=feat, result=result, error=error, query=query, remaining=remaining)

# ==========================================
# ADMIN PANEL (HIDDEN ENDPOINT)
# ==========================================
ADMIN_USER = "bronx"
ADMIN_PASS = "850956"

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/v3/bronx-server-admin-panel', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USER and request.form.get('password') == ADMIN_PASS:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        flash('Invalid admin credentials', 'error')
    return render_template('admin_login.html')

@app.route('/v3/bronx-server-admin-panel/dashboard')
@admin_required
def admin_dashboard():
    users = User.query.all()
    prime_users = User.query.filter_by(is_prime=True).all()
    return render_template('admin.html', 
        total_users=len(users), total_prime_users=len(prime_users),
        total_txns=Transaction.query.filter_by(status='PAID').count(),
        total_revenue=db.session.query(db.func.sum(Transaction.amount)).filter_by(status='PAID').scalar() or 0,
        features=Feature.query.all(), users_list=users, prime_users=prime_users,
        broadcasts=Broadcast.query.all()
    )

@app.route('/v3/bronx-server-admin-panel/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/v3/bronx-server-admin-panel/add-feature', methods=['POST'])
@admin_required
def add_feature():
    db.session.add(Feature(name=request.form.get('name'), icon=request.form.get('icon'), api_url=request.form.get('api_url')))
    db.session.commit()
    flash('Feature added!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/v3/bronx-server-admin-panel/toggle-feature/<int:id>')
@admin_required
def toggle_feature(id):
    feat = Feature.query.get_or_404(id)
    feat.is_visible = not feat.is_visible
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/v3/bronx-server-admin-panel/delete-feature/<int:id>')
@admin_required
def delete_feature(id):
    db.session.delete(Feature.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/v3/bronx-server-admin-panel/broadcast', methods=['POST'])
@admin_required
def broadcast():
    if request.form.get('message'):
        db.session.add(Broadcast(message=request.form.get('message')))
        db.session.commit()
        flash('Broadcast sent!', 'success')
    return redirect(url_for('admin_dashboard'))

# --- DATA EXPORT / IMPORT ---
@app.route('/v3/bronx-server-admin-panel/export-data')
@admin_required
def export_data():
    data = {
        "users": [{"name": u.name, "username": u.username, "email": u.email, "prime": u.is_prime} for u in User.query.all()],
        "features": [{"name": f.name, "icon": f.icon, "api_url": f.api_url} for f in Feature.query.all()],
    }
    response = make_response(json.dumps(data, indent=4))
    response.headers["Content-Disposition"] = "attachment; filename=bronx_backup.json"
    response.headers["Content-type"] = "application/json"
    return response

@app.route('/v3/bronx-server-admin-panel/import-data', methods=['POST'])
@admin_required
def import_data():
    if 'file' not in request.files: return redirect(url_for('admin_dashboard'))
    file = request.files['file']
    if file.filename == '': return redirect(url_for('admin_dashboard'))
    
    if file:
        data = json.load(file)
        # Note: Simplified import logic for safety. Add try/except in production.
        for f in data.get('features', []):
            if not Feature.query.filter_by(name=f['name']).first():
                db.session.add(Feature(name=f['name'], icon=f['icon'], api_url=f['api_url']))
        db.session.commit()
        flash('Data Imported Successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

# ==========================================
# AUTO-GENERATE TEMPLATES (ALL-IN-ONE)
# ==========================================
def create_templates():
    os.makedirs('templates', exist_ok=True)
    templates = {
        "base.html": """<!DOCTYPE html><html><head><title>BRONX ULTRA</title><script src="https://cdn.tailwindcss.com"></script><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"></head><body class="bg-gray-100 flex h-screen"><div class="w-64 bg-gray-900 text-white flex flex-col"><div class="p-6 text-center border-b border-gray-700"><h1 class="text-2xl font-bold">BRONX ULTRA</h1><p class="text-xs text-gray-400">OSINT</p></div><nav class="flex-1"><a href="/dashboard" class="block p-4 hover:bg-gray-800"><i class="fas fa-home mr-2"></i>Dashboard</a><a href="/account" class="block p-4 hover:bg-gray-800"><i class="fas fa-user mr-2"></i>Account</a><a href="/history" class="block p-4 hover:bg-gray-800"><i class="fas fa-history mr-2"></i>History</a><a href="/buy-prime" class="block p-4 bg-blue-600 hover:bg-blue-700"><i class="fas fa-crown mr-2"></i>BUY PRIME</a></nav><div class="p-4 border-t border-gray-700"><p class="text-sm mb-2">Contact: <a href="https://t.me/BRONX_ULTRA" target="_blank" class="text-blue-400 font-bold">@BRONX_ULTRA</a></p><a href="/logout" class="block text-center bg-red-600 p-2 rounded">Logout</a></div></div><div class="flex-1 flex flex-col h-screen overflow-y-auto"><header class="bg-white shadow p-4"><h2 class="text-xl font-bold">{% block header %}Dashboard{% endblock %}</h2></header><main class="p-6">{% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}{% for c,m in messages %}<div class="p-4 mb-4 rounded {% if c=='error' %}bg-red-100 text-red-700{% else %}bg-green-100 text-green-700{% endif %}">{{ m }}</div>{% endfor %}{% endif %}{% endwith %}{% block content %}{% endblock %}</main></div></body></html>""",
        
        "index.html": """<!DOCTYPE html><html><head><title>BRONX ULTRA</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-gray-900 h-screen flex items-center justify-center text-white"><div class="bg-gray-800 p-8 rounded-xl shadow-2xl text-center max-w-sm w-full"><h1 class="text-4xl font-black mb-2 text-blue-500">BRONX ULTRA</h1><p class="text-gray-400 mb-8">OSINT Platform</p><a href="/login" class="block w-full bg-blue-600 p-3 rounded mb-2 font-bold hover:bg-blue-700">Login</a><a href="/register" class="block w-full bg-gray-700 p-3 rounded font-bold hover:bg-gray-600">Register</a><p class="mt-6 text-sm text-gray-500">Support: <a href="https://t.me/BRONX_ULTRA" class="text-blue-400">@BRONX_ULTRA</a></p></div></body></html>""",
        
        "login.html": """{% extends 'base.html' %}{% block content %}<div class="max-w-md mx-auto bg-white p-8 rounded shadow mt-10"><h2 class="text-2xl font-bold mb-6 text-center">Login</h2><form method="POST"><input type="text" name="identifier" placeholder="Username or Email" required class="w-full p-3 border rounded mb-4"><input type="password" name="password" placeholder="Password" required class="w-full p-3 border rounded mb-4"><button class="w-full bg-blue-600 text-white p-3 rounded font-bold">Login</button></form><p class="text-center mt-4 text-sm">No account? <a href="/register" class="text-blue-600 font-bold">Register</a></p></div>{% endblock %}""",
        
        "register.html": """{% extends 'base.html' %}{% block content %}<div class="max-w-md mx-auto bg-white p-8 rounded shadow mt-10"><h2 class="text-2xl font-bold mb-6 text-center">Register</h2><form method="POST"><input type="text" name="name" placeholder="Full Name" required class="w-full p-3 border rounded mb-4"><input type="text" name="username" placeholder="Username" required class="w-full p-3 border rounded mb-4"><input type="email" name="email" placeholder="Email" required class="w-full p-3 border rounded mb-4"><input type="password" name="password" placeholder="Password (5-12 chars)" required minlength="5" maxlength="12" class="w-full p-3 border rounded mb-4"><button class="w-full bg-green-600 text-white p-3 rounded font-bold">Create Account</button></form></div>{% endblock %}""",
        
        "dashboard.html": """{% extends 'base.html' %}{% block header %}Dashboard{% endblock %}{% block content %}<div class="grid grid-cols-3 gap-4 mb-6"><div class="bg-white p-4 rounded shadow border-l-4 border-blue-500"><p class="text-gray-500 text-sm">Date & Time</p><p class="font-bold">{{ now.strftime('%d %b %Y, %I:%M %p') }}</p></div><div class="bg-white p-4 rounded shadow border-l-4 border-green-500"><p class="text-gray-500 text-sm">Prime Status</p>{% if current_user.is_prime %}<p class="font-bold text-green-600">Active ({{ current_user.prime_plan_name }})</p>{% else %}<p class="font-bold text-red-600">Inactive</p>{% endif %}</div><div class="bg-white p-4 rounded shadow border-l-4 border-purple-500"><p class="text-gray-500 text-sm">Searches Left</p>{% if current_user.is_prime %}<p class="font-bold text-purple-600">{{ current_user.prime_limit - current_user.searches_used }}</p>{% else %}<p class="font-bold text-gray-400">0</p>{% endif %}</div></div>{% if broadcasts %}<div class="bg-yellow-50 p-4 rounded border border-yellow-300 mb-6"><h3 class="font-bold text-yellow-800 mb-2"><i class="fas fa-bullhorn"></i> Announcements</h3><ul>{% for b in broadcasts %}<li>{{ b.message }}</li>{% endfor %}</ul></div>{% endif %}<h3 class="text-xl font-bold mb-4">Premium Lookups</h3><div class="grid grid-cols-4 gap-4">{% for f in features %}<a href="/feature/{{ f.id }}" class="bg-white p-6 rounded shadow text-center hover:shadow-lg transition"><div class="text-blue-600 text-3xl mb-2"><i class="{{ f.icon }}"></i></div><h4 class="font-bold">{{ f.name }}</h4></a>{% endfor %}</div>{% endblock %}""",
        
        "features.html": """{% extends 'base.html' %}{% block header %}{{ feature.name }}{% endblock %}{% block content %}<div class="max-w-3xl mx-auto"><div class="bg-white p-6 rounded shadow mb-6"><h2 class="text-2xl font-bold mb-4"><i class="{{ feature.icon }} text-blue-500"></i> {{ feature.name }}</h2><p class="text-sm font-bold text-blue-600 mb-4">Remaining: {{ remaining }}</p><form method="POST" class="flex gap-2"><input type="text" name="query" value="{{ query }}" required class="flex-1 p-3 border rounded font-mono"><button class="bg-blue-600 text-white px-6 rounded font-bold">Search</button></form></div>{% if error %}<div class="bg-red-100 text-red-700 p-4 rounded mb-6">{{ error }}</div>{% endif %}{% if result %}<div class="bg-gray-900 rounded overflow-hidden"><div class="bg-gray-800 p-2 text-xs text-green-400 font-bold">API RESPONSE</div><pre class="p-6 text-green-400 font-mono text-sm overflow-auto max-h-96">{{ result }}</pre></div>{% endif %}</div>{% endblock %}""",
        
        "buy_prime.html": """{% extends 'base.html' %}{% block header %}Buy Prime{% endblock %}{% block content %}<div class="grid grid-cols-4 gap-4">{% for k, p in plans.items() %}<div class="bg-white p-6 rounded shadow text-center border hover:border-blue-500"><h3 class="font-bold">{{ p.name }}</h3><p class="text-3xl font-black text-blue-600 my-2">₹{{ p.price }}</p><p class="text-sm text-gray-600">{{ p.limit }} Searches</p><p class="text-sm text-gray-600 mb-4">{{ p.days }} Days</p><a href="/process-payment/{{ k }}" class="block bg-blue-600 text-white p-2 rounded">Buy Now</a></div>{% endfor %}</div>{% endblock %}""",
        
        "payment.html": """{% extends 'base.html' %}{% block header %}Payment{% endblock %}{% block content %}<div class="max-w-md mx-auto bg-white p-8 rounded shadow text-center"><h2 class="text-2xl font-bold mb-2">{{ plan.name }}</h2><p class="text-4xl font-black text-blue-600 mb-6">₹{{ plan.price }}</p><div class="mb-6"><a href="{{ payment_url }}" target="_blank" class="bg-blue-600 text-white px-6 py-3 rounded font-bold shadow">Open Payment Page</a></div><div id="status" class="bg-yellow-100 text-yellow-700 p-4 rounded font-bold">Waiting for payment...</div></div><script>setInterval(()=>{fetch('/check-payment/{{ order_id }}').then(r=>r.json()).then(d=>{if(d.status=='PAID'){document.getElementById('status').className='bg-green-100 text-green-700 p-4 rounded font-bold';document.getElementById('status').innerText='Success! Activating...';setTimeout(()=>window.location.href='/dashboard',2000);}})},5000);</script>{% endblock %}""",
        
        "account.html": """{% extends 'base.html' %}{% block header %}Account{% endblock %}{% block content %}<div class="max-w-xl mx-auto bg-white p-8 rounded shadow"><h2 class="text-2xl font-bold mb-4">{{ current_user.username }}</h2><p class="text-gray-600 mb-6">{{ current_user.email }}</p><div class="bg-gray-50 p-4 rounded mb-4 border">{% if current_user.is_prime %}<p class="text-green-600 font-bold">Prime Active ({{ current_user.prime_plan_name }})</p><p class="text-sm">Expires: {{ current_user.prime_expiry.strftime('%d %b %Y') }}</p><p class="text-sm">Usage: {{ current_user.searches_used }}/{{ current_user.prime_limit }}</p>{% else %}<p class="text-red-500 font-bold">No Prime</p>{% endif %}</div><div class="bg-gray-100 p-4 rounded font-mono text-xs text-gray-500"><p>IP: {{ current_user.ip_address }}</p><p>Device: {{ current_user.device_type }}</p><p>OS: {{ current_user.os_info }}</p><p>Browser: {{ current_user.browser_info }}</p></div></div>{% endblock %}""",
        
        "history.html": """{% extends 'base.html' %}{% block header %}History{% endblock %}{% block content %}<div class="bg-white p-6 rounded shadow"><table class="w-full text-left"><tr class="border-b"><th>Feature</th><th>Query</th><th>Date</th></tr>{% for r in records %}<tr class="border-b"><td class="p-2">{{ r.feature_name }}</td><td class="p-2 font-mono">{{ r.query }}</td><td class="p-2 text-sm">{{ r.timestamp.strftime('%d %b, %I:%M %p') }}</td></tr>{% endfor %}</table></div>{% endblock %}""",
        
        "admin_login.html": """<html><head><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-gray-900 flex items-center justify-center h-screen"><form method="POST" class="bg-white p-8 rounded shadow w-80"><h2 class="text-xl font-bold mb-4 text-center">Admin</h2><input type="text" name="username" placeholder="User" required class="w-full p-2 border rounded mb-2"><input type="password" name="password" placeholder="Pass" required class="w-full p-2 border rounded mb-4"><button class="w-full bg-red-600 text-white p-2 rounded">Login</button></form></body></html>""",
        
        "admin.html": """<html><head><script src="https://cdn.tailwindcss.com"></script><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"></head><body class="bg-gray-100"><nav class="bg-gray-900 text-white p-4 flex justify-between"><h1>BRONX ADMIN</h1><a href="/v3/bronx-server-admin-panel/logout" class="text-red-400">Logout</a></nav><div class="p-6"><div class="grid grid-cols-4 gap-4 mb-6"><div class="bg-white p-4 rounded"><p class="text-xs text-gray-500">Users</p><p class="text-xl font-bold">{{ total_users }}</p></div><div class="bg-white p-4 rounded"><p class="text-xs text-gray-500">Prime Users</p><p class="text-xl font-bold text-green-600">{{ total_prime_users }}</p></div><div class="bg-white p-4 rounded"><p class="text-xs text-gray-500">Payments</p><p class="text-xl font-bold">{{ total_txns }}</p></div><div class="bg-white p-4 rounded"><p class="text-xs text-gray-500">Revenue</p><p class="text-xl font-bold text-blue-600">₹{{ total_revenue }}</p></div></div><div class="grid grid-cols-2 gap-4 mb-6"><div class="bg-white p-4 rounded shadow"><h3 class="font-bold mb-2">Add Feature</h3><form action="/v3/bronx-server-admin-panel/add-feature" method="POST"><input name="name" placeholder="Name" required class="w-full p-2 border rounded mb-2"><input name="icon" placeholder="Icon (fa-solid fa-car)" required class="w-full p-2 border rounded mb-2"><input name="api_url" placeholder="URL (http://api.com/num={p})" required class="w-full p-2 border rounded mb-2"><button class="bg-blue-600 text-white p-2 rounded w-full">Add</button></form></div><div class="bg-white p-4 rounded shadow"><h3 class="font-bold mb-2">Broadcast</h3><form action="/v3/bronx-server-admin-panel/broadcast" method="POST"><textarea name="message" required class="w-full p-2 border rounded mb-2"></textarea><button class="bg-yellow-500 text-white p-2 rounded w-full">Send</button></form><div class="mt-4 flex gap-2"><a href="/v3/bronx-server-admin-panel/export-data" class="bg-green-600 text-white p-2 rounded flex-1 text-center">Export Data</a><form action="/v3/bronx-server-admin-panel/import-data" method="POST" enctype="multipart/form-data" class="flex-1 flex gap-1"><input type="file" name="file" accept=".json" class="text-xs w-full border p-1"><button class="bg-purple-600 text-white px-2 rounded">Import</button></form></div></div></div><div class="bg-white p-4 rounded shadow mb-6"><h3 class="font-bold mb-2">Prime Users List</h3><table class="w-full text-left text-sm"><tr class="border-b"><th>Username</th><th>Email</th><th>Plan</th><th>Expiry</th></tr>{% for u in prime_users %}<tr class="border-b"><td>{{ u.username }}</td><td>{{ u.email }}</td><td>{{ u.prime_plan_name }}</td><td>{{ u.prime_expiry.strftime('%d %b %Y') }}</td></tr>{% endfor %}</table></div><div class="bg-white p-4 rounded shadow"><h3 class="font-bold mb-2">Features</h3><table class="w-full text-left text-sm"><tr class="border-b"><th>Name</th><th>URL</th><th>Status</th><th>Actions</th></tr>{% for f in features %}<tr class="border-b"><td class="p-2">{{ f.name }}</td><td class="p-2 font-mono text-xs">{{ f.api_url }}</td><td class="p-2">{% if f.is_visible %}Visible{% else %}Hidden{% endif %}</td><td class="p-2"><a href="/v3/bronx-server-admin-panel/toggle-feature/{{ f.id }}" class="text-blue-600">Toggle</a> | <a href="/v3/bronx-server-admin-panel/delete-feature/{{ f.id }}" class="text-red-600">Delete</a></td></tr>{% endfor %}</table></div></div></body></html>"""
    }
    
    for filename, content in templates.items():
        with open(os.path.join('templates', filename), 'w', encoding='utf-8') as f:
            f.write(content)

# Initialize Database and Templates
with app.app_context():
    create_templates()
    db.create_all()
    if Feature.query.count() == 0:
        db.session.bulk_save_objects([
            Feature(name="Number Info", icon="fa-solid fa-sim-card", api_url="https://api.example.com/num={p}"),
            Feature(name="Aadhar To PAN", icon="fa-solid fa-id-card-clip", api_url="https://api.example.com/aadhar={p}"),
            Feature(name="Vehicle RC", icon="fa-solid fa-car", api_url="https://api.example.com/rc={p}"),
            Feature(name="UPI Info", icon="fa-solid fa-indian-rupee-sign", api_url="https://api.example.com/upi={p}")
        ])
        db.session.commit()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
