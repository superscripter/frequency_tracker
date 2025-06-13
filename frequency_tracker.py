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

Spin up the user_calculations.db and user.db

Plan to deploy on Render (free tier works great for FastAPI)

Later, connect it to PostgreSQL (e.g., Supabase, Railway, or Render’s own DB service)

Support for the seasonalty frequency calculations
Support fot tier 2 or monthly goals
Be able to put dates that shouldnt matter to the calculation (sick time, vacation time, injury, etc.)
Be able to ingest ALL my strava data
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


    def sync_strava(self):
        # This function does not attempt to trim the activities to only new ones
        # Duplicates are handled on the sql end
        activities = self.strava_handler.fetch_strava_activities()
        for strava_activity in activities:
            activity = Activity(type=strava_activity['sport_type'], time=strava_activity['start_date'])
            self.add_activity(activity)
        self.compute_frequency_averages()

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

        activity_counter = {"Swim" : [0, 0, 0, 0],
                            "Ride" : [0, 0, 0, 0],
                            "Run" : [0, 0, 0, 0],
                            "WeightTraining" : [0, 0, 0, 0],
                            "Pilates" : [0, 0, 0, 0],
                            "Yoga" : [0, 0, 0, 0],
                            "Reading" : [0, 0, 0, 0],
                            "Woodworking" : [0, 0, 0, 0],
                            "Chess" : [0, 0, 0, 0],
                            "Piano" : [0, 0, 0, 0]}
        
        activity_set = set()
        for activity_name in activity_counter:
            activity_set.add(activity_name)

        # 30 Days ago
        local_timestamp = datetime.now()
        rollback = local_timestamp.hour * 3600 + local_timestamp.minute*60 + local_timestamp.second
        difference =  timedelta(seconds = (30*24*3600 +  rollback))
        thirty_days_ago = datetime.now(timezone.utc) - difference

        # Summer start
        user_timezone = pytz.timezone("UTC")
        with self.database_handler.user_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, timezone
                FROM user
            """,)
            row = cursor.fetchone() #{"id": row[0], "timezone": row[1]}
            user_timezone = pytz.timezone(row[1])
        summer_start = user_timezone.localize(datetime(2025, 6, 1), is_dst=None)

        # We want to start with the oldest activities to make calculations easier
        # Note : This loop recalculates ALL averages and not just thoose that have activities that are pertinent
        with self.database_handler.activities_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, type, time
                FROM activities
                ORDER BY time ASC
            """,)
            rows = cursor.fetchall() #{"id": row[0], "type": row[1], "time": row[2]}
            activities = [Activity(type=row[1], time=row[2]) for row in rows]  
            for activity in activities:

                # We use a set to record the earliest time of each activity
                if activity.type in activity_set:
                    activity_counter[activity.type][3] = activity.time
                    activity_set.remove(activity.type)

                # Increment our counters for each average we hold
                if activity.type in activity_counter:
                    activity_counter[activity.type][0] += 1 # Increment total counter
                    if  datetime.fromisoformat(activity.time) > thirty_days_ago:
                        activity_counter[activity.type][1] += 1 # Increment 30 day counter
                    if  datetime.fromisoformat(activity.time) > summer_start:
                        activity_counter[activity.type][2] += 1 # Increment seasonal counter


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
                season_frequency = round(self.calculation_handler.days_ago(summer_start.isoformat()) / activity_data[2], 2)

            with self.database_handler.user_calculations_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE user_calculations
                    SET total = ?, thirty = ?, season = ?
                    WHERE type = ?
                """, (total_frequency, thirty_frequency, season_frequency, activity_name))
                conn.commit()
            

    def view_frequencies(self):

        print("\n")

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

                # Print Name
                rprint(f"{activity_name:<16} | ", end="")

                # Current Track
                current_frequency = self.time_of_last_activity(activity_name)
                color = "[red]" 
                if current_frequency >= 0 and current_frequency <= expected_frequency:
                    color = "[green]"
                rprint(f"{color + str(current_frequency):<3}", end="")  

                # Expected Number
                rprint(f"  [blue]{str(expected_frequency):<3}", end="")

                #30 Day Average
                color = "[red]"
                if thirty_frequency <= expected_frequency and thirty_frequency != 0:
                    color = "[green]"
                rprint(f"  Thirty Day Average: {color + str(thirty_frequency):<5}", end="")  

                #Summer Average
                color = "[red]"
                if season_frequency <= expected_frequency and season_frequency != 0:
                    color = "[green]"
                rprint(f"  Summer Average: {color + str(season_frequency)}", end="")

                # Total Average
                color = "[red]"
                if total_frequency <= expected_frequency and total_frequency != 0:
                    color = "[green]"
                rprint(f"  Running Average: {color + str(total_frequency):<5}  ")

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

                color = "[red]"
                frequency = self.time_of_last_activity(activity_name)
                if frequency >= expected_frequency or frequency < 0:
                    today.append([activity_name, str(frequency), expected_frequency, str(thirty_frequency), str(season_frequency), str(total_frequency)])
                elif frequency == expected_frequency - 1:
                    tomorrow.append([activity_name, str(frequency), expected_frequency, str(thirty_frequency), str(season_frequency), str(total_frequency)])

        print("\nTodays Recommendations")
        for entry in today:

            # Print Name
            rprint(f"{entry[0]:<16} | ", end="")

            # Current Track
            color = "[green]"
            if float(entry[1]) < 0 or float(entry[1]) > float(entry[2]):
                color = "[red]"
            rprint(f"{color + entry[1]:<3}", end="")  

            # Expected Number
            rprint(f"  [blue]{entry[2]:<3}", end="")

            #30 Day Average
            color = "[red]"
            if float(entry[4]) <= float(entry[2]) and float(entry[4]) != 0:
                color = "[green]"
            rprint(f"  Thirty Day Average: {color + entry[4]:<5}", end="")  

            #Summer Average
            color = "[red]"
            if float(entry[5]) <= float(entry[2]) and float(entry[5]) != 0:
                color = "[green]"
            rprint(f"  Summer Average: {color + entry[5]}", end="")

            # Total Average
            color = "[red]"
            if float(entry[3]) <= float(entry[2]) and float(entry[3]) != 0:
                    color = "[green]"
            rprint(f"  Running Average: {color + entry[3]:<3}")


        print("\nTomorrows Recommendations")
        for entry in tomorrow:

            # Print Name
            rprint(f"{entry[0]:<16} | ", end="")

            # Current Track
            rprint(f"{"[green]" + entry[1]:<3}", end="")  

            # Expected Number
            rprint(f"  [blue]{entry[2]:<3}", end="")

            #30 Day Average
            color = "[red]"
            if float(entry[4]) <= float(entry[2]) and float(entry[4]) != 0:
                color = "[green]"
            rprint(f"  Thirty Day Average: {color + entry[4]:<5}", end="")  

            #Summer Average
            color = "[red]"
            if float(entry[5]) <= float(entry[2]) and float(entry[5]) != 0:
                color = "[green]"
            rprint(f"  Summer Average: {color + entry[5]}", end="")
            
            # Total Average
            color = "[red]"
            if float(entry[3]) <= float(entry[2]) and float(entry[3]) != 0:
                    color = "[green]"
            rprint(f"  Running Average: {color + entry[3]:<3}")

    def delete_activity_by_id(self, activity_id: int):
        with self.database_handler.activities_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM activities
                WHERE id = ?
            """, (activity_id,))
            conn.commit()
            if cursor.rowcount == 0:
                return {"message": f"No activity with id {activity_id} found."}
            return {"message": f"Activity with id {activity_id} deleted."}