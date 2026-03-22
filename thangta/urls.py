# urls.py
from django.urls import path
from .views import TournamentListView, TournamentCreateView, TournamentDeleteView,ParticipantListView,TournamentDashboardView,ParticipantCreateView,OfficialCreateView,end_tournament,ParticipantDeleteView,ParticipantUpdateView,manage_fixtures,tournament_matches,update_match_winner,auto_generate_next_round,tournament_results
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
    
    path('officials/add/', OfficialCreateView.as_view(), name='official-add'),
    path('tournaments/<int:tournament_id>/end/', end_tournament, name='tournament-end'),
    path('participants/<int:pk>/edit/', ParticipantUpdateView.as_view(), name='participant-edit'),
    path('participants/<int:pk>/delete/', ParticipantDeleteView.as_view(), name='participant-delete'),
    
    path('tournaments/<int:tournament_id>/fixtures/', manage_fixtures, name='manage-fixtures'),
    path('tournaments/<int:tournament_id>/matches/', tournament_matches, name='tournament-matches'),
    
    path('matches/<int:match_id>/update/', update_match_winner, name='match-update'),
    path('',TournamentDashboardView.as_view(), name='tournament-dashboard'),
    path('matches/<int:match_id>/auto-advance/', auto_generate_next_round, name='match-auto-advance'),
    
   
    
    path('tournaments/<int:tournament_id>/results/', tournament_results, name='tournament-results'),
    ]