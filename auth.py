"""Customer register / login with hashed passwords (SQLite) and Flask sessions."""
import re, sqlite3
from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash

auth = Blueprint("auth", __name__)
DB = "users.db"


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, email TEXT UNIQUE, pw TEXT)")
    return c


def ensure_demo_user():
    """Demo account for judges: demo@agentpay.com / Demo@12345"""
    with db() as c:
        if not c.execute("SELECT 1 FROM users WHERE email='demo@agentpay.com'").fetchone():
            c.execute("INSERT INTO users (name, email, pw) VALUES (?,?,?)",
                      ("Demo Customer", "demo@agentpay.com", generate_password_hash("Demo@12345")))


@auth.route("/auth/register", methods=["POST"])
def register():
    b = request.json or {}
    name, email, pw = (b.get("name") or "").strip(), (b.get("email") or "").strip().lower(), b.get("password") or ""
    if len(name) < 2:
        return jsonify(error="Please enter your name"), 400
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify(error="Enter a valid email"), 400
    if len(pw) < 8:
        return jsonify(error="Password must be at least 8 characters"), 400
    try:
        with db() as c:
            c.execute("INSERT INTO users (name, email, pw) VALUES (?,?,?)", (name, email, generate_password_hash(pw)))
    except sqlite3.IntegrityError:
        return jsonify(error="This email is already registered. Please log in."), 409
    session["user"], session["name"] = email, name
    return jsonify(ok=True, name=name)


@auth.route("/auth/login", methods=["POST"])
def login():
    b = request.json or {}
    email, pw = (b.get("email") or "").strip().lower(), b.get("password") or ""
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not row or not check_password_hash(row["pw"], pw):
        return jsonify(error="Wrong email or password"), 401
    session["user"], session["name"] = row["email"], row["name"]
    return jsonify(ok=True, name=row["name"])


@auth.route("/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify(ok=True)


@auth.route("/auth/me")
def me():
    if "user" not in session:
        return jsonify(error="not logged in"), 401
    return jsonify(email=session["user"], name=session.get("name"))
