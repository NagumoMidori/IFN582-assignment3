from flask import session, redirect, flash, url_for
from functools import wraps

def only_admins(func):
    #Allow only admin users.
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = session.get('user')
        if not user:
            flash('Please log in first.', 'error')
            return redirect(url_for('main.login'))
        if not user.get('is_admin'):
            flash('You do not have permission to view this page.', 'error')
            return redirect(url_for('main.index'))
        return func(*args, **kwargs)
    return wrapper

def only_vendors(func):
    # Allow only vendor users.
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = session.get('user')
        if not user:
            flash('Please log in first.', 'error')
            return redirect(url_for('main.login'))
        if user.get('role') != 'vendor':
            flash('Vendor access required.', 'error')
            return redirect(url_for('main.index'))
        return func(*args, **kwargs)
    return wrapper

def only_guests_or_customers(func):
    # Allow access only if no user is logged in (guest) OR role == 'customer'.
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = session.get('user')
        if not user:
            # guest -> allowed
            return func(*args, **kwargs)
        if user.get('role') == 'customer':
            # logged-in customer -> allowed
            return func(*args, **kwargs)
        # vendors/admins -> block
        flash('Customers only. Please log out or use a customer account.', 'error')
        return redirect(url_for('main.index'))
    return wrapper

def only_guests(func):
    #Allow access only when no user is logged in.
    @wraps(func)
    def wrapper(*args, **kwargs):
        if session.get('user'):
            flash('You are already logged in.', 'info')
            return redirect(url_for('main.index'))
        return func(*args, **kwargs)
    return wrapper

def only_customers(func):
    # Allow access only if user is a 'customer'.
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = session.get('user')
        if not user:
            flash('Please log in first.', 'error')
            return redirect(url_for('main.login'))
        if user.get('role') != 'customer':
            flash('This page is available to customers only.', 'error')
            return redirect(url_for('main.index'))
        return func(*args, **kwargs)
    return wrapper