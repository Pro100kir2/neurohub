import unittest
import time
import secrets
from app import app, db, User

class TestNeuroHubAPI(unittest.TestCase):

    def setUp(self):
        """Настройка перед каждым тестом"""
        self.app = app.test_client()
        self.app.testing = True

        # Очистка базы данных перед тестами
        with app.app_context():
            db.session.query(User).delete()
            db.session.commit()

            # Генерация публичных и приватных ключей для пользователя
            private_key = secrets.token_hex(24)  # Пример генерации 24-байтного приватного ключа
            public_key = secrets.token_hex(12)  # Пример генерации 12-байтного публичного ключа

            # Добавление пользователя в базу данных
            user = User(
                email="testuser@gmail.com",
                name="testuser",
                private_key=private_key,
                public_key=public_key,
                plan="free"
            )
            db.session.add(user)
            db.session.commit()

    def tearDown(self):
        """Очистка после каждого теста"""
        with app.app_context():
            db.session.query(User).delete()
            db.session.commit()

    def test_register(self):
        """Тест регистрации пользователя"""
        data = {
            "email": "newuser@example.com",
            "password": "securepassword",
            "name": "New User",
            "private_key": "private_key_example",
            "public_key": "public_key_example"
        }
        response = self.app.post('/register', json=data)
        self.assertEqual(response.status_code, 201)
        self.assertIn('Регистрация прошла успешно!', response.get_json()['message'])

    def test_register_invalid_email(self):
        """Тест регистрации с неверным email"""
        data = {
            "email": "invalid-email",
            "password": "securepassword",
            "name": "Test User",
            "private_key": "private_key_example",
            "public_key": "public_key_example"
        }
        response = self.app.post('/register', json=data)
        self.assertEqual(response.status_code, 400)
        self.assertIn('Некорректный email', response.get_json()['message'])

    def test_register_short_password(self):
        """Тест регистрации с коротким паролем"""
        data = {
            "email": "newuser@example.com",
            "password": "short",
            "name": "Test User",
            "private_key": "private_key_example",
            "public_key": "public_key_example"
        }
        response = self.app.post('/register', json=data)
        self.assertEqual(response.status_code, 400)
        self.assertIn('Пароль слишком короткий', response.get_json()['message'])

    def test_login(self):
        # Отправляем корректные данные
        data = {'name': 'Test User', 'public_key': 'valid_public_key'}
        response = self.client.post('/login', json=data)

        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.get_json())
        self.assertIn('plan', response.get_json())

    def test_login_invalid_credentials(self):
        # Отправляем неправильный public_key для существующего имени
        data = {'name': 'Test User', 'public_key': 'wrong_public_key'}
        response = self.client.post('/login', json=data)

        self.assertEqual(response.status_code, 401)
        self.assertIn('Неверные данные', response.get_json()['message'])

    def test_login_non_existent_user(self):
        # Отправляем запрос с несуществующим пользователем
        data = {'name': 'Nonexistent User', 'public_key': 'some_public_key'}
        response = self.client.post('/login', json=data)

        self.assertEqual(response.status_code, 401)
        self.assertIn('Пользователь с таким именем не найден', response.get_json()['message'])
    def test_services_access(self):
        """Тест доступа к услугам по токену"""
        login_data = {
            "email": "testuser@gmail.com",
            "password": "securepassword"
        }
        login_response = self.app.post('/login', json=login_data)
        self.assertEqual(login_response.status_code, 200)  # Убедитесь, что логин успешен
        token = login_response.get_json().get('token')

        # Проверка, что токен существует
        self.assertIsNotNone(token, "Токен не был получен")

        headers = {'Authorization': f'Bearer {token}'}
        response = self.app.get('/services', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn('available_services', response.get_json())

    def test_performance(self):
        """Тест производительности"""
        start_time = time.time()
        for _ in range(100):
            self.app.get('/')
        end_time = time.time()
        self.assertLess(end_time - start_time, 5, "Тесты производительности слишком медленные!")

    def test_register_duplicate_email(self):
        """Тест регистрации с существующим email"""
        user_data = {
            "email": "testuser@gmail.com",
            "password": "securepassword",
            "name": "Test User",
            "private_key": "private_key_example",
            "public_key": "public_key_example"
        }
        self.app.post('/register', json=user_data)
        response = self.app.post('/register', json=user_data)
        self.assertEqual(response.status_code, 400)
        self.assertIn('Пользователь с таким email уже существует', response.get_json()['message'])

    def test_request_with_large_input(self):
        """Тест запроса с большим входным текстом"""
        login_data = {
            "email": "testuser@gmail.com",
            "password": "securepassword"
        }
        login_response = self.app.post('/login', json=login_data)
        token = login_response.get_json()['token']

        headers = {'Authorization': f'Bearer {token}'}
        long_text = "x" * 101  # Превышаем лимит для бесплатного плана

        response = self.app.post('/request', headers=headers, json={
            "service_type": "resume_generation",
            "input_text": long_text
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('Длина сообщения превышает лимит', response.get_json()['message'])

if __name__ == '__main__':
    unittest.main()
