"""
═══════════════════════════════════════════════════════════════════════
  BRONX ULTRA — All-In-One OSINT Platform
  Single file app.py | Render.com Ready
  Telegram: @BRONX_ULTRA
═══════════════════════════════════════════════════════════════════════
"""

import os
import json
import time
import secrets
import requests
from datetime import datetime, timedelta
from functools import wraps
from flask import (
    Flask, request, redirect, url_for,
    session, jsonify, flash, send_file, abort, render_template_string
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ══════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

ADMIN_USER = "bronx"
ADMIN_PASS = "850956"

FAMPAY_API_KEY = "KTSQ8XXAVQMWQMPFML0T"
FAMPAY_BASE = "https://fampay-bronx-opop.onrender.com"

limiter = Limiter(
    get_remote_address, app=app,
    default_limits=["300 per minute"],
    storage_uri="memory://",
)

BANNED_IPS = {}

# ══════════════════════════════════════════════════════════════
#  STORAGE
# ══════════════════════════════════════════════════════════════
def load(name, default=None):
    p = os.path.join(DATA_DIR, f"{name}.json")
    if not os.path.exists(p):
        return default if default is not None else ({} if name == "users" else [])
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else ({} if name == "users" else [])

def save(name, data):
    p = os.path.join(DATA_DIR, f"{name}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def users():        return load("users", {})
def features():     return load("features", [])
def transactions(): return load("transactions", [])
def plans():        return load("plans", [])

# ══════════════════════════════════════════════════════════════
#  DEFAULT DATA
# ══════════════════════════════════════════════════════════════
DEFAULT_PLANS = [
    {"id":"p1",  "days":1,   "price":20,   "limit":10,   "label":"1 Day"},
    {"id":"p5",  "days":5,   "price":100,  "limit":50,   "label":"5 Days"},
    {"id":"p10", "days":10,  "price":200,  "limit":100,  "label":"10 Days"},
    {"id":"p15", "days":15,  "price":300,  "limit":150,  "label":"15 Days"},
    {"id":"p20", "days":20,  "price":400,  "limit":200,  "label":"20 Days"},
    {"id":"p30", "days":30,  "price":500,  "limit":500,  "label":"30 Days"},
    {"id":"p40", "days":40,  "price":700,  "limit":800,  "label":"40 Days"},
    {"id":"p60", "days":60,  "price":1199, "limit":1500, "label":"60 Days"},
    {"id":"p100","days":100, "price":2999, "limit":5000, "label":"100 Days"},
    {"id":"p180","days":180, "price":5999, "limit":-1,   "label":"180 Days (Unlimited)"},
]

DEFAULT_FEATURES = [
    {"id":"f1","name":"Mobile Number Info","icon":"fa-sim-card","api":"https://api.example.com/num={q}","input_label":"Mobile Number","visible":True,"free_limit":0,"prime_only":True},
    {"id":"f2","name":"Aadhaar Lookup","icon":"fa-id-card","api":"https://api.example.com/aadhaar={q}","input_label":"Aadhaar Number","visible":True,"free_limit":0,"prime_only":True},
    {"id":"f3","name":"PAN Card Info","icon":"fa-address-card","api":"https://api.example.com/pan={q}","input_label":"PAN Number","visible":True,"free_limit":0,"prime_only":True},
    {"id":"f4","name":"Vehicle RC","icon":"fa-car-side","api":"https://api.example.com/rc={q}","input_label":"Vehicle Number","visible":True,"free_limit":0,"prime_only":True},
    {"id":"f5","name":"GST Lookup","icon":"fa-file-invoice-dollar","api":"https://api.example.com/gst={q}","input_label":"GST Number","visible":True,"free_limit":0,"prime_only":True},
    {"id":"f6","name":"Pincode Info","icon":"fa-location-dot","api":"https://api.postalpincode.in/pincode/{q}","input_label":"Pincode","visible":True,"free_limit":5,"prime_only":False},
]

for name, data in [("features", DEFAULT_FEATURES), ("plans", DEFAULT_PLANS), ("users", {}), ("transactions", [])]:
    if not os.path.exists(os.path.join(DATA_DIR, f"{name}.json")):
        save(name, data)

# ══════════════════════════════════════════════════════════════
#  AUTH DECORATORS
# ══════════════════════════════════════════════════════════════
def login_required(f):
    @wraps(f)
    def wrapper(*a, **k):
        if "uid" not in session: return redirect(url_for("login_page"))
        if session.get("uid") not in users():
            session.clear(); return redirect(url_for("login_page"))
        return f(*a, **k)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*a, **k):
        if not session.get("admin"): return redirect(url_for("admin_login"))
        return f(*a, **k)
    return wrapper

@app.before_request
def block_banned():
    ip = request.remote_addr or "unknown"
    now = time.time()
    if ip in BANNED_IPS and BANNED_IPS[ip] > now:
        return jsonify({"error": "IP banned. Contact @BRONX_ULTRA on Telegram."}), 403

# ══════════════════════════════════════════════════════════════
#  HELPER: RENDER TEMPLATE (inline)
# ══════════════════════════════════════════════════════════════
def render(tpl, **ctx):
    return render_template_string(tpl, **ctx)

# ══════════════════════════════════════════════════════════════
#  TEMPLATES (INLINE)
# ══════════════════════════════════════════════════════════════

BASE_HEAD = """
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://cdn.tailwindcss.com"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
*{font-family:'Plus Jakarta Sans',sans-serif}
body{background:#0a0e1a;color:#fff;overflow-x:hidden;margin:0}
.bg-grid{position:fixed;inset:0;z-index:-10;background-image:radial-gradient(rgba(77,107,254,0.12) 1px,transparent 1px);background-size:40px 40px}
.glow{position:fixed;width:500px;height:500px;border-radius:50%;filter:blur(120px);opacity:.25;z-index:-9;pointer-events:none}
.glow-1{top:-10%;left:-10%;background:#4D6BFE}.glow-2{bottom:-10%;right:-10%;background:#6B85FF}
.btn-primary{background:linear-gradient(135deg,#4D6BFE,#3A54D6);box-shadow:0 10px 30px -8px rgba(77,107,254,.5);transition:all .3s}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 15px 40px -8px rgba(77,107,254,.7)}
.card{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:16px;backdrop-filter:blur(20px);transition:all .3s}
.card:hover{transform:translateY(-4px);border-color:rgba(77,107,254,.5)}
.input{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.15);color:#fff;outline:none;transition:.2s}
.input:focus{border-color:#4D6BFE;box-shadow:0 0 0 3px rgba(77,107,254,.2)}
.nav-item{transition:.2s;border-left:3px solid transparent}
.nav-item:hover{background:rgba(77,107,254,.15);border-left-color:#4D6BFE}
.nav-item.active{background:rgba(77,107,254,.2);border-left-color:#4D6BFE;color:#6B85FF}
.result-box{background:#000;border:1px solid rgba(255,255,255,.1);border-radius:12px;font-family:'SF Mono',Menlo,Consolas,monospace;white-space:pre-wrap;word-break:break-word;max-height:500px;overflow-y:auto}
::-webkit-scrollbar{width:6px;height:6px}::-webkit-scrollbar-thumb{background:#334155;border-radius:10px}
</style>
<div class="bg-grid"></div>
<div class="glow glow-1"></div>
<div class="glow glow-2"></div>
"""

# ═══════ LANDING ═══════
TPL_LANDING = BASE_HEAD + """
<!DOCTYPE html><html><head><title>BRONX ULTRA — Premium OSINT Portal</title>"""+BASE_HEAD+"""</head>
<body>
<nav class="sticky top-0 z-50 backdrop-blur-xl bg-black/40 border-b border-white/10">
  <div class="max-w-7xl mx-auto px-6 h-20 flex justify-between items-center">
    <div class="flex items-center gap-3">
      <div class="w-12 h-12 rounded-full bg-gradient-to-br from-indigo-500 to-blue-700 flex items-center justify-center shadow-lg">
        <i class="fa-solid fa-bolt text-white text-xl"></i>
      </div>
      <span class="text-2xl font-black">BRONX <span class="text-indigo-400">ULTRA</span></span>
    </div>
    <div class="hidden md:flex gap-8 font-bold text-gray-300">
      <a href="#features" class="hover:text-indigo-400">Features</a>
      <a href="#pricing" class="hover:text-indigo-400">Pricing</a>
      <a href="https://t.me/BRONX_ULTRA" target="_blank" class="hover:text-indigo-400"><i class="fa-brands fa-telegram mr-1"></i>Contact</a>
    </div>
    <div class="flex gap-3">
      <a href="/login" class="px-5 py-2.5 rounded-full font-bold text-gray-300 hover:text-white border border-white/20">Login</a>
      <a href="/register" class="btn-primary px-6 py-2.5 rounded-full font-bold text-white">Register</a>
    </div>
  </div>
</nav>
<section class="max-w-7xl mx-auto px-6 pt-24 pb-16 text-center">
  <div class="inline-block px-5 py-2 bg-indigo-500/20 border border-indigo-500/40 rounded-full mb-8">
    <span class="text-sm font-black text-indigo-300 tracking-widest">⚡ PREMIUM OSINT PLATFORM</span>
  </div>
  <h1 class="text-5xl md:text-7xl font-black leading-tight mb-6">
    Digital Intelligence<br>
    <span class="bg-gradient-to-r from-indigo-400 to-blue-400 bg-clip-text text-transparent">Redefined</span>
  </h1>
  <p class="text-lg md:text-xl text-gray-400 max-w-2xl mx-auto mb-10 font-medium">
    India's most advanced OSINT platform. Mobile, Aadhaar, PAN, Vehicle, GST — get real-time verified data.
  </p>
  <div class="flex flex-col sm:flex-row gap-4 justify-center">
    <a href="/register" class="btn-primary px-10 py-4 rounded-full font-black text-white text-lg">Get Started <i class="fa-solid fa-arrow-right ml-2"></i></a>
    <a href="https://t.me/BRONX_ULTRA" target="_blank" class="px-10 py-4 rounded-full font-black border-2 border-white/20 text-white hover:border-indigo-400 flex items-center justify-center">
      <i class="fa-brands fa-telegram mr-2 text-indigo-400"></i> Join Telegram
    </a>
  </div>
</section>
<section class="max-w-7xl mx-auto px-6 py-16">
  <div class="grid grid-cols-2 md:grid-cols-4 gap-6">
    <div class="card p-6 text-center"><div class="text-4xl font-black text-indigo-400">10K+</div><div class="text-xs text-gray-400 uppercase tracking-widest mt-2">Users</div></div>
    <div class="card p-6 text-center"><div class="text-4xl font-black text-indigo-400">50+</div><div class="text-xs text-gray-400 uppercase tracking-widest mt-2">Services</div></div>
    <div class="card p-6 text-center"><div class="text-4xl font-black text-indigo-400">99.9%</div><div class="text-xs text-gray-400 uppercase tracking-widest mt-2">Uptime</div></div>
    <div class="card p-6 text-center"><div class="text-4xl font-black text-indigo-400">24/7</div><div class="text-xs text-gray-400 uppercase tracking-widest mt-2">Support</div></div>
  </div>
</section>
<section id="features" class="max-w-7xl mx-auto px-6 py-16">
  <div class="text-center mb-12">
    <h2 class="text-4xl font-black mb-3">Powerful Features</h2>
    <p class="text-gray-400">Everything you need in one place</p>
  </div>
  <div class="grid md:grid-cols-3 gap-6">
    {% for f in feats %}
    <div class="card p-8">
      <div class="w-14 h-14 rounded-xl bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center mb-4">
        <i class="fa-solid {{ f.icon }} text-indigo-400 text-2xl"></i>
      </div>
      <h3 class="text-xl font-bold mb-2">{{ f.name }}</h3>
      <p class="text-gray-400 text-sm">{% if f.prime_only %}Prime Only{% else %}Free: {{ f.free_limit }}/day{% endif %}</p>
    </div>
    {% endfor %}
  </div>
</section>
<section class="max-w-4xl mx-auto px-6 py-16">
  <div class="card p-12 text-center relative overflow-hidden">
    <div class="absolute inset-0 bg-gradient-to-r from-indigo-500/20 to-blue-500/20"></div>
    <div class="relative">
      <h2 class="text-4xl font-black mb-4">Start Today</h2>
      <p class="text-gray-300 mb-8">Join thousands of professionals using BRONX ULTRA</p>
      <a href="/register" class="btn-primary inline-block px-10 py-4 rounded-full font-black text-lg">Create Free Account <i class="fa-solid fa-arrow-right ml-2"></i></a>
    </div>
  </div>
</section>
<footer class="border-t border-white/10 py-8 text-center text-gray-500 text-sm">
  <p>&copy; 2026 BRONX ULTRA. All rights reserved.</p>
  <p class="mt-2"><a href="https://t.me/BRONX_ULTRA" class="text-indigo-400 hover:underline"><i class="fa-brands fa-telegram mr-1"></i> @BRONX_ULTRA</a></p>
</footer>
</body></html>
"""

# ═══════ LOGIN ═══════
TPL_LOGIN = "<!DOCTYPE html><html><head><title>Login — BRONX ULTRA</title>"+BASE_HEAD+"</head><body class='min-h-screen flex items-center justify-center p-4'><div class='w-full max-w-md'><div class='text-center mb-8'><div class='inline-flex w-20 h-20 rounded-full bg-gradient-to-br from-indigo-500 to-blue-700 items-center justify-center mb-4'><i class='fa-solid fa-bolt text-3xl'></i></div><h1 class='text-3xl font-black'>BRONX <span class='text-indigo-400'>ULTRA</span></h1></div><div class='card p-8'><h2 class='text-2xl font-black mb-6 text-center'>Welcome Back</h2>{% if error %}<div class='bg-red-500/20 border border-red-500/40 text-red-300 p-3 rounded-lg mb-4 text-sm font-bold'>{{ error }}</div>{% endif %}{% with msgs = get_flashed_messages(with_categories=true) %}{% for cat, m in msgs %}<div class='bg-{{ 'green' if cat=='success' else 'red' }}-500/20 border border-{{ 'green' if cat=='success' else 'red' }}-500/40 p-3 rounded-lg mb-4 text-sm font-bold'>{{ m }}</div>{% endfor %}{% endwith %}<form method='POST' class='space-y-4'><div><label class='block text-sm font-bold text-gray-300 mb-1'>Email or Username</label><input type='text' name='ident' required class='input w-full p-3 rounded-lg'></div><div><label class='block text-sm font-bold text-gray-300 mb-1'>Password (5-12 chars)</label><input type='password' name='password' minlength='5' maxlength='12' required class='input w-full p-3 rounded-lg'></div><button type='submit' class='w-full py-3 rounded-lg bg-gradient-to-r from-indigo-500 to-blue-700 font-black'><i class='fa-solid fa-sign-in-alt mr-2'></i> Login</button></form><p class='text-center text-gray-400 text-sm mt-6'>No account? <a href='/register' class='text-indigo-400 font-bold hover:underline'>Register</a></p><p class='text-center text-gray-500 text-xs mt-4'><a href='https://t.me/BRONX_ULTRA' class='hover:text-indigo-400'><i class='fa-brands fa-telegram mr-1'></i> @BRONX_ULTRA</a></p></div></div></body></html>"

# ═══════ REGISTER ═══════
TPL_REGISTER = "<!DOCTYPE html><html><head><title>Register — BRONX ULTRA</title>"+BASE_HEAD+"</head><body class='min-h-screen flex items-center justify-center p-4 py-10'><div class='w-full max-w-md'><div class='text-center mb-8'><div class='inline-flex w-20 h-20 rounded-full bg-gradient-to-br from-indigo-500 to-blue-700 items-center justify-center mb-4'><i class='fa-solid fa-bolt text-3xl'></i></div><h1 class='text-3xl font-black'>BRONX <span class='text-indigo-400'>ULTRA</span></h1></div><div class='card p-8'><h2 class='text-2xl font-black mb-6 text-center'>Create Account</h2>{% if error %}<div class='bg-red-500/20 border border-red-500/40 text-red-300 p-3 rounded-lg mb-4 text-sm font-bold'>{{ error }}</div>{% endif %}<form method='POST' class='space-y-4'><div><label class='block text-sm font-bold text-gray-300 mb-1'>Full Name</label><input type='text' name='name' required minlength='2' class='input w-full p-3 rounded-lg'></div><div><label class='block text-sm font-bold text-gray-300 mb-1'>Username</label><input type='text' name='username' required minlength='3' class='input w-full p-3 rounded-lg'></div><div><label class='block text-sm font-bold text-gray-300 mb-1'>Email</label><input type='email' name='email' required class='input w-full p-3 rounded-lg'></div><div><label class='block text-sm font-bold text-gray-300 mb-1'>Password (5-12 chars)</label><input type='password' name='password' minlength='5' maxlength='12' required class='input w-full p-3 rounded-lg'></div><button type='submit' class='w-full py-3 rounded-lg bg-gradient-to-r from-indigo-500 to-blue-700 font-black'><i class='fa-solid fa-user-plus mr-2'></i> Register</button></form><p class='text-center text-gray-400 text-sm mt-6'>Already have an account? <a href='/login' class='text-indigo-400 font-bold hover:underline'>Login</a></p><p class='text-center text-gray-500 text-xs mt-4'><a href='https://t.me/BRONX_ULTRA' class='hover:text-indigo-400'><i class='fa-brands fa-telegram mr-1'></i> @BRONX_ULTRA</a></p></div></div></body></html>"

# ═══════ DASHBOARD ═══════
TPL_DASHBOARD = "<!DOCTYPE html><html><head><title>Dashboard — BRONX ULTRA</title>"+BASE_HEAD+"""<style>.sidebar{background:rgba(10,14,26,.95);backdrop-filter:blur(20px);border-right:1px solid rgba(255,255,255,.08)}</style></head>
<body><div class='flex min-h-screen'>
<aside class='sidebar w-64 hidden md:flex flex-col sticky top-0 h-screen'>
<div class='p-6 border-b border-white/10'><div class='flex items-center gap-3'><div class='w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-blue-700 flex items-center justify-center'><i class='fa-solid fa-bolt'></i></div><div><div class='font-black text-lg'>BRONX <span class='text-indigo-400'>ULTRA</span></div><div class='text-[10px] font-black text-indigo-400 uppercase tracking-widest'>OSINT</div></div></div></div>
<nav class='flex-1 py-4 overflow-y-auto'>
<div class='text-[10px] font-black text-gray-500 uppercase tracking-widest px-6 py-2'>Main</div>
<a href='/dashboard' class='nav-item active flex items-center gap-3 px-6 py-3 font-bold'><i class='fa-solid fa-gauge-high w-5'></i> Dashboard</a>
<a href='/history' class='nav-item flex items-center gap-3 px-6 py-3 font-bold'><i class='fa-solid fa-clock-rotate-left w-5'></i> History</a>
<a href='/account' class='nav-item flex items-center gap-3 px-6 py-3 font-bold'><i class='fa-solid fa-user w-5'></i> Account</a>
<div class='text-[10px] font-black text-gray-500 uppercase tracking-widest px-6 py-2 mt-4'>Tools</div>
{% for f in feats %}<a href='/feature/{{ f.id }}' class='nav-item flex items-center gap-3 px-6 py-3 font-bold'><i class='fa-solid {{ f.icon }} w-5'></i> {{ f.name }}</a>{% endfor %}
<div class='text-[10px] font-black text-gray-500 uppercase tracking-widest px-6 py-2 mt-4'>Premium</div>
<a href='/prime' class='nav-item flex items-center gap-3 px-6 py-3 font-bold text-yellow-400'><i class='fa-solid fa-crown w-5'></i> Buy Prime</a>
</nav>
<div class='p-4 border-t border-white/10'><a href='/logout' class='flex items-center justify-center gap-2 w-full py-3 bg-red-500/20 border border-red-500/40 text-red-300 rounded-xl font-bold hover:bg-red-500/30'><i class='fa-solid fa-power-off'></i> Logout</a></div>
</aside>
<main class='flex-1 min-w-0'>
<header class='sticky top-0 z-40 backdrop-blur-xl bg-black/40 border-b border-white/10 p-4 flex justify-between items-center'>
<div><h1 class='text-xl font-black'>Dashboard</h1><p class='text-xs text-gray-400'>{{ now }}</p></div>
<div class='flex items-center gap-3'><a href='/prime' class='px-5 py-2.5 rounded-full bg-gradient-to-r from-yellow-500 to-orange-600 font-black text-white text-sm shadow-lg shadow-yellow-500/30'><i class='fa-solid fa-crown mr-1'></i> Buy Prime</a>
<div class='w-10 h-10 rounded-full bg-indigo-500/30 border border-indigo-500/50 flex items-center justify-center font-black'>{{ user.name[0]|upper }}</div></div>
</header>
<div class='p-6 md:p-8'>
{% if not prime_active %}
<div class='card p-6 mb-6 border-yellow-500/40'><div class='flex items-center gap-4'><i class='fa-solid fa-crown text-3xl text-yellow-400'></i><div class='flex-1'><h3 class='font-black'>You're not a PRIME user</h3><p class='text-sm text-gray-400'>Unlock all premium features with a Prime plan.</p></div><a href='/prime' class='px-5 py-2 rounded-lg bg-gradient-to-r from-yellow-500 to-orange-600 font-black text-sm'>Buy Now</a></div></div>
{% else %}
<div class='card p-6 mb-6 border-green-500/40'><div class='flex items-center gap-4'><i class='fa-solid fa-crown text-3xl text-green-400'></i><div class='flex-1'><h3 class='font-black'>PRIME Active ✓</h3><p class='text-sm text-gray-400'>Expires: {{ user.prime_expires[:10] if user.prime_expires else '-' }} · Used: {{ user.prime_used }} / {{ user.prime_limit if user.prime_limit > 0 else '∞' }}</p></div></div></div>
{% endif %}
<div class='card p-6 mb-6'><h2 class='text-2xl font-black mb-1'>Welcome, {{ user.name }}!</h2><p class='text-gray-400'>Choose a tool to start your lookup</p></div>
<div class='grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4'>
{% for f in feats %}
<a href='/feature/{{ f.id }}' class='card p-6 block'>
<div class='w-14 h-14 rounded-xl bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center mb-4 text-indigo-400'><i class='fa-solid {{ f.icon }} text-2xl'></i></div>
<h3 class='font-black mb-1'>{{ f.name }}</h3>
<p class='text-xs text-gray-400'>{% if f.prime_only %}<i class='fa-solid fa-crown text-yellow-400 mr-1'></i>Prime only{% else %}Free: {{ f.free_limit }}/day{% endif %}</p>
</a>
{% endfor %}
</div>
</div></main></div></body></html>"""

# ═══════ FEATURE ═══════
TPL_FEATURE = "<!DOCTYPE html><html><head><title>{{ feature.name }} — BRONX ULTRA</title>"+BASE_HEAD+"""</head><body class='min-h-screen p-4 md:p-8'><div class='max-w-4xl mx-auto'>
<a href='/dashboard' class='inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-sm font-bold hover:bg-white/10 mb-6'><i class='fa-solid fa-arrow-left'></i> Dashboard</a>
<div class='card p-8 mb-6'>
<div class='flex items-center gap-4 mb-6'><div class='w-16 h-16 rounded-xl bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400'><i class='fa-solid {{ feature.icon }} text-3xl'></i></div><div><h1 class='text-3xl font-black'>{{ feature.name }}</h1><p class='text-sm text-gray-400'>{% if remaining is not none %}Remaining: <b class='text-indigo-400'>{{ remaining }}</b>{% else %}Unlimited{% endif %}</p></div></div>
{% if error %}<div class='bg-red-500/20 border border-red-500/40 text-red-300 p-4 rounded-lg mb-4 font-bold'><i class='fa-solid fa-triangle-exclamation mr-2'></i>{{ error }}</div>{% endif %}
{% if prime_ok %}
<form method='POST' class='space-y-4'>
<div><label class='block text-sm font-black text-indigo-400 uppercase mb-2'>{{ feature.input_label }}</label><input type='text' name='query' required class='input w-full p-4 rounded-xl font-bold' placeholder='Enter {{ feature.input_label }}'></div>
<button type='submit' class='w-full py-4 rounded-xl bg-gradient-to-r from-indigo-500 to-blue-700 font-black text-lg'><i class='fa-solid fa-search mr-2'></i> Lookup</button>
</form>
{% endif %}
</div>
{% if result %}<div class='card p-6'><h3 class='font-black text-indigo-400 mb-3'><i class='fa-solid fa-check-circle mr-2'></i>Result</h3><div class='result-box p-4 text-sm'>{{ result }}</div></div>{% endif %}
</div></body></html>"""

# ═══════ PRIME ═══════
TPL_PRIME = "<!DOCTYPE html><html><head><title>Buy Prime — BRONX ULTRA</title>"+BASE_HEAD+"</head><body class='min-h-screen p-4 md:p-8'><div class='max-w-6xl mx-auto'><a href='/dashboard' class='inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-sm font-bold hover:bg-white/10 mb-6'><i class='fa-solid fa-arrow-left'></i> Dashboard</a><div class='text-center mb-12'><div class='inline-flex w-20 h-20 rounded-full bg-gradient-to-br from-yellow-400 to-orange-600 items-center justify-center mb-4'><i class='fa-solid fa-crown text-4xl text-white'></i></div><h1 class='text-5xl font-black mb-2'>PRIME PLANS</h1><p class='text-gray-400'>Unlock all OSINT features instantly</p></div><div class='grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4'>{% for p in plans %}<div class='card p-6'><div class='flex justify-between items-start mb-4'><div><h3 class='text-2xl font-black'>{{ p.label }}</h3><p class='text-sm text-gray-400'>Limit: {% if p.limit == -1 %}Unlimited{% else %}{{ p.limit }} searches{% endif %}</p></div>{% if p.limit == -1 %}<div class='px-2 py-1 rounded bg-yellow-500 text-black text-[10px] font-black'>UNLIMITED</div>{% endif %}</div><div class='text-4xl font-black text-yellow-400 mb-4'>₹{{ p.price }}</div><a href='/buy-prime/{{ p.id }}' class='block w-full py-3 rounded-xl bg-gradient-to-r from-yellow-500 to-orange-600 font-black text-center'>Buy Now <i class='fa-solid fa-arrow-right ml-1'></i></a></div>{% endfor %}</div></div></body></html>"

# ═══════ ACCOUNT ═══════
TPL_ACCOUNT = "<!DOCTYPE html><html><head><title>Account — BRONX ULTRA</title>"+BASE_HEAD+"</head><body class='min-h-screen p-4 md:p-8'><div class='max-w-4xl mx-auto'><a href='/dashboard' class='inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-sm font-bold hover:bg-white/10 mb-6'><i class='fa-solid fa-arrow-left'></i> Dashboard</a>{% with msgs = get_flashed_messages(with_categories=true) %}{% for cat, m in msgs %}<div class='bg-{{ 'green' if cat=='success' else 'red' }}-500/20 border border-{{ 'green' if cat=='success' else 'red' }}-500/40 p-3 rounded-lg mb-4 text-sm font-bold'>{{ m }}</div>{% endfor %}{% endwith %}<div class='card p-8 mb-6'><h1 class='text-3xl font-black mb-6'>Account Info</h1><div class='grid grid-cols-1 md:grid-cols-2 gap-4'><div><div class='text-xs text-indigo-400 font-black uppercase mb-1'>Name</div><div class='font-bold'>{{ user.name }}</div></div><div><div class='text-xs text-indigo-400 font-black uppercase mb-1'>Username</div><div class='font-bold'>{{ user.username }}</div></div><div><div class='text-xs text-indigo-400 font-black uppercase mb-1'>Email</div><div class='font-bold'>{{ user.email }}</div></div><div><div class='text-xs text-indigo-400 font-black uppercase mb-1'>User ID</div><div class='font-mono text-sm'>{{ user.uid }}</div></div><div><div class='text-xs text-indigo-400 font-black uppercase mb-1'>Device</div><div class='font-bold'>{{ user.device }}</div></div><div><div class='text-xs text-indigo-400 font-black uppercase mb-1'>IP</div><div class='font-mono text-sm'>{{ user.ip }}</div></div></div></div><div class='card p-8 mb-6'><h2 class='text-xl font-black mb-4'>Prime Status</h2>{% if prime_active %}<div class='bg-green-500/20 border border-green-500/40 p-4 rounded-lg'><p class='font-black text-green-400'><i class='fa-solid fa-crown mr-2'></i>PRIME ACTIVE</p><p class='text-sm mt-2'>Expires: <b>{{ user.prime_expires[:19] }}</b></p><p class='text-sm'>Used: <b>{{ user.prime_used }}</b> / <b>{{ '∞' if user.prime_limit == -1 else user.prime_limit }}</b></p></div>{% else %}<div class='bg-yellow-500/20 border border-yellow-500/40 p-4 rounded-lg'><p class='font-black text-yellow-400'>Not Active</p><a href='/prime' class='inline-block mt-2 px-4 py-2 bg-yellow-500 rounded-lg font-bold text-black'>Buy Prime</a></div>{% endif %}</div><div class='card p-8'><h2 class='text-xl font-black mb-4'>Change Password</h2><form method='POST' action='/change-password' class='space-y-3'><input type='password' name='old' placeholder='Old password' required class='input w-full p-3 rounded-lg'><input type='password' name='new' placeholder='New password (5-12)' minlength='5' maxlength='12' required class='input w-full p-3 rounded-lg'><button class='w-full py-3 rounded-lg bg-indigo-500 font-black'>Update Password</button></form></div></div></body></html>"

# ═══════ HISTORY ═══════
TPL_HISTORY = "<!DOCTYPE html><html><head><title>History — BRONX ULTRA</title>"+BASE_HEAD+"</head><body class='min-h-screen p-4 md:p-8'><div class='max-w-4xl mx-auto'><a href='/dashboard' class='inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-sm font-bold hover:bg-white/10 mb-6'><i class='fa-solid fa-arrow-left'></i> Dashboard</a><div class='card p-8'><h1 class='text-3xl font-black mb-6'>Lookup History</h1>{% if history %}<div class='space-y-2'>{% for h in history %}<div class='flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10'><div><div class='font-bold'>{{ h.feature }}</div><div class='text-xs text-gray-400'>Query: {{ h.query }}</div></div><div class='text-xs text-gray-400'>{{ h.time[:16] }}</div></div>{% endfor %}</div>{% else %}<p class='text-gray-400 text-center py-10'>No history yet.</p>{% endif %}</div></div></body></html>"

# ═══════ ADMIN LOGIN ═══════
TPL_ADMIN_LOGIN = "<!DOCTYPE html><html><head><title>Admin — BRONX ULTRA</title>"+BASE_HEAD+"</head><body class='min-h-screen flex items-center justify-center p-4'><div class='w-full max-w-md'><div class='card p-8'><h1 class='text-2xl font-black mb-6 text-center'><i class='fa-solid fa-lock mr-2 text-indigo-400'></i>Admin Access</h1>{% if error %}<div class='bg-red-500/20 border border-red-500/40 text-red-300 p-3 rounded-lg mb-4 text-sm font-bold'>{{ error }}</div>{% endif %}<form method='POST' action='/v3/bronx-server-admin-panel/login' class='space-y-4'><input type='text' name='user' placeholder='Username' required class='input w-full p-3 rounded-lg'><input type='password' name='pass' placeholder='Password' required class='input w-full p-3 rounded-lg'><button class='w-full py-3 rounded-lg bg-gradient-to-r from-indigo-500 to-blue-700 font-black'>Login</button></form></div></div></body></html>"

# ═══════ ADMIN PANEL ═══════
TPL_ADMIN_PANEL = "<!DOCTYPE html><html><head><title>Admin Panel — BRONX ULTRA</title>"+BASE_HEAD+"""</head><body class='min-h-screen p-4 md:p-8'><div class='max-w-7xl mx-auto'>
<div class='flex justify-between items-center mb-6'><h1 class='text-3xl font-black'><i class='fa-solid fa-shield-halved mr-2 text-indigo-400'></i>Admin Panel</h1><a href='/v3/bronx-server-admin-panel/logout' class='px-4 py-2 rounded-lg bg-red-500/20 border border-red-500/40 text-red-300 font-bold text-sm'>Logout</a></div>
{% with msgs = get_flashed_messages(with_categories=true) %}{% for cat, m in msgs %}<div class='bg-{{ 'green' if cat=='success' else 'red' }}-500/20 border border-{{ 'green' if cat=='success' else 'red' }}-500/40 p-3 rounded-lg mb-4 text-sm font-bold'>{{ m }}</div>{% endfor %}{% endwith %}
<div class='grid grid-cols-2 md:grid-cols-4 gap-4 mb-6'>
<div class='card p-5'><div class='text-xs text-gray-400 uppercase font-black mb-1'>Total Users</div><div class='text-3xl font-black text-indigo-400'>{{ stats.users }}</div></div>
<div class='card p-5'><div class='text-xs text-gray-400 uppercase font-black mb-1'>Prime Users</div><div class='text-3xl font-black text-yellow-400'>{{ stats.prime_users }}</div></div>
<div class='card p-5'><div class='text-xs text-gray-400 uppercase font-black mb-1'>Payments</div><div class='text-3xl font-black text-green-400'>{{ stats.total_payments }}</div></div>
<div class='card p-5'><div class='text-xs text-gray-400 uppercase font-black mb-1'>Revenue</div><div class='text-3xl font-black text-green-400'>₹{{ stats.total_revenue }}</div></div>
</div>
<div class='card p-6 mb-6'><h2 class='text-xl font-black mb-4'><i class='fa-solid fa-database mr-2'></i>Backup & Restore</h2><div class='flex flex-wrap gap-3 items-center'><a href='/v3/bronx-server-admin-panel/export' class='px-4 py-2 rounded-lg bg-green-500/20 border border-green-500/40 text-green-300 font-bold text-sm'><i class='fa-solid fa-download mr-1'></i> Export All Data</a><form method='POST' action='/v3/bronx-server-admin-panel/import' enctype='multipart/form-data' class='flex gap-2'><input type='file' name='backup' accept='.json' required class='px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm'><button class='px-4 py-2 rounded-lg bg-blue-500/20 border border-blue-500/40 text-blue-300 font-bold text-sm'><i class='fa-solid fa-upload mr-1'></i> Import</button></form></div></div>
<div class='card p-6 mb-6'><h2 class='text-xl font-black mb-4'><i class='fa-solid fa-bullhorn mr-2'></i>Broadcast Message</h2><form method='POST' action='/v3/bronx-server-admin-panel/broadcast' class='flex gap-2'><input type='text' name='msg' placeholder='Message for all users' required class='input flex-1 p-3 rounded-lg'><button class='px-5 py-3 rounded-lg bg-indigo-500 font-black'>Send</button></form></div>
<div class='card p-6 mb-6'><h2 class='text-xl font-black mb-4'><i class='fa-solid fa-plus mr-2'></i>Add Feature</h2><form method='POST' action='/v3/bronx-server-admin-panel/features/add' class='grid grid-cols-1 md:grid-cols-2 gap-3'><input type='text' name='name' placeholder='Feature Name' required class='input p-3 rounded-lg'><input type='text' name='icon' placeholder='FA icon e.g. fa-star' value='fa-star' class='input p-3 rounded-lg'><input type='text' name='api' placeholder='API URL with {q} placeholder' required class='input p-3 rounded-lg col-span-2'><input type='text' name='input_label' placeholder='Input Label' required class='input p-3 rounded-lg'><input type='number' name='free_limit' placeholder='Free limit' value='0' class='input p-3 rounded-lg'><label class='flex items-center gap-2 text-sm'><input type='checkbox' name='prime_only' class='w-4 h-4'> Prime only</label><button class='md:col-span-2 py-3 rounded-lg bg-indigo-500 font-black'>Add Feature</button></form></div>
<div class='card p-6 mb-6'><h2 class='text-xl font-black mb-4'><i class='fa-solid fa-list mr-2'></i>Manage Features</h2>{% for f in features %}<div class='flex items-center gap-3 p-3 rounded-lg bg-white/5 mb-2'><i class='fa-solid {{ f.icon }} text-indigo-400 w-6'></i><div class='flex-1 min-w-0'><div class='font-bold'>{{ f.name }}</div><div class='text-xs text-gray-400 truncate'>{{ f.api }}</div></div><a href='/v3/bronx-server-admin-panel/features/{{ f.id }}/toggle' class='px-3 py-1 rounded bg-{{ 'green' if f.visible else 'red' }}-500/20 text-{{ 'green' if f.visible else 'red' }}-300 text-xs font-bold'>{{ 'Visible' if f.visible else 'Hidden' }}</a><a href='/v3/bronx-server-admin-panel/features/{{ f.id }}/delete' onclick=\"return confirm('Delete?')\" class='px-3 py-1 rounded bg-red-500/20 text-red-300 text-xs font-bold'>Delete</a></div>{% endfor %}</div>
<div class='card p-6 mb-6'><h2 class='text-xl font-black mb-4'><i class='fa-solid fa-tags mr-2'></i>Price Setup</h2><form method='POST' action='/v3/bronx-server-admin-panel/plans/update'><div class='grid grid-cols-1 md:grid-cols-2 gap-3 mb-3'>{% for p in plans %}<div class='p-3 rounded-lg bg-white/5'><div class='font-bold mb-2'>{{ p.label }}</div><div class='flex gap-2'><input type='number' name='price_{{ p.id }}' value='{{ p.price }}' placeholder='Price' class='input p-2 rounded flex-1 text-sm'><input type='number' name='limit_{{ p.id }}' value='{{ p.limit }}' placeholder='Limit' class='input p-2 rounded flex-1 text-sm'></div></div>{% endfor %}</div><button class='w-full py-3 rounded-lg bg-indigo-500 font-black'>Save Plans</button></form></div>
<div class='card p-6 mb-6'><h2 class='text-xl font-black mb-4'><i class='fa-solid fa-users mr-2'></i>All Users ({{ stats.users }})</h2><div class='overflow-x-auto'><table class='w-full text-sm'><thead class='text-xs uppercase text-gray-400 border-b border-white/10'><tr><th class='p-2 text-left'>User</th><th class='p-2 text-left'>Email</th><th class='p-2 text-left'>Device</th><th class='p-2 text-left'>IP</th><th class='p-2 text-left'>Prime</th><th class='p-2 text-left'>Created</th></tr></thead><tbody>{% for uid, u in users.items() %}<tr class='border-b border-white/5'><td class='p-2 font-bold'>{{ u.username }}</td><td class='p-2 text-gray-400'>{{ u.email }}</td><td class='p-2 text-gray-400 text-xs'>{{ u.device }}</td><td class='p-2 font-mono text-xs'>{{ u.ip }}</td><td class='p-2'>{% if u.prime %}<span class='text-yellow-400 font-bold'>✓</span>{% else %}—{% endif %}</td><td class='p-2 text-xs text-gray-400'>{{ u.created_at[:10] }}</td></tr>{% endfor %}</tbody></table></div></div>
<div class='card p-6'><h2 class='text-xl font-black mb-4'><i class='fa-solid fa-receipt mr-2'></i>Recent Transactions</h2>{% if transactions %}<div class='space-y-2'>{% for t in transactions %}<div class='flex justify-between p-3 rounded-lg bg-white/5 text-sm'><div><div class='font-bold'>{{ t.username }} — {{ t.plan }}</div><div class='text-xs text-gray-400'>{{ t.txn_id or '' }} · {{ t.time[:16] }}</div></div><div class='font-black text-green-400'>₹{{ t.amount }}</div></div>{% endfor %}</div>{% else %}<p class='text-gray-400 text-center py-6'>No transactions yet.</p>{% endif %}</div>
</div></body></html>"""

# ══════════════════════════════════════════════════════════════
#  ROUTES — PUBLIC
# ══════════════════════════════════════════════════════════════
@app.route("/")
def landing():
    return render(TPL_LANDING, feats=[f for f in features() if f.get("visible", True)])

@app.route("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat(), "brand": "BRONX ULTRA"})

# ══════════════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════════════
@app.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def register_page():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        username = request.form.get("username", "").strip().lower()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or len(name) < 2:
            return render(TPL_REGISTER, error="Name required (min 2 chars)")
        if not username or len(username) < 3:
            return render(TPL_REGISTER, error="Username min 3 chars")
        if "@" not in email:
            return render(TPL_REGISTER, error="Valid email required")
        if not (5 <= len(password) <= 12):
            return render(TPL_REGISTER, error="Password 5-12 characters")

        db = users()
        for uid, u in db.items():
            if u["email"] == email:
                return render(TPL_REGISTER, error="Email already registered")
            if u["username"] == username:
                return render(TPL_REGISTER, error="Username taken")

        ua = request.headers.get("User-Agent", "")
        device = "Unknown"
        if "iPhone" in ua: device = "iPhone"
        elif "Android" in ua: device = "Android Mobile"
        elif "iPad" in ua: device = "iPad"
        elif "Windows" in ua: device = "Windows PC"
        elif "Mac" in ua: device = "Mac"
        elif "Linux" in ua: device = "Linux"

        uid = "U" + secrets.token_hex(6).upper()
        db[uid] = {
            "uid": uid, "name": name, "username": username, "email": email,
            "password": generate_password_hash(password),
            "created_at": datetime.now().isoformat(),
            "ip": request.remote_addr, "device": device,
            "user_agent": ua[:300],
            "prime": False, "prime_expires": None,
            "prime_limit": 0, "prime_used": 0,
            "history": []
        }
        save("users", db)
        session["uid"] = uid
        return redirect(url_for("dashboard"))

    return render(TPL_REGISTER)

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login_page():
    if request.method == "POST":
        ident = request.form.get("ident", "").strip().lower()
        password = request.form.get("password", "")

        if not (5 <= len(password) <= 12):
            return render(TPL_LOGIN, error="Password 5-12 chars")

        db = users()
        found = None
        for uid, u in db.items():
            if u["email"] == ident or u["username"] == ident:
                found = u
                break
        if not found or not check_password_hash(found["password"], password):
            return render(TPL_LOGIN, error="Invalid credentials")

        session["uid"] = found["uid"]
        return redirect(url_for("dashboard"))

    return render(TPL_LOGIN)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))

# ══════════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════════
@app.route("/dashboard")
@login_required
def dashboard():
    db = users()
    me = db[session["uid"]]
    feats = [f for f in features() if f.get("visible", True)]

    prime_active = False
    if me.get("prime") and me.get("prime_expires"):
        try:
            if datetime.fromisoformat(me["prime_expires"]) > datetime.now():
                prime_active = True
            else:
                me["prime"] = False
                db[me["uid"]] = me
                save("users", db)
        except Exception:
            pass

    return render(TPL_DASHBOARD, user=me, feats=feats, prime_active=prime_active,
                  now=datetime.now().strftime("%d %b %Y, %I:%M %p"))

# ══════════════════════════════════════════════════════════════
#  FEATURE (with API call)
# ══════════════════════════════════════════════════════════════
@app.route("/feature/<fid>", methods=["GET", "POST"])
@login_required
def feature_page(fid):
    feats = features()
    feat = next((f for f in feats if f["id"] == fid and f.get("visible", True)), None)
    if not feat:
        abort(404)

    db = users()
    me = db[session["uid"]]

    prime_ok = False
    if me.get("prime") and me.get("prime_expires"):
        try:
            prime_ok = datetime.fromisoformat(me["prime_expires"]) > datetime.now()
        except Exception:
            pass

    if feat.get("prime_only") and not prime_ok:
        return render(TPL_FEATURE, feature=feat, user=me, prime_ok=False,
                      error="⛔ This feature requires PRIME. Buy from /prime", remaining=None)

    if prime_ok and me.get("prime_limit", 0) > 0:
        if me.get("prime_used", 0) >= me["prime_limit"]:
            return render(TPL_FEATURE, feature=feat, user=me, prime_ok=True,
                          error="⛔ Usage limit reached. Buy new plan.", remaining=0)

    result = None
    error = None
    remaining = None

    if request.method == "POST":
        query = request.form.get("query", "").strip()
        if not query:
            error = "Enter a value"
        else:
            api_url = feat["api"].replace("{q}", query)
            try:
                r = requests.get(api_url, timeout=25, headers={"Accept": "application/json", "User-Agent": "BRONX-ULTRA"})
                txt = r.text
                try:
                    data = r.json()
                    result = json.dumps(data, indent=2, ensure_ascii=False)
                except Exception:
                    result = txt

                is_error = (
                    not txt.strip()
                    or "not found" in txt.lower()[:200]
                    or "error" in txt.lower()[:100] and len(txt) < 60
                    or r.status_code >= 400
                )

                if not is_error:
                    if me.get("prime_limit", 0) > 0:
                        me["prime_used"] = me.get("prime_used", 0) + 1
                    me.setdefault("history", []).insert(0, {
                        "feature": feat["name"], "query": query,
                        "time": datetime.now().isoformat(), "success": True
                    })
                    me["history"] = me["history"][:50]
                    db[session["uid"]] = me
                    save("users", db)

            except Exception as e:
                error = f"API Error: {str(e)[:200]}"

    if me.get("prime_limit", 0) > 0:
        remaining = max(0, me["prime_limit"] - me.get("prime_used", 0))

    return render(TPL_FEATURE, feature=feat, user=me, prime_ok=prime_ok,
                  result=result, error=error, remaining=remaining)

# ══════════════════════════════════════════════════════════════
#  ACCOUNT & HISTORY
# ══════════════════════════════════════════════════════════════
@app.route("/account")
@login_required
def account():
    me = users()[session["uid"]]
    prime_active = False
    if me.get("prime") and me.get("prime_expires"):
        try:
            prime_active = datetime.fromisoformat(me["prime_expires"]) > datetime.now()
        except Exception:
            pass
    return render(TPL_ACCOUNT, user=me, prime_active=prime_active)

@app.route("/change-password", methods=["POST"])
@login_required
def change_password():
    old = request.form.get("old", "")
    new = request.form.get("new", "")
    if not (5 <= len(new) <= 12):
        flash("New password must be 5-12 characters", "error")
        return redirect(url_for("account"))

    db = users()
    me = db[session["uid"]]
    if not check_password_hash(me["password"], old):
        flash("Old password is wrong", "error")
        return redirect(url_for("account"))

    me["password"] = generate_password_hash(new)
    db[session["uid"]] = me
    save("users", db)
    flash("Password updated successfully", "success")
    return redirect(url_for("account"))

@app.route("/history")
@login_required
def history_page():
    me = users()[session["uid"]]
    return render(TPL_HISTORY, user=me, history=me.get("history", []))

# ══════════════════════════════════════════════════════════════
#  PRIME / PAYMENT
# ══════════════════════════════════════════════════════════════
@app.route("/prime")
@login_required
def prime_page():
    return render(TPL_PRIME, user=users()[session["uid"]], plans=plans())

@app.route("/buy-prime/<pid>")
@login_required
def buy_prime(pid):
    plan = next((p for p in plans() if p["id"] == pid), None)
    if not plan:
        abort(404)
    return redirect(f"{FAMPAY_BASE}/v2/fam/{FAMPAY_API_KEY}?qr={plan['price']}&minutes=30")

@app.route("/verify-prime/<pid>", methods=["POST"])
@login_required
def verify_prime(pid):
    plan = next((p for p in plans() if p["id"] == pid), None)
    if not plan:
        return jsonify({"ok": False, "msg": "Plan not found"})

    order_id = request.json.get("order_id") if request.is_json else None
    if not order_id:
        return jsonify({"ok": False, "msg": "No order_id"})

    try:
        r = requests.get(f"{FAMPAY_BASE}/api/v2/check/{FAMPAY_API_KEY}?order_id={order_id}", timeout=15)
        data = r.json()
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

    if data.get("status") != "PAID":
        return jsonify({"ok": False, "msg": data.get("status", "PENDING")})

    db = users()
    me = db[session["uid"]]
    days = plan["days"]
    expires = datetime.now() + timedelta(days=days)
    me["prime"] = True
    me["prime_expires"] = expires.isoformat()
    me["prime_limit"] = plan["limit"]
    me["prime_used"] = 0
    db[session["uid"]] = me
    save("users", db)

    txs = transactions()
    txs.append({
        "uid": me["uid"], "username": me["username"],
        "plan": plan["label"], "amount": plan["price"],
        "txn_id": data.get("txn_id"), "utr": data.get("utr"),
        "status": "PAID", "time": datetime.now().isoformat()
    })
    save("transactions", txs)

    return jsonify({"ok": True, "msg": "Prime activated", "expires": expires.isoformat()})

# ══════════════════════════════════════════════════════════════
#  ADMIN
# ══════════════════════════════════════════════════════════════
@app.route("/v3/bronx-server-admin-panel")
def admin_login():
    if session.get("admin"):
        return redirect(url_for("admin_panel"))
    return render(TPL_ADMIN_LOGIN)

@app.route("/v3/bronx-server-admin-panel/login", methods=["POST"])
@limiter.limit("5 per minute")
def admin_login_post():
    u = request.form.get("user", "")
    p = request.form.get("pass", "")
    if u == ADMIN_USER and p == ADMIN_PASS:
        session["admin"] = True
        return redirect(url_for("admin_panel"))
    return render(TPL_ADMIN_LOGIN, error="Invalid credentials")

@app.route("/v3/bronx-server-admin-panel/panel")
@admin_required
def admin_panel():
    db = users()
    txs = transactions()
    stats = {
        "users": len(db),
        "prime_users": sum(1 for u in db.values() if u.get("prime")),
        "total_payments": sum(1 for t in txs if t.get("status") == "PAID"),
        "total_revenue": sum(t.get("amount", 0) for t in txs if t.get("status") == "PAID"),
    }
    return render(TPL_ADMIN_PANEL, stats=stats, users=db,
                  features=features(), plans=plans(),
                  transactions=txs[-50:][::-1])

@app.route("/v3/bronx-server-admin-panel/features/add", methods=["POST"])
@admin_required
def admin_add_feature():
    feats = features()
    nid = "f" + secrets.token_hex(4)
    feats.append({
        "id": nid,
        "name": request.form.get("name", "New Feature"),
        "icon": request.form.get("icon", "fa-star"),
        "api": request.form.get("api", ""),
        "input_label": request.form.get("input_label", "Value"),
        "visible": True,
        "free_limit": int(request.form.get("free_limit", 0) or 0),
        "prime_only": request.form.get("prime_only") == "on"
    })
    save("features", feats)
    flash("Feature added", "success")
    return redirect(url_for("admin_panel"))

@app.route("/v3/bronx-server-admin-panel/features/<fid>/toggle")
@admin_required
def admin_toggle_feature(fid):
    feats = features()
    for f in feats:
        if f["id"] == fid:
            f["visible"] = not f.get("visible", True)
            break
    save("features", feats)
    return redirect(url_for("admin_panel"))

@app.route("/v3/bronx-server-admin-panel/features/<fid>/delete")
@admin_required
def admin_delete_feature(fid):
    feats = [f for f in features() if f["id"] != fid]
    save("features", feats)
    flash("Feature deleted", "success")
    return redirect(url_for("admin_panel"))

@app.route("/v3/bronx-server-admin-panel/plans/update", methods=["POST"])
@admin_required
def admin_update_plan():
    pl = plans()
    for p in pl:
        try:
            p["price"] = int(request.form.get(f"price_{p['id']}", p["price"]))
            p["limit"] = int(request.form.get(f"limit_{p['id']}", p["limit"]))
        except Exception:
            pass
    save("plans", pl)
    flash("Plans updated", "success")
    return redirect(url_for("admin_panel"))

@app.route("/v3/bronx-server-admin-panel/export")
@admin_required
def admin_export():
    backup = {
        "users": users(), "features": features(),
        "plans": plans(), "transactions": transactions(),
        "exported_at": datetime.now().isoformat(),
        "brand": "BRONX ULTRA"
    }
    path = os.path.join(DATA_DIR, "backup.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(backup, f, indent=2, ensure_ascii=False)
    return send_file(path, as_attachment=True, download_name=f"bronx_backup_{int(time.time())}.json")

@app.route("/v3/bronx-server-admin-panel/import", methods=["POST"])
@admin_required
def admin_import():
    file = request.files.get("backup")
    if not file:
        flash("No file uploaded", "error")
        return redirect(url_for("admin_panel"))
    try:
        data = json.load(file)
        if "users" in data: save("users", data["users"])
        if "features" in data: save("features", data["features"])
        if "plans" in data: save("plans", data["plans"])
        if "transactions" in data: save("transactions", data["transactions"])
        flash("Data imported successfully", "success")
    except Exception as e:
        flash(f"Import failed: {e}", "error")
    return redirect(url_for("admin_panel"))

@app.route("/v3/bronx-server-admin-panel/broadcast", methods=["POST"])
@admin_required
def admin_broadcast():
    msg = request.form.get("msg", "").strip()
    if msg:
        save("broadcast", {"msg": msg, "time": datetime.now().isoformat()})
        flash("Broadcast saved", "success")
    return redirect(url_for("admin_panel"))

@app.route("/v3/bronx-server-admin-panel/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login"))

# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
