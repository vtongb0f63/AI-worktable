"""Pure scheduling and learning rules. No HTTP or database dependencies."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import re
import unicodedata

ZONE = ZoneInfo('Asia/Shanghai')
INTERVALS = (1, 3, 7, 14, 30, 60)


class Conflict(ValueError):
    pass


def today():
    return datetime.now(ZONE).date().isoformat()


def week_start(day):
    value = date.fromisoformat(day)
    return (value - timedelta(days=value.weekday())).isoformat()


def minutes(value):
    h, m = map(int, value.split(':'))
    if not 0 <= h < 24 or not 0 <= m < 60:
        raise ValueError('时间必须在 00:00 至 23:59 之间')
    return h * 60 + m


def course_occurrences(courses, start, end):
    result = []
    current, last = date.fromisoformat(start), date.fromisoformat(end)
    while current <= last:
        for course in courses:
            first = date.fromisoformat(course['semester_start'])
            first -= timedelta(days=first.weekday())
            week = (current - first).days // 7 + 1
            if current.weekday() != course['weekday'] or not course['start_week'] <= week <= course['end_week']:
                continue
            if course['parity'] == 'odd' and week % 2 != 1 or course['parity'] == 'even' and week % 2 != 0:
                continue
            if current.isoformat() in course.get('excluded_dates', []):
                continue
            result.append({**course, 'date': current.isoformat(), 'type': 'course', 'week_number': week})
        current += timedelta(days=1)
    return result


def check_conflicts(items, occupied):
    seen = list(occupied)
    for item in items:
        if not item.get('start_time'):
            continue
        for other in seen:
            if other.get('id') and other.get('id') == item.get('id'):
                continue
            if item['date'] != other['date'] or not other.get('start_time'):
                continue
            if minutes(item['start_time']) < minutes(other['end_time']) and minutes(other['start_time']) < minutes(item['end_time']):
                raise Conflict(f"{item['date']}「{item['title']}」与「{other['title']}」时间冲突，请修改时间")
        seen.append(item)


def normalize_answer(value):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', value).strip().casefold()).rstrip('.。')


def next_review(stage, correct, day):
    stage = min(stage + 1, len(INTERVALS)) if correct else 0
    interval = INTERVALS[max(stage - 1, 0)]
    return stage, (date.fromisoformat(day) + timedelta(days=interval)).isoformat()
