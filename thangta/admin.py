# thangta/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Tournament, Participant, Match

# 1. Custom User Admin
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # What columns show up in the list
    list_display = ('username', 'first_name', 'last_name', 'role', 'district', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'district')
    
    # Adding our custom fields to the edit screen
    fieldsets = UserAdmin.fieldsets + (
        ('Thang-Ta Official Info', {'fields': ('role', 'district', 'district_code')}),
    )

# 2. Tournament Admin
@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'location', 'battle_rings')
    list_filter = ('start_date', 'end_date')
    search_fields = ('name', 'location')

# 3. Participant Admin
@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('name', 'tournament', 'gender', 'age_category', 'weight_category', 'event_type', 'district')
    list_filter = ('tournament', 'gender', 'age_category', 'weight_category', 'event_type')
    search_fields = ('name', 'district', 'contact')
    
# 4. Match Admin
@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('tournament', 'ring_number', 'round_number', 'participant_red', 'participant_blue', 'winner', 'is_completed')
    list_filter = ('tournament', 'is_completed', 'ring_number', 'round_number', 'event_type', 'gender', 'age_category', 'weight_category')
    search_fields = ('participant_red__name', 'participant_blue__name')