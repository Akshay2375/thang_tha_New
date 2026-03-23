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

def judge_required(view_func):
    """Decorator to ensure only logged-in Judges can access the view."""
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role == 'JUDGE':
            return view_func(request, *args, **kwargs)
        # If they aren't a judge, send them to the login page
        from django.shortcuts import redirect
        return redirect('login')
    return _wrapped_view