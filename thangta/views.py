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

# Public Dashboard (No Mixin required)
class TournamentDashboardView(TemplateView):
    template_name = 'tournament_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()

        context['live_tournaments'] = Tournament.objects.filter(
            start_date__lte=today
        ).filter(Q(end_date__isnull=True) | Q(end_date__gte=today)).order_by('start_date')

        context['upcoming_tournaments'] = Tournament.objects.filter(
            start_date__gt=today
        ).order_by('start_date')

        context['past_tournaments'] = Tournament.objects.filter(
            end_date__lt=today, end_date__isnull=False
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

@admin_required
def manage_fixtures(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    
    if request.method == 'POST':
        form = FixtureGenerationForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            
            existing_matches = Match.objects.filter(
                tournament=tournament,
                event_type=data['event_type'],
                age_category=data['age_category'],
                weight_category=data['weight_category'],
                gender=data['gender']
            )
            
            if existing_matches.exists():
                messages.error(request, "Fixtures have already been generated for this category!")
            else:
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

@login_required(login_url='login')
def tournament_matches(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    
    # Fetch all matches for this tournament, ordered logically
    matches = Match.objects.filter(tournament=tournament).order_by(
        'ring_number', 
        'event_type', 
        'gender', 
        'age_category', 
        'weight_category', 
        'round_number', 
        'match_sequence'
    )
    
    return render(request, 'tournament_matches.html', {
        'tournament': tournament,
        'matches': matches
    })
    
    
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