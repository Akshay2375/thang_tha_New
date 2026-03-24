# thangta/views.py

# ==========================================
# 1. DJANGO IMPORTS
# ==========================================
import random
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.db.models import Q, Sum, Count
from django.contrib import messages
from django.views.generic import ListView, CreateView, DeleteView, UpdateView, TemplateView
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

# ==========================================
# 2. LOCAL IMPORTS
# ==========================================
from .models import Tournament, Participant, CustomUser, Match, Score
from .forms import TournamentForm, ParticipantFilterForm, OfficialCreationForm, FixtureGenerationForm
from .permissions import AdminRequiredMixin, admin_required, judge_required
from .services import generate_round_one_fixtures, generate_next_round


# ==========================================
# 3. PUBLIC & DASHBOARD VIEWS
# ==========================================

class TournamentDashboardView(TemplateView):
    template_name = 'tournament_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()

        context['live_tournaments'] = Tournament.objects.filter(
            start_date__lte=today
        ).filter(Q(end_date__isnull=True) | Q(end_date__gt=today)).order_by('start_date')

        context['upcoming_tournaments'] = Tournament.objects.filter(
            start_date__gt=today
        ).order_by('start_date')

        context['past_tournaments'] = Tournament.objects.filter(
            end_date__lte=today, end_date__isnull=False
        ).order_by('-end_date')

        return context

@login_required(login_url='login')
def tournament_results(request, tournament_id):
    """Publicly viewable results for completed matches."""
    tournament = get_object_or_404(Tournament, id=tournament_id)
    
    completed_matches = Match.objects.filter(
        tournament=tournament, 
        is_completed=True
    ).order_by('event_type', 'gender', 'age_category', 'weight_category', '-round_number')
    
    return render(request, 'tournament_results.html', {
        'tournament': tournament,
        'completed_matches': completed_matches
    })


# ==========================================
# 4. ADMIN: TOURNAMENT & PARTICIPANT CRUD
# ==========================================

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
    fields = ['tournament', 'name', 'actual_age', 'gender', 'contact', 'district', 'district_code', 'event_type', 'age_category', 'weight_category']
    template_name = 'participant_form.html'
    success_url = reverse_lazy('participant-list')

class ParticipantUpdateView(AdminRequiredMixin, UpdateView):
    model = Participant
    fields = ['tournament', 'name', 'actual_age', 'gender', 'contact', 'district', 'district_code', 'event_type', 'age_category', 'weight_category']
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

class OfficialCreateView(AdminRequiredMixin, CreateView):
    model = CustomUser
    form_class = OfficialCreationForm
    template_name = 'official_form.html'
    success_url = reverse_lazy('tournament-dashboard')


# ==========================================
# 5. BRACKET & MATCH MANAGEMENT
# ==========================================

 
@judge_required
def tournament_matches(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    matches = Match.objects.filter(tournament=tournament).order_by(
        'round_number', 'event_type', 'gender', 'age_category', 'weight_category', 'match_sequence'
    )
    return render(request, 'tournament_matches.html', {'tournament': tournament, 'matches': matches})


@judge_required
def update_match_winner(request, match_id):
    """Manually declares a winner and auto-generates the next round if category is complete."""
    match = get_object_or_404(Match, id=match_id)
    
    if match.is_completed:
        messages.info(request, "This match is already completed.")
        return redirect('tournament-matches', tournament_id=match.tournament.id)

    if request.method == 'POST':
        winner_id = request.POST.get('winner_id')
        if winner_id:
            winner = get_object_or_404(Participant, id=winner_id)
            if winner == match.participant_red or winner == match.participant_blue:
                match.winner = winner
                match.is_completed = True
                match.save()
                
                category_matches = Match.objects.filter(
                    tournament=match.tournament, event_type=match.event_type,
                    gender=match.gender, age_category=match.age_category,
                    weight_category=match.weight_category, round_number=match.round_number
                )
                
                if not category_matches.filter(is_completed=False).exists():
                    if category_matches.count() > 1:
                        success, msg = generate_next_round(
                            tournament=match.tournament, event_type=match.event_type,
                            age_category=match.age_category, weight_category=match.weight_category,
                            gender=match.gender, current_round=match.round_number, ring_number=match.ring_number
                        )
                        if success:
                            messages.success(request, f"🏆 {winner.name} wins! Round {match.round_number + 1} automatically generated!")
                            url = reverse('tournament-matches', args=[match.tournament.id])
                            return redirect(f"{url}?round={match.round_number + 1}")
                    else:
                        messages.success(request, f"🏆 {winner.name} wins the Final! Category Complete.")
                else:
                    messages.success(request, f"🏆 {winner.name} declared as the winner!")
                
                url = reverse('tournament-matches', args=[match.tournament.id])
                return redirect(f"{url}?round={match.round_number}")
            else:
                messages.error(request, "Invalid winner selected.")

    return render(request, 'match_update_score.html', {'match': match})

 
@judge_required
def auto_generate_next_round(request, match_id):
    reference_match = get_object_or_404(Match, id=match_id)
    if request.method == 'POST':
        latest_round = Match.objects.filter(
            tournament=reference_match.tournament, event_type=reference_match.event_type,
            age_category=reference_match.age_category, weight_category=reference_match.weight_category,
            gender=reference_match.gender
        ).order_by('-round_number').first().round_number
        
        success, msg = generate_next_round(
            tournament=reference_match.tournament, event_type=reference_match.event_type,
            age_category=reference_match.age_category, weight_category=reference_match.weight_category,
            gender=reference_match.gender, current_round=latest_round, ring_number=reference_match.ring_number
        )
        if success:
            messages.success(request, msg)
        else:
            messages.warning(request, msg)
            
    return redirect('tournament-matches', tournament_id=reference_match.tournament.id)


# ==========================================
# 6. JUDGE MAT CONTROL
# ==========================================

@judge_required
def judge_dashboard(request):
    """Shows live tournaments and lets the judge pick a ring."""
    today = timezone.now().date()
    live_tournaments = Tournament.objects.filter(
        start_date__lte=today
    ).filter(Q(end_date__isnull=True) | Q(end_date__gt=today)).order_by('start_date')
    return render(request, 'judge_dashboard.html', {'live_tournaments': live_tournaments})

@judge_required
def judge_ring_matches(request, tournament_id, ring_number):
    """Shows all matches for a specific ring in order."""
    tournament = get_object_or_404(Tournament, id=tournament_id)
    matches = Match.objects.filter(tournament=tournament, ring_number=ring_number).order_by('round_number', 'match_sequence')
    active_match = matches.filter(is_active=True, is_completed=False).first()
    
    return render(request, 'judge_ring_matches.html', {
        'tournament': tournament, 'ring_number': ring_number,
        'matches': matches, 'active_match': active_match
    })

@judge_required
def judge_generate_fixtures(request, tournament_id, ring_number):
    """Judge generates a bracket and it auto-assigns to their current ring."""
    tournament = get_object_or_404(Tournament, id=tournament_id)
    
    if request.method == 'POST':
        event_type = request.POST.get('event_type')
        gender = request.POST.get('gender')
        age_category = request.POST.get('age_category')
        weight_category = request.POST.get('weight_category')

        participants = Participant.objects.filter(
            tournament=tournament, event_type=event_type, gender=gender,
            age_category=age_category, weight_category=weight_category
        )

        num_participants = participants.count()
        if num_participants < 2:
            messages.error(request, 'Not enough participants to create a bracket.')
            return redirect('judge-generate-fixtures', tournament_id=tournament.id, ring_number=ring_number)

        participant_list = list(participants)
        random.shuffle(participant_list)

        match_seq = 1
        for i in range(0, num_participants, 2):
            p1 = participant_list[i]
            p2 = participant_list[i+1] if (i + 1) < num_participants else None

            Match.objects.create(
                tournament=tournament, participant_red=p1, participant_blue=p2,
                ring_number=ring_number, match_sequence=match_seq, round_number=1,
                gender=gender, age_category=age_category, weight_category=weight_category, event_type=event_type
            )
            match_seq += 1

        messages.success(request, f'Fixtures successfully generated for Ring {ring_number}!')
        return redirect('judge-ring-matches', tournament_id=tournament.id, ring_number=ring_number)

    return render(request, 'generate_fixtures.html', {'tournament': tournament, 'ring_number': ring_number})

@judge_required
def start_match(request, match_id):
    """Flips the match to active and redirects to the Live Panel."""
    match = get_object_or_404(Match, id=match_id)
    if request.method == 'POST':
        if not match.is_completed:
            match.is_active = True
            match.save()
            return redirect('judge-live-match', match_id=match.id)
    return redirect('judge-ring-matches', tournament_id=match.tournament.id, ring_number=match.ring_number)

@judge_required
def judge_live_match(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    score_feed = match.scores.all()
    valid_scores = score_feed.filter(is_flagged=False, is_foul=False)
    
    red_score = valid_scores.filter(participant=match.participant_red).aggregate(Sum('points'))['points__sum'] or 0
    blue_score = 0
    if match.participant_blue:
        blue_score = valid_scores.filter(participant=match.participant_blue).aggregate(Sum('points'))['points__sum'] or 0

    return render(request, 'judge_live_match.html', {
        'match': match, 'red_score': red_score, 'blue_score': blue_score, 'score_feed': score_feed
    })


# ==========================================
# 7. REAL-TIME APIs (AJAX)
# ==========================================

@judge_required
def match_live_data(request, match_id):
    """API endpoint that returns the latest scores and HTML for the event feed."""
    match = get_object_or_404(Match, id=match_id)
    
    score_feed = match.scores.all()
    valid_scores = score_feed.filter(is_flagged=False, is_foul=False)
    
    red_score = valid_scores.filter(participant=match.participant_red).aggregate(Sum('points'))['points__sum'] or 0
    blue_score = 0
    if match.participant_blue:
        blue_score = valid_scores.filter(participant=match.participant_blue).aggregate(Sum('points'))['points__sum'] or 0

    feed_html = render_to_string('partials/score_feed_rows.html', {
        'score_feed': score_feed, 'match': match
    })

    return JsonResponse({'red_score': red_score, 'blue_score': blue_score, 'feed_html': feed_html})

@judge_required
@require_POST
def toggle_score_flag(request, score_id):
    """Secretly toggles the flagged status of a score without reloading the page."""
    score = get_object_or_404(Score, id=score_id)
    score.is_flagged = not score.is_flagged
    score.save()
    return JsonResponse({'status': 'success', 'is_flagged': score.is_flagged})


# thangta/views.py

# thangta/views.py

# Make sure these are imported at the very top of views.py!
from .services import generate_round_one_fixtures, generate_next_round
from .forms import FixtureGenerationForm

@judge_required
def manage_fixtures(request, tournament_id):
    """Allows Admins and Judges to generate brackets using the services algorithms."""
    tournament = get_object_or_404(Tournament, id=tournament_id)
    
    if request.method == 'POST':
        form = FixtureGenerationForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            
            # 1. Check if ANY matches already exist for this exact category
            existing_matches = Match.objects.filter(
                tournament=tournament,
                event_type=data['event_type'],
                age_category=data['age_category'],
                weight_category=data['weight_category'],
                gender=data['gender']
            )
            
            if existing_matches.exists():
                # ROUND 2+ LOGIC: Matches exist, so we are generating the NEXT round
                latest_round = existing_matches.order_by('-round_number').first().round_number
                
                success, msg = generate_next_round(
                    tournament=tournament,
                    event_type=data['event_type'],
                    age_category=data['age_category'],
                    weight_category=data['weight_category'],
                    gender=data['gender'],
                    current_round=latest_round,
                    ring_number=data['ring_number']
                )
            else:
                # ROUND 1 LOGIC: No matches exist, generate the initial bracket
                success, msg = generate_round_one_fixtures(
                    tournament=tournament,
                    event_type=data['event_type'],
                    age_category=data['age_category'],
                    weight_category=data['weight_category'],
                    gender=data['gender'],
                    ring_number=data['ring_number']
                )
                
            # Flash the success or error message from your services.py file
            if success:
                messages.success(request, msg)
                return redirect('tournament-matches', tournament_id=tournament.id)
            else:
                messages.error(request, msg)
                return redirect('manage-fixtures', tournament_id=tournament.id)
                
    else:
        # GET REQUEST: Show the empty form
        form = FixtureGenerationForm()

    return render(request, 'manage_fixtures.html', {
        'tournament': tournament,
        'form': form
    })
    """Allows Admins and Judges to generate brackets independent of a specific ring."""
    tournament = get_object_or_404(Tournament, id=tournament_id)
    
    if request.method == 'POST':
        # Use the form to validate the incoming data
        form = FixtureGenerationForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            
            # Find eligible participants
            participants = Participant.objects.filter(
                tournament=tournament, 
                event_type=data['event_type'], 
                gender=data['gender'],
                age_category=data['age_category'], 
                weight_category=data['weight_category']
            )

            num_participants = participants.count()

            if num_participants < 2:
                messages.error(request, 'Not enough participants to create a bracket.')
                return redirect('manage-fixtures', tournament_id=tournament.id)

            # Shuffle for fair matchups
            participant_list = list(participants)
            random.shuffle(participant_list)

            # Generate Round 1 matches
            # Generate Round 1 matches
            match_seq = 1
            for i in range(0, num_participants, 2):
                p1 = participant_list[i]
                p2 = participant_list[i+1] if (i + 1) < num_participants else None

                # NEW: Check if this match is a BYE (no p2)
                is_bye = (p2 is None)

                Match.objects.create(
                    tournament=tournament, participant_red=p1, participant_blue=p2,
                    ring_number=data['ring_number'], match_sequence=match_seq, round_number=1,
                    gender=data['gender'], age_category=data['age_category'], 
                    weight_category=data['weight_category'], event_type=data['event_type'],
                    
                    # NEW: Auto-complete and assign winner if it's a BYE!
                    is_completed=is_bye,
                    winner=p1 if is_bye else None
                )
                match_seq += 1
            messages.success(request, 'Fixtures successfully generated!')
            return redirect('tournament-matches', tournament_id=tournament.id)

    else:
        # GET REQUEST: Create a fresh, empty form to send to the template!
        form = FixtureGenerationForm()

    return render(request, 'manage_fixtures.html', {
        'tournament': tournament,
        'form': form # <-- This is what makes the dropdowns appear!
    })
    """Allows Admins and Judges to generate brackets independent of a specific ring."""
    tournament = get_object_or_404(Tournament, id=tournament_id)
    
    if request.method == 'POST':
        # Grab the data from your standard form
        event_type = request.POST.get('event_type')
        gender = request.POST.get('gender')
        age_category = request.POST.get('age_category')
        weight_category = request.POST.get('weight_category')
        
        # If your form has a ring_number dropdown, we use it. Otherwise, default to 1.
        ring_number = int(request.POST.get('ring_number', 1))

        # Find eligible participants
        participants = Participant.objects.filter(
            tournament=tournament, event_type=event_type, gender=gender,
            age_category=age_category, weight_category=weight_category
        )

        num_participants = participants.count()

        if num_participants < 2:
            messages.error(request, 'Not enough participants to create a bracket.')
            return redirect('manage-fixtures', tournament_id=tournament.id)

        # Shuffle for fair matchups
        participant_list = list(participants)
        random.shuffle(participant_list)

        # Generate Round 1 matches
        match_seq = 1
        for i in range(0, num_participants, 2):
            p1 = participant_list[i]
            p2 = participant_list[i+1] if (i + 1) < num_participants else None

            Match.objects.create(
                tournament=tournament, participant_red=p1, participant_blue=p2,
                ring_number=ring_number, match_sequence=match_seq, round_number=1,
                gender=gender, age_category=age_category, weight_category=weight_category, event_type=event_type
            )
            match_seq += 1

        messages.success(request, f'Fixtures successfully generated!')
        
        # Redirect to the main Matches overview so they can see the new bracket
        return redirect('tournament-matches', tournament_id=tournament.id)

    # For GET requests, show the setup form
    # Note: If you are using Django forms, you might pass 'form': FixtureGenerationForm() here instead
    return render(request, 'manage_fixtures.html', {
        'tournament': tournament
    })