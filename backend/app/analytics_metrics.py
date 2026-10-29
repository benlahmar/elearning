import math
from collections import Counter, defaultdict

from .metrics import coverage


def played_intervals(events):
    intervals = []
    for event in events:
        if event.event_type != 'heartbeat':
            continue
        a, b = event.payload.get('from_seconds'), event.payload.get('to_seconds')
        if all(type(v) in (int, float) and math.isfinite(v) for v in (a, b)) and 0 <= a < b:
            intervals.append((a, b))
    return intervals


def learner_metrics(events, duration):
    intervals = played_intervals(events)
    result = coverage(intervals, duration)
    played = sum(max(0, min(b, duration) - max(a, 0)) for a, b in intervals)
    manual = [e for e in events if e.event_type == 'seek' and e.payload.get('reason') != 'resume']
    return {**result, 'played_seconds': played, 'replayed_seconds': max(0, played - result['covered_seconds']), 'completed': result['coverage'] >= .9, 'resume_seeks': sum(e.event_type == 'seek' and e.payload.get('reason') == 'resume' for e in events), 'backward_seeks': sum(e.payload.get('to_seconds', 0) < e.payload.get('from_seconds', 0) for e in manual), 'forward_seeks': sum(e.payload.get('to_seconds', 0) > e.payload.get('from_seconds', 0) for e in manual), 'event_count': len(events)}


def video_summary(resource, events, sessions):
    grouped = defaultdict(list)
    for event in events:
        grouped[event.user_id].append(event)
    people = set(grouped) | {s.user_id for s in sessions}
    metrics = [learner_metrics(grouped[id_], resource.duration) for id_ in people]
    count = len(metrics)
    return {'resource_id': resource.id, 'title': resource.title, 'duration': resource.duration, 'archived': resource.archived, 'opens': len({s.id for s in sessions} | {e.session_id for e in events}), 'learners': count, 'average_coverage': sum(m['coverage'] for m in metrics) / count if count else 0, 'completion_rate': sum(m['completed'] for m in metrics) / count if count else 0, 'replayed_seconds': sum(m['replayed_seconds'] for m in metrics), 'backward_seeks': sum(m['backward_seeks'] for m in metrics), 'forward_seeks': sum(m['forward_seeks'] for m in metrics), 'events': len(events)}


def heatmap(events, duration):
    width = max(10, math.ceil(duration / 300 / 10) * 10)
    grouped = defaultdict(list)
    for event in events:
        grouped[event.user_id].append(event)
    bins = []
    for start in range(0, math.ceil(duration), width):
        end = min(duration, start + width)
        viewed, replayed, skipped = 0, 0, 0
        for learner_events in grouped.values():
            clipped = [(max(start, a), min(end, b)) for a, b in played_intervals(learner_events) if a < end and b > start]
            distinct = coverage(clipped, duration)['covered_seconds']
            played = sum(b - a for a, b in clipped)
            viewed += distinct > 0
            replayed += played - distinct > .01
            skipped += any(e.event_type == 'seek' and e.payload.get('reason') != 'resume' and e.payload.get('to_seconds', 0) > e.payload.get('from_seconds', 0) and e.payload.get('from_seconds', 0) < end and e.payload.get('to_seconds', 0) > start for e in learner_events)
        bins.append({'start': start, 'end': end, 'viewed_learners': viewed, 'replayed_learners': replayed, 'skipped_learners': skipped})
    return {'bin_seconds': width, 'bins': bins}


def quality(events, receipts):
    sequences = Counter((e.session_id, e.sequence) for e in events)
    from datetime import timezone
    return {'accepted': sum(r.accepted for r in receipts), 'duplicate': sum(r.duplicate for r in receipts), 'rejected': sum(r.rejected for r in receipts), 'duplicate_sequences': sum(n - 1 for n in sequences.values() if n > 1), 'clock_skew_events': sum(abs((e.occurred_at.replace(tzinfo=timezone.utc) - e.received_at.replace(tzinfo=timezone.utc)).total_seconds()) > 300 for e in events), 'retained_events': len(events)}
