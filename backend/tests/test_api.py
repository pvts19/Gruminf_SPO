from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import booking, db, main

NOW = datetime(2026, 12, 1, 10, 0)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(main, "now", lambda: NOW)
    with TestClient(main.app) as c:
        yield c


def register(client, email="ivan@mail.ru"):
    r = client.post("/api/auth/register", json={
        "email": email, "password": "secret1", "name": "Иван", "phone": "+79991234567"})
    assert r.status_code == 201
    return {"Authorization": "Bearer " + r.json()["token"]}


def admin(client):
    r = client.post("/api/auth/login", json={"email": "admin@salon.ru", "password": "admin123"})
    return {"Authorization": "Bearer " + r.json()["token"]}


def add_pet(client, h, name="Бобик"):
    r = client.post("/api/pets", headers=h, json={"name": name, "species": "собака", "breed": "шпиц", "weight": 3.5})
    assert r.status_code == 201
    return r.json()["id"]


def book(client, h, pet_id, start, service_id=1):
    return client.post("/api/appointments", headers=h, json={
        "pet_id": pet_id, "service_id": service_id, "start_at": start})


# ---- бизнес-логика без API ----

def test_overlap():
    a, b = datetime(2026, 12, 2, 10), datetime(2026, 12, 2, 11)
    assert booking.is_overlap(a, b, datetime(2026, 12, 2, 10, 30), datetime(2026, 12, 2, 12))
    # запись, которая начинается ровно когда закончилась другая, не пересекается
    assert not booking.is_overlap(a, b, b, datetime(2026, 12, 2, 12))


def test_check_start_time():
    assert booking.check_start_time(datetime(2026, 12, 2, 10, 0), 60, NOW) is None
    assert booking.check_start_time(datetime(2026, 11, 30, 10, 0), 60, NOW) is not None  # прошлое
    assert booking.check_start_time(datetime(2026, 12, 2, 8, 30), 60, NOW) is not None   # до открытия
    assert booking.check_start_time(datetime(2026, 12, 2, 19, 30), 60, NOW) is not None  # не успеет до закрытия
    assert booking.check_start_time(datetime(2026, 12, 2, 10, 15), 60, NOW) is not None  # не по сетке


def test_free_slots():
    day = datetime(2026, 12, 2)
    busy = [(datetime(2026, 12, 2, 10), datetime(2026, 12, 2, 12))]
    slots = booking.free_slots(day, 60, busy, NOW)
    assert slots[0] == "09:00"
    assert "09:30" not in slots and "10:00" not in slots and "11:30" not in slots
    assert "12:00" in slots
    assert slots[-1] == "19:00"


def test_can_cancel():
    assert booking.can_client_cancel(datetime(2026, 12, 1, 12, 0), NOW)
    assert not booking.can_client_cancel(datetime(2026, 12, 1, 11, 30), NOW)


# ---- авторизация ----

def test_register_and_me(client):
    h = register(client)
    r = client.get("/api/auth/me", headers=h)
    assert r.json()["email"] == "ivan@mail.ru"
    assert r.json()["role"] == "client"


def test_register_duplicate_email(client):
    register(client)
    r = client.post("/api/auth/register", json={
        "email": "IVAN@mail.ru", "password": "secret1", "name": "Иван", "phone": "+79991234567"})
    assert r.status_code == 409


def test_register_bad_data(client):
    r = client.post("/api/auth/register", json={"email": "нет", "password": "1", "name": "", "phone": "abc"})
    assert r.status_code == 422


def test_login_wrong_password(client):
    register(client)
    r = client.post("/api/auth/login", json={"email": "ivan@mail.ru", "password": "wrong"})
    assert r.status_code == 401


def test_logout(client):
    h = register(client)
    client.post("/api/auth/logout", headers=h)
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_no_token(client):
    assert client.get("/api/pets").status_code == 401


# ---- питомцы ----

def test_pet_crud(client):
    h = register(client)
    pet_id = add_pet(client, h)
    r = client.put(f"/api/pets/{pet_id}", headers=h, json={"name": "Барсик", "species": "кошка", "weight": 4})
    assert r.json()["name"] == "Барсик"
    assert len(client.get("/api/pets", headers=h).json()) == 1
    assert client.delete(f"/api/pets/{pet_id}", headers=h).status_code == 200
    assert client.get("/api/pets", headers=h).json() == []


def test_pet_bad_weight(client):
    h = register(client)
    r = client.post("/api/pets", headers=h, json={"name": "Бобик", "species": "собака", "weight": -1})
    assert r.status_code == 422


def test_other_user_pet(client):
    h1 = register(client)
    h2 = register(client, "petr@mail.ru")
    pet_id = add_pet(client, h1)
    assert client.delete(f"/api/pets/{pet_id}", headers=h2).status_code == 404
    assert book(client, h2, pet_id, "2026-12-02T10:00").status_code == 404


# ---- услуги ----

def test_client_cannot_edit_services(client):
    h = register(client)
    r = client.post("/api/services", headers=h, json={"title": "X", "price": 100, "duration": 30})
    assert r.status_code == 403


def test_admin_service_crud(client):
    h = admin(client)
    r = client.post("/api/services", headers=h, json={"title": "Стрижка кота", "price": 2000, "duration": 90})
    assert r.status_code == 201
    sid = r.json()["id"]
    r = client.put(f"/api/services/{sid}", headers=h, json={"title": "Стрижка кота", "price": 2500, "duration": 90})
    assert r.json()["price"] == 2500
    assert client.delete(f"/api/services/{sid}", headers=h).status_code == 200


def test_service_bad_duration(client):
    h = admin(client)
    r = client.post("/api/services", headers=h, json={"title": "X", "price": 100, "duration": 45})
    assert r.status_code == 422


# ---- записи ----

def test_book_ok_and_price_saved(client):
    h = register(client)
    pet_id = add_pet(client, h)
    r = book(client, h, pet_id, "2026-12-02T10:00")
    assert r.status_code == 201
    assert r.json()["end_at"] == "2026-12-02T11:00"
    assert r.json()["price"] == 1200
    # админ меняет цену, но в старой записи цена остаётся прежней
    client.put("/api/services/1", headers=admin(client),
               json={"title": "Гигиеническая стрижка", "price": 9999, "duration": 60})
    assert client.get("/api/appointments", headers=h).json()[0]["price"] == 1200


def test_book_busy_time(client):
    h = register(client)
    pet_id = add_pet(client, h)
    book(client, h, pet_id, "2026-12-02T10:00", service_id=2)  # 2 часа: 10:00-12:00
    h2 = register(client, "petr@mail.ru")
    pet2 = add_pet(client, h2, "Шарик")
    assert book(client, h2, pet2, "2026-12-02T11:00").status_code == 409
    assert book(client, h2, pet2, "2026-12-02T12:00").status_code == 201


def test_book_past_and_closed(client):
    h = register(client)
    pet_id = add_pet(client, h)
    assert book(client, h, pet_id, "2026-11-30T10:00").status_code == 422
    assert book(client, h, pet_id, "2026-12-02T21:00").status_code == 422


def test_book_inactive_service(client):
    client.put("/api/services/1", headers=admin(client),
               json={"title": "Гигиеническая стрижка", "price": 1200, "duration": 60, "is_active": False})
    h = register(client)
    pet_id = add_pet(client, h)
    assert book(client, h, pet_id, "2026-12-02T10:00").status_code == 404


def test_slots_endpoint(client):
    h = register(client)
    pet_id = add_pet(client, h)
    book(client, h, pet_id, "2026-12-02T10:00")
    slots = client.get("/api/slots", params={"date": "2026-12-02", "service_id": 1}).json()
    assert "10:00" not in slots and "11:00" in slots


def test_cancel_frees_time(client):
    h = register(client)
    pet_id = add_pet(client, h)
    a_id = book(client, h, pet_id, "2026-12-02T10:00").json()["id"]
    assert client.post(f"/api/appointments/{a_id}/cancel", headers=h).status_code == 200
    assert book(client, h, pet_id, "2026-12-02T10:00").status_code == 201


def test_cancel_too_late(client):
    h = register(client)
    pet_id = add_pet(client, h)
    a_id = book(client, h, pet_id, "2026-12-01T11:00").json()["id"]  # через час
    assert client.post(f"/api/appointments/{a_id}/cancel", headers=h).status_code == 409
    # администратор отменить может
    assert client.post(f"/api/appointments/{a_id}/cancel", headers=admin(client)).status_code == 200


def test_cannot_delete_pet_with_booking(client):
    h = register(client)
    pet_id = add_pet(client, h)
    book(client, h, pet_id, "2026-12-02T10:00")
    assert client.delete(f"/api/pets/{pet_id}", headers=h).status_code == 409


def test_cannot_delete_used_service(client):
    h = register(client)
    pet_id = add_pet(client, h)
    book(client, h, pet_id, "2026-12-02T10:00")
    assert client.delete("/api/services/1", headers=admin(client)).status_code == 409


def test_admin_sees_all_and_sets_status(client):
    h1 = register(client)
    h2 = register(client, "petr@mail.ru")
    book(client, h1, add_pet(client, h1), "2026-12-02T10:00")
    book(client, h2, add_pet(client, h2, "Шарик"), "2026-12-02T12:00")
    assert len(client.get("/api/appointments", headers=h1).json()) == 1
    rows = client.get("/api/appointments", headers=admin(client)).json()
    assert len(rows) == 2
    r = client.patch(f"/api/appointments/{rows[0]['id']}/status", headers=admin(client), json={"status": "done"})
    assert r.status_code == 200
    assert client.patch(f"/api/appointments/{rows[0]['id']}/status", headers=h1,
                        json={"status": "cancelled"}).status_code == 403
