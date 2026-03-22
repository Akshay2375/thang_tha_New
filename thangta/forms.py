# thangta/forms.py
from django import forms
from .models import Participant

class ParticipantFilterForm(forms.Form):
    # Standard choice fields for predefined lists
    
    # CHANGED: Participant.AgeGroupChoices.choices -> Participant.AgeCategory.choices
    age_group = forms.ChoiceField(
        choices=[('', 'All Age Groups')] + Participant.AgeCategory.choices,
        required=False,
        label="Age Group"
    )
    
    gender = forms.ChoiceField(
        choices=[('', 'Both Gender')] + Participant.GenderChoices.choices,
        required=False,
        label="Gender"
    )
    
    # CHANGED: Participant.WeightCategoryChoices.choices -> Participant.WeightCategory.choices
    weight_category = forms.ChoiceField(
        choices=[('', 'All Weight Categories')] + Participant.WeightCategory.choices,
        required=False,
        label="Weight Category"
    )
    
    event_type = forms.ChoiceField(
        choices=[('', 'All Event Types')] + Participant.EventTypeChoices.choices,
        required=False,
        label="Event Type"
    )

    # DYNAMIC CHOICE FIELD for District (Populated in __init__)
    district = forms.ChoiceField(choices=[], required=False, label="District")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Query distinct districts and create choices directly from the database
        distinct_districts = Participant.objects.values_list('district', flat=True).distinct().order_by('district')
        
        # Add 'All Districts' option followed by dynamic choices
        district_choices = [('', 'All Districts')] + [(d, d) for d in distinct_districts if d] 
        self.fields['district'].choices = district_choices
        
        
 
# thangta/forms.py
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser

class OfficialCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        # NEW: Added 'district' and 'district_code' to the list
        fields = ('username', 'first_name', 'last_name', 'role', 'district', 'district_code')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = [
            (CustomUser.Role.JUDGE, 'Judge'),
            (CustomUser.Role.SCORER, 'Scorer'),
        ]
        
        
# thangta/forms.py
from django import forms
from .models import Tournament

class TournamentForm(forms.ModelForm):
    class Meta:
        model = Tournament
        # Notice we REMOVED end_date from this list so it doesn't show up on creation!
        fields = ['name', 'start_date', 'location', 'battle_rings']
        widgets = {
            # This line forces the browser to show a calendar picker
            'start_date': forms.DateInput(attrs={'type': 'date'}), 
        }
        
        
        
        
# thangta/forms.py
from django import forms
from .models import Participant

# ... your existing forms ...

class FixtureGenerationForm(forms.Form):
    event_type = forms.ChoiceField(
        choices=Participant.EventTypeChoices.choices, 
        label="Event Type"
    )
    gender = forms.ChoiceField(
        choices=Participant.GenderChoices.choices, 
        label="Gender"
    )
    age_category = forms.ChoiceField(
        choices=Participant.AgeCategory.choices, 
        label="Age Category"
    )
    weight_category = forms.ChoiceField(
        choices=Participant.WeightCategory.choices, 
        label="Weight Category"
    )
    ring_number = forms.IntegerField(
        min_value=1, 
        initial=1, 
        label="Assign to Ring Number",
        help_text="Which ring will this category fight in?"
    )