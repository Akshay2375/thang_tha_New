import threading

# The Global Thread Lock ensures atomic operations
state_lock = threading.Lock()

# The In-Memory Dictionaries
scores = {}
liveState = {}
total = {}

def process_submission(match_id, round_num, subround, corner, scorer_id, score):
    """Handles Phase 1 (Capture), Phase 2 (Wait), and Phase 3 (Compute)"""
    with state_lock:
        # --- INITIALIZATION ---
        if match_id not in scores:
            scores[match_id] = {}
            liveState[match_id] = {}
            total[match_id] = {}
            
        if round_num not in scores[match_id]:
            scores[match_id][round_num] = {}
            liveState[match_id][round_num] = {}
            total[match_id][round_num] = {'red': 0.0, 'blue': 0.0}
            
        if subround not in scores[match_id][round_num]:
            scores[match_id][round_num][subround] = {'red': {}, 'blue': {}}
            liveState[match_id][round_num][subround] = {
                'red': {'status': 'PENDING'}, 
                'blue': {'status': 'PENDING'}
            }

        # --- PHASE 1: CAPTURE ---
        # Overwrites if scorer resubmits
        scores[match_id][round_num][subround][corner][scorer_id] = float(score)

        # --- PHASE 2: WAIT ---
        corner_scores = scores[match_id][round_num][subround][corner]
        if len(corner_scores) == 3:
            
            # --- PHASE 3: COMPUTE ---
            # Critical Safety Rule: Check if already COMPLETE
            if liveState[match_id][round_num][subround][corner].get('status') == 'COMPLETE':
                return
                
            # Compute Average
            vals = list(corner_scores.values())
            avg = round(sum(vals) / 3.0, 2)
            
            # Update Live State
            liveState[match_id][round_num][subround][corner] = {
                'scores': vals,
                'average': avg,
                'status': 'COMPLETE'
            }
            
            # Update Running Total
            total[match_id][round_num][corner] += avg