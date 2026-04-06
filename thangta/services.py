# thangta/services.py
import random
from .models import Match, Participant

def generate_round_one_fixtures(tournament, event_type, age_category, weight_category, gender, ring_number):
    """
    Generates Round 1 fixtures based on exact rules: filter, shuffle, odd/even check, assign corners.
    """
    
    # 1. Input Criteria: Filter all eligible participants
    participants_query = Participant.objects.filter(
        tournament=tournament,
        event_type=event_type,
        age_category=age_category,
        weight_category=weight_category,
        gender=gender
    )
    
    # Convert queryset to a standard Python list so we can shuffle it
    participants = list(participants_query)
    
    if len(participants) < 2:
        return False, "Not enough participants to create a bracket."

    # 2. Shuffling: Randomly shuffle to ensure fair matchups
    random.shuffle(participants)
    
    match_sequence = 1

    # 3. Match Formation (Odd Number Check)
    if len(participants) % 2 != 0:
        # The first participant gets a BYE
        bye_participant = participants.pop(0)
        
        # Create a "Bye" match where they automatically win and advance
        Match.objects.create(
            tournament=tournament,
            event_type=event_type, age_category=age_category, 
            weight_category=weight_category, gender=gender,
            round_number=1,
            match_sequence=match_sequence,
            ring_number=ring_number,
            participant_red=bye_participant,
            participant_blue=None, # No opponent
            winner=bye_participant, # Automatically advances
            is_completed=True
        )
        match_sequence += 1

    # 4. Match Formation (Even/Remaining Numbers)
    # Loop through the remaining list in steps of 2
    for i in range(0, len(participants), 2):
        player_1 = participants[i]
        player_2 = participants[i+1]
        
        # Player 1 gets Red, Player 2 gets Blue
        Match.objects.create(
            tournament=tournament,
            event_type=event_type, age_category=age_category, 
            weight_category=weight_category, gender=gender,
            round_number=1,
            match_sequence=match_sequence,
            ring_number=ring_number,
            participant_red=player_1,
            participant_blue=player_2,
            winner=None,
            is_completed=False
        )
        match_sequence += 1
        
    return True, "Round 1 fixtures generated successfully."


 
 
from .models import Match
def generate_next_round(tournament, event_type, age_category, weight_category, gender, current_round, ring_number):
    """Generates the next round, including Gold and Bronze medal matches."""
    
    current_matches = Match.objects.filter(
        tournament=tournament, event_type=event_type, age_category=age_category,
        weight_category=weight_category, gender=gender, round_number=current_round
    ).order_by('match_sequence')
    
    if current_matches.filter(is_completed=False).exists():
        return False, f"Cannot generate next round. Round {current_round} still has unfinished matches!"

    # ==========================================
    # 🚨 THE FIX: THE TOURNAMENT LOCKDOWN
    # Stop the script if we are already in the Medal Phase!
    # ==========================================
    if current_matches.filter(match_sequence__in=[1001, 1002]).exists():
        return False, "🏆 Category is complete! The Gold and Bronze medal matches have already been generated."

    next_round_num = current_round + 1

    if Match.objects.filter(
        tournament=tournament, event_type=event_type, age_category=age_category,
        weight_category=weight_category, gender=gender, round_number=next_round_num
    ).exists():
        return False, f"Round {next_round_num} has already been generated."

    # ==========================================
    # 🏆 THE MEDAL PHASE (Exactly 2 matches left)
    # ==========================================
    if current_matches.count() == 2:
        match_a, match_b = current_matches[0], current_matches[1]
        
        finalists = [match_a.winner, match_b.winner]
        
        loser_a = match_a.participant_red if match_a.winner == match_a.participant_blue else match_a.participant_blue
        loser_b = match_b.participant_red if match_b.winner == match_b.participant_blue else match_b.participant_blue
        
        # 🥇 Match 1: Gold/Silver Final
        Match.objects.create(
            tournament=tournament, event_type=event_type, age_category=age_category,
            weight_category=weight_category, gender=gender, round_number=next_round_num,
            participant_red=finalists[0], participant_blue=finalists[1],
            ring_number=ring_number, 
            match_sequence=1001  # Secret Gold Code
        )
        
        # 🥉 Match 2: Bronze Playoff
        if loser_a and loser_b:
            Match.objects.create(
                tournament=tournament, event_type=event_type, age_category=age_category,
                weight_category=weight_category, gender=gender, round_number=next_round_num,
                participant_red=loser_a, participant_blue=loser_b,
                ring_number=ring_number, 
                match_sequence=1002  # Secret Bronze Code
            )
            
        return True, "🏆 Gold/Silver Final and Bronze Playoff successfully generated!"

    # ==========================================
    # NORMAL ELIMINATION PHASE (> 2 matches)
    # ==========================================
    elif current_matches.count() > 2:
        winners = [m.winner for m in current_matches if m.winner]
        
        if not winners:
            return False, "No winners found to advance."

        seq = 1
        for i in range(0, len(winners), 2):
            p_red = winners[i]
            p_blue = winners[i+1] if i + 1 < len(winners) else None
            
            Match.objects.create(
                tournament=tournament, event_type=event_type, age_category=age_category,
                weight_category=weight_category, gender=gender, round_number=next_round_num,
                participant_red=p_red, participant_blue=p_blue,
                ring_number=ring_number, match_sequence=seq
            )
            seq += 1
            
        return True, f"Round {next_round_num} successfully generated!"

    elif current_matches.count() == 1:
        return False, "Category is complete! The final match has already been played."

    return False, "Failed to generate next round."