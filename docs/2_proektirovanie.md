[README](../README.md) · [1. Описание](1_opisanie.md) · **2. Проектирование** · [3. Backend](3_backend.md) · [4. Frontend](4_frontend.md) · [5. Тестирование](5_testirovanie.md)

# 2. Аналитика и проектирование

> **Кратко:** пять обязательных диаграмм (Use Case, Activity, ER, Component, Sequence), прототипы экранов и выбор технологий.

| Диаграмма | Что показывает | Раздел |
|-----------|----------------|:------:|
| Use Case | кто и что делает в системе | [2.1](#21-use-case-diagram) |
| Activity | процесс записи на услугу | [2.2](#22-activity-diagram--запись-на-услугу) |
| ER | таблицы базы данных и связи | [2.3](#23-er-diagram) |
| Component | из каких частей состоит система | [2.4](#24-component-diagram) |
| Sequence | обмен запросами при записи | [2.5](#25-sequence-diagram--запись-на-услугу) |

## 2.1 Use Case Diagram

```mermaid
flowchart LR
    guest([Гость])
    client([Клиент])
    admin([Администратор])

    subgraph sys [Система Пушистик]
        uc1(Регистрация)
        uc2(Вход / выход)
        uc3(Просмотр услуг)
        uc4(Управление питомцами)
        uc5(Запись на услугу)
        uc6(Просмотр своих записей)
        uc7(Отмена записи)
        uc8(Управление услугами)
        uc9(Просмотр всех записей)
        uc10(Изменение статуса записи)
    end

    guest --- uc1
    guest --- uc3
    client --- uc2
    client --- uc3
    client --- uc4
    client --- uc5
    client --- uc6
    client --- uc7
    admin --- uc2
    admin --- uc7
    admin --- uc8
    admin --- uc9
    admin --- uc10
```

## 2.2 Activity Diagram — запись на услугу

```mermaid
flowchart TD
    start((Начало)) --> catalog[Открыть каталог услуг]
    catalog --> service[Выбрать услугу и нажать Записаться]
    service --> login{Пользователь вошёл?}
    login -- нет --> hasAcc{Есть аккаунт?}
    hasAcc -- да --> doLogin[Войти]
    hasAcc -- нет --> doReg[Зарегистрироваться]
    doLogin --> hasPet
    doReg --> hasPet
    login -- да --> hasPet{Есть питомец?}
    hasPet -- нет --> addPet[Добавить питомца] --> choose
    hasPet -- да --> choose[Услуга уже выбрана, выбрать питомца]
    choose --> date[Выбрать дату]
    date --> slots[Система показывает свободное время]
    slots --> any{Есть свободное время?}
    any -- нет --> date
    any -- да --> pick[Выбрать время и нажать Записаться]
    pick --> check{Сервер: время свободно, в рабочих часах, не в прошлом?}
    check -- нет --> err[Показать ошибку] --> slots
    check -- да --> save[Сохранить запись со статусом Записан]
    save --> done((Конец))
```

## 2.3 ER Diagram

```mermaid
erDiagram
    users ||--o{ sessions : "входит"
    users ||--o{ pets : "владеет"
    pets ||--o{ appointments : "записан"
    services ||--o{ appointments : "по услуге"

    users {
        int id PK
        text email UK
        text password_hash
        text name
        text phone
        text role "client / admin"
    }
    sessions {
        text token PK
        int user_id FK
    }
    pets {
        int id PK
        int owner_id FK
        text name
        text species
        text breed
        real weight
    }
    services {
        int id PK
        text title
        text description
        int price
        int duration "минуты"
        int is_active
    }
    appointments {
        int id PK
        int pet_id FK
        int service_id FK
        text start_at
        text end_at
        int price "цена на момент записи"
        text comment
        text status "booked / done / cancelled"
    }
```

Подробное описание таблиц — в [3. Backend](3_backend.md#32-база-данных).

## 2.4 Component Diagram

```mermaid
flowchart LR
    subgraph browser [Браузер]
        pages[HTML-страницы<br/>index, pets, book, my, admin, services]
        common[common.js<br/>функция api, меню]
        pages --> common
    end

    subgraph docker [Docker-контейнер]
        subgraph server [Сервер FastAPI]
            main[main.py<br/>REST API, проверка прав]
            booking[booking.py<br/>правила записи]
            security[security.py<br/>хеш паролей]
            dbm[db.py<br/>подключение и схема]
            static[StaticFiles<br/>раздача frontend]
            main --> booking
            main --> security
            main --> dbm
        end
        db[(SQLite<br/>/data/salon.db)]
        dbm --> db
    end

    common -- "HTTP JSON /api/*" --> main
    pages -- "GET *.html" --> static
```

## 2.5 Sequence Diagram — запись на услугу

```mermaid
sequenceDiagram
    actor C as Клиент
    participant B as Браузер (book.html)
    participant A as FastAPI (main.py)
    participant L as booking.py
    participant D as SQLite

    C->>B: выбирает услугу и дату
    B->>A: GET /api/slots?date=...&service_id=...
    A->>D: занятые записи на эту дату
    D-->>A: список интервалов
    A->>L: free_slots(...)
    L-->>A: 09:00, 12:00, ...
    A-->>B: свободные слоты
    C->>B: выбирает время, жмёт Записаться
    B->>A: POST /api/appointments (Bearer токен)
    A->>D: проверить токен, питомца, услугу
    A->>L: check_start_time(), is_overlap()
    alt время занято или неверно
        A-->>B: 409 / 422 и текст ошибки
        B-->>C: показывает ошибку
    else всё в порядке
        A->>D: INSERT INTO appointments
        A-->>B: 201 и данные записи
        B-->>C: Вы записаны, переход в Мои записи
    end
```

## 2.6 Прототипы экранов

Черновые макеты, нарисованные до разработки:

![Прототипы](mockup.svg)

Как экраны выглядят в готовом приложении — в [4. Frontend](4_frontend.md).

## 2.7 Технологии и почему выбраны они

| Слой | Технология | Почему именно она |
|------|------------|-------------------|
| Backend | Python + **FastAPI** | мало кода; сам проверяет входные данные по схемам и делает Swagger |
| Сервер | **Uvicorn** | стандартный сервер для FastAPI |
| База данных | **SQLite** | встроена в Python, не нужно ставить отдельную СУБД |
| Frontend | **HTML + CSS + JavaScript** | без сборки и фреймворков, каждую страницу легко понять |
| Тесты | **pytest** + TestClient | стандарт для Python, тесты API без запуска сервера |
| Запуск | **Docker Compose** | одинаковый запуск на любом компьютере одной командой |
| Диаграммы | **Mermaid** | пишутся текстом и сразу отображаются на GitHub |

---

← [1. Описание](1_opisanie.md) · Далее: [3. Backend →](3_backend.md)
