import os

import psycopg2
import psycopg2.extras


def query(sql, params=(), one=False):
    connection = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with connection:
            with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(sql, params)
                if cursor.description is None:
                    return None
                rows = cursor.fetchall()
    finally:
        connection.close()
    if one:
        return rows[0] if rows else None
    return rows
