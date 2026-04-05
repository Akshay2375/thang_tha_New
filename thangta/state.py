import threading
import math
import queue
import json

# ==========================================
# 🚨 THE GLOBAL RAM MEMORY & LOCK
# ==========================================
# This dictionary is your "RAM". It stays alive as long as the server is running.
active_matches = {}

# This lock prevents two scorers from saving at the exact same millisecond
state_lock = threading.Lock()

# ==========================================
# DATABASE HYDRATION
# ==========================================
def hydrate_match_from_db(match_id, match_state):
    """Pulls all historical scores from the database and rebuilds the RAM matrix."""
    from .models import Score, Match 
    
    try:
        match = Match.objects.get(id=match_id)
        historical_scores = Score.objects.filter(match=match).order_by('round_num', 'sub_round', 'timestamp')
    except Exception:
        return 

    for score in historical_scores:
        r_num = str(score.round_num)
        sr_num = str(score.sub_round)
        
        if score.participant_id == match.participant_red_id:
            corner = 'red'
        else:
            corner = 'blue'
            
        sr_state = get_or_create_subround(match_state, r_num, sr_num)
        corner_state = sr_state[corner]
        
        actual_score = 0 if score.is_foul else score.points
        actual_foul = score.points if score.is_foul else 0
       
        scorer_name = score.scorer.get_full_name() or score.scorer.username if score.scorer else f"Scorer {score.scorer_id}"
        corner_state['scorers'][score.scorer_id] = {
            'name': scorer_name,
            'score': actual_score,
            'foul': actual_foul,
            'flagged': score.is_flagged
        }
        
        submissions = list(corner_state['scorers'].values())
        if len(submissions) == 3:
            corner_state['status'] = 'COMPLETE'
            
            foul_count = sum(1 for s in submissions if s['foul'] < 0)
            final_foul_penalty = -3 if foul_count == 3 else 0
            
            total_points = sum(s['score'] for s in submissions)
            average_points = total_points // 3  
            
            corner_state['final_score'] = average_points + final_foul_penalty

# ==========================================
# RAM STATE MANAGEMENT
# ==========================================
def get_or_create_match_state(match_id):
    """Gets the RAM state. If it's empty, it builds it and hydrates it!"""
    str_id = str(match_id)
    
    if str_id not in active_matches:
        active_matches[str_id] = {
            'rounds': {},
            'clients': []  # 🚨 FIXED: Now the broadcaster has a place to put connected Judges!
        }
        hydrate_match_from_db(match_id, active_matches[str_id])
        
    return active_matches[str_id]



 

def get_or_create_subround(match_state, round_num, subround):
    # 🚨 THE FIX: Force both of these to strings immediately to prevent JSON overwrite!
    r_str = str(round_num)
    sr_str = str(subround)
    
    # Create the Round folder if it doesn't exist yet!
    if r_str not in match_state['rounds']:
        match_state['rounds'][r_str] = {
            'subrounds': {}
        }
        
    round_state = match_state['rounds'][r_str]
    
    # Now it is safe to check for the subround
    if sr_str not in round_state['subrounds']:
        round_state['subrounds'][sr_str] = {
            'red': {
                'scorers': {}, 
                'status': 'PENDING',
                'final_score': 0,
                'final_foul': 0
            },
            'blue': {
                'scorers': {},
                'status': 'PENDING',
                'final_score': 0,
                'final_foul': 0
            }
        }
    return round_state['subrounds'][sr_str]


def submit_scorer_data(match_id, round_num, subround, corner, scorer_id, scorer_name, score, foul=0):
    """Called when a scorer submits their score."""
    
    # 🚨 THE FIX: Also force them to strings here just to be safe!
    r_str = str(round_num)
    sr_str = str(subround)
    
    with state_lock:
        match_state = get_or_create_match_state(match_id)
        sr_state = get_or_create_subround(match_state, r_str, sr_str)
        corner_state = sr_state[corner]

        if corner_state['status'] == 'COMPLETE':
            return False, match_state

        corner_state['scorers'][scorer_id] = {
            'name': scorer_name,
            'score': score,
            'foul': foul,
            'flagged': False
        }

        newly_completed = False
        submissions = list(corner_state['scorers'].values())

        if len(submissions) == 3:
            corner_state['status'] = 'COMPLETE'
            newly_completed = True

            foul_count = sum(1 for s in submissions if s['foul'] < 0)
            final_foul_penalty = -3 if foul_count == 3 else 0

            total_points = sum(s['score'] for s in submissions)
            average_points = total_points // 3  

            corner_state['final_score'] = average_points + final_foul_penalty

    event_name = 'SUBROUND_COMPLETE' if newly_completed else 'SCORER_SUBMITTED'
    broadcast_match_update(match_id, event_name)
    
    return newly_completed, match_state


def flag_score(match_id, round_num, subround, corner, scorer_id):
    """Called by the judge to flag a specific scorer's input."""
    success = False
    str_id = str(match_id)
    with state_lock:
        try:
            # 🚨 FIXED: Changed matches_state to active_matches
            corner_state = active_matches[str_id]['rounds'][round_num]['subrounds'][subround][corner]
            if scorer_id in corner_state['scorers']:
                current_flag = corner_state['scorers'][scorer_id]['flagged']
                corner_state['scorers'][scorer_id]['flagged'] = not current_flag
                success = True
        except KeyError:
            pass
            
    if success:
        broadcast_match_update(match_id, 'SCORE_FLAGGED')
        return True, active_matches[str_id]
        
    return False, None
    
 
 
def register_client(match_id):
    """Creates a unique listening queue for a new Judge connection."""
    with state_lock:
        match_state = get_or_create_match_state(match_id)
        client_queue = queue.Queue()
        match_state['clients'].append(client_queue)
        return client_queue

def remove_client(match_id, client_queue):
    """Removes the queue when the Judge closes their browser."""
    str_id = str(match_id)
    with state_lock:
        try:
            # 🚨 FIXED: Changed matches_state to active_matches
            active_matches[str_id]['clients'].remove(client_queue)
        except (KeyError, ValueError):
            pass

def broadcast_match_update(match_id, event_type):
    """Pushes the ENTIRE current match state to all connected Judges."""
    str_id = str(match_id)
    with state_lock:
        # 🚨 FIXED: Changed matches_state to active_matches
        if str_id in active_matches:
            payload = {
                'type': event_type,
                'state': active_matches[str_id]['rounds']
            }
            
            for q in active_matches[str_id]['clients']:
                q.put(payload)