import psycopg2
import os
from urllib.parse import urlparse

# Строка подключения (например, из переменной окружения)
DATABASE_URL = "postgresql://uae7p6m2pt04pi:p733605ddca92bb5a327ad1cb96c15700576e49ce648afe39784dee57050b7fa3@caij57unh724n3.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com:5432/d30jsb2kqs37l6"

# Если строка подключения задана, парсим ее
if DATABASE_URL:
    url = urlparse(DATABASE_URL)
    if url.scheme != 'postgresql':
        raise ValueError(f"Неверная строка подключения: {DATABASE_URL}")
    DB_CONFIG = {
        'dbname': url.path.lstrip('/'),
        'user': url.username,
        'password': url.password,
        'host': url.hostname,
        'port': url.port,
    }
else:
    DB_CONFIG = {
        'dbname': os.getenv('DB_NAME', 'neurohub'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'password'),
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
    }

def delete_user(user_id):
    conn = None
    try:
        # Подключаемся к базе данных
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # Выполняем запрос на удаление пользователя по ID
        cur.execute("DELETE FROM public.user WHERE id = %s", (str(user_id),))  # Преобразуем ID в строку
        conn.commit()

        # Проверяем, был ли удален пользователь
        if cur.rowcount > 0:
            print(f"Пользователь с ID {user_id} был успешно удален.")
        else:
            print(f"Пользователь с ID {user_id} не найден.")

    except Exception as e:
        print(f"Ошибка при удалении пользователя: {str(e)}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    while True:
        try:
            user_input = input("Введите ID пользователя для удаления или 'exit' для выхода: ")
            if user_input.lower() == 'exit':
                print("Выход из программы.")
                break

            # Проверяем, что ID не пустой
            if not user_input.strip():
                print("ID пользователя не может быть пустым.")
                continue

            # Удаляем пользователя
            delete_user(user_input)

        except KeyboardInterrupt:
            print("\nВыход из программы.")
            break