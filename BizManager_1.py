#!/usr/bin/env python3
"""
BizManager v2 — Single file, double-click to run
Requires Python 3.8+  (Flask auto-installed on first run)
"""
import sys, subprocess
def ensure_flask():
    try: import flask
    except ImportError:
        print("Installing Flask (one-time)...")
        subprocess.check_call([sys.executable,"-m","pip","install","flask","--quiet"],
                              stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
        print("Done!")
ensure_flask()

import os,sqlite3,hashlib,hmac,secrets,threading,webbrowser,time
from datetime import datetime,timezone
from functools import wraps
from pathlib import Path
from flask import Flask,request,session,redirect,jsonify,g,make_response
from markupsafe import escape

APP_DIR=Path(__file__).parent
DB_PATH=APP_DIR/"bizmanager.db"
PORT=5000
app=Flask(__name__)
app.secret_key=secrets.token_hex(32)

SCHEMA="""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'employee',
    status TEXT NOT NULL DEFAULT 'active',
    payment_status TEXT NOT NULL DEFAULT 'unpaid',
    position TEXT DEFAULT '',phone TEXT DEFAULT '',created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS invite_codes(
    id INTEGER PRIMARY KEY AUTOINCREMENT,code TEXT UNIQUE NOT NULL,
    owner_id INTEGER NOT NULL,used_by_id INTEGER,label TEXT DEFAULT '',
    is_active INTEGER DEFAULT 1,created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS payment_records(
    id INTEGER PRIMARY KEY AUTOINCREMENT,employee_id INTEGER NOT NULL,
    amount REAL NOT NULL,currency TEXT DEFAULT 'USD',period TEXT DEFAULT '',
    method TEXT DEFAULT '',reference TEXT DEFAULT '',notes TEXT DEFAULT '',
    paid_on TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notes(
    id INTEGER PRIMARY KEY AUTOINCREMENT,employee_id INTEGER NOT NULL,
    author_id INTEGER NOT NULL,content TEXT NOT NULL,created_at TEXT NOT NULL
);
"""

def init_db():
    with sqlite3.connect(str(DB_PATH)) as db:
        db.executescript(SCHEMA);db.commit()

def get_db():
    if "db" not in g:
        g.db=sqlite3.connect(str(DB_PATH))
        g.db.row_factory=sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db=g.pop("db",None)
    if db:db.close()

def q(sql,args=(),one=False):
    cur=get_db().execute(sql,args);rv=cur.fetchall()
    return (rv[0] if rv else None) if one else rv

def m(sql,args=()):
    db=get_db();cur=db.execute(sql,args);db.commit();return cur.lastrowid

def now(): return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
def fdate(s):
    try:return datetime.strptime(str(s)[:10],"%Y-%m-%d").strftime("%b %d, %Y")
    except:return str(s)

def hash_pw(pw):
    salt=secrets.token_hex(16)
    h=hashlib.pbkdf2_hmac("sha256",pw.encode(),salt.encode(),260000)
    return f"{salt}:{h.hex()}"

def check_pw(pw,stored):
    try:
        salt,hx=stored.split(":",1)
        h=hashlib.pbkdf2_hmac("sha256",pw.encode(),salt.encode(),260000)
        return hmac.compare_digest(h.hex(),hx)
    except:return False

def me(): uid=session.get("user_id"); return q("SELECT * FROM users WHERE id=?",[uid],one=True) if uid else None
def initials(n): p=n.strip().split(); return (p[0][0]+p[-1][0]).upper() if len(p)>=2 else n[:2].upper()

def login_required(f):
    @wraps(f)
    def d(*a,**k):
        if not session.get("user_id"):return redir("/login")
        return f(*a,**k)
    return d

def owner_req(f):
    @wraps(f)
    def d(*a,**k):
        u=me()
        if not u or u["role"]!="owner":return redir("/login")
        return f(*a,**k)
    return d

def redir(url,code=302):
    r=make_response("",code);r.headers["Location"]=url;return r

def flash(msg,cat="info"):
    session.setdefault("_f",[]).append({"m":msg,"c":cat})

def flash_html():
    msgs=session.pop("_f",[])
    icons={"success":"✓","danger":"✕","info":"ℹ","warning":"⚠"}
    return "".join(f'<div class="alert alert-{x["c"]}">{icons.get(x["c"],"ℹ")} {escape(x["m"])}</div>' for x in msgs)

CSS = """

:root{
  --blue-50:#EFF6FF;--blue-100:#DBEAFE;--blue-200:#BFDBFE;--blue-300:#93C5FD;
  --blue-400:#60A5FA;--blue-500:#3B82F6;--blue-600:#2563EB;--blue-700:#1D4ED8;
  --blue-800:#1E40AF;--blue-900:#1E3A8A;
  --white:#fff;--gray-50:#F8FAFC;--gray-100:#F1F5F9;--gray-200:#E2E8F0;
  --gray-300:#CBD5E1;--gray-400:#94A3B8;--gray-500:#64748B;--gray-700:#334155;--gray-900:#0F172A;
  --success:#10B981;--warning:#F59E0B;--danger:#EF4444;
  --sidebar-w:250px;--r-sm:8px;--r-md:14px;--r-lg:20px;
  --tr:0.2s ease;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
html{scroll-behavior:smooth;}

/* ─── BACKGROUND ─────────────────────────────────── */
body{
  font-family:'Inter',system-ui,sans-serif;font-size:15px;color:var(--gray-700);
  min-height:100vh;
  background:#e8f0fe;
  background-image:
    radial-gradient(ellipse 80% 60% at 10% -10%, rgba(147,197,253,0.55) 0%, transparent 60%),
    radial-gradient(ellipse 60% 50% at 90% 110%, rgba(96,165,250,0.4) 0%, transparent 55%),
    radial-gradient(ellipse 50% 40% at 50% 50%, rgba(219,234,254,0.6) 0%, transparent 70%);
  background-attachment:fixed;
}

/* ─── GLASS COMPONENTS ───────────────────────────── */
.glass{
  background:rgba(255,255,255,0.78);
  backdrop-filter:blur(24px) saturate(180%);
  -webkit-backdrop-filter:blur(24px) saturate(180%);
  border:1px solid rgba(255,255,255,0.65);
  border-radius:var(--r-lg);
  box-shadow:0 4px 24px rgba(37,99,235,0.08),0 1px 4px rgba(37,99,235,0.05),inset 0 1px 0 rgba(255,255,255,0.8);
}
.glass:hover{
  box-shadow:0 8px 32px rgba(37,99,235,0.12),0 2px 8px rgba(37,99,235,0.06),inset 0 1px 0 rgba(255,255,255,0.9);
}

/* ─── SIDEBAR ─────────────────────────────────────── */
.sidebar{
  width:var(--sidebar-w);min-height:100vh;position:fixed;top:0;left:0;bottom:0;
  z-index:100;padding:20px 14px;display:flex;flex-direction:column;
  background:linear-gradient(180deg,#1e3a8a 0%,#1d4ed8 40%,#2563eb 100%);
  box-shadow:4px 0 24px rgba(30,58,138,0.25);
  transition:transform var(--tr);
}

.sidebar-brand{
  display:flex;align-items:center;gap:11px;padding:6px 10px 24px;text-decoration:none;
}
.brand-icon{
  width:38px;height:38px;border-radius:10px;
  background:rgba(255,255,255,0.2);
  border:1px solid rgba(255,255,255,0.3);
  display:flex;align-items:center;justify-content:center;
  color:white;font-size:18px;flex-shrink:0;
  box-shadow:0 2px 8px rgba(0,0,0,0.15);
}
.brand-icon svg{width:20px;height:20px;fill:white;}
.sidebar-brand span{font-size:17px;font-weight:800;color:white;letter-spacing:-0.3px;}

.sidebar-nav{flex:1;display:flex;flex-direction:column;gap:3px;}
.nav-section-label{
  font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;
  color:rgba(255,255,255,0.4);padding:12px 10px 6px;
}
.nav-link{
  display:flex;align-items:center;gap:10px;padding:10px 12px;
  border-radius:10px;text-decoration:none;color:rgba(255,255,255,0.65);
  font-weight:500;font-size:14px;transition:all var(--tr);
}
.nav-link:hover,.nav-link.active{background:rgba(255,255,255,0.15);color:white;}
.nav-link.active{background:rgba(255,255,255,0.2);color:white;font-weight:600;
  box-shadow:inset 0 1px 0 rgba(255,255,255,0.15);}
.nav-link svg{width:16px;height:16px;fill:currentColor;flex-shrink:0;}

.sidebar-footer{
  padding-top:14px;border-top:1px solid rgba(255,255,255,0.12);margin-top:10px;
}
.user-chip{
  display:flex;align-items:center;gap:10px;padding:8px 10px;margin-bottom:8px;
  background:rgba(255,255,255,0.1);border-radius:10px;
  border:1px solid rgba(255,255,255,0.15);
}
.user-avatar{
  width:34px;height:34px;border-radius:50%;
  background:rgba(255,255,255,0.25);
  display:flex;align-items:center;justify-content:center;
  font-weight:700;font-size:12px;color:white;flex-shrink:0;
  border:1.5px solid rgba(255,255,255,0.35);
}
.user-chip-name{font-size:13px;font-weight:600;color:white;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.user-chip-role{font-size:11px;color:rgba(255,255,255,0.5);}

/* ─── LAYOUT ──────────────────────────────────────── */
.app-wrapper{display:flex;min-height:100vh;position:relative;}
.main-content{margin-left:var(--sidebar-w);flex:1;padding:28px 32px;min-height:100vh;}

/* ─── TOPBAR ──────────────────────────────────────── */
.topbar{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:28px;gap:16px;}
.page-title{font-size:26px;font-weight:800;color:var(--gray-900);letter-spacing:-0.5px;line-height:1.2;}
.page-subtitle{font-size:13px;color:var(--gray-400);margin-top:3px;}
.topbar-actions{display:flex;align-items:center;gap:10px;flex-shrink:0;}

/* ─── STAT CARDS ──────────────────────────────────── */
.stats-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px;}
.stat-card{
  padding:22px 22px 20px;
  background:rgba(255,255,255,0.82);
  backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
  border:1px solid rgba(255,255,255,0.7);
  border-radius:var(--r-lg);
  box-shadow:0 2px 16px rgba(37,99,235,0.07),inset 0 1px 0 rgba(255,255,255,0.9);
  transition:all var(--tr);
}
.stat-card:hover{transform:translateY(-2px);box-shadow:0 8px 28px rgba(37,99,235,0.12);}
.stat-icon{
  width:42px;height:42px;border-radius:11px;
  display:flex;align-items:center;justify-content:center;margin-bottom:14px;
}
.stat-icon svg{width:21px;height:21px;}
.stat-icon.blue{background:linear-gradient(135deg,rgba(59,130,246,0.15),rgba(37,99,235,0.08));color:var(--blue-600);}
.stat-icon.blue svg{fill:var(--blue-600);}
.stat-icon.green{background:linear-gradient(135deg,rgba(16,185,129,0.15),rgba(5,150,105,0.08));color:#059669;}
.stat-icon.green svg{fill:#059669;}
.stat-icon.orange{background:linear-gradient(135deg,rgba(245,158,11,0.15),rgba(217,119,6,0.08));color:#D97706;}
.stat-icon.orange svg{fill:#D97706;}
.stat-icon.purple{background:linear-gradient(135deg,rgba(139,92,246,0.15),rgba(109,40,217,0.08));color:#7C3AED;}
.stat-icon.purple svg{fill:#7C3AED;}
.stat-value{font-size:34px;font-weight:800;color:var(--gray-900);letter-spacing:-1.5px;line-height:1;}
.stat-label{font-size:12px;color:var(--gray-400);margin-top:4px;font-weight:500;letter-spacing:0.2px;}

/* ─── BUTTONS ─────────────────────────────────────── */
.btn{
  display:inline-flex;align-items:center;gap:7px;padding:9px 18px;
  border-radius:var(--r-sm);font-size:14px;font-weight:600;cursor:pointer;
  text-decoration:none;border:none;transition:all var(--tr);white-space:nowrap;
  font-family:inherit;line-height:1.4;
}
.btn:active{transform:scale(0.97);}
.btn svg{width:15px;height:15px;fill:currentColor;flex-shrink:0;}

.btn-primary{
  background:linear-gradient(135deg,var(--blue-500),var(--blue-700));color:white;
  box-shadow:0 2px 12px rgba(37,99,235,0.35);
}
.btn-primary:hover{box-shadow:0 4px 20px rgba(37,99,235,0.5);transform:translateY(-1px);color:white;}

.btn-secondary{
  background:rgba(59,130,246,0.08);color:var(--blue-700);
  border:1.5px solid rgba(59,130,246,0.2);
}
.btn-secondary:hover{background:rgba(59,130,246,0.14);border-color:rgba(59,130,246,0.35);}

.btn-ghost{
  background:rgba(255,255,255,0.8);color:var(--gray-500);
  border:1.5px solid var(--gray-200);
  box-shadow:0 1px 4px rgba(0,0,0,0.06);
}
.btn-ghost:hover{background:white;border-color:var(--gray-300);color:var(--gray-800);}

.btn-danger{background:rgba(239,68,68,0.08);color:var(--danger);border:1.5px solid rgba(239,68,68,0.2);}
.btn-danger:hover{background:var(--danger);color:white;}

.btn-success{background:linear-gradient(135deg,#10B981,#059669);color:white;
  box-shadow:0 2px 12px rgba(16,185,129,0.3);}
.btn-success:hover{box-shadow:0 4px 20px rgba(16,185,129,0.45);transform:translateY(-1px);}

.btn-sm{padding:6px 13px;font-size:12px;}
.btn-lg{padding:12px 26px;font-size:16px;}
.btn-icon{padding:8px;aspect-ratio:1;border-radius:var(--r-sm);}
.w-100{width:100%;}

/* ─── FORMS ───────────────────────────────────────── */
.form-group{margin-bottom:16px;}
.form-label{display:block;font-size:13px;font-weight:600;color:var(--gray-700);margin-bottom:5px;}
.form-control{
  width:100%;padding:10px 13px;
  background:rgba(255,255,255,0.9);
  border:1.5px solid var(--gray-200);border-radius:var(--r-sm);
  font-size:14px;color:var(--gray-900);outline:none;
  transition:all var(--tr);font-family:inherit;
}
.form-control:focus{
  border-color:var(--blue-400);
  box-shadow:0 0 0 3px rgba(59,130,246,0.12);
  background:white;
}
.form-control::placeholder{color:var(--gray-400);}
.form-control:disabled{opacity:0.5;cursor:not-allowed;background:var(--gray-50);}
select.form-control{cursor:pointer;}
textarea.form-control{resize:vertical;min-height:88px;}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:14px;}
.form-hint{font-size:11px;color:var(--gray-400);margin-top:4px;}

/* ─── CARDS ───────────────────────────────────────── */
.card{
  background:rgba(255,255,255,0.82);
  backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
  border:1px solid rgba(255,255,255,0.7);
  border-radius:var(--r-lg);
  box-shadow:0 2px 16px rgba(37,99,235,0.07),inset 0 1px 0 rgba(255,255,255,0.9);
  padding:22px;
}
.card-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;}
.card-title{font-size:15px;font-weight:700;color:var(--gray-900);display:flex;align-items:center;gap:7px;}
.card-title svg{width:16px;height:16px;fill:var(--blue-500);}
.card-subtitle{font-size:12px;color:var(--gray-400);margin-top:2px;}

/* ─── TABLES ──────────────────────────────────────── */
.table-wrap{overflow-x:auto;margin:0 -4px;}
table{width:100%;border-collapse:collapse;}
thead th{
  padding:10px 14px;font-size:10.5px;font-weight:700;
  text-transform:uppercase;letter-spacing:0.8px;color:var(--gray-400);
  background:rgba(248,250,252,0.8);text-align:left;
}
thead th:first-child{border-radius:8px 0 0 8px;}
thead th:last-child{border-radius:0 8px 8px 0;}
tbody tr{border-bottom:1px solid rgba(226,232,240,0.7);transition:background var(--tr);}
tbody tr:hover{background:rgba(59,130,246,0.03);}
tbody tr:last-child{border-bottom:none;}
tbody td{padding:13px 14px;font-size:13.5px;vertical-align:middle;}

/* ─── BADGES ──────────────────────────────────────── */
.badge{
  display:inline-flex;align-items:center;gap:5px;padding:3px 10px;
  border-radius:20px;font-size:11px;font-weight:700;
  letter-spacing:0.3px;text-transform:capitalize;
}
.badge::before{content:"●";font-size:7px;}
.badge-active{background:rgba(16,185,129,0.1);color:#059669;border:1px solid rgba(16,185,129,0.2);}
.badge-inactive{background:rgba(100,116,139,0.1);color:var(--gray-500);border:1px solid rgba(100,116,139,0.2);}
.badge-suspended{background:rgba(239,68,68,0.1);color:var(--danger);border:1px solid rgba(239,68,68,0.2);}
.badge-paid{background:rgba(16,185,129,0.1);color:#059669;border:1px solid rgba(16,185,129,0.2);}
.badge-unpaid{background:rgba(245,158,11,0.1);color:#D97706;border:1px solid rgba(245,158,11,0.2);}
.badge-owner{background:rgba(139,92,246,0.1);color:#7C3AED;border:1px solid rgba(139,92,246,0.2);}
.badge-employee{background:rgba(59,130,246,0.1);color:var(--blue-600);border:1px solid rgba(59,130,246,0.2);}

/* ─── ALERTS ──────────────────────────────────────── */
.alert{
  padding:12px 16px;border-radius:var(--r-md);font-size:13.5px;font-weight:500;
  display:flex;align-items:flex-start;gap:9px;margin-bottom:18px;
  animation:fadeDown 0.3s ease;
}
@keyframes fadeDown{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}
.alert-success{background:rgba(16,185,129,0.1);color:#065F46;border:1px solid rgba(16,185,129,0.25);}
.alert-danger{background:rgba(239,68,68,0.1);color:#991B1B;border:1px solid rgba(239,68,68,0.25);}
.alert-info{background:rgba(59,130,246,0.1);color:#1E40AF;border:1px solid rgba(59,130,246,0.25);}
.alert-warning{background:rgba(245,158,11,0.1);color:#92400E;border:1px solid rgba(245,158,11,0.25);}

/* ─── EMPLOYEE CARDS ──────────────────────────────── */
.employee-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:16px;}
.emp-card{
  padding:20px;text-decoration:none;display:block;color:inherit;
  background:rgba(255,255,255,0.82);
  backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
  border:1px solid rgba(255,255,255,0.7);border-radius:var(--r-lg);
  box-shadow:0 2px 16px rgba(37,99,235,0.07);
  transition:all var(--tr);
}
.emp-card:hover{transform:translateY(-3px);box-shadow:0 10px 32px rgba(37,99,235,0.14);border-color:rgba(59,130,246,0.2);}
.emp-card-top{display:flex;align-items:center;gap:13px;margin-bottom:14px;}
.emp-avatar{
  width:46px;height:46px;border-radius:50%;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;
  font-size:15px;font-weight:800;color:white;
  background:linear-gradient(135deg,var(--blue-400),var(--blue-700));
  box-shadow:0 3px 10px rgba(37,99,235,0.3);
}
.emp-name{font-size:14px;font-weight:700;color:var(--gray-900);}
.emp-pos{font-size:12px;color:var(--gray-400);margin-top:2px;}
.emp-badges{display:flex;gap:7px;flex-wrap:wrap;}

/* ─── INVITE CODE ─────────────────────────────────── */
.code-pill{
  display:inline-block;font-family:monospace;font-size:15px;font-weight:800;
  letter-spacing:3px;color:var(--blue-700);
  background:linear-gradient(135deg,rgba(59,130,246,0.08),rgba(37,99,235,0.04));
  border:1.5px dashed rgba(59,130,246,0.35);
  border-radius:10px;padding:9px 16px;
  cursor:copy;transition:all var(--tr);user-select:all;
}
.code-pill:hover{background:rgba(59,130,246,0.12);border-color:var(--blue-400);}

/* ─── SEARCH BAR ──────────────────────────────────── */
.search-bar{
  display:flex;gap:10px;align-items:center;flex-wrap:wrap;
  margin-bottom:20px;padding:14px 18px;
}
.search-wrap{position:relative;flex:1;min-width:180px;}
.search-wrap svg{position:absolute;left:12px;top:50%;transform:translateY(-50%);
  width:14px;height:14px;fill:var(--gray-400);}
.search-wrap .form-control{padding-left:36px;}

/* ─── MODAL ───────────────────────────────────────── */
.modal-overlay{
  display:none;position:fixed;inset:0;
  background:rgba(15,23,42,0.5);
  backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);
  z-index:1000;align-items:center;justify-content:center;
}
.modal-overlay.open{display:flex;animation:fadeIn 0.2s ease;}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
.modal-box{
  width:100%;max-width:460px;max-height:90vh;overflow-y:auto;
  padding:28px;
  background:rgba(255,255,255,0.95);
  backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);
  border:1px solid rgba(255,255,255,0.8);border-radius:var(--r-lg);
  box-shadow:0 24px 64px rgba(0,0,0,0.2);
  animation:popUp 0.25s cubic-bezier(0.34,1.56,0.64,1);
}
@keyframes popUp{from{opacity:0;transform:scale(0.92) translateY(16px)}to{opacity:1;transform:none}}
.modal-title{font-size:17px;font-weight:700;color:var(--gray-900);margin-bottom:18px;
  display:flex;align-items:center;gap:8px;}
.modal-title svg{width:18px;height:18px;fill:var(--blue-500);}

/* ─── AUTH PAGES ──────────────────────────────────── */
.auth-page{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px;}
.auth-card{
  width:100%;max-width:420px;padding:36px;
  background:rgba(255,255,255,0.88);
  backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);
  border:1px solid rgba(255,255,255,0.7);border-radius:24px;
  box-shadow:0 8px 40px rgba(37,99,235,0.12),0 1px 4px rgba(37,99,235,0.06);
}
.auth-logo{display:flex;align-items:center;gap:11px;justify-content:center;
  margin-bottom:28px;text-decoration:none;}
.auth-logo .brand-icon{width:46px;height:46px;border-radius:13px;
  background:linear-gradient(135deg,var(--blue-500),var(--blue-700));
  border:none;box-shadow:0 4px 16px rgba(37,99,235,0.35);}
.auth-logo span{font-size:21px;font-weight:800;color:var(--blue-900);letter-spacing:-0.4px;}
.auth-title{font-size:21px;font-weight:700;color:var(--gray-900);margin-bottom:5px;text-align:center;}
.auth-sub{font-size:13.5px;color:var(--gray-400);text-align:center;margin-bottom:24px;}
.auth-divider{text-align:center;font-size:12px;color:var(--gray-400);margin:18px 0;
  display:flex;align-items:center;gap:12px;}
.auth-divider::before,.auth-divider::after{content:"";flex:1;height:1px;background:var(--gray-200);}

/* ─── UTILS ───────────────────────────────────────── */
.d-flex{display:flex;}.align-center{align-items:center;}
.justify-between{justify-content:space-between;}.gap-2{gap:8px;}.gap-3{gap:14px;}
.text-muted{color:var(--gray-400);}.text-sm{font-size:13px;}.text-xs{font-size:11px;}
.text-center{text-align:center;}.fw-bold{font-weight:700;}
.mt-2{margin-top:8px;}.mt-3{margin-top:14px;}.mt-4{margin-top:20px;}
.mb-2{margin-bottom:8px;}.mb-3{margin-bottom:14px;}.mb-4{margin-bottom:20px;}

/* ─── SCROLLBAR ───────────────────────────────────── */
::-webkit-scrollbar{width:5px;height:5px;}
::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:var(--blue-200);border-radius:3px;}

/* ─── MOBILE ──────────────────────────────────────── */
.sidebar-toggle{display:none;position:fixed;top:14px;left:14px;z-index:200;
  width:38px;height:38px;border-radius:8px;border:none;cursor:pointer;
  background:white;box-shadow:0 2px 8px rgba(0,0,0,0.15);
  align-items:center;justify-content:center;font-size:17px;}
@media(max-width:900px){
  .sidebar{transform:translateX(calc(-1 * var(--sidebar-w) - 20px));}
  .sidebar.open{transform:translateX(0);}
  .main-content{margin-left:0;padding:72px 16px 20px;}
  .sidebar-toggle{display:flex;}
  .stats-grid{grid-template-columns:1fr 1fr;}
  .form-row{grid-template-columns:1fr;}
}
@media(max-width:500px){
  .auth-card{padding:24px 20px;}
  .stats-grid{grid-template-columns:1fr;}
  .employee-grid{grid-template-columns:1fr;}
}
"""

JS = """

document.addEventListener('DOMContentLoaded',()=>{
  // Auto-dismiss alerts
  document.querySelectorAll('.alert').forEach(a=>{
    setTimeout(()=>{
      a.style.transition='opacity .4s,transform .4s';
      a.style.opacity='0';a.style.transform='translateY(-6px)';
      setTimeout(()=>a.remove(),400);
    },4500);
  });

  // Mobile sidebar
  const tg=document.getElementById('sidebarToggle');
  const sb=document.getElementById('sidebar');
  const ov=document.getElementById('sidebarOverlay');
  if(tg&&sb){
    tg.addEventListener('click',()=>{
      sb.classList.toggle('open');
      if(ov)ov.style.display=ov.style.display==='flex'?'none':'flex';
    });
    if(ov)ov.addEventListener('click',()=>{sb.classList.remove('open');ov.style.display='none';});
  }

  // Modals
  document.querySelectorAll('[data-modal]').forEach(btn=>{
    btn.addEventListener('click',()=>{
      const el=document.getElementById(btn.dataset.modal);
      if(el)el.classList.toggle('open');
    });
  });
  document.querySelectorAll('.modal-overlay').forEach(el=>{
    el.addEventListener('click',e=>{if(e.target===el)el.classList.remove('open');});
  });

  // Copy invite codes
  document.querySelectorAll('.code-pill').forEach(el=>{
    el.title='Click to copy';
    el.addEventListener('click',()=>{
      navigator.clipboard.writeText(el.textContent.trim()).then(()=>{
        const o=el.textContent;el.textContent='✓ Copied!';el.style.color='#059669';
        setTimeout(()=>{el.textContent=o;el.style.color='';},1600);
      }).catch(()=>{});
    });
  });

  // Password strength
  const pw=document.getElementById('pw');const ps=document.getElementById('pwStrength');
  if(pw&&ps){
    pw.addEventListener('input',()=>{
      const v=pw.value;let s=0;
      if(v.length>=8)s++;if(/[A-Z]/.test(v))s++;if(/[0-9]/.test(v))s++;if(/[^A-Za-z0-9]/.test(v))s++;
      ps.textContent=v?['','Weak','Fair','Good','Strong'][s]:'';
      ps.style.color=['','#EF4444','#F59E0B','#3B82F6','#10B981'][s];
    });
  }
});

function showToast(msg,type){
  type=type||'info';
  const t=document.createElement('div');
  t.className='alert alert-'+type;
  t.style.cssText='position:fixed;bottom:20px;right:20px;z-index:9999;min-width:250px;max-width:340px;box-shadow:0 8px 24px rgba(0,0,0,.15);animation:popUp .3s cubic-bezier(.34,1.56,.64,1)';
  t.textContent=msg;document.body.appendChild(t);
  setTimeout(()=>{t.style.transition='opacity .3s';t.style.opacity='0';setTimeout(()=>t.remove(),300);},3000);
}
"""


I = {
  "bag":    '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M20 7h-4V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v2H4a2 2 0 00-2 2v11a2 2 0 002 2h16a2 2 0 002-2V9a2 2 0 00-2-2zm-10-2h4v2h-4V5z"/></svg>',
  "grid":   '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 3h7v7H3zm11 0h7v7h-7zM3 14h7v7H3zm11 0h7v7h-7z"/></svg>',
  "ppl":    '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>',
  "tkt":    '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M22 10V6a2 2 0 00-2-2H4a2 2 0 00-2 2v4c1.1 0 2 .9 2 2s-.9 2-2 2v4a2 2 0 002 2h16a2 2 0 002-2v-4c-1.1 0-2-.9-2-2s.9-2 2-2zm-2-1.46A4 4 0 0118 12a4 4 0 002 3.46V18H4v-2.54A4 4 0 006 12a4 4 0 00-2-3.46V6h16v2.54z"/></svg>',
  "usr":    '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>',
  "out":    '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z"/></svg>',
  "plus":   '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>',
  "srch":   '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 5-1.49 1.49-4.99-5zm-6 0C7.01 14 5 12 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 12 14 9.5 14z"/></svg>',
  "crd":    '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M20 4H4c-1.11 0-2 .89-2 2v12c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V6c0-1.11-.89-2-2-2zm0 14H4v-6h16v6zm0-10H4V6h16v2z"/></svg>',
  "cash":   '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M11.8 10.9c-2.27-.59-3-1.2-3-2.15 0-1.09 1.01-1.85 2.7-1.85 1.78 0 2.44.85 2.5 2.1h2.21c-.07-1.72-1.12-3.3-3.21-3.81V3h-3v2.16c-1.94.42-3.5 1.68-3.5 3.61 0 2.31 1.91 3.46 4.7 4.13 2.5.6 3 1.48 3 2.41 0 .69-.49 1.79-2.7 1.79-2.06 0-2.87-.92-2.98-2.1h-2.2c.12 2.19 1.76 3.42 3.68 3.83V21h3v-2.15c1.95-.37 3.5-1.5 3.5-3.55 0-2.84-2.43-3.81-4.7-4.4z"/></svg>',
  "nte":    '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg>',
  "arr":    '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z"/></svg>',
  "bck":    '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M15.41 16.59L10.83 12l4.58-4.59L14 6l-6 6 6 6 1.41-1.41z"/></svg>',
  "del":    '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>',
  "lnk":    '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M3.9 12c0-1.71 1.39-3.1 3.1-3.1h4V7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h4v-1.9H7c-1.71 0-3.1-1.39-3.1-3.1zM8 13h8v-2H8v2zm9-6h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1s-1.39 3.1-3.1 3.1h-4V17h4c2.76 0 5-2.24 5-5s-2.24-5-5-5z"/></svg>',
  "chk":    '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>',
  "x":      '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>',
}

FONTS = '<link rel="preconnect" href="https://fonts.googleapis.com"/><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet"/>'

def head(title):
    return f"""<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{title} — BizManager</title>
{FONTS}<style>{CSS}</style></head>"""

def layout(title, content, user, nav_active=""):
    nav_cfg = ([
        ("/dashboard","grid","Dashboard"),
        ("/employees","ppl","Employees"),
        ("/invites","tkt","Invite Codes"),
        ("/profile","usr","My Profile"),
    ] if user["role"]=="owner" else [
        ("/dashboard","grid","Dashboard"),
        ("/profile","usr","My Profile"),
    ])
    nav = "".join(f'<a href="{h}" class="nav-link {"active" if nav_active.startswith(h) else ""}">{I[ic]} {lb}</a>'
                  for h,ic,lb in nav_cfg)
    ini = initials(user["full_name"])
    return f"""{head(title)}<body>
<div id="sidebarOverlay" style="display:none;position:fixed;inset:0;background:rgba(15,23,42,.45);backdrop-filter:blur(4px);z-index:99;"></div>
<button id="sidebarToggle" class="sidebar-toggle">&#9776;</button>
<div class="app-wrapper">
<aside id="sidebar" class="sidebar">
  <a href="/dashboard" class="sidebar-brand">
    <div class="brand-icon">{I["bag"]}</div><span>BizManager</span>
  </a>
  <nav class="sidebar-nav">
    <span class="nav-section-label">Menu</span>{nav}
  </nav>
  <div class="sidebar-footer">
    <div class="user-chip">
      <div class="user-avatar">{ini}</div>
      <div style="flex:1;min-width:0;">
        <div class="user-chip-name">{escape(user["full_name"])}</div>
        <div class="user-chip-role">{user["role"].capitalize()}</div>
      </div>
    </div>
    <a href="/logout" class="nav-link" style="color:rgba(255,130,130,.9);">{I["out"]} Sign Out</a>
  </div>
</aside>
<main class="main-content">
  {flash_html()}
  {content}
</main>
</div>
<script>{JS}</script>
<script>
// highlight active nav
document.querySelectorAll(".sidebar .nav-link").forEach(a=>{{
  if(a.href&&window.location.pathname.startsWith(new URL(a.href,location).pathname)&&a.pathname!="/"&&!a.classList.contains("active")){{
    a.style.background="rgba(255,255,255,.12)";a.style.color="white";
  }}
}});
const ov=document.getElementById("sidebarOverlay");
const tg=document.getElementById("sidebarToggle");
const sb=document.getElementById("sidebar");
if(tg)tg.addEventListener("click",()=>{{sb.classList.toggle("open");ov.style.display=ov.style.display==="flex"?"none":"flex";}});
if(ov)ov.addEventListener("click",()=>{{sb.classList.remove("open");ov.style.display="none";}});
</script>
</body></html>"""

def auth_layout(title, content):
    return f"""{head(title)}<body>
<div class="auth-page">{content}</div>
<script>{JS}</script></body></html>"""

# ═══════════════════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ═══════════════════════════════════════════════════════════════════════════
@app.route("/")
def index(): return redir("/dashboard" if me() else "/login")

@app.route("/login", methods=["GET","POST"])
def login():
    if me(): return redir("/dashboard")
    if request.method=="POST":
        email=request.form.get("email","").strip().lower()
        pw=request.form.get("password","")
        u=q("SELECT * FROM users WHERE email=?",[email],one=True)
        if u and check_pw(pw,u["password_hash"]):
            if u["status"]=="suspended": flash("Account suspended. Contact your manager.","danger")
            else: session["user_id"]=u["id"]; return redir("/dashboard")
        else: flash("Invalid email or password.","danger")
    c=f"""<div class="auth-card">
    <a href="/" class="auth-logo"><div class="brand-icon">{I["bag"]}</div><span>BizManager</span></a>
    <h1 class="auth-title">Welcome back</h1>
    <p class="auth-subtitle">Sign in to continue</p>
    {flash_html()}
    <form method="POST">
      <div class="form-group"><label class="form-label">Email</label>
        <input type="email" name="email" class="form-control" placeholder="you@company.com" required autofocus/></div>
      <div class="form-group"><label class="form-label">Password</label>
        <input type="password" name="password" class="form-control" placeholder="••••••••" required/></div>
      <button type="submit" class="btn btn-primary w-100 btn-lg" style="margin-top:8px;">{I["arr"]} Sign In</button>
    </form>
    <div class="auth-divider">or</div>
    <a href="/register/employee" class="btn btn-secondary w-100 mb-2">{I["ppl"]} Join with Invite Code</a>
    <a href="/register/owner" class="btn btn-ghost w-100">{I["bag"]} Create Owner Account</a>
    </div>"""
    return auth_layout("Sign In", c)

@app.route("/logout")
def logout(): session.clear(); return redir("/login")

@app.route("/register/owner", methods=["GET","POST"])
def register_owner():
    if me(): return redir("/dashboard")
    errors=[]; fd={}
    if request.method=="POST":
        fd=request.form
        name=fd.get("full_name","").strip(); email=fd.get("email","").strip().lower()
        pw=fd.get("password",""); pw2=fd.get("confirm_password","")
        if not name: errors.append("Full name required.")
        if "@" not in email: errors.append("Valid email required.")
        if len(pw)<8: errors.append("Password must be 8+ characters.")
        if pw!=pw2: errors.append("Passwords don\'t match.")
        if q("SELECT id FROM users WHERE email=?",[email],one=True): errors.append("Email already in use.")
        if not errors:
            m("INSERT INTO users(email,password_hash,full_name,role,status,payment_status,created_at) VALUES(?,?,?,?,?,?,?)",
              [email,hash_pw(pw),name,"owner","active","paid",now()])
            flash("Owner account created! Please sign in.","success")
            return redir("/login")
    errs="".join(f'<div class="alert alert-danger">&#x2715; {e}</div>' for e in errors)
    c=f"""<div class="auth-card">
    <a href="/login" class="auth-logo"><div class="brand-icon">{I["bag"]}</div><span>BizManager</span></a>
    <h1 class="auth-title">Create Owner Account</h1>
    <p class="auth-subtitle">Set up your business workspace</p>
    {errs}
    <form method="POST">
      <div class="form-group"><label class="form-label">Full Name</label>
        <input type="text" name="full_name" class="form-control" placeholder="Jane Smith" value="{escape(fd.get('full_name',''))}" required/></div>
      <div class="form-group"><label class="form-label">Email</label>
        <input type="email" name="email" class="form-control" placeholder="jane@company.com" value="{escape(fd.get('email',''))}" required/></div>
      <div class="form-row">
        <div class="form-group"><label class="form-label">Password</label>
          <input type="password" id="pw" name="password" class="form-control" placeholder="Min. 8 chars" required/>
          <small style="font-size:11px;color:var(--gray-400);margin-top:4px;display:block;">Strength: <span id="pwStrength" style="font-weight:600;"></span></small></div>
        <div class="form-group"><label class="form-label">Confirm</label>
          <input type="password" name="confirm_password" class="form-control" placeholder="Repeat" required/></div>
      </div>
      <button type="submit" class="btn btn-primary w-100 btn-lg">{I["chk"]} Create Account</button>
    </form>
    <p style="text-align:center;font-size:13px;color:var(--gray-400);margin-top:20px;">
      Already have an account? <a href="/login" style="color:var(--blue-600);font-weight:600;">Sign in</a></p>
    </div>"""
    return auth_layout("Create Owner", c)

@app.route("/register/employee", methods=["GET","POST"])
def register_employee():
    if me(): return redir("/dashboard")
    prefill=request.args.get("code",""); errors=[]; fd={}
    if request.method=="POST":
        fd=request.form
        code_s=fd.get("invite_code","").strip().upper()
        name=fd.get("full_name","").strip(); email=fd.get("email","").strip().lower()
        pw=fd.get("password",""); pw2=fd.get("confirm_password","")
        inv=q("SELECT * FROM invite_codes WHERE code=?",[code_s],one=True)
        if not inv or not inv["is_active"] or inv["used_by_id"]: errors.append("Invalid or already-used invite code.")
        if not name: errors.append("Full name required.")
        if "@" not in email: errors.append("Valid email required.")
        if len(pw)<8: errors.append("Password must be 8+ characters.")
        if pw!=pw2: errors.append("Passwords don\'t match.")
        if email and q("SELECT id FROM users WHERE email=?",[email],one=True): errors.append("Email already in use.")
        if not errors:
            uid=m("INSERT INTO users(email,password_hash,full_name,role,status,payment_status,created_at) VALUES(?,?,?,?,?,?,?)",
                  [email,hash_pw(pw),name,"employee","active","unpaid",now()])
            m("UPDATE invite_codes SET used_by_id=? WHERE id=?",[uid,inv["id"]])
            flash("Account created! Please sign in.","success")
            return redir("/login")
    errs="".join(f'<div class="alert alert-danger">&#x2715; {e}</div>' for e in errors)
    cv=escape(fd.get("invite_code",prefill))
    c=f"""<div class="auth-card">
    <a href="/login" class="auth-logo"><div class="brand-icon">{I["bag"]}</div><span>BizManager</span></a>
    <h1 class="auth-title">Join Your Team</h1>
    <p class="auth-subtitle">Enter your invite code to register</p>
    {errs}
    <form method="POST">
      <div class="form-group"><label class="form-label">{I["tkt"]} Invite Code</label>
        <input type="text" name="invite_code" class="form-control"
               placeholder="XXXX-XXXX-XXXX" value="{cv}" required maxlength="32"
               style="font-family:monospace;font-size:17px;font-weight:700;letter-spacing:3px;text-transform:uppercase;"/></div>
      <div class="form-group"><label class="form-label">Full Name</label>
        <input type="text" name="full_name" class="form-control" placeholder="Your name" value="{escape(fd.get('full_name',''))}" required/></div>
      <div class="form-group"><label class="form-label">Work Email</label>
        <input type="email" name="email" class="form-control" placeholder="you@company.com" value="{escape(fd.get('email',''))}" required/></div>
      <div class="form-row">
        <div class="form-group"><label class="form-label">Password</label>
          <input type="password" id="pw" name="password" class="form-control" placeholder="Min. 8 chars" required/>
          <small style="font-size:11px;color:var(--gray-400);margin-top:4px;display:block;">Strength: <span id="pwStrength" style="font-weight:600;"></span></small></div>
        <div class="form-group"><label class="form-label">Confirm</label>
          <input type="password" name="confirm_password" class="form-control" placeholder="Repeat" required/></div>
      </div>
      <button type="submit" class="btn btn-primary w-100 btn-lg">{I["chk"]} Create Account</button>
    </form>
    <p style="text-align:center;font-size:13px;color:var(--gray-400);margin-top:20px;">
      Already registered? <a href="/login" style="color:var(--blue-600);font-weight:600;">Sign in</a></p>
    </div>"""
    return auth_layout("Join Team", c)

# ═══════════════════════════════════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════
@app.route("/dashboard")
@login_required
def dashboard():
    u=me()
    return owner_dash(u) if u["role"]=="owner" else emp_dash(u)

def owner_dash(u):
    emps=q("SELECT * FROM users WHERE role='employee'")
    total=len(emps); active=sum(1 for e in emps if e["status"]=="active")
    unpaid=sum(1 for e in emps if e["payment_status"]=="unpaid")
    codes=q("SELECT * FROM invite_codes WHERE owner_id=? ORDER BY created_at DESC LIMIT 8",[u["id"]])
    open_inv=sum(1 for c in codes if c["is_active"] and not c["used_by_id"])
    rows=""
    for e in emps[:8]:
        ini=initials(e["full_name"])
        rows+=f"""<tr>
          <td><div class="d-flex align-center gap-2">
            <div class="emp-avatar" style="width:34px;height:34px;font-size:12px;">{ini}</div>
            <div><div style="font-weight:600;font-size:13px;">{escape(e["full_name"])}</div>
            <div class="text-muted text-xs">{escape(e["position"] or e["email"])}</div></div></div></td>
          <td><span class="badge badge-{e["status"]}">{e["status"]}</span></td>
          <td><span class="badge badge-{e["payment_status"]}">{e["payment_status"]}</span></td>
          <td><a href="/employees/{e["id"]}" class="btn btn-ghost btn-sm btn-icon">{I["arr"]}</a></td></tr>"""
    if not rows: rows='<tr><td colspan="4" style="text-align:center;padding:40px;color:var(--gray-400);">No employees yet. Generate an invite code to get started.</td></tr>'
    codeshtml=""
    for c in codes:
        ub=""
        if c["used_by_id"]:
            r=q("SELECT full_name FROM users WHERE id=?",[c["used_by_id"]],one=True)
            ub=f" by {escape(r['full_name'])}" if r else ""
        valid=c["is_active"] and not c["used_by_id"]
        bg="rgba(16,185,129,.06)" if valid else "rgba(100,116,139,.06)"
        bc="rgba(16,185,129,.15)" if valid else "rgba(226,232,240,.8)"
        tc="var(--blue-700)" if valid else "var(--gray-400)"
        st="Active" if valid else ("Used"+ub if c["used_by_id"] else "Off")
        bclass="badge-active" if valid else "badge-inactive"
        lb="Open" if valid else ("Used" if c["used_by_id"] else "Off")
        codeshtml+=f"""<div style="display:flex;align-items:center;justify-content:space-between;
          padding:12px 14px;background:{bg};border-radius:var(--radius-md);border:1px solid {bc};">
          <div><div style="font-family:monospace;font-weight:700;font-size:13px;color:{tc};">{c["code"]}</div>
          <div class="text-xs text-muted mt-1">{st}</div></div>
          <span class="badge {bclass}">{lb}</span></div>"""
    if not codeshtml: codeshtml='<p class="text-muted text-sm text-center" style="padding:16px;">No codes yet.</p>'
    first=u["full_name"].split()[0]
    cnt=f"""
    <div class="topbar">
      <div><div class="page-title">Dashboard</div>
      <div class="page-subtitle">Good to see you, {escape(first)} &#128075;</div></div>
      <div class="topbar-actions">
        <a href="/employees" class="btn btn-secondary btn-sm">{I["ppl"]} Employees</a>
        <a href="/invites" class="btn btn-primary btn-sm">{I["plus"]} New Invite</a>
      </div>
    </div>
    <div class="stats-grid">
      <div class="stat-card"><div class="stat-icon blue">{I["ppl"]}</div>
        <div class="stat-value">{total}</div><div class="stat-label">Total Employees</div></div>
      <div class="stat-card"><div class="stat-icon green">{I["chk"]}</div>
        <div class="stat-value">{active}</div><div class="stat-label">Active</div></div>
      <div class="stat-card"><div class="stat-icon orange">{I["cash"]}</div>
        <div class="stat-value">{unpaid}</div><div class="stat-label">Unpaid</div></div>
      <div class="stat-card"><div class="stat-icon blue">{I["tkt"]}</div>
        <div class="stat-value">{open_inv}</div><div class="stat-label">Open Invites</div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 360px;gap:24px;" class="rg">
      <div class="card">
        <div class="card-header">
          <div><div class="card-title">Recent Employees</div><div class="card-subtitle">{total} total</div></div>
          <a href="/employees" class="btn btn-ghost btn-sm">{I["arr"]} View all</a>
        </div>
        <div class="table-wrap"><table>
          <thead><tr><th>Employee</th><th>Status</th><th>Payment</th><th></th></tr></thead>
          <tbody>{rows}</tbody></table></div>
      </div>
      <div class="card">
        <div class="card-header">
          <div><div class="card-title">Invite Codes</div><div class="card-subtitle">Recent</div></div>
          <a href="/invites" class="btn btn-ghost btn-sm">Manage</a>
        </div>
        <div style="display:flex;flex-direction:column;gap:10px;">{codeshtml}</div>
        <div class="mt-4"><a href="/invites" class="btn btn-primary w-100">{I["plus"]} Generate New Code</a></div>
      </div>
    </div>
    <style>@media(max-width:900px){{.rg{{grid-template-columns:1fr!important;}}}}</style>"""
    return layout("Dashboard",cnt,u,"/dashboard")

def emp_dash(u):
    pays=q("SELECT * FROM payment_records WHERE employee_id=? ORDER BY paid_on DESC LIMIT 5",[u["id"]])
    nts=q("SELECT * FROM notes WHERE employee_id=? ORDER BY created_at DESC LIMIT 5",[u["id"]])
    ini=initials(u["full_name"]); first=u["full_name"].split()[0]
    sc="green" if u["status"]=="active" else "red" if u["status"]=="suspended" else "orange"
    pc="green" if u["payment_status"]=="paid" else "orange"
    pitems="".join(f"""<div style="display:flex;justify-content:space-between;align-items:center;
      padding:12px 14px;background:rgba(16,185,129,.05);border:1px solid rgba(16,185,129,.12);border-radius:var(--radius-md);">
      <div><div style="font-weight:600;font-size:13px;">{escape(p["period"] or "Payment")}</div>
      <div class="text-xs text-muted mt-1">{fdate(p["paid_on"])}</div></div>
      <span style="font-weight:800;font-size:15px;color:var(--success);">{p["currency"]} {float(p["amount"]):.2f}</span>
    </div>""" for p in pays) or '<p class="text-muted text-sm text-center" style="padding:16px;">No payments yet.</p>'
    nitems="".join(f"""<div style="padding:12px 14px;background:rgba(245,158,11,.06);
      border:1px solid rgba(245,158,11,.15);border-radius:var(--radius-md);">
      <p style="font-size:13px;color:var(--gray-700);">{escape(n["content"])}</p>
      <div class="text-xs text-muted mt-2">{fdate(n["created_at"])}</div></div>""" for n in nts)
    nsec=f"""<div class="card" style="margin-top:24px;">
      <div class="card-header"><div class="card-title">{I["nte"]} Notes from Management</div></div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px;">{nitems}</div>
    </div>""" if nts else ""
    cnt_pays=q("SELECT COUNT(*) as c FROM payment_records WHERE employee_id=?",[u["id"]],one=True)["c"]
    cnt=f"""
    <div class="topbar">
      <div><div class="page-title">My Dashboard</div>
      <div class="page-subtitle">Welcome, {escape(first)} &#128075;</div></div>
      <a href="/profile" class="btn btn-secondary btn-sm">{I["usr"]} My Profile</a>
    </div>
    <div class="stats-grid">
      <div class="stat-card"><div class="stat-icon {sc}">{I["chk"]}</div>
        <div class="stat-value" style="font-size:20px;margin-top:4px;">{u["status"].capitalize()}</div>
        <div class="stat-label">Employment Status</div></div>
      <div class="stat-card"><div class="stat-icon {pc}">{I["crd"]}</div>
        <div class="stat-value" style="font-size:20px;margin-top:4px;">{u["payment_status"].capitalize()}</div>
        <div class="stat-label">Payment Status</div></div>
      <div class="stat-card"><div class="stat-icon blue">{I["ppl"]}</div>
        <div class="stat-value" style="font-size:18px;margin-top:4px;">{fdate(u["created_at"][:10])}</div>
        <div class="stat-label">Member Since</div></div>
      <div class="stat-card"><div class="stat-icon green">{I["cash"]}</div>
        <div class="stat-value" style="font-size:20px;margin-top:4px;">{cnt_pays}</div>
        <div class="stat-label">Payment Records</div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 360px;gap:24px;" class="dg2">
      <div class="card">
        <div class="card-header"><div class="card-title">My Information</div>
          <a href="/profile" class="btn btn-ghost btn-sm">{I["arr"]} Edit</a></div>
        <div style="display:flex;gap:20px;align-items:flex-start;">
          <div class="emp-avatar" style="width:64px;height:64px;font-size:22px;flex-shrink:0;">{ini}</div>
          <div style="flex:1;">
            <div style="font-size:18px;font-weight:700;color:var(--gray-900);">{escape(u["full_name"])}</div>
            <div style="color:var(--gray-400);font-size:13px;margin-top:2px;">{escape(u["position"] or "Employee")}</div>
            <div style="margin-top:14px;display:flex;flex-direction:column;gap:8px;">
              <div style="font-size:13px;">&#128231; {escape(u["email"])}</div>
              {f'<div style="font-size:13px;">&#128222; {escape(u["phone"])}</div>' if u["phone"] else ""}
            </div>
            <div style="margin-top:16px;display:flex;gap:8px;flex-wrap:wrap;">
              <span class="badge badge-{u["status"]}">{u["status"]}</span>
              <span class="badge badge-{u["payment_status"]}">{u["payment_status"]}</span>
              <span class="badge badge-employee">Employee</span>
            </div>
          </div>
        </div>
      </div>
      <div class="card">
        <div class="card-header"><div class="card-title">Recent Payments</div>
          <a href="/profile" class="btn btn-ghost btn-sm">View all</a></div>
        <div style="display:flex;flex-direction:column;gap:10px;">{pitems}</div>
      </div>
    </div>
    {nsec}
    <style>@media(max-width:900px){{.dg2{{grid-template-columns:1fr!important;}}}}</style>"""
    return layout("Dashboard",cnt,u,"/dashboard")

# ═══════════════════════════════════════════════════════════════════════════
#  PROFILE (shared owner+employee)
# ═══════════════════════════════════════════════════════════════════════════
@app.route("/profile", methods=["GET","POST"])
@login_required
def profile():
    u=me()
    if request.method=="POST":
        phone=request.form.get("phone","").strip()
        npw=request.form.get("new_password",""); cpw=request.form.get("confirm_password","")
        if npw:
            if npw!=cpw: flash("Passwords don\'t match.","danger"); return redir("/profile")
            if len(npw)<8: flash("Password must be 8+ characters.","danger"); return redir("/profile")
            m("UPDATE users SET phone=?,password_hash=? WHERE id=?",[phone,hash_pw(npw),u["id"]])
        else: m("UPDATE users SET phone=? WHERE id=?",[phone,u["id"]])
        flash("Profile updated.","success"); return redir("/profile")
    u=me(); pays=q("SELECT * FROM payment_records WHERE employee_id=? ORDER BY paid_on DESC",[u["id"]])
    ini=initials(u["full_name"])
    prows="".join(f"""<tr>
      <td><div style="font-weight:600;">{escape(p["period"] or "—")}</div></td>
      <td><span style="font-weight:700;color:var(--success);">{p["currency"]} {float(p["amount"]):.2f}</span></td>
      <td class="text-muted text-sm">{escape(p["method"] or "—")}</td>
      <td class="text-muted text-sm">{fdate(p["paid_on"])}</td></tr>""" for p in pays) or \
      '<tr><td colspan="4" class="text-center text-muted" style="padding:24px;">No payments yet.</td></tr>'
    cnt=f"""
    <div class="topbar">
      <div><div class="page-title">My Profile</div><div class="page-subtitle">Account settings</div></div>
      <span class="badge badge-{u["role"]}">{u["role"].capitalize()}</span>
    </div>
    <div style="max-width:580px;">
      <div class="card mb-4" style="background:linear-gradient(135deg,rgba(37,99,235,.1),rgba(59,130,246,.04));
           text-align:center;padding:32px 24px;margin-bottom:24px;">
        <div class="emp-avatar" style="width:68px;height:68px;font-size:22px;margin:0 auto 14px;">{ini}</div>
        <div style="font-size:19px;font-weight:800;color:var(--gray-900);">{escape(u["full_name"])}</div>
        <div style="color:var(--gray-400);font-size:13px;margin-top:4px;">{escape(u["position"] or "—")}</div>
        <div style="margin-top:10px;display:flex;gap:8px;justify-content:center;flex-wrap:wrap;">
          <span class="badge badge-{u["status"]}">{u["status"]}</span>
          <span class="badge badge-{u["payment_status"]}">{u["payment_status"]}</span>
        </div>
      </div>
      <form method="POST" class="card mb-4" style="margin-bottom:24px;">
        <div class="card-header"><div class="card-title">Account Settings</div></div>
        <div class="form-group"><label class="form-label">Full Name</label>
          <input class="form-control" value="{escape(u["full_name"])}" disabled/></div>
        <div class="form-group"><label class="form-label">Email</label>
          <input class="form-control" value="{escape(u["email"])}" disabled/></div>
        <div class="form-group"><label class="form-label">Phone</label>
          <input type="text" name="phone" class="form-control" placeholder="+1 555…" value="{escape(u["phone"] or "")}"/></div>
        <hr style="border:none;border-top:1px solid var(--gray-200);margin:18px 0;"/>
        <div style="font-size:14px;font-weight:700;margin-bottom:14px;">Change Password <span class="text-muted text-sm">(leave blank to keep current)</span></div>
        <div class="form-row">
          <div class="form-group"><label class="form-label">New Password</label>
            <input type="password" id="pw" name="new_password" class="form-control" placeholder="Min. 8 chars" autocomplete="new-password"/>
            <small style="font-size:11px;color:var(--gray-400);margin-top:4px;display:block;">Strength: <span id="pwStrength" style="font-weight:600;"></span></small></div>
          <div class="form-group"><label class="form-label">Confirm</label>
            <input type="password" name="confirm_password" class="form-control" placeholder="Repeat" autocomplete="new-password"/></div>
        </div>
        <button type="submit" class="btn btn-primary w-100">{I["chk"]} Save Changes</button>
      </form>
      <div class="card">
        <div class="card-header"><div class="card-title">{I["crd"]} Payment History</div></div>
        <div class="table-wrap"><table>
          <thead><tr><th>Period</th><th>Amount</th><th>Method</th><th>Date</th></tr></thead>
          <tbody>{prows}</tbody></table></div>
      </div>
    </div>"""
    return layout("Profile",cnt,u,"/profile")

# ═══════════════════════════════════════════════════════════════════════════
#  EMPLOYEES (owner only)
# ═══════════════════════════════════════════════════════════════════════════
@app.route("/employees")
@owner_req
def employees():
    u=me(); qp=request.args.get("q","").strip()
    st=request.args.get("status",""); py=request.args.get("payment","")
    sql="SELECT * FROM users WHERE role=\'employee\'"; args=[]
    if qp: sql+=" AND (full_name LIKE ? OR email LIKE ?)"; args+=[f"%{qp}%",f"%{qp}%"]
    if st: sql+=" AND status=?"; args.append(st)
    if py: sql+=" AND payment_status=?"; args.append(py)
    sql+=" ORDER BY full_name"
    emps=q(sql,args)
    cards=""
    for e in emps:
        ini=initials(e["full_name"])
        ph=f'<div class="text-xs text-muted" style="margin-top:4px;">&#128222; {escape(e["phone"])}</div>' if e["phone"] else ""
        cards+=f"""<a href="/employees/{e["id"]}" class="emp-card">
          <div class="emp-card-top">
            <div class="emp-avatar">{ini}</div>
            <div><div class="emp-name">{escape(e["full_name"])}</div>
            <div class="emp-position">{escape(e["position"] or "No position set")}</div></div>
          </div>
          <div class="emp-badges">
            <span class="badge badge-{e["status"]}">{e["status"]}</span>
            <span class="badge badge-{e["payment_status"]}">{e["payment_status"]}</span>
          </div>
          <div class="text-xs text-muted" style="margin-top:10px;">&#128231; {escape(e["email"])}</div>
          {ph}
          <div class="text-xs text-muted" style="margin-top:8px;padding-top:8px;border-top:1px solid var(--gray-200);">
            Joined {fdate(e["created_at"][:10])}</div>
        </a>"""
    if not cards: cards=f"""<div class="card" style="text-align:center;padding:60px 20px;">
      <div style="font-size:48px;margin-bottom:16px;">&#128101;</div>
      <div style="font-size:18px;font-weight:700;color:var(--gray-700);margin-bottom:8px;">No employees found</div>
      <p style="color:var(--gray-400);margin-bottom:24px;">{"Try adjusting filters." if qp or st or py else "Generate an invite code to get started."}</p>
      <a href="/invites" class="btn btn-primary">{I["tkt"]} Generate Invite Code</a></div>"""
    clr=f'<a href="/employees" class="btn btn-ghost">{I["x"]} Clear</a>' if qp or st or py else ""
    sel=lambda n,v: "selected" if n==v else ""
    cnt=f"""
    <div class="topbar">
      <div><div class="page-title">Employees</div><div class="page-subtitle">{len(emps)} member{"s" if len(emps)!=1 else ""}</div></div>
      <a href="/invites" class="btn btn-primary">{I["plus"]} Invite Employee</a>
    </div>
    <form class="search-bar card" method="GET">
      <div class="search-input-wrapper">{I["srch"]}
        <input type="text" name="q" class="form-control" placeholder="Search name or email…" value="{escape(qp)}"/></div>
      <select name="status" class="form-control" style="width:auto;">
        <option value="">All statuses</option>
        <option value="active" {sel(st,"active")}>Active</option>
        <option value="inactive" {sel(st,"inactive")}>Inactive</option>
        <option value="suspended" {sel(st,"suspended")}>Suspended</option>
      </select>
      <select name="payment" class="form-control" style="width:auto;">
        <option value="">All payments</option>
        <option value="paid" {sel(py,"paid")}>Paid</option>
        <option value="unpaid" {sel(py,"unpaid")}>Unpaid</option>
      </select>
      <button type="submit" class="btn btn-primary">{I["srch"]} Filter</button>
      {clr}
    </form>
    <div class="employee-grid">{cards}</div>"""
    return layout("Employees",cnt,u,"/employees")

@app.route("/employees/<int:eid>", methods=["GET","POST"])
@owner_req
def employee_detail(eid):
    u=me(); emp=q("SELECT * FROM users WHERE id=? AND role=\'employee\'",[eid],one=True)
    if not emp: flash("Employee not found.","danger"); return redir("/employees")
    if request.method=="POST":
        act=request.form.get("action")
        if act=="update_profile":
            m("UPDATE users SET full_name=?,position=?,phone=?,status=?,payment_status=? WHERE id=?",
              [request.form.get("full_name",emp["full_name"]).strip(),
               request.form.get("position","").strip(),
               request.form.get("phone","").strip(),
               request.form.get("status",emp["status"]),
               request.form.get("payment_status",emp["payment_status"]),eid])
            flash("Profile updated.","success")
        elif act=="add_payment":
            try:
                amt=float(request.form.get("amount",0))
                m("INSERT INTO payment_records(employee_id,amount,currency,period,method,reference,notes,paid_on) VALUES(?,?,?,?,?,?,?,?)",
                  [eid,amt,request.form.get("currency","USD"),request.form.get("period",""),
                   request.form.get("method",""),request.form.get("reference",""),
                   request.form.get("payment_notes",""),now()])
                m("UPDATE users SET payment_status=\'paid\' WHERE id=?",[eid])
                flash("Payment recorded.","success")
            except ValueError: flash("Invalid amount.","danger")
        elif act=="add_note":
            cn=request.form.get("note_content","").strip()
            if cn:
                m("INSERT INTO notes(employee_id,author_id,content,created_at) VALUES(?,?,?,?)",
                  [eid,u["id"],cn,now()])
                flash("Note added.","success")
        return redir(f"/employees/{eid}")
    emp=q("SELECT * FROM users WHERE id=?",[eid],one=True)
    pays=q("SELECT * FROM payment_records WHERE employee_id=? ORDER BY paid_on DESC",[eid])
    nts=q("""SELECT n.*,u.full_name as aname FROM notes n
             JOIN users u ON n.author_id=u.id WHERE n.employee_id=? ORDER BY n.created_at DESC""",[eid])
    ini=initials(emp["full_name"])
    total=sum(float(p["amount"]) for p in pays)
    prows="".join(f"""<tr>
      <td><div style="font-weight:600;">{escape(p["period"] or "—")}</div>
          {f'<div class="text-xs text-muted">Ref: {escape(p["reference"])}</div>' if p["reference"] else ""}</td>
      <td><span style="font-weight:700;color:var(--success);">{p["currency"]} {float(p["amount"]):.2f}</span></td>
      <td>{escape(p["method"] or "—")}</td>
      <td class="text-muted text-sm">{fdate(p["paid_on"])}</td></tr>""" for p in pays) or \
      '<tr><td colspan="4" class="text-center text-muted" style="padding:30px;">No payments yet.</td></tr>'
    trow=f"""<div style="margin-top:16px;padding:14px 16px;background:rgba(16,185,129,.08);
      border-radius:var(--radius-md);display:flex;justify-content:space-between;align-items:center;">
      <span style="font-weight:600;">Total Paid</span>
      <span style="font-size:18px;font-weight:800;color:var(--success);">USD {total:.2f}</span></div>""" if pays else ""
    nhtml="".join(f"""<div id="note-{n["id"]}" style="padding:12px 14px;background:rgba(245,158,11,.06);
      border:1px solid rgba(245,158,11,.15);border-radius:var(--radius-md);">
      <p style="font-size:13px;color:var(--gray-700);">{escape(n["content"])}</p>
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span class="text-xs text-muted">{escape(n["aname"])} · {fdate(n["created_at"])}</span>
        <button onclick="delNote({n["id"]})" class="btn btn-danger btn-sm btn-icon">{I["del"]}</button>
      </div></div>""" for n in nts) or '<p class="text-muted text-sm text-center" style="padding:16px;">No notes yet.</p>'
    sel=lambda a,b: "selected" if a==b else ""
    cnt=f"""
    <div class="topbar">
      <div style="display:flex;align-items:center;gap:16px;">
        <a href="/employees" class="btn btn-ghost btn-sm btn-icon">{I["bck"]}</a>
        <div><div class="page-title">{escape(emp["full_name"])}</div>
        <div class="page-subtitle">{escape(emp["position"] or "Employee")} · Joined {fdate(emp["created_at"][:10])}</div></div>
      </div>
      <div class="d-flex gap-2">
        <span class="badge badge-{emp["status"]}" style="font-size:13px;padding:7px 14px;">{emp["status"]}</span>
        <span class="badge badge-{emp["payment_status"]}" style="font-size:13px;padding:7px 14px;">{emp["payment_status"]}</span>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;" class="dg">
      <div style="display:flex;flex-direction:column;gap:20px;">
        <div class="card">
          <div class="card-header"><div class="card-title">{I["usr"]} Profile</div></div>
          <form method="POST">
            <input type="hidden" name="action" value="update_profile"/>
            <div class="form-group"><label class="form-label">Full Name</label>
              <input type="text" name="full_name" class="form-control" value="{escape(emp["full_name"])}" required/></div>
            <div class="form-row">
              <div class="form-group"><label class="form-label">Position</label>
                <input type="text" name="position" class="form-control" placeholder="e.g. Developer" value="{escape(emp["position"] or "")}"/></div>
              <div class="form-group"><label class="form-label">Phone</label>
                <input type="text" name="phone" class="form-control" placeholder="+1 555…" value="{escape(emp["phone"] or "")}"/></div>
            </div>
            <div class="form-row">
              <div class="form-group"><label class="form-label">Status</label>
                <select name="status" class="form-control">
                  <option value="active" {sel(emp["status"],"active")}>&#10003; Active</option>
                  <option value="inactive" {sel(emp["status"],"inactive")}>&#9675; Inactive</option>
                  <option value="suspended" {sel(emp["status"],"suspended")}>&#10005; Suspended</option>
                </select></div>
              <div class="form-group"><label class="form-label">Payment</label>
                <select name="payment_status" class="form-control">
                  <option value="paid" {sel(emp["payment_status"],"paid")}>&#10003; Paid</option>
                  <option value="unpaid" {sel(emp["payment_status"],"unpaid")}>&#9675; Unpaid</option>
                </select></div>
            </div>
            <div class="form-group"><label class="form-label">Email</label>
              <input class="form-control" value="{escape(emp["email"])}" disabled/></div>
            <button type="submit" class="btn btn-primary w-100">{I["chk"]} Save Changes</button>
          </form>
        </div>
        <div class="card">
          <div class="card-header"><div class="card-title">{I["nte"]} Notes</div></div>
          <form method="POST" class="mb-3">
            <input type="hidden" name="action" value="add_note"/>
            <div class="form-group">
              <textarea name="note_content" class="form-control"
                        placeholder="Add a note about this employee…" rows="3"></textarea></div>
            <button type="submit" class="btn btn-secondary btn-sm">{I["plus"]} Add Note</button>
          </form>
          <div style="display:flex;flex-direction:column;gap:10px;">{nhtml}</div>
        </div>
      </div>
      <div>
        <div class="card">
          <div class="card-header">
            <div class="card-title">{I["crd"]} Payments</div>
            <button type="button" class="btn btn-primary btn-sm" data-modal="payModal">{I["plus"]} Record</button>
          </div>
          <div class="table-wrap"><table>
            <thead><tr><th>Period</th><th>Amount</th><th>Method</th><th>Date</th></tr></thead>
            <tbody>{prows}</tbody></table></div>
          {trow}
        </div>
      </div>
    </div>
    <div id="payModal" class="modal-overlay">
      <div class="modal-box">
        <h3 class="modal-title">{I["cash"]} Record Payment</h3>
        <form method="POST">
          <input type="hidden" name="action" value="add_payment"/>
          <div class="form-row">
            <div class="form-group"><label class="form-label">Amount</label>
              <input type="number" name="amount" class="form-control" step="0.01" placeholder="0.00" required min="0"/></div>
            <div class="form-group"><label class="form-label">Currency</label>
              <select name="currency" class="form-control"><option>USD</option><option>EUR</option><option>GBP</option><option>CAD</option></select></div>
          </div>
          <div class="form-row">
            <div class="form-group"><label class="form-label">Period</label>
              <input type="text" name="period" class="form-control" placeholder="e.g. March 2025"/></div>
            <div class="form-group"><label class="form-label">Method</label>
              <input type="text" name="method" class="form-control" placeholder="Bank Transfer…"/></div>
          </div>
          <div class="form-group"><label class="form-label">Reference</label>
            <input type="text" name="reference" class="form-control" placeholder="Transaction ID (optional)"/></div>
          <div class="form-group"><label class="form-label">Notes</label>
            <textarea name="payment_notes" class="form-control" rows="2" placeholder="Optional…"></textarea></div>
          <div class="d-flex gap-2 mt-3">
            <button type="submit" class="btn btn-primary" style="flex:1;">{I["chk"]} Record</button>
            <button type="button" class="btn btn-ghost" onclick="document.getElementById(\'payModal\').classList.remove(\'open\')">Cancel</button>
          </div>
        </form>
      </div>
    </div>
    <style>@media(max-width:900px){{.dg{{grid-template-columns:1fr!important;}}}}</style>
    <script>
    async function delNote(id){{
      if(!confirm("Delete this note?"))return;
      const r=await fetch("/api/notes/"+id+"/delete",{{method:"DELETE"}});
      const d=await r.json();
      if(d.ok){{const el=document.getElementById("note-"+id);
        if(el){{el.style.transition="opacity .3s,transform .3s";el.style.opacity="0";el.style.transform="scale(.95)";
          setTimeout(()=>el.remove(),300);}}}}
    }}
    </script>"""
    return layout(emp["full_name"],cnt,u,"/employees")

@app.route("/api/notes/<int:nid>/delete", methods=["DELETE"])
@owner_req
def del_note(nid):
    m("DELETE FROM notes WHERE id=?",[nid]); return jsonify({"ok":True})

# ═══════════════════════════════════════════════════════════════════════════
#  INVITES (owner only)
# ═══════════════════════════════════════════════════════════════════════════
def gen_code(): return secrets.token_urlsafe(9).upper()[:12]

@app.route("/invites", methods=["GET","POST"])
@owner_req
def invites():
    u=me()
    if request.method=="POST":
        label=request.form.get("label","").strip()
        code=gen_code()
        m("INSERT INTO invite_codes(code,owner_id,label,is_active,created_at) VALUES(?,?,?,1,?)",
          [code,u["id"],label or "",now()])
        flash(f"Invite code generated: {code}","success")
        return redir("/invites")
    codes=q("SELECT * FROM invite_codes WHERE owner_id=? ORDER BY created_at DESC",[u["id"]])
    rows=""
    for c in codes:
        ub_html="—"
        if c["used_by_id"]:
            r=q("SELECT id,full_name FROM users WHERE id=?",[c["used_by_id"]],one=True)
            if r: ub_html=f'<a href="/employees/{r["id"]}" style="color:var(--blue-600);font-weight:600;">{escape(r["full_name"])}</a>'
        valid=c["is_active"] and not c["used_by_id"]
        badge="badge-active" if valid else "badge-suspended" if not c["is_active"] else "badge-inactive"
        st="Active" if valid else "Deactivated" if not c["is_active"] else "Used"
        lbtn=f"""<button onclick="cpLink(\'{c["code"]}\')" class="btn btn-secondary btn-sm">{I["lnk"]} Copy Link</button>""" if valid else '<span class="text-muted text-xs">N/A</span>'
        dbtn=f"""<form method="POST" action="/invites/{c["id"]}/deactivate" onsubmit="return confirm(\'Deactivate?\')">
                 <button type="submit" class="btn btn-danger btn-sm btn-icon" title="Deactivate">{I["x"]}</button></form>""" if valid else ""
        rows+=f"""<tr>
          <td><span class="code-pill" style="font-size:14px;padding:7px 12px;display:inline-block;">{c["code"]}</span></td>
          <td class="text-muted text-sm">{escape(c["label"] or "—")}</td>
          <td><span class="badge {badge}">{st}</span></td>
          <td>{ub_html}</td>
          <td class="text-muted text-sm">{fdate(c["created_at"])}</td>
          <td>{lbtn}</td><td>{dbtn}</td></tr>"""
    host=request.host_url.rstrip("/")
    # Build code cards
    code_cards=""
    for c in codes:
        ub_html=""
        if c["used_by_id"]:
            r=q("SELECT id,full_name FROM users WHERE id=?",[c["used_by_id"]],one=True)
            if r: ub_html=f'<a href="/employees/{r["id"]}" style="color:var(--blue-600);font-weight:600;font-size:12px;">&#10003; Used by {escape(r["full_name"])}</a>'
            else: ub_html='<span class="text-xs text-muted">&#10003; Used</span>'
        valid=c["is_active"] and not c["used_by_id"]
        border_color="rgba(59,130,246,0.2)" if valid else "rgba(226,232,240,0.8)"
        bg_color="rgba(255,255,255,0.9)" if valid else "rgba(248,250,252,0.7)"
        badge_cls="badge-active" if valid else ("badge-suspended" if not c["is_active"] else "badge-inactive")
        badge_lbl="Active" if valid else ("Deactivated" if not c["is_active"] else "Used")
        copy_btn=f"""<button onclick="cpCode(\'{c["code"]}\',this)" class="btn btn-secondary btn-sm">{I["lnk"]} Copy Link</button>""" if valid else ""
        link_btn=f"""<a href="{host}/register/employee?code={c["code"]}" target="_blank" class="btn btn-ghost btn-sm">{I["arr"]} Open</a>""" if valid else ""
        deact_btn=f"""<form method="POST" action="/invites/{c["id"]}/deactivate" style="display:inline;" onsubmit="return confirm('Deactivate this code?')">
          <button type="submit" class="btn btn-danger btn-sm btn-icon" title="Deactivate">{I["x"]}</button></form>""" if valid else ""
        label_disp=f'<span style="font-size:12px;color:var(--gray-400);margin-bottom:6px;display:block;">{escape(c["label"])}</span>' if c["label"] else ""
        code_cards+=f"""
        <div style="padding:16px 18px;border-radius:14px;background:{bg_color};
          border:1.5px solid {border_color};transition:all .2s;
          box-shadow:0 2px 8px rgba(37,99,235,0.06);">
          {label_disp}
          <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;">
            <span class="code-pill" style="font-size:16px;">{c["code"]}</span>
            <span class="badge {badge_cls}" style="flex-shrink:0;">{badge_lbl}</span>
          </div>
          <div style="margin-top:10px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
            <div style="font-size:12px;color:var(--gray-400);">
              {f'Created {fdate(c["created_at"])}'}
              {f" &nbsp;|&nbsp; {ub_html}" if ub_html else ""}
            </div>
            <div style="display:flex;gap:6px;">{copy_btn}{link_btn}{deact_btn}</div>
          </div>
        </div>"""
    if not code_cards:
        code_cards=f"""<div style="text-align:center;padding:48px 20px;color:var(--gray-400);">
          <div style="font-size:44px;margin-bottom:12px;">&#127903;</div>
          <div style="font-size:15px;font-weight:600;color:var(--gray-700);margin-bottom:6px;">No invite codes yet</div>
          <p style="font-size:13px;">Use the form on the right to generate your first code.</p></div>"""
    cnt=f"""
    <div class="topbar">
      <div><div class="page-title">Invite Codes</div>
      <div class="page-subtitle">Generate codes &amp; invite employees to join</div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 320px;gap:20px;align-items:start;" class="inv-grid">
      <!-- Left: codes list -->
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">{I["tkt"]} All Codes</div>
            <div class="card-subtitle">{len(codes)} code{"s" if len(codes)!=1 else ""} total &nbsp;·&nbsp; {sum(1 for c in codes if c["is_active"] and not c["used_by_id"])} active</div>
          </div>
        </div>
        <div style="display:flex;flex-direction:column;gap:10px;">{code_cards}</div>
      </div>
      <!-- Right: generate form -->
      <div style="position:sticky;top:24px;">
        <div class="card" style="border:1.5px solid rgba(59,130,246,0.2);background:linear-gradient(160deg,rgba(239,246,255,0.9),rgba(255,255,255,0.95));">
          <div class="card-header" style="margin-bottom:14px;">
            <div class="card-title" style="color:var(--blue-800);">{I["plus"]} Generate New Code</div>
          </div>
          <p style="font-size:13px;color:var(--gray-500);margin-bottom:16px;line-height:1.5;">
            Create a unique one-time invite code. Share it with the employee so they can register.
          </p>
          <form method="POST">
            <div class="form-group">
              <label class="form-label">Label <span class="text-muted fw-normal">(optional)</span></label>
              <input type="text" name="label" class="form-control"
                     placeholder="e.g. For John Smith" maxlength="100" autofocus/>
              <div class="form-hint">Helps you remember who this code is for</div>
            </div>
            <button type="submit" class="btn btn-primary w-100" style="margin-top:6px;padding:12px;">
              {I["plus"]} Generate Invite Code
            </button>
          </form>
          <div style="margin-top:18px;padding-top:14px;border-top:1px solid var(--gray-200);">
            <div style="font-size:12px;font-weight:700;color:var(--gray-700);margin-bottom:8px;">&#128073; How it works</div>
            <div style="font-size:12px;color:var(--gray-500);line-height:1.6;">
              1. Generate a code here<br/>
              2. Share the code or link with your employee<br/>
              3. They open the <a href="{host}/register/employee" target="_blank" style="color:var(--blue-600);">join page</a> and register<br/>
              4. Each code works <strong>once</strong> only
            </div>
          </div>
        </div>
      </div>
    </div>
    <style>@media(max-width:900px){{.inv-grid{{grid-template-columns:1fr!important;}}}}</style>
    <script>
    function cpCode(code,btn){{
      const url=window.location.origin+"/register/employee?code="+code;
      navigator.clipboard.writeText(url).then(()=>{{
        const orig=btn.textContent;btn.textContent="✓ Copied!";btn.style.color="#059669";
        setTimeout(()=>{{btn.textContent=orig;btn.style.color="";}},1800);
      }}).catch(()=>showToast("Could not copy","danger"));
    }}
    </script>"""
    return layout("Invite Codes",cnt,u,"/invites")

@app.route("/invites/<int:cid>/deactivate", methods=["POST"])
@owner_req
def deactivate_invite(cid):
    u=me(); m("UPDATE invite_codes SET is_active=0 WHERE id=? AND owner_id=?",[cid,u["id"]])
    flash("Invite code deactivated.","info"); return redir("/invites")

# ═══════════════════════════════════════════════════════════════════════════
#  FAVICON
# ═══════════════════════════════════════════════════════════════════════════
@app.route("/favicon.ico")
def favicon():
    svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><rect width="24" height="24" rx="6" fill="#2563EB"/><path fill="white" d="M6 7h12v2H6zm0 4h12v2H6zm0 4h8v2H6z"/></svg>'
    r=make_response(svg); r.headers["Content-Type"]="image/svg+xml"; return r

# ═══════════════════════════════════════════════════════════════════════════
#  LAUNCH
# ═══════════════════════════════════════════════════════════════════════════
def open_browser():
    time.sleep(1.4)
    webbrowser.open(f"http://127.0.0.1:{PORT}")

if __name__=="__main__":
    init_db()
    print("""
  ╔══════════════════════════════════════════════════════╗
  ║            BizManager is starting...                 ║
  ║                                                      ║
  ║  Browser opens automatically at http://localhost:5000 ║
  ║  Database file: bizmanager.db  (auto-created)        ║
  ║  To stop: close this window or press Ctrl+C          ║
  ╚══════════════════════════════════════════════════════╝
""")
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
