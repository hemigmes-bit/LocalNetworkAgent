from datetime import datetime, timedelta, timezone


def review(ease, interval_days, repetitions, quality):
    if quality < 3:
        repetitions = 0
        interval_days = 1
    else:
        if repetitions == 0:
            interval_days = 1
        elif repetitions == 1:
            interval_days = 6
        else:
            interval_days = max(1, round(interval_days * ease))
        repetitions += 1
    ease = ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ease = max(1.3, ease)
    next_review = (datetime.now(timezone.utc) + timedelta(days=interval_days)).isoformat()
    return ease, interval_days, repetitions, next_review
