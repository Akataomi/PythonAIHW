URL Shortener Service

Описание:
Сервис для сокращения ссылок на Python (FastAPI). Позволяет создавать короткие URL, следить за статистикой переходов, устанавливать время жизни ссылки и управлять ими через личный кабинет.

Технологии:
Python 3.10+
FastAPI (веб-фреймворк)
SQLAlchemy (работа с БД)
SQLite (хранение данных)
JWT (авторизация)

ИНСТРУКЦИЯ ПО ЗАПУСКУ
Установите зависимости:
pip install -r requirements.txt

Запустите сервер:
uvicorn main:app --reload

Откройте документацию в браузере:
http://127.0.0.1:8000/docs

ОПИСАНИЕ API

Авторизация:
POST /register — Регистрация нового пользователя
POST /login — Получение JWT токена
Ссылки:

POST /links/shorten — Создать короткую ссылку (требуется токен)
GET /links/{code} — Перенаправление на оригинальный URL (доступно всем)
GET /links/{code}/stats — Статистика по ссылке (требуется токен)
PUT /links/{code} — Обновить оригинальный URL (требуется токен)
DELETE /links/{code} — Удалить ссылку (требуется токен)
GET /links/search — Поиск ссылок по оригинальному URL (требуется токен)

Дополнительно:
POST /admin/cleanup-unused — Удаление старых неиспользуемых ссылок
GET /links/history/deleted — История удалённых ссылок
GET /health — Проверка статуса сервисов

ПРИМЕРЫ ЗАПРОСОВ (cURL)
Регистрация:
curl -X POST http://127.0.0.1:8000/register -H "Content-Type: application/json" -d "{"username":"user","password":"pass"}"
Логин (получение токена):
curl -X POST http://127.0.0.1:8000/login -H "Content-Type: application/json" -d "{"username":"user","password":"pass"}"
(Сохраните access_token из ответа)
Создание ссылки (вставьте токен вместо YOUR_TOKEN):
curl -X POST http://127.0.0.1:8000/links/shorten -H "Content-Type: application/json" -H "Authorization: Bearer YOUR_TOKEN" -d "{"url":"https://google.com"}"
Переход по ссылке:
Просто откройте в браузере: http://127.0.0.1:8000/links/{полученный_код}

СТРУКТУРА БАЗЫ ДАННЫХ

Файл БД: shortener.db (SQLite)
Таблица users (Пользователи):
id: уникальный номер
username: логин (уникальный)
hashed_password: хеш пароля
Таблица links (Ссылки):
id: уникальный номер
short_code: короткий код ссылки (уникальный)
original_url: исходная длинная ссылка
created_at: дата создания
expires_at: дата истечения (если установлена)
clicks: количество переходов
last_accessed_at: дата последнего перехода
is_deleted: флаг удаления (0/1)
owner_id: ID владельца ссылки

ПРИМЕЧАНИЯ
Для доступа к методам изменения/удаления необходим JWT токен.
Ссылки удаляются "мягко" (помечаются флагом), их можно восстановить через историю.
Если ссылка имеет expires_at и время вышло, при переходе будет ошибка 410.
Для продакшена рекомендуется заменить SQLite на PostgreSQL.