import psycopg2
import os
from urllib.parse import urlparse

# Строка подключения (например, из переменной окружения)
DATABASE_URL = "postgresql://uae7p6m2pt04pi:p733605ddca92bb5a327ad1cb96c15700576e49ce648afe39784dee57050b7fa3@caij57unh724n3.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com:5432/d30jsb2kqs37l6"

if DATABASE_URL:
    # Разбираем строку подключения с помощью urllib.parse.urlparse
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

def get_all_users():
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # Получение всех пользователей
        cur.execute("SELECT id, name, email, public_key, private_key, plan FROM public.user")
        users = cur.fetchall()

        if not users:
            print("Нет пользователей в базе данных.")
            return

        print("Список всех пользователей:")
        for user in users:
            print(f"ID: {user[0]} , "  + "\n"
                  f"Name: {user[1]} , " + "\n"
                  f"Email: {user[2]} , " + "\n"
                  f"Public Key: {user[3]} ," + "\n"
                  f"Private Key: {user[4]} ," + "\n"
                  f"Plan: {user[5]}" + "\n"
                  '------------------------------------')

    except Exception as e:
        print(f"Ошибка при получении списка пользователей: {str(e)}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    get_all_users()
