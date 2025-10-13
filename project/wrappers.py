from flask import session, redirect, flash, url_for
from functools import wraps

def only_admins(func):
    """Allow only admin users."""
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
    """Allow only vendor users."""
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
