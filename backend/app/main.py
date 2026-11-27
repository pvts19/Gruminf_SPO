import os
import secrets
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import booking
from app.db import get_db, init_db
from app.security import check_password, hash_password


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(title="Груминг-салон «Пушистик»", version="1.0", lifespan=lifespan)
bearer = HTTPBearer(auto_error=False)


def now():
    return datetime.now()


# ---------- схемы ----------

class RegisterIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=100)
    password: str = Field(min_length=6, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(pattern=r"^\+?\d{10,15}$")


class LoginIn(BaseModel):
    email: str
    password: str


class PetIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    species: Literal["собака", "кошка", "другое"]
    breed: str = Field(default="", max_length=50)
    weight: float = Field(gt=0, le=100)


class ServiceIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    price: int = Field(gt=0, le=100000)
    duration: int = Field(ge=30, le=480, multiple_of=30)
    is_active: bool = True


class AppointmentIn(BaseModel):
    pet_id: int
    service_id: int
    start_at: datetime
    comment: str = Field(default="", max_length=500)


class StatusIn(BaseModel):
    status: Literal["booked", "done", "cancelled"]


# ---------- авторизация ----------

def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer), db=Depends(get_db)):
    if creds is None:
        raise HTTPException(401, "Нужно войти в систему")
    user = db.execute(
        "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?",
        (creds.credentials,),
    ).fetchone()
    if user is None:
        raise HTTPException(401, "Сессия недействительна, войдите заново")
    return user


def admin_user(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Доступно только администратору")
    return user


def user_out(u):
    return {"id": u["id"], "email": u["email"], "name": u["name"], "phone": u["phone"], "role": u["role"]}


def new_session(db, user_id):
    token = secrets.token_hex(32)
    db.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
    db.commit()
    return token


@app.post("/api/auth/register", status_code=201, tags=["Авторизация"])
def register(data: RegisterIn, db=Depends(get_db)):
    try:
        cur = db.execute(
            "INSERT INTO users (email, password_hash, name, phone) VALUES (?, ?, ?, ?)",
            (data.email.lower(), hash_password(data.password), data.name, data.phone),
        )
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Пользователь с таким email уже есть")
    user = db.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    return {"token": new_session(db, user["id"]), "user": user_out(user)}


@app.post("/api/auth/login", tags=["Авторизация"])
def login(data: LoginIn, db=Depends(get_db)):
    user = db.execute("SELECT * FROM users WHERE email = ?", (data.email.lower(),)).fetchone()
    if user is None or not check_password(data.password, user["password_hash"]):
        raise HTTPException(401, "Неверный email или пароль")
    return {"token": new_session(db, user["id"]), "user": user_out(user)}


@app.get("/api/auth/me", tags=["Авторизация"])
def me(user=Depends(current_user)):
    return user_out(user)


@app.post("/api/auth/logout", tags=["Авторизация"])
def logout(creds: HTTPAuthorizationCredentials = Depends(bearer), user=Depends(current_user), db=Depends(get_db)):
    db.execute("DELETE FROM sessions WHERE token = ?", (creds.credentials,))
    db.commit()
    return {"ok": True}


# ---------- питомцы ----------

def get_own_pet(db, pet_id, user):
    pet = db.execute("SELECT * FROM pets WHERE id = ?", (pet_id,)).fetchone()
    if pet is None or pet["owner_id"] != user["id"]:
        raise HTTPException(404, "Питомец не найден")
    return pet


@app.get("/api/pets", tags=["Питомцы"])
def list_pets(user=Depends(current_user), db=Depends(get_db)):
    rows = db.execute("SELECT * FROM pets WHERE owner_id = ? ORDER BY id", (user["id"],)).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/pets", status_code=201, tags=["Питомцы"])
def create_pet(data: PetIn, user=Depends(current_user), db=Depends(get_db)):
    cur = db.execute(
        "INSERT INTO pets (owner_id, name, species, breed, weight) VALUES (?, ?, ?, ?, ?)",
        (user["id"], data.name, data.species, data.breed, data.weight),
    )
    db.commit()
    return dict(db.execute("SELECT * FROM pets WHERE id = ?", (cur.lastrowid,)).fetchone())


@app.put("/api/pets/{pet_id}", tags=["Питомцы"])
def update_pet(pet_id: int, data: PetIn, user=Depends(current_user), db=Depends(get_db)):
    get_own_pet(db, pet_id, user)
    db.execute(
        "UPDATE pets SET name = ?, species = ?, breed = ?, weight = ? WHERE id = ?",
        (data.name, data.species, data.breed, data.weight, pet_id),
    )
    db.commit()
    return dict(db.execute("SELECT * FROM pets WHERE id = ?", (pet_id,)).fetchone())


@app.delete("/api/pets/{pet_id}", tags=["Питомцы"])
def delete_pet(pet_id: int, user=Depends(current_user), db=Depends(get_db)):
    get_own_pet(db, pet_id, user)
    active = db.execute(
        "SELECT COUNT(*) FROM appointments WHERE pet_id = ? AND status = 'booked'", (pet_id,)
    ).fetchone()[0]
    if active:
        raise HTTPException(409, "У питомца есть активные записи, сначала отмените их")
    db.execute("DELETE FROM pets WHERE id = ?", (pet_id,))
    db.commit()
    return {"ok": True}


# ---------- услуги ----------

def service_out(r):
    d = dict(r)
    d["is_active"] = bool(d["is_active"])
    return d


@app.get("/api/services", tags=["Услуги"])
def list_services(db=Depends(get_db)):
    return [service_out(r) for r in db.execute("SELECT * FROM services ORDER BY id").fetchall()]


@app.post("/api/services", status_code=201, tags=["Услуги"])
def create_service(data: ServiceIn, admin=Depends(admin_user), db=Depends(get_db)):
    cur = db.execute(
        "INSERT INTO services (title, description, price, duration, is_active) VALUES (?, ?, ?, ?, ?)",
        (data.title, data.description, data.price, data.duration, int(data.is_active)),
    )
    db.commit()
    return service_out(db.execute("SELECT * FROM services WHERE id = ?", (cur.lastrowid,)).fetchone())


@app.put("/api/services/{service_id}", tags=["Услуги"])
def update_service(service_id: int, data: ServiceIn, admin=Depends(admin_user), db=Depends(get_db)):
    cur = db.execute(
        "UPDATE services SET title = ?, description = ?, price = ?, duration = ?, is_active = ? WHERE id = ?",
        (data.title, data.description, data.price, data.duration, int(data.is_active), service_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(404, "Услуга не найдена")
    db.commit()
    return service_out(db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone())


@app.delete("/api/services/{service_id}", tags=["Услуги"])
def delete_service(service_id: int, admin=Depends(admin_user), db=Depends(get_db)):
    used = db.execute("SELECT COUNT(*) FROM appointments WHERE service_id = ?", (service_id,)).fetchone()[0]
    if used:
        raise HTTPException(409, "На эту услугу уже были записи. Её можно только отключить")
    cur = db.execute("DELETE FROM services WHERE id = ?", (service_id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "Услуга не найдена")
    db.commit()
    return {"ok": True}


# ---------- записи ----------

def busy_intervals(db, day: datetime, exclude_id=None):
    rows = db.execute(
        "SELECT id, start_at, end_at FROM appointments WHERE status = 'booked' AND start_at LIKE ?",
        (day.strftime("%Y-%m-%d") + "%",),
    ).fetchall()
    return [
        (datetime.fromisoformat(r["start_at"]), datetime.fromisoformat(r["end_at"]))
        for r in rows if r["id"] != exclude_id
    ]


def get_active_service(db, service_id):
    service = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
    if service is None or not service["is_active"]:
        raise HTTPException(404, "Услуга не найдена или недоступна")
    return service


@app.get("/api/slots", tags=["Записи"])
def get_slots(date: str, service_id: int, db=Depends(get_db)):
    try:
        day = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(422, "Дата должна быть в формате ГГГГ-ММ-ДД")
    service = get_active_service(db, service_id)
    return booking.free_slots(day, service["duration"], busy_intervals(db, day), now())


APPOINTMENT_SELECT = """
SELECT a.*, p.name AS pet_name, p.species, s.title AS service_title,
       u.name AS owner_name, u.phone AS owner_phone
FROM appointments a
JOIN pets p ON p.id = a.pet_id
JOIN services s ON s.id = a.service_id
JOIN users u ON u.id = p.owner_id
"""


@app.get("/api/appointments", tags=["Записи"])
def list_appointments(user=Depends(current_user), db=Depends(get_db)):
    if user["role"] == "admin":
        rows = db.execute(APPOINTMENT_SELECT + " ORDER BY a.start_at").fetchall()
    else:
        rows = db.execute(APPOINTMENT_SELECT + " WHERE p.owner_id = ? ORDER BY a.start_at DESC", (user["id"],)).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/appointments", status_code=201, tags=["Записи"])
def create_appointment(data: AppointmentIn, user=Depends(current_user), db=Depends(get_db)):
    get_own_pet(db, data.pet_id, user)
    service = get_active_service(db, data.service_id)
    start = data.start_at.replace(tzinfo=None, microsecond=0)
    error = booking.check_start_time(start, service["duration"], now())
    if error:
        raise HTTPException(422, error)
    end = start + timedelta(minutes=service["duration"])
    for b_start, b_end in busy_intervals(db, start):
        if booking.is_overlap(start, end, b_start, b_end):
            raise HTTPException(409, "Это время уже занято, выберите другое")
    cur = db.execute(
        "INSERT INTO appointments (pet_id, service_id, start_at, end_at, price, comment) VALUES (?, ?, ?, ?, ?, ?)",
        (data.pet_id, data.service_id, start.isoformat(timespec="minutes"),
         end.isoformat(timespec="minutes"), service["price"], data.comment),
    )
    db.commit()
    return dict(db.execute(APPOINTMENT_SELECT + " WHERE a.id = ?", (cur.lastrowid,)).fetchone())


def get_appointment_for(db, appointment_id, user):
    a = db.execute(APPOINTMENT_SELECT + " WHERE a.id = ?", (appointment_id,)).fetchone()
    if a is None:
        raise HTTPException(404, "Запись не найдена")
    if user["role"] != "admin":
        owner = db.execute("SELECT owner_id FROM pets WHERE id = ?", (a["pet_id"],)).fetchone()
        if owner["owner_id"] != user["id"]:
            raise HTTPException(404, "Запись не найдена")
    return a


@app.post("/api/appointments/{appointment_id}/cancel", tags=["Записи"])
def cancel_appointment(appointment_id: int, user=Depends(current_user), db=Depends(get_db)):
    a = get_appointment_for(db, appointment_id, user)
    if a["status"] != "booked":
        raise HTTPException(409, "Эту запись уже нельзя отменить")
    if user["role"] != "admin" and not booking.can_client_cancel(datetime.fromisoformat(a["start_at"]), now()):
        raise HTTPException(409, f"Отменить запись можно не позже чем за {booking.CANCEL_HOURS} часа")
    db.execute("UPDATE appointments SET status = 'cancelled' WHERE id = ?", (appointment_id,))
    db.commit()
    return {"ok": True}


@app.patch("/api/appointments/{appointment_id}/status", tags=["Записи"])
def set_status(appointment_id: int, data: StatusIn, admin=Depends(admin_user), db=Depends(get_db)):
    a = get_appointment_for(db, appointment_id, admin)
    if data.status == "booked" and a["status"] != "booked":
        # возвращаем запись обратно - надо проверить, что время ещё свободно
        start, end = datetime.fromisoformat(a["start_at"]), datetime.fromisoformat(a["end_at"])
        for b_start, b_end in busy_intervals(db, start, exclude_id=a["id"]):
            if booking.is_overlap(start, end, b_start, b_end):
                raise HTTPException(409, "Это время уже занято другой записью")
    db.execute("UPDATE appointments SET status = ? WHERE id = ?", (data.status, appointment_id))
    db.commit()
    return {"ok": True}


# фронтенд (обычные html-файлы) отдаём с того же сервера
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
