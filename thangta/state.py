import threading
import math

# Global lock to ensure thread safety when multiple scorers submit at the exact same millisecond
state_lock = threading.Lock()

# The global in-memory state dictionary
# Structure: matches_state[match_id]['rounds'][round_num]['subrounds'][subround_num][corner]['scorers'][scorer_id]
matches_state = {}

def get_or_create_match_state(match_id):
    if match_id not in matches_state:
        matches_state[match_id] = {
            'rounds': {1: {'subrounds': {}}, 2: {'subrounds': {}}, 3: {'subrounds': {}}},
            'clients': [] # We will store SSE queues here in Step 2
        }
    return matches_state[match_id]

def get_or_create_subround(match_state, round_num, subround):
    round_state = match_state['rounds'][round_num]
    if subround not in round_state['subrounds']:
        round_state['subrounds'][subround] = {
            'red': {
                'scorers': {}, # Format: scorer_id: {'score': int, 'foul': int, 'flagged': bool}
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
    return round_state['subrounds'][subround]
# UPDATE THIS FUNCTION IN state.py
def submit_scorer_data(match_id, round_num, subround, corner, scorer_id, scorer_name, score, foul=0):
    """Called when a scorer submits their score."""
    with state_lock:
        match_state = get_or_create_match_state(match_id)
        sr_state = get_or_create_subround(match_state, round_num, subround)
        corner_state = sr_state[corner]

        if corner_state['status'] == 'COMPLETE':
            return False, match_state

        # 🚨 NEW: Record the scorer's actual name along with their input
        corner_state['scorers'][scorer_id] = {
            'name': scorer_name,
            'score': score,
            'foul': foul,
            'flagged': False
        }

        # Check if all 3 scorers have submitted
        newly_completed = False
        if len(corner_state['scorers']) == 3:
            _finalize_corner_subround(corner_state)
            newly_completed = True

        event_name = 'SUBROUND_COMPLETE' if newly_completed else 'SCORER_SUBMITTED'
        
    broadcast_match_update(match_id, event_name)
    return newly_completed, match_state



def _finalize_corner_subround(corner_state):
    """Calculates the floor average and applies the 3/3 foul rule."""
    scorers_data = list(corner_state['scorers'].values())
    
    # 1. Calculate floor of average score
    total_score = sum(s['score'] for s in scorers_data)
    corner_state['final_score'] = math.floor(total_score / 3.0)

    # 2. Foul Logic: Only apply if ALL 3 scorers gave the EXACT same foul value
    foul_values = [s['foul'] for s in scorers_data]
    if len(set(foul_values)) == 1 and foul_values[0] < 0:
        # All 3 submitted the same foul
        corner_state['final_foul'] = foul_values[0]
    else:
        # Disagreement or no foul -> ignored
        corner_state['final_foul'] = 0

    corner_state['status'] = 'COMPLETE'

def flag_score(match_id, round_num, subround, corner, scorer_id):
    """Called by the judge to flag a specific scorer's input."""
    success = False
    with state_lock:
        try:
            corner_state = matches_state[match_id]['rounds'][round_num]['subrounds'][subround][corner]
            if scorer_id in corner_state['scorers']:
                current_flag = corner_state['scorers'][scorer_id]['flagged']
                corner_state['scorers'][scorer_id]['flagged'] = not current_flag
                success = True
        except KeyError:
            pass
            
    if success:
        # 🚨 NEW: Broadcast the flag update!
        broadcast_match_update(match_id, 'SCORE_FLAGGED')
        return True, matches_state[match_id]
        
    return False, None
    
    
import queue # Add this to the very top of state.py if it isn't there!
import json

# ==========================================
# SSE BROADCASTER LOGIC
# ==========================================

def register_client(match_id):
    """Creates a unique listening queue for a new Judge connection."""
    with state_lock:
        match_state = get_or_create_match_state(match_id)
        client_queue = queue.Queue()
        match_state['clients'].append(client_queue)
        return client_queue

def remove_client(match_id, client_queue):
    """Removes the queue when the Judge closes their browser."""
    with state_lock:
        try:
            matches_state[match_id]['clients'].remove(client_queue)
        except (KeyError, ValueError):
            pass

def broadcast_match_update(match_id, event_type):
    """Pushes the ENTIRE current match state to all connected Judges."""
    with state_lock:
        if match_id in matches_state:
            # We send the whole state so the Judge's matrix is always perfectly synced
            payload = {
                'type': event_type,
                'state': matches_state[match_id]['rounds']
            }
            
            # Send to every connected judge
            for q in matches_state[match_id]['clients']:
                q.put(payload)