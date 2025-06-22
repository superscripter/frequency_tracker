import os
import psycopg2

from dotenv import load_dotenv

load_dotenv()

class DatabaseHandler:

    db_url = ''

    def __init__(self, db_url = ''):

        self.db_url = db_url
        if db_url == '':
            self.db_url = os.environ.get("DATABASE_URL")
        self._initialize_tables()

    def _get_connection(self):
        return psycopg2.connect(self.db_url)

    def _initialize_tables(self):
        self._create_user_table()
        self._create_activity_types_table()
        self._create_activities_table()
        self._create_user_calculations_table()

    # User table methods

    def _create_user_table(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    name TEXT,
                    timezone TEXT,
                    strava_athlete_id INTEGER,
                    strava_access_token TEXT,
                    strava_refresh_token TEXT,
                    strava_token_expires_at INTEGER
                )
            """)
            conn.commit()

    def _create_user(self, email, password, name, timezone):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO users (email, password, name, timezone)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, (email, password, name, timezone))
                conn.commit()
                result = cursor.fetchone()
                return {"success": True, "message": "User created", "id": result[0]}
            except Exception as e:
                print(f"DATABASE ERROR in _create_user: {str(e)}")
                return {"success": False, "message": str(e)}
            
    def _sign_in(self, email, password):
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("SELECT id, password FROM users WHERE email = %s", (email,))
            user_data = cur.fetchone()
            cur.close()
            conn.close()

            if user_data:
                user_id, hashed_password = user_data
                if self.verify_password(password, hashed_password):
                    return {"success": True, "id": user_id}
                else:
                    return {"success": False, "message": "Invalid password"}
            else:
                return {"success": False, "message": "User not found"}
        except Exception as e:
            return {"success": False, "message": str(e)}
            
    def _remove_user(self, id):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                DELETE FROM users WHERE id = %s
            """, (id,))
            conn.commit()
            return {"success": True, "message": "User deleted"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _get_user_timezone(self, id):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timezone FROM users WHERE id = %s
            """, (id,))
            return cursor.fetchone()[0]
        except Exception as e:
            print(f"DATABASE ERROR in _get_user_timezone: {str(e)}")
            return None
        
    def _set_user_timezone(self, id, timezone):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET timezone = %s WHERE id = %s
            """, (timezone, id))
            conn.commit()

    def _get_user_name(self, id):
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("SELECT name FROM users WHERE id = %s", (id,))
            user_data = cur.fetchone()
            cur.close()
            conn.close()
            if user_data:
                return user_data[0]
            return None
        except Exception as e:
            print(f"DATABASE ERROR in _get_user_name: {str(e)}")
            return None

    def _get_user_count(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM users
            """)
            return cursor.fetchone()[0]
        
    def _find_user_by_email(self, email):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM users WHERE email = %s
            """, (email,))
            row = cursor.fetchone()
            if row:
                return {"id": row[0], "email": row[1], "name": row[2], "timezone": row[3]}
            else:
                return None

    def _store_strava_tokens(self, user_id, athlete_id, access_token, refresh_token, expires_at):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE users
                    SET strava_athlete_id = %s,
                        strava_access_token = %s,
                        strava_refresh_token = %s,
                        strava_token_expires_at = %s
                    WHERE id = %s
                """, (athlete_id, access_token, refresh_token, expires_at, user_id))
                conn.commit()
            return {"success": True}
        except Exception as e:
            print(f"DATABASE ERROR in _store_strava_tokens: {str(e)}")
            return {"success": False, "message": str(e)}

    def _update_strava_tokens(self, user_id, access_token, refresh_token, expires_at):
        """Update only the token fields without changing athlete_id"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE users
                    SET strava_access_token = %s,
                        strava_refresh_token = %s,
                        strava_token_expires_at = %s
                    WHERE id = %s
                """, (access_token, refresh_token, expires_at, user_id))
                conn.commit()
            return {"success": True}
        except Exception as e:
            print(f"DATABASE ERROR in _update_strava_tokens: {str(e)}")
            return {"success": False, "message": str(e)}

    def _get_strava_tokens(self, user_id):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT strava_access_token, strava_refresh_token, strava_token_expires_at
                    FROM users WHERE id = %s
                """, (user_id,))
                row = cursor.fetchone()
                if row and row[0]:  # Check if tokens exist
                    return {
                        "access_token": row[0],
                        "refresh_token": row[1],
                        "expires_at": row[2]
                    }
                else:
                    return None
        except Exception as e:
            print(f"DATABASE ERROR in _get_strava_tokens: {str(e)}")
            return None

    # Activity types table methods

    def _create_activity_types_table(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS activity_types (
                    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    type TEXT NOT NULL,
                    winter INTEGER NOT NULL,
                    summer INTEGER NOT NULL,
                    spring INTEGER NOT NULL,
                    fall INTEGER NOT NULL,
                    UNIQUE(user_id, type)
                )
            """)
            conn.commit()

    def _create_activity_type(self, user_id, type, winter, spring, summer, fall):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO activity_types (user_id, type, winter, spring, summer, fall)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, type) DO NOTHING
                RETURNING id
            """, (user_id, type, winter, spring, summer, fall))
            conn.commit()
            result = cursor.fetchone()
            return result[0] if result else None
        
    def _get_activity_type_name(self, type_id):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT type FROM activity_types WHERE id = %s
            """, (type_id,))
            return cursor.fetchone()[0]

    def _get_user_activity_types(self, user_id):
        activity_types = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, type, winter, spring, summer, fall 
                FROM activity_types 
                WHERE user_id = %s
                ORDER BY type
            """, (user_id,))
            rows = cursor.fetchall()
            for row in rows:
                activity_types.append({
                    "id": row[0],
                    "type": row[1],
                    "winter": row[2],
                    "spring": row[3],
                    "summer": row[4],
                    "fall": row[5]
                })
        return activity_types
        
    def _remove_activity_type(self, user_id, type):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM activity_types WHERE user_id = %s AND type = %s
            """, (user_id, type))
            conn.commit()

    def _get_activity_type_id(self, user_id, type):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM activity_types WHERE user_id = %s AND type = %s
            """, (user_id, type))
            result = cursor.fetchone()
            conn.commit()
            return result[0] if result else -1

    # Activity table methods

    def _create_activities_table(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS activities (
                    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    type_id INTEGER REFERENCES activity_types(id) ON DELETE CASCADE,
                    time TIMESTAMP WITH TIME ZONE NOT NULL,
                    UNIQUE(user_id, type_id, time)
                )
            """)
            conn.commit()

    def _add_activity(self, user_id, type_id, time):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO activities (user_id, type_id, time)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, type_id, time) DO NOTHING
            """, (user_id, type_id, time))
            conn.commit()

    def _get_activities(self, user_id):
        activities = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.id, a.user_id, at.type, a.time 
                FROM activities a
                JOIN activity_types at ON a.type_id = at.id
                WHERE a.user_id = %s
                ORDER BY a.time ASC
            """, (user_id,))
            rows = cursor.fetchall()
            for row in rows:
                activities.append({
                    "id": row[0],
                    "user_id": row[1],
                    "type": row[2],
                    "time": row[3]
                })
        return activities
        
    def _get_activities_by_type(self, user_id, type_id):
        activities = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM activities WHERE user_id = %s AND type_id = %s
                ORDER BY time ASC
            """, (user_id, type_id))
            rows = cursor.fetchall()
            for row in rows:
                activities.append({
                    "id": row[0],
                    "user_id": row[1],
                    "type_id": row[2],
                    "time": row[3]
                })
        return activities
        
    def _get_most_recent_activity(self, user_id, type_id):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM activities WHERE user_id = %s AND type_id = %s ORDER BY time DESC LIMIT 1
            """, (user_id, type_id))
            return cursor.fetchone()
        
    def _remove_activity(self, user_id, type_id, time):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM activities WHERE user_id = %s AND type_id = %s AND time = %s
            """, (user_id, type_id, time))
            conn.commit()

    # User calculations table methods

    def _create_user_calculations_table(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_calculations (
                    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    type_id INTEGER REFERENCES activity_types(id) ON DELETE CASCADE,
                    total FLOAT,
                    thirty FLOAT,
                    season FLOAT,
                    valid BOOLEAN DEFAULT FALSE,
                    UNIQUE(user_id, type_id)
                )
            """)
            conn.commit()

    def _add_user_calculation(self, user_id, type_id, total = 0, thirty = 0, season = 0, valid = False):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_calculations (user_id, type_id, total, thirty, season, valid)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, type_id) DO NOTHING
            """, (user_id, type_id, total, thirty, season, valid))
            conn.commit()

    def _get_user_calculations(self, user_id):
        calculations = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM user_calculations WHERE user_id = %s
            """, (user_id,))
            rows = cursor.fetchall()
            for row in rows:
                calculations.append({
                    "id": row[0],
                    "user_id": row[1],
                    "type_id": row[2],
                    "total": row[3],
                    "thirty": row[4],
                    "season": row[5],
                    "valid": row[6]
                })
        return calculations
    
    def _get_invalid_user_calculations(self, user_id):
        calculations = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM user_calculations WHERE user_id = %s AND valid = FALSE
            """, (user_id,))
            rows = cursor.fetchall()
            for row in rows:
                calculations.append({
                    "id": row[0],
                    "user_id": row[1],
                    "type_id": row[2],
                    "total": row[3],
                    "thirty": row[4],
                    "season": row[5],
                    "valid": row[6]
                })
        return calculations

    def _invalidate_user_calculation(self, user_id, type_id):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE user_calculations SET valid = FALSE WHERE user_id = %s AND type_id = %s
            """, (user_id, type_id))
            conn.commit()

    def _update_user_calculation(self, user_id, type_id, total = 0, thirty = 0, season = 0, valid = True):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE user_calculations SET total = %s, thirty = %s, season = %s, valid = %s WHERE user_id = %s AND type_id = %s
            """, (total, thirty, season, valid, user_id, type_id))
            conn.commit()