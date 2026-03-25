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

 
# thangta/views.py
from django.contrib.auth.decorators import login_required

@login_required(login_url='login')
def tournament_matches(request, tournament_id):
    """Unified filter-driven Fixtures and Matches page for all roles."""
    tournament = get_object_or_404(Tournament, id=tournament_id)
    
    # 1. Start with ALL matches for this tournament
    matches = Match.objects.filter(tournament=tournament)
    
    # 2. Capture the requested filters from the URL (GET parameters)
    event_type = request.GET.get('event_type', '')
    gender = request.GET.get('gender', '')
    age_category = request.GET.get('age_category', '')
    weight_category = request.GET.get('weight_category', '')
    ring_number = request.GET.get('ring_number', '')

    # 3. Apply the filters dynamically if they exist
    if event_type:
        matches = matches.filter(event_type=event_type)
    if gender:
        matches = matches.filter(gender=gender)
    if age_category:
        matches = matches.filter(age_category=age_category)
    if weight_category:
        matches = matches.filter(weight_category=weight_category)
    if ring_number:
        matches = matches.filter(ring_number=ring_number)

    # 4. Order them logically
    matches = matches.order_by('round_number', 'match_sequence')
    
    # 5. Send the current filters back to the template so the dropdowns stay selected!
    current_filters = {
        'event_type': event_type,
        'gender': gender,
        'age_category': age_category,
        'weight_category': weight_category,
        'ring_number': ring_number
    }

    return render(request, 'tournament_matches.html', {
        'tournament': tournament,
        'matches': matches,
        'current_filters': current_filters
    })

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
    
    
    
    
# thangta/views.py
from .permissions import scorer_required
from .models import Score

# ==========================================
# 8. SCORER MAT CONTROL
# ==========================================

 
 
@scorer_required
def scorer_dashboard(request):
    """Shows live tournaments for the scorer to select a ring."""
    today = timezone.now().date()
    live_tournaments = Tournament.objects.filter(
        start_date__lte=today
    ).filter(Q(end_date__isnull=True) | Q(end_date__gt=today)).order_by('start_date')
    
    return render(request, 'scorer_dashboard.html', {'live_tournaments': live_tournaments})

@scorer_required
def scorer_ring_matches(request, tournament_id, ring_number):
    """Shows the Scorer what match is currently LIVE on their ring."""
    tournament = get_object_or_404(Tournament, id=tournament_id)
    
    active_match = Match.objects.filter(
        tournament=tournament, 
        ring_number=ring_number, 
        is_active=True, 
        is_completed=False
    ).first()
    
    return render(request, 'scorer_ring_matches.html', {
        'tournament': tournament,
        'ring_number': ring_number,
        'active_match': active_match
    })

@scorer_required
def scorer_select_corner(request, match_id):
    """The intermediate page for the scorer to pick Red or Blue."""
    match = get_object_or_404(Match, id=match_id)
    
    if match.is_completed or not match.is_active:
        messages.warning(request, "This match is not currently active.")
        return redirect('scorer-dashboard')

    return render(request, 'scorer_select_corner.html', {'match': match})




@scorer_required
def scorer_panel(request, match_id):
    """The mobile-friendly, single-fighter focused scoring panel."""
    match = get_object_or_404(Match, id=match_id)
    corner = request.GET.get('corner', 'red') 
    
    if match.is_completed or not match.is_active:
        messages.warning(request, "This match is not currently active.")
        return redirect('scorer-dashboard')

    if corner == 'blue' and not match.participant_blue:
        messages.error(request, "Invalid corner selected.")
        return redirect('scorer-select-corner', match_id=match.id)

    current_sub_round = getattr(match, 'current_sub_round', 1)
    
    participant = match.participant_red if corner == 'red' else match.participant_blue
    valid_scores = Score.objects.filter(
        match=match, participant=participant, is_flagged=False, is_foul=False, sub_round=current_sub_round
    ).order_by('timestamp')
    
    points_list = [str(s.points) for s in valid_scores]
    points_string = " + ".join(points_list) if points_list else ""
    total_score = sum(s.points for s in valid_scores)
    
    # NEW: Count how many times they have actually scored
    db_score_count = valid_scores.count()

    return render(request, 'scorer_panel.html', {
        'match': match,
        'corner': corner,
        'current_sub_round': current_sub_round, 
        'points_string': points_string,
        'total_score': total_score,
        'db_score_count': db_score_count, # Pass the count to the frontend!
    })

@scorer_required
@require_POST
def submit_score(request, match_id):
    """AJAX endpoint to receive and save a score/foul."""
    match = get_object_or_404(Match, id=match_id)
    
    participant_id = request.POST.get('participant_id')
    is_foul = request.POST.get('is_foul') == 'true'
    foul_reason = request.POST.get('foul_reason', '')

    participant = get_object_or_404(Participant, id=participant_id)
    current_sub_round = getattr(match, 'current_sub_round', 1)

    if is_foul:
        Score.objects.create(
            match=match, participant=participant, scorer=request.user,
            points=-3, is_foul=True, foul_reason=foul_reason, sub_round=current_sub_round 
        )
    else:
        points_str = request.POST.get('points', '')
        if points_str:
            
            incoming_points = []
            for p_str in points_str.split(','):
                try:
                    p = int(p_str.strip())
                    if p > 0:
                        incoming_points.append(p)
                except ValueError:
                    pass
            
            # NEW: Check how many ENTRIES they already have, not the sum of points!
            existing_count = Score.objects.filter(
                match=match, participant=participant, is_flagged=False, is_foul=False, sub_round=current_sub_round
            ).count()
            
            if existing_count + len(incoming_points) > 3:
                return JsonResponse({'status': 'error', 'message': f'Max 3 score entries allowed per sub-round.'})
            
            for p in incoming_points:
                Score.objects.create(
                    match=match, participant=participant, scorer=request.user,
                    points=p, is_foul=False, sub_round=current_sub_round 
                )
    
    return JsonResponse({'status': 'success'})

@scorer_required
@require_POST
def submit_score(request, match_id):
    """AJAX endpoint to receive and save a score/foul."""
    match = get_object_or_404(Match, id=match_id)
    
    participant_id = request.POST.get('participant_id')
    is_foul = request.POST.get('is_foul') == 'true'
    foul_reason = request.POST.get('foul_reason', '')

    participant = get_object_or_404(Participant, id=participant_id)
    current_sub_round = getattr(match, 'current_sub_round', 1)

    if is_foul:
        # Save a single foul
        Score.objects.create(
            match=match, participant=participant, scorer=request.user,
            points=-3, is_foul=True, foul_reason=foul_reason, sub_round=current_sub_round 
        )
    else:
        # Save multiple points sent as a combo string (e.g., "1,2,1")
        points_str = request.POST.get('points', '')
        if points_str:
            for p_str in points_str.split(','):
                try:
                    p = int(p_str.strip())
                    if p > 0:
                        Score.objects.create(
                            match=match, participant=participant, scorer=request.user,
                            points=p, is_foul=False, sub_round=current_sub_round 
                        )
                except ValueError:
                    continue
    
    return JsonResponse({'status': 'success'})
@scorer_required
def fetch_score_history(request, match_id):
    """AJAX endpoint to return the score history table snippet."""
    match = get_object_or_404(Match, id=match_id)
    
    # NEW: Only show the history for the corner the scorer is currently sitting at!
    corner = request.GET.get('corner', 'red')
    participant = match.participant_red if corner == 'red' else match.participant_blue
    
    scores = Score.objects.filter(match=match, participant=participant, is_foul=False).order_by('-timestamp')
    
    response = render(request, 'scorer_history_table.html', {'scores': scores})
    # Attach the sub-round for the auto-refresh check
    response['X-Current-Sub-Round'] = getattr(match, 'current_sub_round', 1)
    return response

@scorer_required
def fetch_foul_history(request, match_id):
    """AJAX endpoint to return the foul history table snippet."""
    match = get_object_or_404(Match, id=match_id)
    
    # NEW: Only show the history for the corner the scorer is currently sitting at!
    corner = request.GET.get('corner', 'red')
    participant = match.participant_red if corner == 'red' else match.participant_blue
    
    fouls = Score.objects.filter(match=match, participant=participant, is_foul=True).order_by('-timestamp')
    
    return render(request, 'scorer_foul_table.html', {'fouls': fouls})
@judge_required
def update_match_winner(request, match_id):
    """Manually declares a winner, frees the ring, and auto-generates the next round."""
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
                
                # NEW: Free up the ring!
                match.is_active = False 
                match.save()
                
                # ... (The rest of your auto-generate next round logic stays exactly the same!)
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
                
                # Go back to the Judge's Ring Dashboard so they can start the next fight!
                return redirect('judge-ring-matches', tournament_id=match.tournament.id, ring_number=match.ring_number)
            else:
                messages.error(request, "Invalid winner selected.")
    valid_scores = match.scores.filter(is_flagged=False, is_foul=False)
    red_score = valid_scores.filter(participant=match.participant_red).aggregate(Sum('points'))['points__sum'] or 0
    blue_score = 0
    if match.participant_blue:
        blue_score = valid_scores.filter(participant=match.participant_blue).aggregate(Sum('points'))['points__sum'] or 0
    return render(request, 'match_update_score.html', {'match': match,'red_score': red_score,
        'blue_score': blue_score})