import csv
from pydantic import BaseModel
from rich import print as rprint
from strava_handler import StravaHandler
from database_handler import DatabaseHandler
from calculation_handler import CalculationHandler
from datetime import datetime, timezone, timedelta
import pytz

"""
Working on...



Plan to deploy on Render (free tier works great for FastAPI)

Later, connect it to PostgreSQL (e.g., Supabase, Railway, or Render's own DB service)


Allow the user to set a date that strava synce shoudl go back to, go to 20 days ago by default

---

npm run dev
uvicorn main:app --reload

Support for seasonal expectations
Support for tier 2 or monthly goals
Be able to put dates that shouldnt matter to the calculation (sick time, vacation time, injury, etc.)
Be able to calculate the average from a specific date
Give a "start" date for when you want an activity to being being calcualted from (for total avg)
"""

#activities.db
# Used to hold the activities

#user_calculation.db
# Used to hold all the averages for each type, and the season starts for each type

#user.db
# Used to hold broad user info, such as timezone and number of season(s) [If I ever support that]

class Activity(BaseModel):

    type: str
    time: str  # format: YYYY-MM-DDTHH:MM:SSZ example : 2025-02-24T20:16:13Z


class FrequencyTracker:

    # Class attributes
    strava_handler = StravaHandler()
    database_handler = DatabaseHandler()
    calculation_handler = CalculationHandler()
    csv_file = ''
    activities_db = ''
    user_db = ''
    user_calculations_db = ''
    user_frequencies_db = ''

    # Temp User Data

    monthly_activity_bank = { "Drawing" : [1, 0, 0],
                            "Ice Skating" : [1, 0, 0],
                            "Coding" : [1, 0, 0]
                            }

    # Create access token on construction
    def __init__(self):
        self.activities_db = "activities.db"
        self.user_db = "user.db"
        self.user_calculations_db = "user_calculations.db"
        self.user_frequencies_db = "user_frequencies.db"
        self.database_handler = DatabaseHandler(self.activities_db, self.user_db, self.user_calculations_db, self.user_frequencies_db)
        self.database_handler.initialize()

        # Make sure the user time zone is set
        with self.database_handler.user_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, timezone
                FROM user
            """,)
            row = cursor.fetchone() #{"id": row[0], "timezone": row[1]}
            if not row:
                cursor.execute("""
                    INSERT OR IGNORE INTO user (timezone)
                    VALUES (?)
                """, ("MST",))
                conn.commit()

        expected_frequencies = { "Swim" : 4,
                "Ride" : 4,
                "Run" : 4,
                "WeightTraining" : 3,
                "Pilates" : 5,
                "Yoga" : 4,
                "Reading" : 7,
                "Woodworking" : 7,
                "Chess" : 6,
                "Piano" : 3}

        # Make sure the user frequencies are set
        with self.database_handler.user_frequencies_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, type, winter, summer, spring, fall
                FROM user_frequencies
            """,)
            row = cursor.fetchone()
            if not row:
                for activity_name, expected_frequency in expected_frequencies.items():
                    cursor.execute("""
                        INSERT OR IGNORE INTO user_frequencies (type, winter, summer, spring, fall)
                        VALUES (?, ?, ?, ?, ?)
                    """, (activity_name, expected_frequency, expected_frequency, expected_frequency, expected_frequency))
                    conn.commit()

        # Make sure the user calculations are set
        with self.database_handler.user_calculations_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, type, total, thirty, season
                FROM user_calculations
            """,)
            row = cursor.fetchone()
            if not row:
                for activity_name in expected_frequencies:
                    cursor.execute("""
                        INSERT OR IGNORE INTO user_calculations (type, total, thirty, season)
                        VALUES (?, ?, ?, ?)
                    """, (activity_name, 0, 0, 0))
                    conn.commit()


    def sync_strava(self, since: str = None):
        # This function does not attempt to trim the activities to only new ones
        # Duplicates are handled on the sql end
        activities = self.strava_handler.fetch_strava_activities(since)
        for strava_activity in activities:
            activity = Activity(type=strava_activity['sport_type'], time=strava_activity['start_date'])
            self.add_activity(activity)
        self.compute_frequency_averages()
        return {"message": f"Successfully synced {len(activities)} activities from Strava"}

    def add_activity(self, activity):             
        with self.database_handler.activities_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO activities (type, time)
                VALUES (?, ?)
            """, (activity.type, activity.time))
            conn.commit()
            """if cursor.rowcount == 0:
                return {"message": "Duplicate activity"}
            else:
                return {"message": "Added activity successfully"}"""
            self.compute_frequency_averages()

    def time_of_last_activity(self, activity_type):
        with self.database_handler.activities_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, type, time
                FROM activities
                WHERE type = ?
                ORDER BY time DESC
                LIMIT 1
            """, (activity_type,))
            row = cursor.fetchone() #{"id": row[0], "type": row[1], "time": row[2]}
            if row:
                return self.calculation_handler.days_ago(row[2])
            else:
                return -1

    def compute_frequency_averages(self):
        
        # Find the earliest time for each activity
        # Count all activities between that time and today
        # Compute the average
        # Initialize activity counter from user_frequencies table
        activity_counter = {}
        activity_set = set()
        
        with self.database_handler.user_frequencies_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT type
                FROM user_frequencies
            """)
            rows = cursor.fetchall()
            for row in rows:
                activity_type = row[0]
                activity_counter[activity_type] = [0, 0, 0, 0]  # [total, thirty_days, season, earliest_time]
                activity_set.add(activity_type)

        # 30 Days ago
        local_timestamp = datetime.now()
        rollback = local_timestamp.hour * 3600 + local_timestamp.minute*60 + local_timestamp.second
        difference = timedelta(seconds=(30*24*3600 + rollback))
        thirty_days_ago = datetime.now(timezone.utc) - difference

        # Get user timezone
        user_timezone = pytz.timezone("UTC")
        with self.database_handler.user_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, timezone
                FROM user
            """)
            row = cursor.fetchone()
            user_timezone = pytz.timezone(row[1])
        
        # Determine current season and set season start date
        current_date = datetime.now(user_timezone)
        current_month = current_date.month
        
        if 3 <= current_month < 6:  # Spring (March-May)
            season_start = user_timezone.localize(datetime(current_date.year, 3, 1), is_dst=None)
        elif 6 <= current_month < 9:  # Summer (June-August)
            season_start = user_timezone.localize(datetime(current_date.year, 6, 1), is_dst=None)
        elif 9 <= current_month < 12:  # Fall (September-November)
            season_start = user_timezone.localize(datetime(current_date.year, 9, 1), is_dst=None)
        else:  # Winter (December-February)
            season_start = user_timezone.localize(datetime(current_date.year, 12, 1), is_dst=None)

        # Process activities in chronological order
        with self.database_handler.activities_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, type, time
                FROM activities
                ORDER BY time ASC
            """)
            rows = cursor.fetchall()
            activities = [Activity(type=row[1], time=row[2]) for row in rows]
            
            for activity in activities:
                # Record earliest time for each activity type
                if activity.type in activity_set:
                    activity_counter[activity.type][3] = activity.time
                    activity_set.remove(activity.type)

                # Update counters for each average
                if activity.type in activity_counter:
                    activity_counter[activity.type][0] += 1  # Increment total counter
                    if datetime.fromisoformat(activity.time) > thirty_days_ago:
                        activity_counter[activity.type][1] += 1  # Increment 30 day counter
                    if datetime.fromisoformat(activity.time) > season_start:
                        activity_counter[activity.type][2] += 1  # Increment seasonal counter


        # Wrtie out the averages calculated to our user_calculation db
        for activity_name, activity_data in activity_counter.items():

            # If we no activity at all was found leave early
            if not activity_data[3]:
                continue

            total_frequency = round(self.calculation_handler.days_ago(activity_data[3]) / activity_data[0], 2)

            # If we have activities within 30 days calculate the average
            thirty_frequency = 0
            if activity_data[1] != 0:
                thirty_frequency = round(30 / activity_data[1], 2)

            season_frequency = 0
            if activity_data[2] != 0:
                season_frequency = round(self.calculation_handler.days_ago(season_start.isoformat()) / activity_data[2], 2)

            with self.database_handler.user_calculations_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE user_calculations
                    SET total = ?, thirty = ?, season = ?
                    WHERE type = ?
                """, (total_frequency, thirty_frequency, season_frequency, activity_name))
                conn.commit()
            

    def view_frequencies(self):
        activities = []
        
        with self.database_handler.user_calculations_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, type, total, thirty, season
                FROM user_calculations
            """,)
            rows = cursor.fetchall() 
            for row in rows:  #{"id": row[0], "type": row[1], "total": row[2], "thirty": row[3], "season": row[4]}
                activity_name = row[1]
                total_frequency = float(row[2])
                thirty_frequency = float(row[3])
                season_frequency = float(row[4])

                # Find expected frequency
                expected_frequency = 0
                with self.database_handler.user_frequencies_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT id, type, winter, summer, spring, fall
                        FROM user_frequencies
                    """,)
                    freq_rows = cursor.fetchall() 
                    for freq_row in freq_rows:  #{"id": row[0], "type": row[1], "winter": row[2], "spring": row[3], "summer": row[4], "fall": row[5]}
                        if activity_name == freq_row[1]:                
                            expected_frequency = int(freq_row[2])

                current_frequency = self.time_of_last_activity(activity_name)
                
                activity_data = {
                    "name": activity_name,
                    "current_frequency": current_frequency,
                    "expected_frequency": expected_frequency,
                    "thirty_day_average": thirty_frequency,
                    "season_average": season_frequency,
                    "running_average": total_frequency
                }
                activities.append(activity_data)
                
        return {"activities": activities}

    def view_recommendations(self):
        today = []
        tomorrow = []

        with self.database_handler.user_calculations_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, type, total, thirty, season
                FROM user_calculations
            """,)
            rows = cursor.fetchall() 
            for row in rows:  #{"id": row[0], "type": row[1], "total": row[2], "thirty": row[3], "season": row[4]}

                activity_name = row[1]
                total_frequency = float(row[2])
                thirty_frequency = float(row[3])
                season_frequency = float(row[4])

                expected_frequency = 0
                with self.database_handler.user_frequencies_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT id, type, winter, summer, spring, fall
                        FROM user_frequencies
                    """,)
                    freq_rows = cursor.fetchall() 
                    for freq_row in freq_rows:  #{"id": row[0], "type": row[1], "winter": row[2], "spring": row[3], "summer": row[4], "fall": row[5]}
                        if activity_name == freq_row[1]:                
                            expected_frequency = freq_row[2]

                frequency = self.time_of_last_activity(activity_name)
                activity_data = {
                    "name": activity_name,
                    "current_frequency": frequency,
                    "expected_frequency": expected_frequency,
                    "thirty_day_average": thirty_frequency,
                    "season_average": season_frequency,
                    "running_average": total_frequency
                }
                
                if frequency >= expected_frequency or frequency < 0:
                    today.append(activity_data)
                elif frequency == expected_frequency - 1:
                    tomorrow.append(activity_data)

        return {
            "today": today,
            "tomorrow": tomorrow
        }

    def delete_activity(self, activity_type: str, date: str):
        # Convert date string to datetime and format to match database format
        date_obj = datetime.fromisoformat(date.replace('Z', '+00:00'))
        date_str = date_obj.strftime('%Y-%m-%d')
        
        with self.database_handler.activities_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM activities
                WHERE type = ? AND date(time) = ?
            """, (activity_type, date_str))
            conn.commit()
            if cursor.rowcount == 0:
                return {"message": f"No activity found for {activity_type} on {date_str}"}
            return {"message": f"Activity deleted for {activity_type} on {date_str}"}

    def delete_activity_type(self, activity_type: str):
        # Delete from activities table
        with self.database_handler.activities_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM activities
                WHERE type = ?
            """, (activity_type,))
            conn.commit()

        # Delete from user_frequencies table
        with self.database_handler.user_frequencies_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM user_frequencies
                WHERE type = ?
            """, (activity_type,))
            conn.commit()

        # Delete from user_calculations table
        with self.database_handler.user_calculations_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM user_calculations
                WHERE type = ?
            """, (activity_type,))
            conn.commit()

        return {"message": f"Activity type {activity_type} deleted successfully"}

    def add_activity_type(self, activity_type: str, winter: int, spring: int, summer: int, fall: int):
        # Add to user_frequencies table
        with self.database_handler.user_frequencies_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO user_frequencies (type, winter, summer, spring, fall)
                VALUES (?, ?, ?, ?, ?)
            """, (activity_type, winter, spring, summer, fall))
            conn.commit()

        # Add to user_calculations table
        with self.database_handler.user_calculations_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO user_calculations (type, total, thirty, season)
                VALUES (?, ?, ?, ?)
            """, (activity_type, 0, 0, 0))
            conn.commit()

        return {"message": f"Activity type {activity_type} added with seasonal frequencies: Winter={winter}, Spring={spring}, Summer={summer}, Fall={fall}"}

    def get_user_timezone(self):
        with self.database_handler.user_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timezone
                FROM user
                LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                return {"timezone": row[0]}
            return {"timezone": "UTC"}  # Default to UTC if no timezone is set

    def update_timezone(self, timezone: str):
        with self.database_handler.user_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE user
                SET timezone = ?
                WHERE id = 1
            """, (timezone,))
            conn.commit()
            return {"message": f"Timezone updated to {timezone}"}

    def get_activity_table(self):
        activities = []
        with self.database_handler.activities_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT type, time
                FROM activities
                ORDER BY time DESC
            """)
            rows = cursor.fetchall()
            for row in rows:
                activities.append({
                    "type": row[0],
                    "time": row[1]
                })
        return {"activities": activities}

    def get_goal_frequencies(self):
        frequencies = []
        with self.database_handler.user_frequencies_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT type, winter, spring, summer, fall
                FROM user_frequencies
                ORDER BY type
            """)
            rows = cursor.fetchall()
            for row in rows:
                frequencies.append({
                    "type": row[0],
                    "winter": row[1],
                    "spring": row[2],
                    "summer": row[3],
                    "fall": row[4]
                })
        return {"frequencies": frequencies}