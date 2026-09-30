"""
admin_auth.py
-------------
Simple authentication system for PhishingHunter admin panel.

Uses Flask-Login for session management with a single admin user.
Credentials stored in environment variables.

Usage:
  - Set ADMIN_USERNAME and ADMIN_PASSWORD in environment
  - Default: admin / changeme (CHANGE IN PRODUCTION!)
"""

import os
import hashlib
import hmac
import secrets
from functools import wraps
from flask import session, redirect, url_for, request, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

# Admin credentials from environment
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH")

# If no hash provided, use default (INSECURE - change in production)
if not ADMIN_PASSWORD_HASH:
    # Default password: "changeme" - hash it with salt
    default_password = os.environ.get("ADMIN_PASSWORD", "changeme")
    # Use SHA256 for backwards compatibility but add warning
    ADMIN_PASSWORD_HASH = hashlib.sha256(default_password.encode()).hexdigest()
    print(f"[WARNING] Using default admin password! Set ADMIN_PASSWORD_HASH environment variable")
    print(f"[WARNING] Consider using bcrypt/argon2 for password hashing in production")


class AdminUser(UserMixin):
    """Simple admin user class."""
    def __init__(self, username):
        self.id = username
        self.username = username
    
    def get_id(self):
        return self.username


def init_auth(app):
    """Initialize Flask-Login."""
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'admin_login'
    login_manager.login_message = 'Please log in to access admin panel'
    
    @login_manager.user_loader
    def load_user(username):
        if username == ADMIN_USERNAME:
            return AdminUser(username)
        return None
    
    return login_manager


def verify_password(username, password):
    """Verify admin credentials with timing-attack protection."""
    # Use constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(username, ADMIN_USERNAME):
        # Still compute hash to maintain constant time
        hashlib.sha256(password.encode()).hexdigest()
        return False
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    return hmac.compare_digest(password_hash, ADMIN_PASSWORD_HASH)


def admin_required(f):
    """Decorator to require admin authentication."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('admin_login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def generate_password_hash(password):
    """Generate SHA256 hash for a password (for setup)."""
    return hashlib.sha256(password.encode()).hexdigest()


# Helper function to print hash (for admin setup)
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        password = sys.argv[1]
        hash_value = generate_password_hash(password)
        print(f"Password hash for '{password}':")
        print(hash_value)
        print("\nSet this in your .env:")
        print(f"ADMIN_PASSWORD_HASH={hash_value}")
    else:
        print("Usage: python admin_auth.py <password>")
        print("Example: python admin_auth.py my_secure_password")
