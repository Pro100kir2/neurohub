import unittest
from flask import Flask, jsonify
from flask_testing import TestCase
import psycopg2
import jwt
import datetime
import os
from io import StringIO
from unittest.mock import patch
import time
import requests


# Подключаем ваше приложение (например, app.py)
from app import app, get_db_connection, JWT_SECRET, JWT_ALGORITHM, DB_CONFIG


class TestNeuroHubApp(TestCase):

    def create_app(self):
        # Настроим тестовую среду
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = DB_CONFIG['dbname']
        return app

    def setUp(self):
        """ Set up the database and any necessary resources """
        self.conn = get_db_connection()
        self.cur = self.conn.cursor()
        # Создание тестовой таблицы или очистка базы данных
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS public.user (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE,
                name TEXT,
                public_key TEXT,
                private_key TEXT,
                plan TEXT
            )
        """)
        self.conn.commit()

    def tearDown(self):
        """ Clean up after each test """
        self.cur.execute("DROP TABLE IF EXISTS public.user")
        self.conn.commit()
        self.cur.close()
        self.conn.close()

    # Проверка подключения к базе данных
    def test_db_connection(self):
        try:
            conn = get_db_connection()
            self.assertIsNotNone(conn)
        except Exception as e:
            self.fail(f"Database connection failed: {str(e)}")

    # Регистрация пользователя
    def test_register_user(self):
        with self.client:
            response = self.client.post('/register', data=dict(
                email='test@example.com',
                name='Test User'
            ))
            self.assertEqual(response.status_code, 200)

    def test_register_existing_user(self):
        # Сначала зарегистрируем пользователя
        self.client.post('/register', data=dict(
            email='test@example.com',
            name='Test User'
        ))

        # Попробуем зарегистрировать с тем же email
        response = self.client.post('/register', data=dict(
            email='test@example.com',
            name='Another User'
        ))
        self.assertEqual(response.status_code, 400)
        response_data = response.get_json()
        self.assertEqual(response_data['message'], 'Пользователь с таким email уже существует.')

    # Проверка защиты от SQL инъекций
    def test_sql_injection(self):
        malicious_email = "' OR 1=1 --"
        response = self.client.post('/register', data=dict(
            email=malicious_email,
            name='Test User'
        ))
        self.assertEqual(response.status_code, 400)  # Должен быть отказ из-за инъекции

    # Проверка защиты от XSS
    def test_xss_protection(self):
        malicious_script = "<script>alert('xss');</script>"
        response = self.client.post('/register', data=dict(
            email='xss@example.com',
            name=malicious_script
        ))
        self.assertNotIn(malicious_script, response.data.decode())  # Данные не должны быть выполнены

    # Проверка работы с токенами
    def test_create_token(self):
        token = jwt.encode({
            'id': 1,
            'name': 'Test User',
            'email': 'test@example.com',
            'plan': 'free',
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        }, JWT_SECRET, algorithm=JWT_ALGORITHM)
        self.assertIsNotNone(token)

    def test_token_expiration(self):
        token = jwt.encode({
            'id': 1,
            'name': 'Test User',
            'email': 'test@example.com',
            'plan': 'free',
            'exp': datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
        }, JWT_SECRET, algorithm=JWT_ALGORITHM)

        with self.assertRaises(jwt.ExpiredSignatureError):
            jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

    def test_token_refresh(self):
        token = jwt.encode({
            'id': 1,
            'name': 'Test User',
            'email': 'test@example.com',
            'plan': 'free',
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        }, JWT_SECRET, algorithm=JWT_ALGORITHM)
    # Проверка кэширования
    def test_cache(self):
        response1 = self.client.get('/some-expensive-query')
        response2 = self.client.get('/some-expensive-query')
        self.assertEqual(response1.data, response2.data)  # Результаты должны совпасть, если кэш работает

    # Проверка производительности
    def test_performance(self):
        start_time = time.time()
        response = self.client.get('/some-heavy-endpoint')
        elapsed_time = time.time() - start_time
        self.assertLess(elapsed_time, 2)  # Запрос должен выполняться быстрее 2 секунд

    # Обновление настроек
    def test_update_settings(self):
        user_id = 1  # Тестовый ID пользователя
        token = jwt.encode({
            'id': user_id,
            'name': 'Test User',
            'email': 'test@example.com',
            'plan': 'free',
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        }, JWT_SECRET, algorithm=JWT_ALGORITHM)

        with self.client:
            response = self.client.post('/update-settings', json=dict(
                name='Updated Name',
                email='updated@example.com',
                private_key='privatekey'
            ), headers=dict(Cookie=f'token={token}'))
            self.assertEqual(response.status_code, 200)
            self.assertIn('Settings updated successfully', response.data.decode())

    def test_update_settings_without_private_key(self):
        user_id = 1  # Тестовый ID пользователя
        token = jwt.encode({
            'id': user_id,
            'name': 'Test User',
            'email': 'test@example.com',
            'plan': 'free',
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        }, JWT_SECRET, algorithm=JWT_ALGORITHM)

        with self.client:
            response = self.client.post('/update-settings', json=dict(
                name='Updated Name'
            ), cookies=dict(token=token))

            self.assertEqual(response.status_code, 400)
            self.assertIn('Private key is required.', response.data.decode())


class TestServerAvailability(unittest.TestCase):

    def test_server_ping(self):
        urls = [
            'https://neural-networks-hub.ru',
            'https://neural-networks-hub.site'
        ]

        for url in urls:
            with self.subTest(url=url):
                try:
                    response = requests.get(url)
                    self.assertEqual(response.status_code, 200, f"Server at {url} is down or not responding correctly.")
                except requests.exceptions.RequestException as e:
                    self.fail(f"Server at {url} could not be reached. Error: {e}")

if __name__ == '__main__':
    unittest.main()
