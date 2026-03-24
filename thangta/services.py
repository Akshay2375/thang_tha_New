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




def generate_next_round(tournament, event_type, age_category, weight_category, gender, current_round, ring_number):
    """
    Takes the winners of the current round and sequentially pairs them for the next round.
    """
    
    # Get all matches from the current round, ordered by their sequence
    current_matches = Match.objects.filter(
        tournament=tournament, event_type=event_type, age_category=age_category, 
        weight_category=weight_category, gender=gender, round_number=current_round
    ).order_by('match_sequence')

    # Check termination condition: If there's only 1 match, the winner of it is the Final Champion
    if current_matches.count() == 1:
        return False, "Tournament is already complete. We have a champion."

    # Verify all matches in the current round are finished
    if current_matches.filter(is_completed=False).exists():
        return False, "Cannot generate next round. Not all matches are completed."

    # Extract winners sequentially (Player 1 vs 3, etc.)
    winners = [match.winner for match in current_matches if match.winner]
    
    next_round_number = current_round + 1
    match_sequence = 1

    # Apply the exact same Odd/Even Bye logic, but WITHOUT shuffling to maintain bracket integrity
    if len(winners) % 2 != 0:
        bye_participant = winners.pop(0)
        Match.objects.create(
            tournament=tournament, event_type=event_type, age_category=age_category, 
            weight_category=weight_category, gender=gender,
            round_number=next_round_number, match_sequence=match_sequence, ring_number=ring_number,
            participant_red=bye_participant, participant_blue=None, 
            winner=bye_participant, is_completed=True
        )
        match_sequence += 1

    # Pair up the remaining winners sequentially
    for i in range(0, len(winners), 2):
        Match.objects.create(
            tournament=tournament, event_type=event_type, age_category=age_category, 
            weight_category=weight_category, gender=gender,
            round_number=next_round_number, match_sequence=match_sequence, ring_number=ring_number,
            participant_red=winners[i], participant_blue=winners[i+1]
            
        )
        match_sequence += 1
        
        
    return True, f"Round {next_round_number} generated successfully."