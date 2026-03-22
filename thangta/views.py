# thangta/views.py

# --- 1. DJANGO IMPORTS ---
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Q
from django.contrib import messages
from django.views.generic import ListView, CreateView, DeleteView, UpdateView, TemplateView

# --- 2. LOCAL IMPORTS ---
from .models import Tournament, Participant, CustomUser, Match
from .forms import TournamentForm, ParticipantFilterForm, OfficialCreationForm, FixtureGenerationForm
from .permissions import AdminRequiredMixin, admin_required
from .services import generate_round_one_fixtures

# ==========================================
# TOURNAMENT VIEWS
# ==========================================

# thangta/views.py

class TournamentDashboardView(TemplateView):
    template_name = 'tournament_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()

        # LIVE: Started today or earlier AND (has NO end date OR ends strictly after today)
        context['live_tournaments'] = Tournament.objects.filter(
            start_date__lte=today
        ).filter(Q(end_date__isnull=True) | Q(end_date__gt=today)).order_by('start_date')

        # UPCOMING: Starts strictly after today
        context['upcoming_tournaments'] = Tournament.objects.filter(
            start_date__gt=today
        ).order_by('start_date')

        # PAST: Has an end date AND that end date is today or earlier
        context['past_tournaments'] = Tournament.objects.filter(
            end_date__lte=today, end_date__isnull=False
        ).order_by('-end_date')

        return context
class TournamentListView(AdminRequiredMixin, ListView):
    model = Tournament
    template_name = 'tournament_list.html'
    context_object_name = 'tournaments'
    
class TournamentCreateView(AdminRequiredMixin, CreateView):
    model = Tournament
    form_class = TournamentForm
    template_name = 'tournament_form.html'
    success_url = reverse_lazy('tournament-dashboard')

@admin_required
def end_tournament(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    tournament.end_date = timezone.now().date()
    tournament.save()
    return redirect('tournament-dashboard')

class TournamentDeleteView(AdminRequiredMixin, DeleteView):
    model = Tournament
    template_name = 'tournament_confirm_delete.html'
    success_url = reverse_lazy('tournament-list')

# ==========================================
# PARTICIPANT VIEWS
# ==========================================

class ParticipantListView(AdminRequiredMixin, ListView):
    model = Participant
    template_name = 'participant_list.html'
    context_object_name = 'participants'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        self.filter_form = ParticipantFilterForm(self.request.GET)

        if self.filter_form.is_valid():
            data = self.filter_form.cleaned_data
            if data.get('age_group'):
                queryset = queryset.filter(age_category=data['age_group'])
            if data.get('gender'):
                queryset = queryset.filter(gender=data['gender'])
            if data.get('district'):
                queryset = queryset.filter(district=data['district'])
            if data.get('event_type'):
                queryset = queryset.filter(event_type=data['event_type'])
            if data.get('weight_category'):
                queryset = queryset.filter(weight_category=data['weight_category'])
                
        return queryset.order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filter_form
        return context

class ParticipantCreateView(AdminRequiredMixin, CreateView):
    model = Participant
    fields = [
        'tournament', 'name', 'actual_age', 'gender', 'contact', 
        'district', 'district_code', 'event_type', 'age_category', 'weight_category'
    ]
    template_name = 'participant_form.html'
    success_url = reverse_lazy('participant-list')

class ParticipantUpdateView(AdminRequiredMixin, UpdateView):
    model = Participant
    fields = [
        'tournament', 'name', 'actual_age', 'gender', 'contact', 
        'district', 'district_code', 'event_type', 'age_category', 'weight_category'
    ]
    template_name = 'participant_form.html'
    success_url = reverse_lazy('participant-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_update'] = True 
        return context

class ParticipantDeleteView(AdminRequiredMixin, DeleteView):
    model = Participant
    template_name = 'participant_confirm_delete.html'
    success_url = reverse_lazy('participant-list')

# ==========================================
# OFFICIALS & FIXTURE VIEWS
# ==========================================

class OfficialCreateView(AdminRequiredMixin, CreateView):
    model = CustomUser
    form_class = OfficialCreationForm
    template_name = 'official_form.html'
    success_url = reverse_lazy('tournament-dashboard')

# thangta/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Tournament, Match
from .forms import FixtureGenerationForm
from .permissions import admin_required

# Make sure you import BOTH algorithms here!
from .services import generate_round_one_fixtures, generate_next_round 

@admin_required
def manage_fixtures(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    
    if request.method == 'POST':
        form = FixtureGenerationForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            
            # Find all matches for this specific category
            existing_matches = Match.objects.filter(
                tournament=tournament,
                event_type=data['event_type'],
                age_category=data['age_category'],
                weight_category=data['weight_category'],
                gender=data['gender']
            )
            
            if existing_matches.exists():
                # ROUND 2+ LOGIC
                # Find the highest round number currently generated
                latest_round = existing_matches.order_by('-round_number').first().round_number
                
                # Trigger the next round algorithm
                success, msg = generate_next_round(
                    tournament=tournament,
                    event_type=data['event_type'],
                    age_category=data['age_category'],
                    weight_category=data['weight_category'],
                    gender=data['gender'],
                    current_round=latest_round,
                    ring_number=data['ring_number']
                )
                
                if success:
                    messages.success(request, msg)
                else:
                    messages.warning(request, msg) # Warns if current matches aren't finished yet
            else:
                # ROUND 1 LOGIC (First time generating)
                success, msg = generate_round_one_fixtures(
                    tournament=tournament,
                    event_type=data['event_type'],
                    age_category=data['age_category'],
                    weight_category=data['weight_category'],
                    gender=data['gender'],
                    ring_number=data['ring_number']
                )
                
                if success:
                    messages.success(request, msg)
                else:
                    messages.warning(request, msg) 
                    
            return redirect('manage-fixtures', tournament_id=tournament.id)
    else:
        form = FixtureGenerationForm()

    return render(request, 'manage_fixtures.html', {
        'form': form, 
        'tournament': tournament
    })
    
# thangta/views.py
from django.contrib.auth.decorators import login_required
# Make sure you import Match at the top if you haven't already!
from .models import Match 

# thangta/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from .models import Tournament, Match
from .permissions import admin_required
from .services import generate_next_round

@admin_required
def tournament_matches(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    
    # 1. Find all distinct rounds that exist for this tournament
    # We convert to a set and back to a sorted list to get unique rounds like [1, 2, 3]
    rounds_list = Match.objects.filter(tournament=tournament).values_list('round_number', flat=True)
    rounds = sorted(list(set(rounds_list)))
    
    # 2. Get the requested round from the URL (e.g., ?round=2). Default to the latest round.
    current_round = int(request.GET.get('round', rounds[-1] if rounds else 1))
    
    # 3. Filter matches to ONLY show the selected round
    matches = Match.objects.filter(tournament=tournament, round_number=current_round).order_by(
        'ring_number', 'event_type', 'gender', 'age_category', 'weight_category', 'match_sequence'
    )
    
    # 4. Check if ALL matches in this specific round are completed
    # If there are matches, and NONE of them are incomplete, it's safe to advance!
    can_generate_next_round = matches.exists() and not matches.filter(is_completed=False).exists()
    
    return render(request, 'tournament_matches.html', {
        'tournament': tournament,
        'matches': matches,
        'rounds': rounds,
        'current_round': current_round,
        'can_generate_next_round': can_generate_next_round
    })

@admin_required
def generate_next_round_all(request, tournament_id, current_round):
    """Master button logic: Generates the next round for ALL categories in the current round."""
    tournament = get_object_or_404(Tournament, id=tournament_id)
    
    if request.method == 'POST':
        # Find all unique categories that fought in this round
        matches_in_round = Match.objects.filter(tournament=tournament, round_number=current_round)
        categories = matches_in_round.values(
            'event_type', 'age_category', 'weight_category', 'gender', 'ring_number'
        ).distinct()
        
        success_count = 0
        
        # Run your algorithm for every single category
        for cat in categories:
            success, msg = generate_next_round(
                tournament=tournament,
                event_type=cat['event_type'],
                age_category=cat['age_category'],
                weight_category=cat['weight_category'],
                gender=cat['gender'],
                current_round=current_round,
                ring_number=cat['ring_number']
            )
            if success:
                success_count += 1
                
        if success_count > 0:
            messages.success(request, f"🔥 Successfully generated Round {current_round + 1} for {success_count} categories!")
        else:
            messages.info(request, "Tournament complete! No more matches to generate.")
            
    # Redirect back to the matches page, automatically jumping to the NEW round tab!
    url = reverse('tournament-matches', args=[tournament.id])
    return redirect(f"{url}?round={current_round + 1}")




# thangta/views.py
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from .models import Match, Participant
from .permissions import admin_required

@admin_required
def update_match_winner(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    
    # If it's a BYE or already finished, send them back to the list
    if match.is_completed:
        messages.info(request, "This match is already completed.")
        return redirect('tournament-matches', tournament_id=match.tournament.id)

    if request.method == 'POST':
        # Grab the ID of the participant they clicked
        winner_id = request.POST.get('winner_id')
        
        if winner_id:
            winner = get_object_or_404(Participant, id=winner_id)
            
            # Security check: Make sure the chosen winner is actually in this match!
            if winner == match.participant_red or winner == match.participant_blue:
                match.winner = winner
                match.is_completed = True
                match.save()
                
                messages.success(request, f"🏆 {winner.name} declared as the winner!")
                return redirect('tournament-matches', tournament_id=match.tournament.id)
            else:
                messages.error(request, "Invalid winner selected.")

    return render(request, 'match_update_score.html', {'match': match})




# thangta/views.py

# Make sure you have generate_next_round imported at the top!
from .services import generate_next_round 

@admin_required
def auto_generate_next_round(request, match_id):
    # Get the match the Admin clicked on
    reference_match = get_object_or_404(Match, id=match_id)
    
    if request.method == 'POST':
        # 1. Find the highest round currently generated for this EXACT category
        latest_round = Match.objects.filter(
            tournament=reference_match.tournament,
            event_type=reference_match.event_type,
            age_category=reference_match.age_category,
            weight_category=reference_match.weight_category,
            gender=reference_match.gender
        ).order_by('-round_number').first().round_number
        
        # 2. Trigger the algorithm using the latest round
        success, msg = generate_next_round(
            tournament=reference_match.tournament,
            event_type=reference_match.event_type,
            age_category=reference_match.age_category,
            weight_category=reference_match.weight_category,
            gender=reference_match.gender,
            current_round=latest_round,
            ring_number=reference_match.ring_number
        )
        
        # 3. Flash the success or warning message
        if success:
            messages.success(request, msg)
        else:
            messages.warning(request, msg)
            
    # Redirect right back to the matches page!
    return redirect('tournament-matches', tournament_id=reference_match.tournament.id)

