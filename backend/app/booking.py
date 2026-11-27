"""Бизнес-логика записи на груминг. Без FastAPI, чтобы было легко тестировать."""
from datetime import datetime, timedelta

OPEN_HOUR = 9     # салон открывается в 9:00
CLOSE_HOUR = 20   # и закрывается в 20:00
STEP_MIN = 30     # записываться можно на каждые полчаса
CANCEL_HOURS = 2  # клиент может отменить запись не позже чем за 2 часа


def check_start_time(start: datetime, duration: int, now: datetime):
    """Возвращает текст ошибки или None, если время подходит."""
    if start <= now:
        return "Нельзя записаться на прошедшее время"
    if start.minute % STEP_MIN != 0 or start.second != 0:
        return "Запись возможна только на начало часа или половину часа"
    end = start + timedelta(minutes=duration)
    close = start.replace(hour=CLOSE_HOUR, minute=0)
    if start.hour < OPEN_HOUR or end > close:
        return f"Салон работает с {OPEN_HOUR}:00 до {CLOSE_HOUR}:00"
    return None


def is_overlap(start1, end1, start2, end2):
    return start1 < end2 and start2 < end1


def free_slots(day: datetime, duration: int, busy: list, now: datetime):
    """busy - список пар (start, end) уже занятых записей в этот день."""
    slots = []
    t = day.replace(hour=OPEN_HOUR, minute=0, second=0, microsecond=0)
    while True:
        end = t + timedelta(minutes=duration)
        if end > day.replace(hour=CLOSE_HOUR, minute=0, second=0, microsecond=0):
            break
        if t > now and not any(is_overlap(t, end, b[0], b[1]) for b in busy):
            slots.append(t.strftime("%H:%M"))
        t += timedelta(minutes=STEP_MIN)
    return slots


def can_client_cancel(start: datetime, now: datetime) -> bool:
    return start - now >= timedelta(hours=CANCEL_HOURS)
