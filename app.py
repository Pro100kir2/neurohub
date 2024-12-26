from flask import Flask, jsonify, request, render_template, redirect, url_for, session, flash
import os
import psycopg2
import jwt
import datetime
from dotenv import load_dotenv
from urllib.parse import urlparse
import random
import string

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

# Путь к папке с фронтендом
FRONTEND_TEMPLATES_PATH = '/neurohub-backend/templates/pages'


# Подключение к базе данных
def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


# Функция для генерации случайного ключа с учетом требований
def generate_key(length: int) -> str:
    # Разрешенные символы: латинские буквы, цифры, кириллица и корейские символы
    allowed_chars = string.ascii_letters + string.digits + 'абвгдеёжзийклмнопрстуфхцчшщыэюя' + '가나다라마바사아자차카타파하'

    # Генерация ключа заданной длины
    return ''.join(random.choice(allowed_chars) for _ in range(length))


def get_user_from_db(user_id):
    # Пример выполнения запроса к базе данных
    query = "SELECT name, gmail, plan FROM users WHERE id = %s"
    cursor.execute(query, (user_id,))
    result = cursor.fetchone()
    if result:
        return {
            'name': result[0],
            'gmail': result[1],
            'plan': result[2]
        }
    return None


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
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)  # Новый срок действия
        }, JWT_SECRET, algorithm=JWT_ALGORITHM)

        return new_token
    except jwt.InvalidTokenError:
        return None


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

# Вход пользователя
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

                print(f"Generated token: {token}")  # Логируем токен при входе

                # Сохраняем токен в cookies
                response = redirect(url_for('profile'))
                response.set_cookie('token', token)

                return jsonify({
                    'message': 'Вход выполнен успешно!',
                    'token': token
                }), 200
            else:
                return jsonify({'message': 'Неверное имя или публичный ключ.'}), 401
        except Exception as e:
            return jsonify({'message': f'Ошибка при входе: {str(e)}'}), 500
        finally:
            if conn:
                conn.close()
# Профиль
@app.route('/profile')
def profile():
    token = request.cookies.get('token')

    if not token:
        print("No token found in cookies")  # Логируем, если токен отсутствует
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
    return render_template('PrivacyPolicyPage.js')


# Обработчик 404 ошибки
@app.errorhandler(404)
def page_not_found(e):
    return render_template('NotFoundPage.js'), 404


# Логика выхода
@app.route('/logout')
def logout():
    response = redirect(url_for('home'))
    response.delete_cookie('token')  # Удаляем cookie с токеном
    return response
@app.route('/neuro')
def neuro():
    return render_template('home-profile.html')

# Запуск приложения
if __name__ == '__main__':
    app.run(debug=True)
