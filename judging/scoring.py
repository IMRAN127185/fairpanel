import math
from collections import defaultdict
from typing import Dict, List, Any, Optional, Set, Tuple


def compute_weighted_score(criteria_scores: Dict[str, float], criteria_defs: Dict[str, Dict[str, float]]) -> float:
    """
    Computes a 0-100 score for a single review given criterion scores and definitions.
    - Each criterion score is mapped from [min_score, max_score] to [0, 1].
    - Weights are normalized by sum of weights.
    - Returns weighted sum scaled to 0-100.
    """
    total_weight = sum(c['weight'] for c in criteria_defs.values() if c.get('weight', 0) > 0)
    if total_weight <= 0:
        return 0.0

    score_sum = 0.0
    for key, c_def in criteria_defs.items():
        min_s = c_def.get('min_score', 1.0)
        max_s = c_def.get('max_score', 5.0)
        weight = c_def.get('weight', 1.0)
        if weight <= 0:
            continue
        
        raw_val = criteria_scores.get(key)
        if raw_val is None:
            continue

        denom = max_s - min_s if max_s > min_s else 1.0
        norm_val = (float(raw_val) - min_s) / denom
        norm_val = max(0.0, min(1.0, norm_val))
        normalized_weight = weight / total_weight
        score_sum += norm_val * normalized_weight

    return score_sum * 100.0


def compute_pool_results(
    projects: List[Dict[str, Any]],
    reviews: List[Dict[str, Any]],
    criteria_defs: Dict[str, Dict[str, float]],
    min_required_reviews: int = 3
) -> Dict[str, Any]:
    """
    Computes raw and adjusted results for a pool of projects and reviews.
    Implements overlap_bias_v1 normalization algorithm.
    """
    # 1. Calculate weighted score for each review
    review_scores = {}  # review_id -> float (0-100)
    judge_project_scores = defaultdict(dict)  # judge_id -> {project_id: score}
    project_judge_scores = defaultdict(dict)  # project_id -> {judge_id: score}
    judge_all_scores = defaultdict(list)     # judge_id -> list of scores

    for r in reviews:
        r_id = r['id']
        j_id = r['judge_id']
        p_id = r['project_id']
        score = compute_weighted_score(r.get('criteria_scores', {}), criteria_defs)
        review_scores[r_id] = score
        judge_project_scores[j_id][p_id] = score
        project_judge_scores[p_id][j_id] = score
        judge_all_scores[j_id].append(score)

    # 2. Check for constant scorers (std dev == 0 over >= 2 reviews)
    constant_judges: Set[str] = set()
    for j_id, scores in judge_all_scores.items():
        if len(scores) >= 2:
            mean_s = sum(scores) / len(scores)
            variance = sum((s - mean_s) ** 2 for s in scores) / len(scores)
            if variance < 1e-6:
                constant_judges.add(j_id)

    # 3. For each judge, compute difference with peers on shared projects
    # A project has shared overlap if len(project_judge_scores[p_id]) >= 2
    judge_diffs = defaultdict(list)
    judge_overlap_count = defaultdict(int)

    # Graph for connected component checking among overlapping judges
    adj: Dict[str, Set[str]] = defaultdict(set)

    for p_id, judges in project_judge_scores.items():
        if len(judges) >= 2:
            j_list = list(judges.keys())
            for i in range(len(j_list)):
                for k in range(i + 1, len(j_list)):
                    adj[j_list[i]].add(j_list[k])
                    adj[j_list[k]].add(j_list[i])

            for j_id, score in judges.items():
                other_scores = [s for other_j, s in judges.items() if other_j != j_id]
                peer_mean = sum(other_scores) / len(other_scores)
                diff = score - peer_mean
                judge_diffs[j_id].append(diff)
                judge_overlap_count[j_id] += 1

    # Connected components check
    all_judges = list(judge_project_scores.keys())
    visited = set()
    components = []
    for j in all_judges:
        if j not in visited:
            comp = set()
            queue = [j]
            visited.add(j)
            while queue:
                curr = queue.pop()
                comp.add(curr)
                for neighbor in adj.get(curr, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            components.append(comp)

    is_graph_connected = len(components) <= 1 if len(all_judges) > 0 else True

    # 4. Compute severity and calibration for each judge
    judge_severity = {}
    judge_calibrated = {}
    judge_warnings = defaultdict(list)

    for j_id in all_judges:
        diffs = judge_diffs.get(j_id, [])
        n_overlap = judge_overlap_count.get(j_id, 0)
        is_constant = j_id in constant_judges

        if is_constant:
            judge_warnings[j_id].append("Constant scorer detected")

        # Must have at least 3 overlapping reviewed projects, not constant, and in main connected component
        can_calibrate = (
            n_overlap >= 3 and
            not is_constant and
            (is_graph_connected or (components and j_id in components[0]))
        )

        if can_calibrate and diffs:
            raw_severity = sum(diffs) / len(diffs)
            shrinkage = n_overlap / (n_overlap + 5.0)
            shrunk_severity = raw_severity * shrinkage
            judge_severity[j_id] = shrunk_severity
            judge_calibrated[j_id] = True
        else:
            judge_severity[j_id] = 0.0
            judge_calibrated[j_id] = False
            if n_overlap < 3:
                judge_warnings[j_id].append(f"Insufficient overlap ({n_overlap}/3 projects)")

    # 5. Compute project scores (raw and adjusted)
    project_results = []
    pool_warnings = []

    if not is_graph_connected and len(all_judges) > 1:
        pool_warnings.append("Judge overlap graph is disconnected into multiple components")

    for p in projects:
        p_id = p['id']
        judges_dict = project_judge_scores.get(p_id, {})
        review_count = len(judges_dict)
        warnings = []

        if review_count < min_required_reviews:
            warnings.append(f"Low review coverage: {review_count}/{min_required_reviews} reviews")

        if review_count == 0:
            project_results.append({
                'project_id': p_id,
                'title': p.get('title', ''),
                'raw_score': 0.0,
                'adjusted_score': None,
                'review_count': 0,
                'eligible_review_count': 0,
                'normalization_status': 'unreviewed',
                'warnings': warnings + ["No reviews submitted"],
            })
            continue

        raw_scores = list(judges_dict.values())
        raw_mean = sum(raw_scores) / len(raw_scores)

        # Adjusted scores
        adjusted_review_scores = []
        has_uncalibrated = False

        for j_id, score in judges_dict.items():
            if judge_calibrated.get(j_id, False):
                adjusted_review_scores.append(score - judge_severity[j_id])
            else:
                adjusted_review_scores.append(score)
                has_uncalibrated = True

        adjusted_mean = sum(adjusted_review_scores) / len(adjusted_review_scores)

        norm_status = "mixed" if has_uncalibrated else "calibrated"
        if all(not judge_calibrated.get(j, False) for j in judges_dict.keys()):
            norm_status = "uncalibrated"

        project_results.append({
            'project_id': p_id,
            'title': p.get('title', ''),
            'raw_score': raw_mean,
            'adjusted_score': adjusted_mean,
            'review_count': review_count,
            'eligible_review_count': review_count,
            'normalization_status': norm_status,
            'warnings': warnings,
        })

    # 6. Rank projects (raw and adjusted)
    # Sort by raw_score descending
    project_results.sort(key=lambda x: (-x['raw_score'], x['project_id']))
    for i, res in enumerate(project_results):
        res['raw_rank'] = i + 1

    # Check ties in raw score
    for i in range(len(project_results)):
        res = project_results[i]
        is_tied = False
        if i > 0 and abs(project_results[i-1]['raw_score'] - res['raw_score']) < 1e-5:
            is_tied = True
        if i < len(project_results) - 1 and abs(project_results[i+1]['raw_score'] - res['raw_score']) < 1e-5:
            is_tied = True
        res['tied'] = is_tied

    # Rank by adjusted score
    # Projects with adjusted_score None go to bottom
    valid_adj = [p for p in project_results if p['adjusted_score'] is not None]
    valid_adj.sort(key=lambda x: (-x['adjusted_score'], x['project_id']))
    for i, res in enumerate(valid_adj):
        res['adjusted_rank'] = i + 1

    for res in project_results:
        if res['adjusted_score'] is None:
            res['adjusted_rank'] = None

    return {
        'projects': project_results,
        'pool_warnings': pool_warnings,
        'judge_severity': judge_severity,
        'judge_calibrated': judge_calibrated,
        'judge_warnings': dict(judge_warnings),
        'is_graph_connected': is_graph_connected,
    }
