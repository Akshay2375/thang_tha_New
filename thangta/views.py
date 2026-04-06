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

# @login_required(login_url='login')
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
    pagination_class = None
    
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


from django.shortcuts import redirect
from .permissions import *
# (Keep your existing imports)
from django.shortcuts import redirect
# Keep your existing imports...

class ParticipantListView(AdminOrJudgeRequiredMixin, ListView):
    model = Participant
    template_name = 'participant_list.html'
    context_object_name = 'participants'

    def get(self, request, *args, **kwargs):
        # 1. HANDLE THE CLEAR BUTTON
        if request.GET.get('clear') == 'true':
            keys = ['f_age', 'f_gender', 'f_district', 'f_event', 'f_weight']
            for key in keys:
                request.session.pop(key, None)
            # Strip the ?clear=true from the URL so it doesn't get stuck in a loop
            return redirect(request.path)
            
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # 1. THE ROBUST CHECK 
        # Instead of looking for a hidden 'action' input, just check if ANY filter parameters are in the URL!
        filter_keys = ['age_group', 'gender', 'district', 'event_type', 'weight_category']
        is_filtering = any(key in self.request.GET for key in filter_keys)
        
        if is_filtering:
            form_data = self.request.GET
            
            # Save the raw choices into the session memory
            self.request.session['f_age'] = self.request.GET.get('age_group', '')
            self.request.session['f_gender'] = self.request.GET.get('gender', '')
            self.request.session['f_district'] = self.request.GET.get('district', '')
            self.request.session['f_event'] = self.request.GET.get('event_type', '')
            self.request.session['f_weight'] = self.request.GET.get('weight_category', '')
        else:
            # Rebuild the form data from the session memory
            form_data = {
                'age_group': self.request.session.get('f_age', ''),
                'gender': self.request.session.get('f_gender', ''),
                'district': self.request.session.get('f_district', ''),
                'event_type': self.request.session.get('f_event', ''),
                'weight_category': self.request.session.get('f_weight', ''),
            }

        # Bind the data to the form so the HTML dropdowns stay visually selected!
        self.filter_form = ParticipantFilterForm(form_data)

        # Force all fields to be optional so is_valid() NEVER fails on empty dropdowns
        for field_name, field in self.filter_form.fields.items():
            field.required = False

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
        # Pass the processed form to the HTML
        context['filter_form'] = self.filter_form
        return context


class ParticipantCreateView(AdminOrJudgeRequiredMixin, CreateView):
    model = Participant
    fields = ['tournament', 'name', 'actual_age', 'gender', 'contact', 'district', 'district_code', 'event_type', 'age_category', 'weight_category']
    template_name = 'participant_form.html'
    success_url = reverse_lazy('participant-list')

class ParticipantUpdateView(AdminOrJudgeRequiredMixin, UpdateView):
    model = Participant
    fields = ['tournament', 'name', 'actual_age', 'gender', 'contact', 'district', 'district_code', 'event_type', 'age_category', 'weight_category']
    template_name = 'participant_form.html'
    success_url = reverse_lazy('participant-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_update'] = True 
        return context

class ParticipantDeleteView(AdminOrJudgeRequiredMixin, DeleteView):
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

# @login_required(login_url='login')
# def tournament_matches(request, tournament_id):
#     """Unified filter-driven Fixtures and Matches page for all roles."""
#     tournament = get_object_or_404(Tournament, id=tournament_id)
    
#     # 1. Start with ALL matches for this tournament
#     matches = Match.objects.filter(tournament=tournament)
    
#     # 2. Capture the requested filters from the URL (GET parameters)
#     event_type = request.GET.get('event_type', '')
#     gender = request.GET.get('gender', '')
#     age_category = request.GET.get('age_category', '')
#     weight_category = request.GET.get('weight_category', '')
#     ring_number = request.GET.get('ring_number', '')

#     # 3. Apply the filters dynamically if they exist
#     if event_type:
#         matches = matches.filter(event_type=event_type)
#     if gender:
#         matches = matches.filter(gender=gender)
#     if age_category:
#         matches = matches.filter(age_category=age_category)
#     if weight_category:
#         matches = matches.filter(weight_category=weight_category)
#     if ring_number:
#         matches = matches.filter(ring_number=ring_number)

#     # 4. Order them logically
#     matches = matches.order_by('round_number', 'match_sequence')
    
#     # 5. Send the current filters back to the template so the dropdowns stay selected!
#     current_filters = {
#         'event_type': event_type,
#         'gender': gender,
#         'age_category': age_category,
#         'weight_category': weight_category,
#         'ring_number': ring_number
#     }

#     return render(request, 'tournament_matches.html', {
#         'tournament': tournament,
#         'matches': matches,
#         'current_filters': current_filters
#     })

from django.views.decorators.http import require_POST
# Make sure your other imports (redirect, get_object_or_404, etc.) are still there!

@judge_required
@require_POST  # 👈 This forces the view to ONLY accept direct button clicks!
def update_match_winner(request, match_id):
    """Instantly declares a winner, calculates scores, flushes temp data, and auto-generates."""
    match = get_object_or_404(Match, id=match_id)
    
    if match.is_completed:
        messages.info(request, "This match is already completed.")
        return redirect('tournament-matches', tournament_id=match.tournament.id)

    winner_id = request.POST.get('winner_id')
    if winner_id:
        winner = get_object_or_404(Participant, id=winner_id)
        if winner == match.participant_red or winner == match.participant_blue:
            
            # 1. Calculate & Save
            final_red = calculate_corner_score(match, match.participant_red)
            final_blue = calculate_corner_score(match, match.participant_blue)
            
            match.score_red = final_red
            match.score_blue = final_blue
            match.winner = winner
            match.is_completed = True
            match.save()
            
            # 2. Flush Temp Data
            Score.objects.filter(match=match).delete()
            
            # 3. Auto-Generate Next Round Logic
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
                        messages.success(request, f"🏆 {winner.name} wins ({final_red} - {final_blue})! Round {match.round_number + 1} generated!")
                        url = reverse('tournament-matches', args=[match.tournament.id])
                        return redirect(f"{url}?round={match.round_number + 1}")
                else:
                    messages.success(request, f"🏆 {winner.name} wins the Final ({final_red} - {final_blue})! Category Complete.")
            else:
                messages.success(request, f"🏆 {winner.name} declared as the winner ({final_red} - {final_blue})!")
            
            url = reverse('tournament-matches', args=[match.tournament.id])
            return redirect(f"{url}?round={match.round_number}")
        else:
            messages.error(request, "Invalid winner selected.")

    # Fallback if something goes wrong (no need to render an HTML page anymore)
    return redirect('tournament-matches', tournament_id=match.tournament.id)
# thangta/views.py

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import Match
from .services import generate_next_round  # <--- MUST ADD THIS IMPORT

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

from django.shortcuts import redirect

@judge_required  # Keep whatever security decorator you currently have here!
def judge_dashboard(request):
    """
    The old intermediate ring selection page is obsolete.
    Instantly route Judges directly to the Master Fixtures list so they can see all matches.
    """
    # Bounce them straight to the global bracket!
    return redirect('global-fixtures') 
    
    # Or, if you prefer they land on the main home screen instead:
    # return redirect('tournament-dashboard')

import random
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Max
# Make sure to import your models!

@judge_required
def judge_generate_fixtures(request, tournament_id, ring_number):
    """Judge generates a bracket and it safely auto-assigns to the end of their current ring's schedule."""
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

        # FIX 1: Find the highest match sequence currently in this ring so we don't overlap!
        current_max_seq = Match.objects.filter(
            tournament=tournament, 
            ring_number=ring_number
        ).aggregate(Max('match_sequence'))['match_sequence__max']
        
        # If there are no matches yet, start at 1. Otherwise, start after the last match.
        match_seq = 1 if current_max_seq is None else current_max_seq + 1

        for i in range(0, num_participants, 2):
            p1 = participant_list[i]
            p2 = participant_list[i+1] if (i + 1) < num_participants else None
            
            # FIX 2: If p2 is None, this is a "Bye". We instantly mark the match as completed!
            is_bye = (p2 is None)

            Match.objects.create(
                tournament=tournament, 
                participant_red=p1, 
                participant_blue=p2,
                ring_number=ring_number, 
                match_sequence=match_seq, 
                round_number=1,
                gender=gender, 
                age_category=age_category, 
                weight_category=weight_category, 
                event_type=event_type,
                
                # If it's a bye, auto-complete it and declare p1 the winner!
                is_completed=is_bye,
                winner=p1 if is_bye else None
            )
            match_seq += 1

        messages.success(request, f'Fixtures successfully generated and added to Ring {ring_number} schedule!')
        return redirect('judge-ring-matches', tournament_id=tournament.id, ring_number=ring_number)

    return render(request, 'generate_fixtures.html', {'tournament': tournament, 'ring_number': ring_number})

@judge_required
def start_match(request, match_id):
    """Flips the match to active and redirects to the Live Panel."""
    match = get_object_or_404(Match, id=match_id)
    
    if not match.participant_blue:
        match.winner = match.participant_red
        match.is_completed = True
        match.save()
        
        # Call your auto-advance logic if you have it imported
        try:
            from .utils import auto_advance_winner # Or wherever your logic lives
            auto_advance_winner(match)
        except Exception as e:
            print("Auto advance skipped/failed:", e)
            
        messages.success(request, f"BYE Match auto-completed. {match.participant_red.name} advances!")
        return redirect('tournament-matches', tournament_id=match.tournament.id)
    
    
    
    if request.method == 'POST':
        if not match.is_completed:
            match.is_active = True
            match.save()
            return redirect('judge-live-match', match_id=match.id)
    return redirect('judge-ring-matches', tournament_id=match.tournament.id, ring_number=match.ring_number)

@judge_required
def judge_live_match(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    
    # ==========================================
    # 🚨 THE ZOMBIE BYE KILLER 🚨
    # If the match somehow became "Live" but has no blue opponent, 
    # kill the live status and auto-win the match.
    # ==========================================
    if not match.participant_blue:
        match.winner = match.participant_red
        match.is_completed = True
        match.is_active = False  # Turn off the "LIVE MATCH" badge!
        match.save()
        
        # Try to auto-advance if you have that logic built
        try:
            from .utils import auto_advance_winner
            auto_advance_winner(match)
        except Exception:
            pass
            
        messages.success(request, f"{match.participant_red.name} automatically advances due to BYE!")
        return redirect('tournament-matches', tournament_id=match.tournament.id)
    # ==========================================
    score_feed = match.scores.all()
    valid_scores = score_feed.filter(is_flagged=False, is_foul=False)
    # sub_round=
    
    red_score = valid_scores.filter(participant=match.participant_red).aggregate(Sum('points'))['points__sum'] or 0
    blue_score = 0
    if match.participant_blue:
        blue_score = valid_scores.filter(participant=match.participant_blue).aggregate(Sum('points'))['points__sum'] or 0
        
    
    red_scores = list(Score.objects.filter(match=match, participant=match.participant_red).order_by('timestamp'))

# 2. THE FIX: Dynamically assign the correct Queue Sub-Round!
# (index // 3) + 1 ensures that scores 0,1,2 become Sub-Round 1. Scores 3,4,5 become Sub-Round 2.
    for index, score in enumerate(red_scores):
        score.display_sub_round = (index // 3) + 1

    # 3. Reverse it so the newest scores appear at the top of the table
    red_scores.reverse()

    # Do the exact same thing for the Blue corner
    blue_scores = list(Score.objects.filter(match=match, participant=match.participant_blue).order_by('timestamp'))
    for index, score in enumerate(blue_scores):
        score.display_sub_round = (index // 3) + 1
    blue_scores.reverse()

    return render(request, 'judge_live_match.html', {
            'match': match, 'red_score': red_score, 'blue_score': blue_score, 'score_feed': score_feed
    })


# ==========================================
# 7. REAL-TIME APIs (AJAX)
# ==========================================



from django.template.loader import render_to_string
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import redirect

import math
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
import math


from django.template.loader import render_to_string
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string

def process_sub_rounds(match, participant):
    """Helper function: Calculates sub-rounds dynamically based on timestamps."""
    if not participant:
        return [], []
        
    # Get ALL scores for this participant, ordered oldest to newest
    all_scores = list(Score.objects.filter(match=match, participant=participant).order_by('timestamp'))
    
    history_current_round = []
    all_fouls = []
    
    # Process round by round so the sub-round resets to 1 each time
    for r in range(1, match.current_round + 1):
        round_scores = [s for s in all_scores if s.round_num == r]
        if not round_scores: continue
        
        current_sub = 1
        last_time = round_scores[0].timestamp
        last_scorer = round_scores[0].scorer_id
        
        for score in round_scores:
            time_diff = abs((score.timestamp - last_time).total_seconds())
            # If submitted by a different scorer, or more than 1.5 seconds apart, it's a new sub-round!
            if score.scorer_id != last_scorer or time_diff > 1.5:
                current_sub += 1
            
            # Attach the dynamic sub-round to the object
            score.display_sub_round = current_sub
            last_time = score.timestamp
            last_scorer = score.scorer_id
            
            # Sort into our lists
            if score.is_foul:
                all_fouls.append(score)
            if r == match.current_round:
                history_current_round.append(score)
                
    # Reverse them so the newest scores appear at the top of the feed
    history_current_round.reverse()
    all_fouls.reverse()
    
    return history_current_round, all_fouls
from django.template.loader import render_to_string
from django.http import JsonResponse
from . import state

@judge_required
def match_live_data(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    
    # Grab the data from the Memory Engine instead of the Database
    with state.state_lock:
        match_live = state.liveState.get(match.id, {})
        match_totals = state.total.get(match.id, {})
        
        # 1. Giant Numbers
        total_red = sum(rnd.get('red', 0) for rnd in match_totals.values())
        total_blue = sum(rnd.get('blue', 0) for rnd in match_totals.values())
        
        # 2. Round-wise Totals
        round_summary = []
        for r in range(1, int(match.current_round) + 1):
            r_red = match_totals.get(r, {}).get('red', 0)
            r_blue = match_totals.get(r, {}).get('blue', 0)
            
            round_summary.append({
                'round': r,
                'status': 'In Progress' if r == int(match.current_round) else 'Completed',
                'red_total': r_red,
                'blue_total': r_blue,
            })
            
        # 3. Process Scores On-The-Fly! (Translating RAM data for your templates)
        red_history = []
        blue_history = []
        
        # We loop through the RAM state and package it exactly how your old process_sub_rounds did
        for rnd_num, subrounds in match_live.items():
            for sub_num, sr_data in sorted(subrounds.items()):
                red_data = sr_data.get('red', {})
                blue_data = sr_data.get('blue', {})
                
                # Only pass COMPLETE scores to your template to prevent partial math bugs
                if red_data.get('status') == 'COMPLETE':
                    red_history.append({
                        'round_num': rnd_num,
                        'sub_round': sub_num,
                        'points': red_data.get('average', 0),
                        'scorer': 'Avg', # Fallback in case your template prints the scorer name
                    })
                    
                if blue_data.get('status') == 'COMPLETE':
                    blue_history.append({
                        'round_num': rnd_num,
                        'sub_round': sub_num,
                        'points': blue_data.get('average', 0),
                        'scorer': 'Avg',
                    })

    # === YOUR ORIGINAL TEMPLATE RENDERING (UNCHANGED) ===
    summary_html = render_to_string('partials/round_summary_cards.html', {
        'round_summary': round_summary,
        'match': match
    }, request=request)
    
    feed_html = render_to_string('partials/score_feed_rows.html', {
        'red_scores': red_history,
        'blue_scores': blue_history,
        'match': match
    }, request=request)
    
    foul_html = render_to_string('partials/foul_feed_rows.html', {
        'red_fouls': [],  # Fouls are now calculated into the averages automatically
        'blue_fouls': [],
        'match': match
    }, request=request)
        
    return JsonResponse({
        'total_red': total_red,
        'total_blue': total_blue,
        'summary_html': summary_html,
        'feed_html': feed_html,
        'foul_html': foul_html,
    })


@judge_required
@require_POST
def advance_match_round(request, match_id, round_num):

    match = get_object_or_404(Match, id=match_id)
    match.current_round = round_num
    match.current_sub_round = 1 
    match.save()
    return redirect('judge-live-match', match_id=match.id)
 


from .permissions import scorer_required




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
    
    prefilled_ring = request.session['selected_ring']
    if request.method == 'POST':
        form = FixtureGenerationForm(request.POST)
        
        if form.is_valid():
            data = form.cleaned_data
            prefilled_ring = request.session.get('selected_ring', 1)
            # 1. Check if ANY matches already exist for this exact category
            existing_matches = Match.objects.filter(
                tournament=tournament,
                event_type=data['event_type'],
                age_category=data['age_category'],
                weight_category=data['weight_category'],
                gender=data['gender']
            )
            
            if existing_matches.exists():
                latest_round = existing_matches.order_by('-round_number').first().round_number
                success, msg = generate_next_round(
                    tournament=tournament, event_type=data['event_type'],
                    age_category=data['age_category'], weight_category=data['weight_category'],
                    gender=data['gender'], current_round=latest_round,
                    ring_number=data['ring_number']
                )
            else:
                success, msg = generate_round_one_fixtures(
                    tournament=tournament, event_type=data['event_type'],
                    age_category=data['age_category'], weight_category=data['weight_category'],
                    gender=data['gender'], ring_number=data['ring_number']
                )
                
            if success:
                messages.success(request, msg)
                return redirect('tournament-matches', tournament_id=tournament.id)
            else:
                messages.error(request, msg)
                return redirect('manage-fixtures', tournament_id=tournament.id)
        
        # THE FIX: If the form is invalid, tell the user WHY!
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Error in {field}: {error}")
                
    else:
        form = FixtureGenerationForm()
    
    is_filtered = bool(request.GET.get('event_type') or request.GET.get('gender'))
    return render(request, 'manage_fixtures.html', {
        'tournament': tournament,
        'form': form,
        'prefilled_ring': prefilled_ring,
        'is_filtered': is_filtered,
    })
    
# thangta/views.py
from .permissions import scorer_required
from .models import Score

# ==========================================
# 8. SCORER MAT CONTROL
# ==========================================

 
 
from django.shortcuts import redirect

@scorer_required
def scorer_dashboard(request):
    """
    This page is no longer needed. 
    Instantly redirect Scorers to the main tournament hub so they can find their matches.
    """
    return redirect('tournament-dashboard')
 
@scorer_required
def scorer_ring_matches(request, tournament_id, ring_number): # (Your function name might be slightly different!)
    """
    This intermediate 'Match is Live' waiting room is no longer needed.
    Instantly bounce them to the main dashboard where they can select their match directly.
    """
    return redirect('global-fixtures')

from django.urls import reverse
from django.contrib import messages

from django.urls import reverse

@scorer_required
def scorer_select_corner(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    
    # ==========================================
    # 🚨 THE BULLETPROOF INTERCEPTOR
    # ==========================================
    session_key = f"locked_corner_match_{match.id}"
    locked_corner = request.session.get(session_key)
    
    if locked_corner:
        # If they are already locked in, do not let them see the buttons!
        # Instantly bounce them back to their assigned panel.
        messages.info(request, f"You are locked to the {locked_corner.upper()} corner.")
        url = reverse('scorer-panel', args=[match.id])
        return redirect(f"{url}?corner={locked_corner}")
    # ==========================================

    request.session['active_tournament_id'] = match.tournament.id
    
    return render(request, 'scorer_select_corner.html', {
        'match': match,
    })
    
    
    
from django.contrib import messages 

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from .models import Match, Score 

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from .models import Match, Score 

@scorer_required
def scorer_panel(request, match_id):
    """The scoring panel that securely locks the scorer into their chosen corner."""
    match = get_object_or_404(Match, id=match_id)
    corner = request.GET.get('corner', '').lower()
    
    # 1. Check if match is live
    if match.is_completed or not match.is_active:
        messages.warning(request, "This match is not currently active.")
        return redirect('scorer-dashboard')

    session_key = f"locked_corner_match_{match.id}"
    
    # ==========================================
    # 🚨 THE DEVELOPER RESET HACK
    # ==========================================
    if request.GET.get('reset') == 'true':
        if session_key in request.session:
            del request.session[session_key]
            request.session.modified = True
        messages.success(request, "Security lock removed! You can now pick a new corner.")
        return redirect('scorer-select-corner', match_id=match.id)

    # ==========================================
    # 🚨 THE URL TAMPER TRAP & SECURITY LOCK
    # ==========================================
    locked_corner = request.session.get(session_key)
    
    if locked_corner:
        if corner != locked_corner:
            # They tried to switch corners mid-match! Trap them and send them back.
            messages.warning(request, f"Access Denied: You are locked to the {locked_corner.upper()} corner.")
            url = reverse('scorer-panel', args=[match.id])
            return redirect(f"{url}?corner={locked_corner}")
        
        # Safe to proceed
        corner = locked_corner 
        
    elif corner in ['red', 'blue']:
        # First time arriving! Check for BYE match mistake, then lock the door.
        if corner == 'blue' and not match.participant_blue:
            messages.error(request, "Invalid corner selected. There is no Blue participant.")
            return redirect('scorer-select-corner', match_id=match.id)
            
        request.session[session_key] = corner
    else:
        # No corner in URL? Kick them to the selection screen.
        return redirect('scorer-select-corner', match_id=match.id)
    
    # ==========================================
    # 🚨 SUB-ROUND MATH
    # ==========================================
    participant = match.participant_red if corner == 'red' else match.participant_blue
    current_round_int = int(match.current_round)

    # The BULLETPROOF Count: Match + Round + Fighter + Specific Judge
    scorer_score_count = Score.objects.filter(
        match=match, 
        round_num=current_round_int, 
        participant=participant,
        scorer=request.user 
    ).count()
    
    current_sub_round = scorer_score_count + 1
    
    return render(request, 'scorer_panel.html', {
        'match': match,
        'corner': corner,  # This makes the HTML Red or Blue
        'current_sub_round': current_sub_round, 
        'points_string': "",
        'total_score': 0,
        'db_score_count': 0, 
    })
    
    
    
from django.http import HttpResponse



import math

from django.db.models import Avg

def calculate_corner_score(match, participant):
    """
    Groups all scores for a fighter by Sub-Round, averages the judges' 
    inputs for each sub-round, and returns the total sum of those averages.
    """
    # 1. Ask the database to group by round & sub_round, and calculate the average points
    sub_round_averages = Score.objects.filter(
        match=match,
        participant=participant
    ).values(
        'round_number', 'sub_round'
    ).annotate(
        avg_points=Avg('points')
    )

    # 2. Add all the averages together
    total_score = 0.0
    for sr in sub_round_averages:
        # avg_points might be None if there are no scores yet, so we default to 0
        total_score += float(sr['avg_points'] or 0)

    # 3. Return rounded to 2 decimal places (e.g., 5.50 or -3.00)
    return round(total_score, 2)

def calculate_round_score(match, participant, round_num):
    """
    Groups scores strictly into sequential queues of 3, ignoring timestamps.
    Works perfectly for both positive points and negative fouls.
    """
    if not participant:
        return 0
        
    # Get all unflagged scores for this round, ordered chronologically
    scores_query = Score.objects.filter(
        match=match, 
        participant=participant, 
        round_num=round_num, 
        is_flagged=False
    ).order_by('timestamp')
        
    # Separate the lists
    point_scores = list(scores_query.filter(is_foul=False))
    foul_scores = list(scores_query.filter(is_foul=True))

    # --- THE QUEUE ENGINE ---
    def get_queue_total(score_list):
        total = 0
        
        # Loop through the list, grabbing exactly 3 items at a time
        for i in range(0, len(score_list), 3):
            chunk = score_list[i:i+3]
            
            # STRICT RULE: Only calculate if the queue chunk has exactly 3 scores!
            if len(chunk) == 3:
                chunk_sum = sum(s.points for s in chunk)
                total += math.floor(chunk_sum / 3.0)
                
        return total
    # ------------------------

    # Pass both lists through the queue engine
    approved_points = get_queue_total(point_scores)
    approved_fouls = get_queue_total(foul_scores)
    
    return approved_points + approved_fouls

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404

from django.http import JsonResponse
from . import state # Make sure you still have this import!





def match_live_state(request, match_id):
    """Phase 4: DISPLAY - Enforces strict order and hides pending partials"""
    with state.state_lock:
        match_live = state.liveState.get(match_id, {})
        match_total = state.total.get(match_id, {})
        
        display_data = {
            'rounds': {},
            'totals': match_total
        }
        
        for rnd, subrounds in match_live.items():
            display_data['rounds'][rnd] = {}
            
            # Sort subrounds to ensure sequential checking (1, 2, 3...)
            sorted_subrounds = sorted(subrounds.keys())
            
            for sr in sorted_subrounds:
                red_state = subrounds[sr]['red']
                blue_state = subrounds[sr]['blue']
                
                # Check if this subround is fully complete for BOTH corners
                # (Or you can split this logic if corners advance asynchronously)
                if red_state.get('status') == 'COMPLETE' and blue_state.get('status') == 'COMPLETE':
                    display_data['rounds'][rnd][sr] = {
                        'status': 'COMPLETE',
                        'red_avg': red_state['average'],
                        'blue_avg': blue_state['average']
                    }
                else:
                    # Show WAITING for current incomplete subround
                    display_data['rounds'][rnd][sr] = {
                        'status': 'WAITING FOR SCORES',
                        'red_status': red_state.get('status'),
                        'blue_status': blue_state.get('status')
                    }
                    # ORDER ENFORCEMENT: Break loop. Do not expose N+1.
                    break 
                    
        return JsonResponse(display_data)
    
    
@require_POST
def finalize_match(request, match_id):
    """Phase 5 & 6: Finalize and Flush"""
    match = get_object_or_404(Match, id=match_id)
    
    with state.state_lock:
        # Phase 5: Finalize (Sum all completed averages from the total dict)
        match_totals = state.total.get(match_id, {})
        
        final_red = sum(rnd_totals['red'] for rnd_totals in match_totals.values())
        final_blue = sum(rnd_totals['blue'] for rnd_totals in match_totals.values())
        
        match.score_red = final_red
        match.score_blue = final_blue
        match.is_completed = True
        match.save()
        
        # Phase 6: Flush (Prevent memory buildup)
        if match_id in state.scores:
            del state.scores[match_id]
        if match_id in state.liveState:
            del state.liveState[match_id]
        if match_id in state.total:
            del state.total[match_id]
            
    return JsonResponse({'status': 'match_completed', 'final_red': final_red, 'final_blue': final_blue})

from django.http import HttpResponse

@scorer_required
def fetch_score_history(request, match_id):
    """Background sync: Safely checks what sub-round the Scorer should be on."""
    match = get_object_or_404(Match, id=match_id)
    
    # BULLETPROOF FIX: Just count how many scores THIS scorer has submitted in THIS round!
    scorer_score_count = Score.objects.filter(
        match=match, 
        round_num=match.current_round, 
        scorer=request.user
    ).count()
    
    current_sub_round = scorer_score_count + 1
    
    response = HttpResponse("")
    response['X-Current-Sub-Round'] = current_sub_round
    response['X-Current-Round'] = match.current_round
    
    return response


from django.http import JsonResponse

@scorer_required
def fetch_my_score_receipts(request, match_id):
    """Returns the logged-in scorer's history for the visual table."""
    scores = Score.objects.filter(
        match_id=match_id, 
        scorer=request.user
    ).order_by('-round_num', '-sub_round', '-timestamp')
    
    history_data = []
    for s in scores:
        history_data.append({
            'round_num': s.round_num,
            'sub_round': s.sub_round,
            'points': s.points,
            'is_foul': s.is_foul,
            'foul_reason': s.foul_reason if s.is_foul else "",
        })
        
    return JsonResponse({'status': 'success', 'history': history_data})


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
    """Manually declares a winner, burns RAM scores to database, and auto-generates next round."""
    match = get_object_or_404(Match, id=match_id)
    
    if match.is_completed:
        messages.info(request, "This match is already completed.")
        return redirect('tournament-matches', tournament_id=match.tournament.id)

    if request.method == 'POST':
        winner_id = request.POST.get('winner_id')
        if winner_id:
            winner = get_object_or_404(Participant, id=winner_id)
            if winner == match.participant_red or winner == match.participant_blue:
                
                # ==========================================
                # 🚨 NEW: BURN THE RAM MATH INTO THE DATABASE
                # ==========================================
                match_state = state.get_or_create_match_state(match_id)
                
                grand_red = 0
                grand_blue = 0
                
                for r_num, r_data in match_state.get('rounds', {}).items():
                    r_red = 0
                    r_blue = 0
                    for sr_num, sr_data in r_data.get('subrounds', {}).items():
                        if sr_data.get('red', {}).get('status') == 'COMPLETE':
                            r_red += sr_data['red']['final_score']
                        if sr_data.get('blue', {}).get('status') == 'COMPLETE':
                            r_blue += sr_data['blue']['final_score']
                    
                    # Burn the Round Totals into the database columns
                    if str(r_num) == '1':
                        match.round_1_red = r_red
                        match.round_1_blue = r_blue
                    elif str(r_num) == '2':
                        match.round_2_red = r_red
                        match.round_2_blue = r_blue
                    elif str(r_num) == '3':
                        match.round_3_red = r_red
                        match.round_3_blue = r_blue
                        
                    grand_red += r_red
                    grand_blue += r_blue
                    
                # Burn the Grand Totals
                match.score_red = grand_red
                match.score_blue = grand_blue
                # ==========================================

                # Finalize the match state
                match.winner = winner
                match.is_completed = True
                match.is_active = False
                match.save()
                
                # 🚨 NOTE: I deleted the line that was erasing all the Score objects!
                # The historical database is now safe.

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
                            messages.success(request, f"🏆 {winner.name} wins ({grand_red} - {grand_blue})! Round {match.round_number + 1} automatically generated!")
                            url = reverse('tournament-matches', args=[match.tournament.id])
                            return redirect(f"{url}?round={match.round_number + 1}")
                    else:
                        messages.success(request, f"🏆 {winner.name} wins the Final ({grand_red} - {grand_blue})! Category Complete.")
                else:
                    messages.success(request, f"🏆 {winner.name} declared as the winner ({grand_red} - {grand_blue})!")
                
                url = reverse('tournament-matches', args=[match.tournament.id])
                return redirect(f"{url}?round={match.round_number}")
            else:
                messages.error(request, "Invalid winner selected.")

    return render(request, 'match_update_score.html', {'match': match})



from django.db.models import Avg
from .models import Score # Ensure you import the temporary Score model

def calculate_corner_score(match, participant):
    """Calculates the sub-round averages and returns the total."""
    sub_round_averages = Score.objects.filter(
        match=match,
        participant=participant
    ).values(
        'round_num', 'sub_round'
    ).annotate(
        avg_points=Avg('points')
    )

    total_score = sum(float(sr['avg_points'] or 0) for sr in sub_round_averages)
    return round(total_score, 2)

@judge_required
def start_match(request, match_id):
    """Shows confirmation screen, then sets match to active and redirects to panel."""
    match = get_object_or_404(Match, id=match_id)

    if request.method == 'POST':
        # If they clicked the confirmation button, start the match!
        match.is_active = True
        match.save()
        return redirect('judge-live-match', match_id=match.id)

    # If it's a GET request, just show the confirmation page
    return render(request, 'judge_start_match.html', {'match': match})



from django.views.decorators.http import require_POST

@judge_required
@require_POST
def advance_sub_round(request, match_id):
    
    """Advances the match to the next sub-round and refreshes the page."""
    match = get_object_or_404(Match, id=match_id)
    
    # Increase the sub-round by 1
    match.current_sub_round += 1
    match.save()
    
    return redirect('judge-live-match', match_id=match.id)
 
 
from django.shortcuts import render, get_object_or_404
from .models import Match, Tournament

def global_fixtures(request):
    # 1. Check if ANY filter was actually selected by the user
    is_filtered = any([
        request.GET.get('tournament'),
        request.GET.get('event_type'),
        request.GET.get('gender'),
        request.GET.get('weight_category'),
        request.GET.get('age_category'),
        request.GET.get('ring_number')
    ])

    # 2. Only run the heavy database search if filters exist!
    if is_filtered:
        matches = Match.objects.all()
        
        # Apply Filters
        if request.GET.get('tournament'):
            matches = matches.filter(tournament_id=request.GET.get('tournament'))
        if request.GET.get('event_type'):
            matches = matches.filter(event_type=request.GET.get('event_type'))
        if request.GET.get('gender'):
            matches = matches.filter(gender=request.GET.get('gender'))
        if request.GET.get('weight_category'):
            matches = matches.filter(weight_category=request.GET.get('weight_category'))
        if request.GET.get('age_category'):
            matches = matches.filter(age_category=request.GET.get('age_category'))
        if request.GET.get('ring_number'):
            matches = matches.filter(ring_number=request.GET.get('ring_number'))

        matches = matches.order_by('round_number', 'match_sequence')
    else:
        # If no filters, send an empty list (saves server memory!)
        matches = Match.objects.none()

    tournaments = Tournament.objects.all()

    # Pass the current filters so the dropdowns "remember" what was selected
    current_filters = {
        'event_type': request.GET.get('event_type', ''),
        'gender': request.GET.get('gender', ''),
        'age_category': request.GET.get('age_category', ''),
        'weight_category': request.GET.get('weight_category', '')
    }

    return render(request, 'global_fixtures.html', {
        'matches': matches,
        'tournaments': tournaments,
        'is_filtered': is_filtered,  # 🚨 THE NEW VARIABLE
        'current_filters': current_filters,
    })
    
    
from django.shortcuts import render, get_object_or_404, redirect
from .models import Match, Tournament

# 1. NEW: The Ring Selection Interceptor Page
def select_ring(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    
    if request.method == 'POST':
        # Save the selected ring to the user's session
        ring_number = request.POST.get('ring_number')
        request.session['selected_ring'] = ring_number
        return redirect('tournament-matches', tournament_id=tournament.id)
        
    return render(request, 'select_ring.html', {'tournament': tournament})

from django.shortcuts import get_object_or_404, redirect

def tournament_matches(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    
    # 1. Check if they have a ring in their session. If not, bounce them!
    session_ring = request.session.get('selected_ring')
    if not session_ring:
        return redirect('select-ring', tournament_id=tournament.id)

    # 2. Check if the user has selected their categories yet
    is_filtered = any([
        request.GET.get('event_type'),
        request.GET.get('gender'),
        request.GET.get('weight_category'),
        request.GET.get('age_category')
    ])

    # 3. Only run the heavy database search if filters exist!
    if is_filtered:
        # Lock to THIS tournament AND their Session Ring
        matches = Match.objects.filter(tournament=tournament, ring_number=session_ring)
        
        # Apply remaining GET filters
        if request.GET.get('event_type'):
            matches = matches.filter(event_type=request.GET.get('event_type'))
        if request.GET.get('gender'):
            matches = matches.filter(gender=request.GET.get('gender'))
        if request.GET.get('weight_category'):
            matches = matches.filter(weight_category=request.GET.get('weight_category'))   
        if request.GET.get('age_category'):
            matches = matches.filter(age_category=request.GET.get('age_category'))

        matches = matches.order_by('round_number', 'match_sequence')
    else:
        # If no filters, send an empty list to trigger the HTML placeholder
        matches = Match.objects.none()

    # Pass the current filters so the dropdowns "remember" what was selected
    current_filters = {
        'event_type': request.GET.get('event_type', ''),
        'gender': request.GET.get('gender', ''),
        'age_category': request.GET.get('age_category', ''),
        'weight_category': request.GET.get('weight_category', '')
    }

    return render(request, 'tournament_matches.html', {
        'tournament': tournament,
        'matches': matches,
        'current_filters': current_filters,
        'session_ring': session_ring,
        'is_filtered': is_filtered,  # 🚨 Critical for the HTML template!
    })


def match_summary(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    
    # We don't need to calculate anything here! 
    # The RAM engine already saved the totals to match.score_red and match.round_1_red, etc.
    
    return render(request, 'match_scoreboard.html', {
        'match': match
    }) 
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import District, Participant # Make sure Participant is imported!
# --- COACH PORTAL VIEWS ---

def district_login_coach(request):
    # Bypass if already logged in
    if request.session.get('coach_district'):
        return redirect('manage-participants-coach')

    if request.method == 'POST':
        district_id = request.POST.get('district_id')
        code = request.POST.get('access_code')
        
        try:
            district = District.objects.get(id=district_id)
            if district.access_code == code:
                request.session['coach_district'] = district.name
                messages.success(request, f"Welcome, Coach from {district.name}!")
                return redirect('manage-participants-coach')
            else:
                messages.error(request, "Incorrect Access Code. Please try again.")
        except District.DoesNotExist:
            messages.error(request, "Invalid District selected.")

    districts = District.objects.all().order_by('name')
    return render(request, 'district_login_coach.html', {'districts': districts})


def manage_participants_coach(request):
    district_name = request.session.get('coach_district')
    if not district_name:
        messages.warning(request, "You must log in to view participants.")
        return redirect('district-login-coach')
        
    participants = Participant.objects.filter(district=district_name).order_by('name')
    
    return render(request, 'manage_participants_coach.html', {
        'district_name': district_name,
        'participants': participants
    })


def add_participant_coach(request):
    district_name = request.session.get('coach_district')
    if not district_name:
        messages.error(request, "Unauthorized access. Please log in first.")
        return redirect('district-login-coach')

    if request.method == 'POST':
        name = request.POST.get('name')
        dob = request.POST.get('dob')
        age = request.POST.get('age')
        gender = request.POST.get('gender')
        contact = request.POST.get('contact')
        
        # THE FIX: Grab 'age_group' from the form, but save it to the DB as 'age_category'!
        age_category_val = request.POST.get('age_group') 
        weight_category = request.POST.get('weight_category')
        event_type = request.POST.get('event_type')

        Participant.objects.create(
            name=name,
            date_of_birth=dob,
            age=age,
            gender=gender,
            contact=contact,
            age_category=age_category_val, # FIXED HERE!
            weight_category=weight_category,
            event_type=event_type,
            district=district_name 
        )

        messages.success(request, f"Successfully added {name} to {district_name}!")
        return redirect('manage-participants-coach')

    return render(request, 'add_participant_coach.html', {'district_name': district_name})


def district_logout_coach(request):
    if 'coach_district' in request.session:
        del request.session['coach_district']
    messages.info(request, "You have been logged out safely.")
    return redirect('district-login-coach')
 
from django.shortcuts import render, redirect, get_object_or_404
# ... your other imports ...

def edit_participant_coach(request, participant_id):
    district_name = request.session.get('coach_district')
    if not district_name:
        messages.error(request, "Unauthorized access. Please log in first.")
        return redirect('district-login-coach')

    # SECURITY: Fetch the participant AND ensure they belong to this specific district!
    participant = get_object_or_404(Participant, id=participant_id, district=district_name)

    if request.method == 'POST':
        participant.name = request.POST.get('name')
        participant.date_of_birth = request.POST.get('dob')
        participant.age = request.POST.get('age')
        participant.gender = request.POST.get('gender')
        participant.contact = request.POST.get('contact')
        participant.age_category = request.POST.get('age_group') # Maps to your DB field
        participant.weight_category = request.POST.get('weight_category')
        participant.event_type = request.POST.get('event_type')
        
        participant.save()

        messages.success(request, f"Successfully updated {participant.name}.")
        return redirect('manage-participants-coach')

    return render(request, 'edit_participant_coach.html', {
        'district_name': district_name,
        'participant': participant
    })


def delete_participant_coach(request, participant_id):
    district_name = request.session.get('coach_district')
    if not district_name:
        messages.error(request, "Unauthorized access. Please log in first.")
        return redirect('district-login-coach')

    # SECURITY: Fetch the participant AND ensure they belong to this specific district!
    participant = get_object_or_404(Participant, id=participant_id, district=district_name)

    if request.method == 'POST':
        name_to_delete = participant.name
        participant.delete()
        messages.success(request, f"Successfully removed {name_to_delete} from the team.")
        return redirect('manage-participants-coach')

    return render(request, 'delete_participant_coach.html', {
        'district_name': district_name,
        'participant': participant
    })
    
 
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import Match

def check_match_status(request, match_id):
    """A high-speed endpoint for the scorer panel to check the current round."""
    match = get_object_or_404(Match, id=match_id)
    return JsonResponse({
    'is_completed': match.is_completed,
    'status': 'completed' if match.is_completed else 'active',
    'current_round': match.current_round   
})
    
    
    # =====================
# SSE IMPLEMNTATIONNN 
# ===========================


from django.http import StreamingHttpResponse
import json
import queue
from . import state # Import your new state engine

def match_sse_stream(request, match_id):
    """The SSE endpoint that keeps a persistent connection with the Judge."""
    
    def event_stream():
        # 1. Register this connection in the state engine
        client_queue = state.register_client(match_id)
        
        try:
            # 2. Immediately send the current state so the UI loads instantly
            current_state = state.get_or_create_match_state(match_id)['rounds']
            initial_payload = {'type': 'INITIAL_STATE', 'state': current_state}
            yield f"data: {json.dumps(initial_payload)}\n\n"

            # 3. Enter an infinite loop, waiting for new data to appear in the queue
            while True:
                try:
                    # Wait up to 15 seconds for a new score or flag
                    message = client_queue.get(timeout=15)
                    yield f"data: {json.dumps(message)}\n\n"
                except queue.Empty:
                    # If 15 seconds pass with no new scores, send a silent "heartbeat".
                    # This prevents Nginx/browsers from closing the connection due to inactivity!
                    yield ": heartbeat\n\n"
                    
        except GeneratorExit:
            # 4. If the Judge closes the tab or navigates away, clean up the queue
            state.remove_client(match_id, client_queue)

    # Return the special Streaming response
    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no' # Crucial if you are using Nginx!
    return response


import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from .models import Match # Adjust if your import is different
from . import state

 
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from .models import Match, Score # Ensure Score is imported!
from . import state

@scorer_required  
@require_POST
def submit_score(request, match_id):
    """Takes input from the Scorer's phone, logs it, and injects it into the RAM State Machine."""
    match = get_object_or_404(Match, id=match_id)
    
    # 1. Safely deduce the corner
    participant_id = request.POST.get('participant_id')
    if str(participant_id) == str(match.participant_red.id):
        corner = 'red'
        target_participant = match.participant_red
    else:
        corner = 'blue'
        target_participant = match.participant_blue

    # 2. Parse the data into strict integers
    round_num = int(match.current_round)
    subround = int(request.POST.get('subround', 1))
    scorer_id = int(request.user.id)
    
    # 3. Calculate Foul & Score values
    is_foul = request.POST.get('is_foul') == 'true'
    foul_val = -3 if is_foul else 0
    
    points_str = request.POST.get('points', '0')
    score_val = sum(int(pt.strip()) for pt in points_str.split(',') if pt.strip().isdigit())
    if score_val > 6:
        score_val = 6

    # Grab the name of the logged-in Scorer
    scorer_name = request.user.get_full_name()
    if not scorer_name:
        scorer_name = request.user.username

    # ==========================================
    # 🚨 STEP A: THE AUDIT TRAIL LOG
    # Save the exact receipt to the database for historical records!
    # ==========================================
    Score.objects.create(
        match=match,
        participant=target_participant,
        scorer=request.user,
        points=foul_val if is_foul else score_val,
        sub_round=subround,
        round_num=round_num,
        is_foul=is_foul,
        foul_reason=request.POST.get('foul_reason', '') if is_foul else None
    )

    # ==========================================
    # 🚨 STEP B: THE LIVE STATE MACHINE
    # Inject into RAM (This automatically triggers the SSE broadcast!)
    # ==========================================
    newly_completed, current_state = state.submit_scorer_data(
        match_id=match.id,
        round_num=round_num,
        subround=subround,
        corner=corner,
        scorer_id=scorer_id,
        scorer_name=scorer_name,  
        score=score_val,
        foul=foul_val
    )
    
    # ==========================================
    # 🚨 STEP C: THE DATABASE CHECKPOINT
    # Save the running totals to the Match model ONLY when 3 judges finish
    # ==========================================
    if newly_completed:
        total_red = 0
        total_blue = 0
        
        round_totals = {1: {'red': 0, 'blue': 0}, 2: {'red': 0, 'blue': 0}, 3: {'red': 0, 'blue': 0}}
        
        # Safely sum up all the finished math from the RAM engine
        for r_num, r_data in current_state['rounds'].items():
            r_num_int = int(r_num)
            for sr_num, sr_data in r_data['subrounds'].items():
                if sr_data['red']['status'] == 'COMPLETE':
                    round_totals[r_num_int]['red'] += sr_data['red']['final_score']
                if sr_data['blue']['status'] == 'COMPLETE':
                    round_totals[r_num_int]['blue'] += sr_data['blue']['final_score']
        
        # Add up the Grand Totals
        for r_totals in round_totals.values():
            total_red += r_totals['red']
            total_blue += r_totals['blue']

        # 🚨 UNCOMMENTED: Save Grand Totals
        match.score_red = total_red    
        match.score_blue = total_blue  
        
        # 🚨 UNCOMMENTED: Save Round 1
        if hasattr(match, 'round_1_red'): 
            match.round_1_red = round_totals[1]['red']
            match.round_1_blue = round_totals[1]['blue']
            
        # 🚨 UNCOMMENTED: Save Round 2
        if hasattr(match, 'round_2_red'): 
            match.round_2_red = round_totals[2]['red']
            match.round_2_blue = round_totals[2]['blue']
            
        # 🚨 UNCOMMENTED: Save Round 3 (Tie Breaker)
        if hasattr(match, 'round_3_red'): 
            match.round_3_red = round_totals[3]['red']
            match.round_3_blue = round_totals[3]['blue']
            
        match.save() # THIS LOCKS IT IN!

    # We return the subround_completed flag so the Scorer's phone knows if it advanced
    return JsonResponse({'status': 'success', 'subround_completed': newly_completed})
@judge_required
@require_POST
def flag_live_score(request, match_id):
    """Allows the Judge to flag an individual scorer's input in real-time."""
    # We use json.loads because the frontend will send this via a JS fetch with a JSON body
    data = json.loads(request.body)
    
    round_num = int(data.get('round_num'))
    subround = int(data.get('subround'))
    corner = data.get('corner')
    scorer_id = int(data.get('scorer_id'))

    # Inject into State Machine (This automatically triggers the SSE broadcast!)
    success, current_state = state.flag_score(
        match_id=match_id, 
        round_num=round_num, 
        subround=subround, 
        corner=corner, 
        scorer_id=scorer_id
    )
    
    if success:
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'message': 'Score not found in active memory.'}, status=400)



# No decorators here! Open to the public.
def public_live_match(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    
    # If the match isn't active, don't let them stare at a blank screen
    if not match.is_active and not match.is_completed:
        messages.info(request, "This match is not live yet.")
        return redirect('tournament-matches', tournament_id=match.tournament.id)

    return render(request, 'public_live_match.html', {
        'match': match,
    })