URL Shortener Service

Описание:
Сервис для сокращения ссылок на Python (FastAPI) с поддержкой кэширования Redis и контейнеризации Docker. Позволяет создавать короткие URL, следить за статистикой переходов, устанавливать время жизни ссылки и управлять ими через личный кабинет.

Технологии:
Python 3.10+
FastAPI (асинхронный веб-фреймворк)
SQLAlchemy (ORM для работы с БД)
SQLite / PostgreSQL (хранение данных)
Redis (кэширование популярных ссылок)
JWT (авторизация через токены)
Docker (контейнеризация)

ВАРИАНТЫ ЗАПУСКА

Вариант 1: Локально (без Docker)
Клонировать проект и перейти в папку:
git clone <repo> && cd url-shortener
Создать виртуальное окружение:
python -m venv venv
Активировать окружение:
Windows: .\venv\Scripts\activate
macOS/Linux: source venv/bin/activate
Установить зависимости:
pip install -r requirements.txt
Запустить сервер:
uvicorn main:app --reload --host 127.0.0.1 --port 8000
Открыть документацию в браузере:
http://127.0.0.1:8000/docs
Примечание: Без Redis сервис будет работать в режиме без кэширования. В логах появится предупреждение — это нормально.

Вариант 2: Docker + Redis (рекомендуется для продакшена)
Убедитесь, что Docker установлен:
docker --version
docker-compose --version
Создайте папку для данных:
mkdir -p data
Запустите все сервисы:
docker-compose up -d
Проверьте статус:
curl http://localhost:8000/health
Открыть документацию:
http://localhost:8000/docs

Управление контейнерами:
Остановка: docker-compose down
Пересборка после изменений: docker-compose up -d --build
Просмотр логов: docker-compose logs -f app
Вход в контейнер: docker-compose exec app bash

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
GET /health — Проверка статуса сервисов (БД и Redis)

ПРИМЕРЫ ЗАПРОСОВ (cURL)
Регистрация:
curl -X POST http://127.0.0.1:8000/register -H "Content-Type: application/json" -d "{"username":"user","password":"pass"}"
Логин (получение токена):
curl -X POST http://127.0.0.1:8000/login -H "Content-Type: application/json" -d "{"username":"user","password":"pass"}"
Сохраните access_token из ответа.
Создание ссылки (вставьте токен вместо YOUR_TOKEN):
curl -X POST http://127.0.0.1:8000/links/shorten -H "Content-Type: application/json" -H "Authorization: Bearer YOUR_TOKEN" -d "{"url":"https://google.com"}"
Переход по ссылке:
Просто откройте в браузере: http://127.0.0.1:8000/links/{полученный_код}

Проверка здоровья сервисов:
curl http://127.0.0.1:8000/health
Ожидаемый ответ: {"database":"ok","redis":"ok"}

СТРУКТУРА БАЗЫ ДАННЫХ
Файл БД: shortener.db (SQLite) или PostgreSQL при настройке
Таблица users (Пользователи):
id: уникальный номер
username: логин (уникальный)
hashed_password: хеш пароля в формате salt$sha256

Таблица links (Ссылки):
id: уникальный номер
short_code: короткий код ссылки (уникальный)
original_url: исходная длинная ссылка
created_at: дата создания (UTC)
expires_at: дата истечения (если установлена, может быть null)
clicks: количество переходов
last_accessed_at: дата последнего перехода
is_deleted: флаг удаления (0 или 1, мягкое удаление)
owner_id: ID владельца ссылки (может быть null для анонимов)

НАСТРОЙКА ЧЕРЕЗ ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ
Создайте файл .env в корне проекта:
SECRET_KEY=ваш_секретный_ключ_для_jwt
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
DATABASE_URL=sqlite:///./data/shortener.db
REDIS_URL=redis://redis:6379/0
CACHE_TTL_REDIRECT=3600
CACHE_TTL_STATS=300
Для PostgreSQL измените DATABASE_URL:
DATABASE_URL=postgresql://user:password@host:5432/dbname

ПРИМЕЧАНИЯ
Авторизация: Для доступа к методам изменения/удаления необходим JWT токен в заголовке: Authorization: Bearer <ваш_токен>
Мягкое удаление: Ссылки не удаляются физически, а помечаются флагом is_deleted. Их можно просмотреть через /links/history/deleted
Время жизни: Если ссылка имеет expires_at и время вышло, при переходе будет ошибка 410 Gone
Кэширование: При подключённом Redis популярные ссылки кэшируются для ускорения редиректов. Кэш автоматически сбрасывается при обновлении или удалении ссылки

Продакшен: Для продакшена рекомендуется:
Заменить SECRET_KEY на криптографически стойкую строку
Использовать PostgreSQL вместо SQLite
Настроить HTTPS
Добавить rate limiting
Использовать Docker для изоляции
Отладка: Если что-то не работает, проверьте логи:
Локально: смотрите вывод uvicorn в терминале
Docker: docker-compose logs -f app

БЫСТРЫЙ СТАРТ (шпаргалка)

Локально:
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
Открыть http://127.0.0.1:8000/docs

Docker:
mkdir -p data
docker-compose up -d
Открыть http://localhost:8000/docs
Проверить http://localhost:8000/health

Структура проекта:
url-shortener/
├── main.py (код приложения)
├── requirements.txt (зависимости)
├── Dockerfile (образ приложения)
├── docker-compose.yml (оркестрация)
├── .env (переменные окружения)
├── .dockerignore (исключения для Docker)
├── data/ (папка для БД)
└── README.md (этот файл)