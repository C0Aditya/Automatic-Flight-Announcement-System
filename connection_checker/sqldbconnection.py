
import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='ak267120',
        database='audiofiles'
    )

conn = get_connection()

cursor = conn.cursor()


cursor.execute("SELECT * FROM file_data")


rows = cursor.fetchall()


for row in rows:
    print(row)
    print('-' * 50)


cursor.close()
conn.close()
