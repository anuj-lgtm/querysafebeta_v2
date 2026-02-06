from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from urllib.parse import urlparse, urlunparse

def redirect_authenticated_user(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if 'user_id' in request.session:
            messages.info(request, 'You are already logged in!')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper

def login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if 'user_id' not in request.session:
            messages.error(request, 'Login required to access this page.')
            
            # Get current path for redirect after login
            current_path = request.get_full_path()
            
            # Store the path in session
            request.session['next_url'] = current_path
            
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper