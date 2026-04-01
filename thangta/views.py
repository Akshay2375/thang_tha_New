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


@judge_required
def match_live_data(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    
    # 1. Giant Numbers
    total_red = sum(calculate_round_score(match, match.participant_red, r) for r in range(1, match.current_round + 1))
    total_blue = sum(calculate_round_score(match, match.participant_blue, r) for r in range(1, match.current_round + 1)) if match.participant_blue else 0
    
    # 2. Round-wise Totals
    round_summary = []
    for r in range(1, match.current_round + 1):
        r_red = calculate_round_score(match, match.participant_red, r)
        r_blue = calculate_round_score(match, match.participant_blue, r) if match.participant_blue else 0
        round_summary.append({
            'round': r,
            'status': 'In Progress' if r == match.current_round else 'Completed',
            'red_total': r_red,
            'blue_total': r_blue,
        })
        
    summary_html = render_to_string('partials/round_summary_cards.html', {
        'round_summary': round_summary,
        'match': match
    }, request=request)
    
    # 3. Process Scores On-The-Fly!
    red_history, red_fouls = process_sub_rounds(match, match.participant_red)
    blue_history, blue_fouls = process_sub_rounds(match, match.participant_blue)
    
    feed_html = render_to_string('partials/score_feed_rows.html', {
        'red_scores': red_history,
        'blue_scores': blue_history,
        'match': match
    }, request=request)
    
    foul_html = render_to_string('partials/foul_feed_rows.html', {
        'red_fouls': red_fouls,
        'blue_fouls': blue_fouls,
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
    """Updates the match to Round 2 or Tie Breaker."""
    match = get_object_or_404(Match, id=match_id)
    match.current_round = round_num
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
            prefilled_ring = data['ring_number']
            
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
    

    return render(request, 'manage_fixtures.html', {
        'tournament': tournament,
        'form': form,
        'prefilled_ring': prefilled_ring,
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

def scorer_select_corner(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    
    # THE FIX: Save the Tournament ID into the scorer's session
    request.session['active_tournament_id'] = match.tournament.id
    
    return render(request, 'scorer_panel.html', {
        'match': match,
    })
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

@scorer_required
def scorer_panel(request, match_id):
    """The scoring panel that securely locks the scorer into their chosen corner."""
    match = get_object_or_404(Match, id=match_id)
    corner = request.GET.get('corner') 
    
    if match.is_completed or not match.is_active:
        messages.warning(request, "This match is not currently active.")
        return redirect('tournament-dashboard')

    # ==========================================
    # 🚨 NEW: THE DEVELOPER RESET HACK
    # ==========================================
    session_key = f"locked_corner_match_{match.id}"
    
    if request.GET.get('reset') == 'true':
        if session_key in request.session:
            del request.session[session_key]
            request.session.modified = True
        messages.success(request, "Security lock removed! You can now pick a new corner.")
        return redirect('scorer-select-corner', match_id=match.id)
    # ==========================================

    if corner == 'blue' and not match.participant_blue:
        messages.error(request, "Invalid corner selected.")
        return redirect('scorer-select-corner', match_id=match.id)

    # --- EXISTING SECURITY LOCK LOGIC ---
    locked_corner = request.session.get(session_key)
    # ... (the rest of your view remains the same)

    if locked_corner:
        # If they try to change the URL manually from ?corner=red to ?corner=blue, stop them!
        if corner != locked_corner:
            messages.warning(request, "Access Denied: You cannot switch corners mid-match.")
            url = reverse('scorer-panel', args=[match.id])
            return redirect(f"{url}?corner={locked_corner}")
        corner = locked_corner # Ensure we use their locked corner
    elif corner in ['red', 'blue']:
        # First time accessing! Lock their choice into the session permanently for this match.
        request.session[session_key] = corner
    else:
        # No corner provided and no lock found? Send them back to selection.
        return redirect('scorer-select-corner', match_id=match.id)
    # -------------------------------

    
  # 1. Figure out exactly which fighter this panel is scoring
    participant = match.participant_red if corner == 'red' else match.participant_blue
    
    # 2. Force the round to be a strict integer to prevent database mismatch bugs
    current_round_int = int(match.current_round)

    # 3. The BULLETPROOF Count: Match + Round + Fighter + Specific Judge
    scorer_score_count = Score.objects.filter(
        match=match, 
        round_num=current_round_int, 
        participant=participant,
        scorer=request.user 
    ).count()
    
    current_sub_round = scorer_score_count + 1
    
    return render(request, 'scorer_panel.html', {
        'match': match,
        'corner': corner,
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

@scorer_required
@require_POST
def submit_score(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    participant = get_object_or_404(Participant, id=request.POST.get('participant_id'))
    is_foul = request.POST.get('is_foul') == 'true'
    
    # Force integer!
    current_round_int = int(match.current_round)
    
    # The exact same bulletproof count
    scorer_score_count = Score.objects.filter(
        match=match, 
        round_num=current_round_int, 
        participant=participant,
        scorer=request.user
    ).count()
    
    current_sub = scorer_score_count + 1
    
    # ... (Keep all your Score.objects.create() code exactly the same below this!) ...
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
    """Manually declares a winner, calculates final scores, flushes temp data, and auto-generates next round."""
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
                # 🚨 NEW: CALCULATE, SAVE, AND FLUSH LOGIC 🚨
                # ==========================================
                
                # 1. Calculate final mathematically perfect scores from the temp DB
                final_red = calculate_corner_score(match, match.participant_red)
                final_blue = calculate_corner_score(match, match.participant_blue)
                
                # 2. Save everything to the permanent Match record
                match.score_red = final_red      # Ensure your Match model has this field!
                match.score_blue = final_blue    # Ensure your Match model has this field!
                match.winner = winner
                match.is_completed = True
                match.save()
                
                # 3. THE CLEANUP (The Flush)
                # Wipe the temporary sub-round click data to keep the database light!
                Score.objects.filter(match=match).delete()
                
                # ==========================================
                
                # ... (The rest of your excellent auto-generation logic remains untouched) ...
                
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
                            messages.success(request, f"🏆 {winner.name} wins ({final_red} - {final_blue})! Round {match.round_number + 1} automatically generated!")
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

# 1. THE MASTER LIST VIEW
def global_fixtures(request):
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
    tournaments = Tournament.objects.all()

    return render(request, 'global_fixtures.html', {
        'matches': matches,
        'tournaments': tournaments,
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

# 2. UPDATED: The Tournament Fixtures Page
def tournament_matches(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    matches = Match.objects.filter(tournament=tournament)
    
    # Check if they have a ring in their session. If not, bounce them to the selection page!
    session_ring = request.session.get('selected_ring')
    if not session_ring:
        return redirect('select-ring', tournament_id=tournament.id)
        
    # Auto-filter by the session ring
    matches = matches.filter(ring_number=session_ring)

    # Apply remaining GET filters (Notice Ring is removed!)
    if request.GET.get('event_type'):
        matches = matches.filter(event_type=request.GET.get('event_type'))
    if request.GET.get('gender'):
        matches = matches.filter(gender=request.GET.get('gender'))
    if request.GET.get('weight_category'):
        matches = matches.filter(weight_category=request.GET.get     ('weight_category'))   
    if request.GET.get('age_category'):
        matches = matches.filter(age_category=request.GET.get('age_category'))

    matches = matches.order_by('round_number', 'match_sequence')

    return render(request, 'tournament_matches.html', {
        'tournament': tournament,
        'matches': matches,
        'current_filters': request.GET,
        'session_ring': session_ring, # Pass the ring to the template so we can display it
    })
def match_summary(request, match_id):
    """Displays the final detailed scoreboard for a completed match."""
    match = get_object_or_404(Match, id=match_id)
    
    # 1. Calculate the FINAL match totals
    total_red = sum(calculate_round_score(match, match.participant_red, r) for r in range(1, match.current_round + 1))
    
    total_blue = 0
    if match.participant_blue:
        total_blue = sum(calculate_round_score(match, match.participant_blue, r) for r in range(1, match.current_round + 1))
        
    # 2. Build the Round-by-Round breakdown for the bottom cards
    round_summary = []
    for r in range(1, match.current_round + 1):
        r_red = calculate_round_score(match, match.participant_red, r)
        r_blue = calculate_round_score(match, match.participant_blue, r) if match.participant_blue else 0
        round_summary.append({
            'round': r,
            'status': 'Completed' if match.is_completed else ('In Progress' if r == match.current_round else 'Completed'),
            'red_total': r_red,
            'blue_total': r_blue,
        })
        
    # Change 'match_scoreboard.html' to whatever the actual name of your template from Image 2 is!
    return render(request, 'match_scoreboard.html', {
        'match': match,
        'total_red': total_red,
        'total_blue': total_blue,
        'round_summary': round_summary,
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
    """A lightweight endpoint for the scorer's phone to ping."""
    match = get_object_or_404(Match, id=match_id)
    
    return JsonResponse({
        'is_completed': match.is_completed
    })