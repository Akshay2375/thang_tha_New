# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    # Add 'role' to the fields displayed in the Django admin list view
    list_display = ['username', 'email', 'role', 'is_staff']
    
    # Add 'role' to the fieldsets so you can edit it in the admin panel
    fieldsets = UserAdmin.fieldsets + (
        ('Role Information', {'fields': ('role',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Role Information', {'fields': ('role',)}),
    )

admin.site.register(CustomUser, CustomUserAdmin)

# admin.py
 
from .models import Participant

@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
   
    list_display = ('district', 'district_code', 'age_category', 'weight_category')
    
    # This adds a handy filter sidebar on the right!
    list_filter = ('age_category', 'weight_category', 'district') 
    search_fields = ('district', 'district_code')