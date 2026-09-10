# HR Platform

REST API на Django REST Framework для управления резюме. Реализованы авторизация по токену, роли пользователей и разграничение доступа к операциям над резюме.

## Роли и права

| Действие | Кандидат (`candidate`) | HR (`hr`) | Администратор (`admin`) |
|----------|------------------------|-----------|-------------------------|
| Список резюме | только свои | все | все |
| Просмотр одного | только своё | любое | любое |
| Создание | да | нет (403) | да |
| Редактирование | только своё | нет (403) | любое |
| Удаление | нет (403) | нет (403) | да |

Если кандидат обращается к чужому резюме по id, API возвращает **404**: объект не попадает в его queryset.

Роль `admin` при сохранении пользователя выставляет `is_staff=True` (доступ в Django Admin). Суперпользователь (`createsuperuser`) получает `role=admin`. Кандидат и HR в `/admin/` не входят. Поле `role` в теле регистрации игнорируется: новый пользователь всегда `candidate`.

## Установка и запуск

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Сервер: http://127.0.0.1:8000/

### Docker

Из **корня репозитория** (`django_course`), рядом с `docker-compose.yml`:

```bash
docker compose up --build
```

Сервис `web` должен дожидаться готовности Postgres (`depends_on` + healthcheck). Статику отдаёт Nginx из общего volume с `collectstatic`, не из копии папки на хосте.

После запуска:

- API и админка: http://127.0.0.1/
- Swagger: http://127.0.0.1/swagger/
- ReDoc: http://127.0.0.1/redoc/

Пример переменных в `.env`:

```
DJANGO_SECRET_KEY=<случайная длинная строка>
DEBUG=False
ALLOWED_HOSTS=127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=http://127.0.0.1
DB_PASS=<пароль>
DB_NAME=hr_platform_project_db
DB_USER=postgres
DB_HOST=postgres
DB_PORT=5432
```

### Тестовые пользователи

```bash
python manage.py shell
```

```python
from users.models import User

users = [
    ('candidate1', 'candidate'),
    ('candidate2', 'candidate'),
    ('hr_manager', 'hr'),
    ('admin_user', 'admin'),
]

for username, role in users:
    user, _ = User.objects.get_or_create(username=username, defaults={'role': role})
    user.set_password('pass123')
    user.role = role
    user.save()
```

Пароль для всех: `pass123` (не короче 6 символов — ограничение сериализатора регистрации).

После `save()` у `admin_user` будет `is_staff=True`.

## API

### Регистрация

```http
POST /api/auth/register/
Content-Type: application/json

{
    "username": "new_candidate",
    "password": "pass123",
    "email": "new@example.com"
}
```

Сериализатор использует `get_user_model()` — создаётся кастомный `users.User`, а не стандартный Django User.


### Авторизация

`POST /api/auth/login/` принимает только POST. Открытие URL в браузере (GET) вернёт **405**.

```http
POST /api/auth/login/
Content-Type: application/json

{
    "username": "candidate1",
    "password": "pass123"
}
```

Ответ:

```json
{
    "token": "44be25fb6f5a93fe2c1e02e4b762e7ade9863955",
    "user_id": 5,
    "username": "candidate1",
    "role": "candidate"
}
```

Дальше во все запросы к резюме передавайте заголовок:

```http
Authorization: Token <ваш_токен>
```

### Резюме

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/resumes/` | список резюме |
| POST | `/api/resumes/` | создать резюме |
| GET | `/api/resumes/{id}/` | одно резюме |
| PUT / PATCH | `/api/resumes/{id}/` | обновить |
| DELETE | `/api/resumes/{id}/` | удалить |

Поле `user` в теле запроса не передаётся — оно заполняется автоматически из текущего пользователя.

Пример создания:

```http
POST /api/resumes/
Authorization: Token <токен>
Content-Type: application/json

{
    "position": "Python Developer",
    "experience": "2 years"
}
```

Пример обновления:

```http
PATCH /api/resumes/1/
Authorization: Token <токен>
Content-Type: application/json

{
    "position": "Senior Python Developer"
}
```

PowerShell:

```powershell
$login = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/auth/login/" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"username":"candidate1","password":"pass123"}'

$headers = @{ Authorization = "Token $($login.token)" }

Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/resumes/" -Headers $headers
```

### Админ-панель

http://127.0.0.1:8000/admin/ — пользователи и роли.

## Структура проекта

```
hr_platform/          настройки Django и корневые URL (в т.ч. swagger/redoc)
users/                кастомный User, роли, логин, тесты
  models.py           User + Role; save() синхронизирует role и is_staff
  serializers.py      username, email, password (write_only)
  views.py            register (AllowAny) + login (throttle)
  urls.py             /api/auth/register/, /api/auth/login/
  tests.py            auth, синхронизация ролей, матрица прав /api/resumes/
resumes/
  models.py           Resume (related_name, ordering)
  serializers.py      ResumeSerializer
  views.py            ResumeViewSet + select_related
  permissions.py      права по ролям
  admin.py            ResumeAdmin
docker-compose.yml    web, nginx, postgres (корень репозитория)
nginx/                reverse proxy и статика
.gitignore            venv/, .env, data/, static/
requirements.txt
```

Доступ к резюме проверяется в трёх местах:

1. `ResumePermission.has_permission` — можно ли роли выполнить действие;
2. `ResumeViewSet.get_queryset` — какие резюме видны пользователю;
3. `ResumePermission.has_object_permission` — можно ли работать с конкретным объектом.

## Тесты

```bash
python manage.py test users -v 2
```

Покрывается:
- логин (успех / неверный пароль);
- регистрация через кастомную модель `User` (`get_user_model`);
- запрет смены роли при регистрации;
- полная матрица прав `/api/resumes/` для анонима, кандидата, HR и админа
  (list / retrieve / create / PUT / PATCH / destroy).

## Частые ошибки

| Код | Причина |
|-----|---------|
| 401 | нет заголовка `Authorization` или неверный токен |
| 403 | роль не позволяет действие (например, HR создаёт резюме) |
| 404 | кандидат запросил чужое резюме |
| 405 | GET на `/api/auth/login/` или `/api/auth/register/` вместо POST |
| 400 | неверный логин или пароль |
| 500 при register | сериализатор должен использовать `get_user_model()`, а не `django.contrib.auth.models.User` |
