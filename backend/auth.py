import hashlib
import secrets
import time
import hmac
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
AUTH_FILE = os.path.join(DATA_DIR, "auth.json")
SECRET_FILE = os.path.join(DATA_DIR, ".secret")
SESSION_MAX_AGE = 7 * 86400


def _get_secret():
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE) as f:
            return f.read().strip()
    secret = secrets.token_hex(32)
    with open(SECRET_FILE, "w") as f:
        f.write(secret)
    return secret


SECRET = _get_secret()


def _hash(password):
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{h}"


def _verify(stored, password):
    salt, h = stored.split(":")
    return hashlib.sha256((salt + password).encode()).hexdigest() == h


def hash_password(password: str) -> str:
    return _hash(password)


def verify_password(stored: str, password: str) -> bool:
    return _verify(stored, password)


def load_credentials():
    if os.path.exists(AUTH_FILE):
        with open(AUTH_FILE) as f:
            return json.load(f)
    return None


def load_legacy_credentials():
    return load_credentials()


def save_credentials(username, password):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(AUTH_FILE, "w") as f:
        json.dump({"username": username, "password": _hash(password)}, f)


def check_login(username, password):
    cred = load_credentials()
    if not cred or cred["username"] != username:
        return False
    return _verify(cred["password"], password)


def create_token(username):
    ts = str(int(time.time()))
    payload = f"{username}:{ts}"
    sig = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def verify_token(token):
    try:
        username, ts, sig = token.rsplit(":", 2)
        expected = hmac.new(
            SECRET.encode(), f"{username}:{ts}".encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        if time.time() - int(ts) > SESSION_MAX_AGE:
            return None
        return username
    except Exception:
        return None
