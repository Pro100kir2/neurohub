from flask import Flask, jsonify, request, render_template, redirect, url_for, session, flash
import os
import psycopg2
import jwt
from apscheduler.schedulers.background import BackgroundScheduler
import datetime
import pytz
from dotenv import load_dotenv
from urllib.parse import urlparse
import random
import string
from functools import wraps
import traceback
import hashlib

# Flask приложение
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'supersecretkey')

load_dotenv()  # Загрузит переменные из .env файла

# Получаем строку подключения из переменной окружения
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    # Разбираем строку подключения
    url = urlparse(DATABASE_URL)

    DB_CONFIG = {
        'dbname': url.path[1:],  # Все после первого слэша
        'user': url.username,
        'password': url.password,
        'host': url.hostname,
        'port': url.port,
    }
else:
    # Если строка подключения не задана, используем локальные настройки
    DB_CONFIG = {
        'dbname': os.getenv('DB_NAME', 'neurohub'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'password'),
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
    }

# JWT конфигурация
JWT_SECRET = os.getenv('JWT_SECRET', 'your_jwt_secret_key')
JWT_ALGORITHM = 'HS256'

# Подключение к базе данных
def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

# Функция для генерации случайного ключа с учетом требований
def generate_key(length: int) -> str:
    # Разрешенные символы: латинские буквы, цифры, кириллица и корейские символы
    allowed_chars = string.ascii_letters + string.digits + 'абвгдеёжзийклмнопрстуфхцчшщыэюя' + '가나다라마바사아자차카타파하'

    # Генерация ключа заданной длины
    return ''.join(random.choice(allowed_chars) for _ in range(length))

def refresh_token(token):
    try:
        # Декодируем старый токен без проверки на срок действия
        user_data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"verify_exp": False})

        # Обновляем токен с новым временем истечения
        new_token = jwt.encode({
            'id': user_data['id'],
            'name': user_data['name'],
            'email': user_data['email'],
            'plan': user_data['plan'],
            'exp': datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)  # Новый срок действия
        }, JWT_SECRET, algorithm=JWT_ALGORITHM)

        return new_token
    except jwt.InvalidTokenError:
        return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('token')

        if not token:
            print("No token found in cookies.")
            return redirect(url_for('login'))  # Перенаправляем на страницу входа, если токен отсутствует

        try:
            # Декодируем токен без проверки на срок действия
            user_data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
            token_exp_time = datetime.datetime.fromtimestamp(user_data['exp'], tz=datetime.timezone.utc)

            # Проверяем истек ли токен
            if datetime.datetime.now(datetime.timezone.utc) > token_exp_time:
                print("Token expired.")
                return redirect(url_for('login'))  # Перенаправляем на страницу входа, если токен истек

        except jwt.InvalidTokenError:
            print("Invalid token.")
            return redirect(url_for('login'))  # Перенаправляем на страницу входа, если токен недействителен

        return f(*args, **kwargs)

    return decorated_function
# Главная страница
@app.route('/')
def home():
    return render_template('home.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register-page.html')

    if request.method == 'POST':
        # Используем request.form для извлечения данных из формы
        email = request.form['email']
        name = request.form['name']

        # Генерация ключей
        public_key = generate_key(12)  # Публичный ключ из 12 символов
        private_key = generate_key(24)

        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            # Проверка: существует ли email
            cur.execute("SELECT COUNT(*) FROM public.user WHERE email = %s", (email,))
            if cur.fetchone()[0] > 0:
                return jsonify({'message': 'Пользователь с таким email уже существует.'}), 400

            # Добавление пользователя в базу данных
            cur.execute(
                '''
                INSERT INTO public.user (email, name, public_key, private_key, plan)
                VALUES (%s, %s, %s, %s, %s)
                ''',
                (email, name, public_key, private_key, 'free')
            )
            conn.commit()
            cur.close()

            return render_template('register-success.html', public_key=public_key, private_key=private_key)
        except Exception as e:
            if conn:
                conn.rollback()
            return jsonify({'message': f'Ошибка при регистрации: {str(e)}'}), 500
        finally:
            if conn:
                conn.close()
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login-page.html')

    if request.method == 'POST':
        if not request.is_json:
            return jsonify({'message': 'Неверный Content-Type. Ожидается application/json.'}), 415

        data = request.get_json()
        name = data.get('name')
        public_key = data.get('public_key')

        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            # Проверка имени и публичного ключа
            cur.execute(
                "SELECT id, name, email, plan FROM public.user WHERE name = %s AND public_key = %s",
                (name, public_key)
            )
            user = cur.fetchone()

            if user:
                # Создание JWT токена
                token = jwt.encode({
                    'id': user[0],
                    'name': user[1],
                    'email': user[2],
                    'plan': user[3],
                    'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
                }, JWT_SECRET, algorithm=JWT_ALGORITHM)

                # Логируем создание токена
                print(f"Generated token: {token}")

                # Устанавливаем cookie с токеном
                response = redirect(url_for('profile'))  # Переход на страницу профиля после логина

                # Устанавливаем токен в cookie
                response.set_cookie('token', token, httponly=True, secure=False, samesite='Strict', max_age=3600)  # max_age = 3600 сек = 1 час

                return response  # Редирект на профиль с установленным токеном в куки
            else:
                return jsonify({'message': 'Неверное имя или публичный ключ.'}), 401

        except Exception as e:
            # Логируем ошибку
            print(f"Ошибка при входе: {str(e)}")
            return jsonify({'message': f'Ошибка при входе: {str(e)}'}), 500

        finally:
            if conn:
                conn.close()

# Профиль
@app.route('/profile')
@login_required
def profile():
    token = request.cookies.get('token')
    print(f"Received token: {token}")  # Логируем токен, полученный из cookies

    if not token:
        print("No token found in cookies")
        return redirect(url_for('login'))  # Перенаправляем на страницу входа, если токен отсутствует
    try:
        user_data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
        print(f"User data from token: {user_data}")  # Логируем декодированные данные токена

        # Приводим время в token в объект с временной зоной (aware datetime)
        token_exp_time = datetime.datetime.fromtimestamp(user_data['exp'], tz=datetime.timezone.utc)
        print(f"Token expiration time: {token_exp_time}")

        # Проверка истечения токена
        if datetime.datetime.now(datetime.timezone.utc) > token_exp_time:
            print("Token expired, refreshing...")  # Логируем, что токен истек
            new_token = refresh_token(token)
            if new_token:
                print(f"New token: {new_token}")  # Логируем новый токен
                response = redirect(url_for('profile'))
                response.set_cookie('token', new_token, httponly=True, secure=True)  # Устанавливаем новый токен
                return response
            else:
                print("Failed to refresh token")  # Логируем ошибку при обновлении токена
                return redirect(url_for('login'))  # Если токен не обновился, перенаправляем на вход

        # Если токен еще действителен, просто рендерим страницу
        print(f"Token is valid. Rendering profile page...")  # Логируем, если токен действителен
        return render_template(
            'profile-page.html',
            name=user_data['name'],
            email=user_data['email'],
            plan=user_data['plan']
        )
    except jwt.ExpiredSignatureError:
        print("Token expired (signature error)")  # Логируем ошибку при истечении срока действия токена
        return redirect(url_for('login'))  # Перенаправляем на страницу входа при истечении токена
    except jwt.InvalidTokenError:
        print("Invalid token error")  # Логируем ошибку при неверном токене
        return redirect(url_for('login'))  # Перенаправляем при неверном токене
# Страницы о проекте и политике конфиденциальности
@app.route('/about')
def about():
    return render_template('about-page.html')


@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy-policy-page.html')

def get_remaining_requests(user_id):
    query = """
    SELECT number_of_requests_per_day - used_requests_per_day AS remaining_daily,
           number_of_requests_per_month - used_requests_per_month AS remaining_monthly
    FROM public.user
    WHERE id = %s;
    """
    cursor = db.cursor()
    cursor.execute(query, (user_id,))
    result = cursor.fetchone()
    cursor.close()

    if result:
        return {"daily": result[0], "monthly": result[1]}
    else:
        return {"error": "User not found"}

scheduler = BackgroundScheduler(timezone=pytz.utc)


# 🕛 Функция для сброса дневных лимитов
def reset_daily_limits():
    cursor = db.cursor()
    cursor.execute("""
        UPDATE public.user
        SET used_requests_per_day = 0;
    """)
    db.commit()
    cursor.close()
    print(f"[{datetime.now()}] Daily limits have been reset.")


# 📅 Функция для сброса месячных лимитов
def reset_monthly_limits():
    cursor = db.cursor()
    cursor.execute("""
        UPDATE public.user
        SET used_requests_per_day = 0,
            used_requests_per_month = 0;
    """)
    db.commit()
    cursor.close()
    print(f"[{datetime.now()}] Monthly limits have been reset.")


# Запуск планировщика задач
def start_scheduler():
    # Сброс дневных лимитов каждый день в полночь (по UTC)
    scheduler.add_job(reset_daily_limits, 'cron', hour=0, minute=0)

    # Сброс месячных лимитов в первый день каждого месяца в полночь (по UTC)
    scheduler.add_job(reset_monthly_limits, 'cron', day=1, hour=0, minute=0)

    # Запуск планировщика
    scheduler.start()

def handle_user_request(user_id):
    # Получаем текущие лимиты и потраченные запросы пользователя
    query = """
    SELECT number_of_requests_per_day, number_of_requests_per_month,
           used_requests_per_day, used_requests_per_month
    FROM public.user
    WHERE id = %s;
    """
    cursor = db.cursor()
    cursor.execute(query, (user_id,))
    user_data = cursor.fetchone()
    cursor.close()

    if not user_data:
        return {"error": "User not found"}

    daily_limit, monthly_limit, used_daily, used_monthly = user_data

    # Проверяем лимиты запросов
    if used_daily >= daily_limit:
        return {"error": "Daily request limit reached. Upgrade your plan to continue."}
    if used_monthly >= monthly_limit:
        return {"error": "Monthly request limit reached. Upgrade your plan to continue."}

    # Если лимиты не достигнуты, уменьшаем количество оставшихся запросов
    update_query = """
    UPDATE public.user
    SET used_requests_per_day = used_requests_per_day + 1,
        used_requests_per_month = used_requests_per_month + 1
    WHERE id = %s;
    """
    cursor = db.cursor()
    cursor.execute(update_query, (user_id,))
    db.commit()
    cursor.close()

    return {"success": "Request processed successfully"}
@app.route('/choose-plan')
def choose_plan():
    return render_template('choose-plan.html')

# Обновление количества запросов
def update_user_requests_limits(user_id, plan):
    plan_limits = {
        "free": {"daily": 4, "monthly": 120},
        "basic": {"daily": 100, "monthly": 100},
        "standard": {"daily": 500, "monthly": 500},
        "premium": {"daily": 1000, "monthly": 1000},
        "pro": {"daily": 3000, "monthly": 3000},
        "developer": {"daily": 8000, "monthly": 8000},
    }

    if plan in plan_limits:
        daily_limit = plan_limits[plan]["daily"]
        monthly_limit = plan_limits[plan]["monthly"]

        query = """
        UPDATE public.user
        SET number_of_requests_per_day = %s,
            number_of_requests_per_month = %s
        WHERE id = %s;
        """
        values = (daily_limit, monthly_limit, user_id)

        cursor = db.cursor()
        cursor.execute(query, values)
        db.commit()
        cursor.close()


# Обработчик 404 ошибки
@app.errorhandler(404)
def page_not_found():
    return render_template('error404.html'), 404

@app.errorhandler(500)
def internal_server_error():
    return render_template('error500.html'), 500
# Логика выхода
@app.route('/logout')
def logout():
    response = redirect(url_for('home'))
    response.delete_cookie('token')  # Удаляем cookie с токеном
    return response
@app.route('/neuro')
@login_required
def neuro():
    return render_template('home-profile.html')
@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@app.route('/update-settings', methods=['POST'])
def update_settings():
    print("Received a request to update settings.")  # Логируем начало обработки запроса

    # Проверка, что запрос содержит тело в формате JSON
    if request.is_json:
        data = request.get_json()
        print("Request body received as JSON.")  # Логируем, что тело запроса в формате JSON

        # Извлекаем значения из данных
        name = data.get('name')
        email = data.get('email')
        public_key = data.get('public_key')
        private_key = data.get('private_key')

        print(f"Extracted data: Name: {name}, Email: {email}, Public Key: {public_key}, Private Key: {private_key}")

        # Логика проверки и сохранения данных
        if not private_key:
            print("Private key is missing!")  # Логируем отсутствие приватного ключа
            return jsonify({'message': 'Private key is required.'}), 400

        # Логируем каждый шаг при обновлении данных в базе
        print("Attempting to update user data in the database...")

        # Получение ID пользователя из базы данных по email (или другому уникальному полю)
        try:
            user_id = get_user_id_by_email(email)
            if not user_id:
                print(f"User with email {email} not found.")  # Логируем, если пользователь не найден
                return jsonify({'message': 'User not found'}), 404
        except Exception as e:
            print(f"Error retrieving user ID: {e}")
            return jsonify({'message': 'Error retrieving user ID'}), 500

        # Пример обновления данных в базе
        success = update_user_in_db(user_id, name, email, public_key, private_key)

        if success:
            print("User data successfully updated in the database.")  # Логируем успешное обновление
            return jsonify({'message': 'Settings updated successfully!'}), 200
        else:
            print("Failed to update user data in the database.")  # Логируем неудачную попытку обновления
            return jsonify({'message': 'Failed to update settings'}), 500
    else:
        print("Request body is not in JSON format!")  # Логируем, что тело запроса не JSON
        return jsonify({'message': 'Request must be in JSON format'}), 400


def get_user_id_by_email(email):
    try:
        # Подключаемся к базе данных
        connection = psycopg2.connect(**DB_CONFIG)
        cursor = connection.cursor()

        # Получаем ID пользователя по email
        cursor.execute("SELECT id FROM public.user WHERE email = %s", (email,))
        user_data = cursor.fetchone()

        cursor.close()
        connection.close()

        # Если пользователь найден, возвращаем его ID
        if user_data:
            return user_data[0]
        else:
            return None
    except Exception as e:
        print(f"Error retrieving user ID by email: {e}")
        return None


def update_user_in_db(user_id, name, email, public_key, private_key):
    try:
        # Подключаемся к базе данных
        connection = psycopg2.connect(**DB_CONFIG)
        cursor = connection.cursor()

        # Получаем текущие значения полей
        cursor.execute("SELECT name, email, public_key, private_key FROM public.user WHERE id = %s", (user_id,))
        current_data = cursor.fetchone()
        if not current_data:
            print(f"User with ID {user_id} not found.")
            return False
        current_name, current_email, current_public_key, current_private_key = current_data

        # Если поля не переданы, оставляем их как есть
        if name is None:
            name = current_name
        if email is None:
            email = current_email
        if public_key is None:
            public_key = current_public_key
        if private_key is None:
            private_key = current_private_key

        # Формируем SQL-запрос для обновления данных
        update_query = """
            UPDATE "public"."user"
            SET name = %s, email = %s, public_key = %s, private_key = %s
            WHERE id = %s
        """

        # Логируем запрос
        print(f"Executing query: {update_query}")
        cursor.execute(update_query, (name, email, public_key, private_key, user_id))

        # Сохраняем изменения в базе
        connection.commit()
        print("Changes committed to the database.")

        # Закрываем соединение
        cursor.close()
        connection.close()

        return True
    except Exception as e:
        print(f"Error updating database: {e}")
        return False

@app.route('/choose-plan/payment-success', methods=['GET'])
def payment_success():
    # Имитация успешной оплаты
    user_id = session.get('user_id')  # Получаем ID пользователя из сессии
    plan = request.args.get('plan')  # Получаем оплаченный тариф из параметров URL

    if not user_id or not plan:
        return jsonify({'message': 'Необходима авторизация и указание плана.'}), 400

    # Привилегии для каждого тарифа
    plan_privileges = {
        "Free": [
            "4 запроса в день",
            "Доступ к 1 нейросети"
        ],
        "Basic": [
            "100 запросов в месяц",
            "Доступ ко всем нейросетям"
        ],
        "Standard": [
            "500 запросов в месяц",
            "Доступ ко всем нейросетям"
        ],
        "Premium": [
            "1000 запросов в месяц",
            "Доступ ко всем нейросетям с приоритетной обработкой"
        ],
        "Pro": [
            "3000 запросов в месяц",
            "Доступ ко всем нейросетям с приоритетной обработкой",
            "Поддержка до 5 пользователей"
        ],
        "Developer": [
            "8000 запросов в месяц",
            "Доступ ко всем нейросетям с приоритетной обработкой",
            "Поддержка до 10 пользователей"
        ]
    }

    if plan not in plan_privileges:
        return jsonify({'message': 'Неверный тарифный план.'}), 400

    conn = None
    try:
        # Обновление тарифа пользователя в базе данных
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE public.user SET plan = %s WHERE id = %s", (plan, user_id))
        conn.commit()

        privileges = plan_privileges[plan]  # Получаем привилегии нового тарифа
        return render_template('payment-success.html', plan=plan, privileges=privileges)
    except Exception as e:
        return jsonify({'message': f'Ошибка при обновлении тарифа: {str(e)}'}), 500
    finally:
        if conn:
            conn.close()

def validate_notification(notification_data, secret_key):
    # Создайте строку для подписи
    str_to_hash = f"{notification_data['notification_type']}&{notification_data['operation_id']}&" \
                  f"{notification_data['amount']}&{notification_data['currency']}&" \
                  f"{notification_data['datetime']}&{notification_data['sender']}&" \
                  f"{notification_data['codepro']}&{secret_key}&{notification_data['label']}"
    # Вычислите sha1-хэш
    computed_hash = hashlib.sha1(str_to_hash.encode('utf-8')).hexdigest()

    # Сравните с `sha1_hash` из уведомления
    return computed_hash == notification_data['sha1_hash']

def determine_plan_based_on_amount(amount):
    plans = {
        0: "Free",          # Бесплатный тариф
        100: "Basic",       # 100 рублей
        500: "Standard",    # 500 рублей
        1000: "Premium",    # 1000 рублей
        3000: "Pro",        # 3000 рублей
        8000: "Developer"   # 8000 рублей
    }
    # Найдите ближайший соответствующий тариф по сумме
    return plans.get(int(amount), "Free")  # По умолчанию "Free", если сумма не соответствует

@app.route('/payment-notification', methods=['POST'])
def payment_notification():
    try:
        # Получение данных из запроса
        notification_data = request.json  # YooMoney отправляет данные в формате JSON

        # Получите секретный ключ из настроек
        secret_key = os.getenv('DrAg/+wEBexyslspYsMj1bve')

        # Проверка подписи уведомления
        if not validate_notification(notification_data, secret_key):
            return jsonify({'message': 'Подпись уведомления недействительна.'}), 403

        # Обработка успешной оплаты
        if notification_data.get('unaccepted', 'true') == 'false':  # unaccepted == 'false' означает успешную оплату
            # Получение метки (label), связанной с оплатой
            user_id = notification_data.get('label')  # Вы указывали label при создании платежа как user_id
            amount = notification_data.get('amount')  # Сумма платежа
            plan = determine_plan_based_on_amount(float(amount))  # Определяем тариф по сумме

            conn = get_db_connection()
            cur = conn.cursor()

            # Обновляем тариф пользователя
            cur.execute("UPDATE public.user SET plan = %s WHERE id = %s", (plan, user_id))
            conn.commit()

            cur.close()
            conn.close()

            return jsonify({'message': 'Платеж успешно обработан.', 'plan': plan}), 200

        # Если платеж не подтвержден
        return jsonify({'message': 'Платеж не подтвержден.'}), 400

    except Exception as e:
        print(f"Ошибка при обработке уведомления: {e}")
        return jsonify({'message': f'Ошибка сервера: {str(e)}'}), 500

# Запуск приложения
if __name__ == '__main__':
    start_scheduler()
    app.run(debug=True)
