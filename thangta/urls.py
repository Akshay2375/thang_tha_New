# urls.py
from django.urls import path
from .views import *
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    path('tournaments/', TournamentListView.as_view(), name='tournament-list'),
    path('tournaments/add/', TournamentCreateView.as_view(), name='tournament-add'),
    path('tournaments/<int:pk>/delete/', TournamentDeleteView.as_view(), name='tournament-delete'),
    path('participants/', ParticipantListView.as_view(), name='participant-list'),
    path('tournaments/dashboard/', TournamentDashboardView.as_view(), name='tournament-dashboard'),
    path('participants/add/', ParticipantCreateView.as_view(), name='participant-add'),
    path('tournaments/<int:tournament_id>/select-ring/',select_ring, name='select-ring'),
    path('officials/add/', OfficialCreateView.as_view(), name='official-add'),
    path('tournaments/<int:tournament_id>/end/', end_tournament, name='tournament-end'),
    path('participants/<int:pk>/edit/', ParticipantUpdateView.as_view(), name='participant-edit'),
    path('participants/<int:pk>/delete/', ParticipantDeleteView.as_view(), name='participant-delete'),
   path('fixtures/', global_fixtures, name='global-fixtures'),   # path('tournaments/<int:tournament_id>/fixtures/', manage_fixtures, name='manage-fixtures'),
    path('tournaments/<int:tournament_id>/matches/', tournament_matches, name='tournament-matches'),
    
    path('matches/<int:match_id>/update/', update_match_winner, name='match-update'),
    path('',TournamentDashboardView.as_view(), name='tournament-dashboard'),
    path('matches/<int:match_id>/auto-advance/', auto_generate_next_round, name='match-auto-advance'),
    
    # Add this line to handle the score updating!
    path('match/<int:match_id>/update/', update_match_winner, name='update-match-winner'),
    
    path('tournaments/<int:tournament_id>/results/', tournament_results, name='tournament-results'),
    
    path('judge/match/<int:match_id>/start/', start_match, name='start-match'),
    path('judge/match/<int:match_id>/live/', judge_live_match, name='judge-live-match'),
    path('judge/dashboard/', judge_dashboard, name='judge-dashboard'),
    path('judge/', judge_dashboard, name='judge-dashboard'),
    

    
    # path('route-dashboard/', dashboard_dispatcher, name='dashboard-dispatcher'),
    path('judge/match/<int:match_id>/api/live-data/', match_live_data, name='match-live-data'),
    
    path('judge/match/<int:match_id>/start-round/<int:round_num>/', advance_match_round, name='advance-match-round'),
    
    path('judge/score/<int:score_id>/flag/', toggle_score_flag, name='toggle-score-flag'),
    path('judge/match/<int:match_id>/advance-sub-round/', advance_sub_round, name='advance-sub-round'),
    
    path('tournament/<int:tournament_id>/fixtures/manage/', manage_fixtures, name='manage-fixtures'),
    path('judge/tournament/<int:tournament_id>/ring/<int:ring_number>/generate/', judge_generate_fixtures, name='judge-generate-fixtures'),
    
    # --- SCORER URLS ---
    path('scorer/dashboard/', scorer_dashboard, name='scorer-dashboard'),
    path('scorer/tournament/<int:tournament_id>/ring/<int:ring_number>/', scorer_ring_matches, name='scorer-ring-matches'),
    
    # New endpoints for the Scorer Redesign
    path('scorer/match/<int:match_id>/select-corner/', scorer_select_corner, name='scorer-select-corner'),
    path('scorer/match/<int:match_id>/panel/', scorer_panel, name='scorer-panel'),
    path('scorer/match/<int:match_id>/submit/', submit_score, name='submit-score'),
    
    # AJAX History endpoints
    path('scorer/match/<int:match_id>/score-history/', fetch_score_history, name='fetch-score-history'),
    path('scorer/match/<int:match_id>/foul-history/', fetch_foul_history, name='fetch-foul-history'),
    
    path('match/<int:match_id>/summary/', match_summary, name='match-summary'),
    
 path('coach/login/', district_login_coach, name='district-login-coach'),
path('coach/participants/', manage_participants_coach, name='manage-participants-coach'),
path('coach/participants/add/', add_participant_coach, name='add-participant-coach'),
path('coach/logout/', district_logout_coach, name='district-logout-coach'),
path('coach/participants/<int:participant_id>/edit/', edit_participant_coach, name='edit-participant-coach'),
path('coach/participants/<int:participant_id>/delete/', delete_participant_coach, name='delete-participant-coach'),

 
 
path('match/<int:match_id>/check-status/', check_match_status, name='check-match-status'),



# SSSE IMPLEMNTATION
path('match/<int:match_id>/stream/', match_sse_stream, name='match-sse-stream'),
path('match/<int:match_id>/flag-live-score/', flag_live_score, name='flag-live-score'),

path('match/<int:match_id>/watch/',public_live_match, name='public-live-match'),




]