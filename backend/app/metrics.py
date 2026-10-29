def coverage(intervals, duration):
    """Union of played media intervals; seeks and repeated sections add no coverage."""
    merged = []
    for start, end in sorted(intervals):
        start, end = max(0, start), min(duration, end)
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    distinct = sum(end - start for start, end in merged)
    return {'covered_seconds': distinct, 'coverage': distinct / duration if duration else 0}
