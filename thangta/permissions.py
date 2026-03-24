# thangta/permissions.py
from django.core.exceptions import PermissionDenied
from functools import wraps
from django.contrib.auth.mixins import AccessMixin

# ---------------------------------------------------
# 1. DECORATOR (For Function-Based Views)
# ---------------------------------------------------
def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Check if user is logged in AND has the ADMIN role
        if not request.user.is_authenticated or request.user.role != 'ADMIN':
            raise PermissionDenied  # Triggers a 403 Forbidden error
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# ---------------------------------------------------
# 2. MIXIN (For Class-Based Views)
# ---------------------------------------------------
class AdminRequiredMixin(AccessMixin):
    """Verify that the current user is authenticated and is an ADMIN."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'ADMIN':
            return self.handle_no_permission() # Redirects to login or shows 403
        return super().dispatch(request, *args, **kwargs)
    
    
    
# thangta/permissions.py

# thangta/permissions.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

def judge_required(view_func):
    """Decorator to ensure Judges OR Admins can access the view."""
    @login_required(login_url='login')
    def _wrapped_view(request, *args, **kwargs):
        
        # Check if the user is a JUDGE, an ADMIN, or a Django Superuser
        if request.user.role in ['JUDGE', 'ADMIN'] or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
            
        # If they are just a Scorer or have no permissions, send them back to the dashboard
        return redirect('tournament-dashboard') 
        
    return _wrapped_view


# thangta/permissions.py (Add to bottom)

def scorer_required(view_func):
    """Decorator to ensure Scorers (or Judges/Admins) can access the view."""
    @login_required(login_url='login')
    def _wrapped_view(request, *args, **kwargs):
        if request.user.role in ['SCORER', 'JUDGE', 'ADMIN'] or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        return redirect('tournament-dashboard') 
    return _wrapped_view