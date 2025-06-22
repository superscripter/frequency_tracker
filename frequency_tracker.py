import csv
from pydantic import BaseModel
from rich import print as rprint
from strava_handler import StravaHandler
from database_handler import DatabaseHandler
from calculation_handler import CalculationHandler
from datetime import datetime, timezone, timedelta
import pytz
import requests

"""
npm run dev
uvicorn main:app --reload

Future Ideas:

Support for seasonal expectations
Support for tier 2 or monthly goals
Be able to put dates that shouldnt matter to the calculation (sick time, vacation time, injury, etc.)
Be able to calculate the average from a specific date
Give a "start" date for when you want an activity to being being calcualted from (for total avg)

    monthly_activity_bank = { "Drawing" : [1, 0, 0],
                            "Ice Skating" : [1, 0, 0],
                            "Coding" : [1, 0, 0]
                            }

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


class FrequencyTracker(DatabaseHandler, StravaHandler, CalculationHandler):

    current_user_id = -1

    # Create access token on construction
    def __init__(self, db_url = ''):
        DatabaseHandler.__init__(self, db_url)
        StravaHandler.__init__(self)
        CalculationHandler.__init__(self)

    def ensure_valid_user(self):
        return self.current_user_id != -1

    def sync_strava(self, since: str = None):

        if not self.ensure_valid_user():
            return {"success": False, "message": "No user is signed in"}

        # Get the user's Strava tokens
        tokens = self.get_strava_tokens()
        if not tokens:
            return {"success": False, "message": "No Strava account linked. Please link your Strava account first."}

        try:
            # This function does not attempt to trim the activities to only new ones
            # Duplicates are handled on the sql end
            activities = self._fetch_strava_activities(tokens["access_token"], since)

            for strava_activity in activities:
                activity = Activity(type=strava_activity['sport_type'], time=strava_activity['start_date'])
                self.add_activity(activity)
            print(f"Synced {len(activities)} activities from Strava")
            self.compute_frequency_averages()
            return {"success": True, "message": f"Successfully synced {len(activities)} activities from Strava"}
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                # Token has expired, try to refresh it
                try:
                    print("Access token expired, attempting to refresh...")
                    refresh_result = self.refresh_access_token(tokens["refresh_token"])
                    
                    if refresh_result["success"]:
                        new_tokens = refresh_result["data"]
                        # Update the database with new tokens
                        self.update_strava_tokens(
                            new_tokens["access_token"],
                            new_tokens["refresh_token"],
                            new_tokens.get("expires_at")
                        )
                        
                        # Retry the sync with the new token
                        print("Token refreshed successfully, retrying sync...")
                        activities = self._fetch_strava_activities(new_tokens["access_token"], since)
                        
                        for strava_activity in activities:
                            activity = Activity(type=strava_activity['sport_type'], time=strava_activity['start_date'])
                            self.add_activity(activity)
                        print(f"Synced {len(activities)} activities from Strava")
                        self.compute_frequency_averages()
                        return {"success": True, "message": f"Successfully synced {len(activities)} activities from Strava"}
                    else:
                        return {"success": False, "message": "Failed to refresh Strava access token. Please re-link your Strava account."}
                except Exception as refresh_error:
                    print(f"Error refreshing token: {refresh_error}")
                    return {"success": False, "message": "Failed to refresh Strava access token. Please re-link your Strava account."}
            else:
                return {"success": False, "message": f"Error syncing Strava activities: {str(e)}"}
        except Exception as e:
            return {"success": False, "message": f"Error syncing Strava activities: {str(e)}"}

    def get_activities(self):
        return self._get_activities(self.current_user_id)

    def add_activity(self, activity: Activity):  

        if not self.ensure_valid_user():
            return
        # Ensure we have a UTC time
        
        timestamp = datetime.fromisoformat(activity.time)
        if timestamp.utcoffset() is not None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        activity_type_id = self._get_activity_type_id(self.current_user_id, activity.type)
        if activity_type_id == -1:
            return

        self._add_activity(self.current_user_id, activity_type_id, timestamp)
        self._invalidate_user_calculation(self.current_user_id, activity_type_id)

        
    def delete_activity(self, activity: Activity):
        
        if not self.ensure_valid_user():
            return
        
        # Ensure we have a UTC time
        timestamp = datetime.fromisoformat(activity.time)
        if timestamp.utcoffset() is not None:
            timestamp = timestamp.replace(tzinfo=None)

        activity_type_id = self._get_activity_type_id(self.current_user_id, activity.type)
        self._remove_activity(self.current_user_id, activity_type_id, timestamp)
        self._invalidate_user_calculation(self.current_user_id, activity_type_id)
        
    def time_of_last_activity(self, type_id):
        
        if not self.ensure_valid_user():
            return
        
        most_recent_activity = self._get_most_recent_activity(self.current_user_id, type_id)
        if most_recent_activity:
            return self._days_ago(most_recent_activity[3], self._get_user_timezone(self.current_user_id))
        else:
            return -1

    def get_user_timezone(self):
                
        if not self.ensure_valid_user():
            return
        
        return self._get_user_timezone(self.current_user_id)

    def set_user_timezone(self, timezone: str):
        self._set_user_timezone(self.current_user_id, timezone)

    def get_current_user_id(self):
        return self.current_user_id

    def sign_in(self, email, password):
        result = self._sign_in(email, password)
        if result["success"]:
            self.current_user_id = result["id"]
        return result

    def sign_out(self):
        self.current_user_id = -1
        return {"success": True, "message": "User signed out"}

    def create_user(self, email, password, name, timezone):
        hashed_password = self.hash_password(password)
        result = self._create_user(email, hashed_password, name, timezone)
        if result["success"]:
            self.current_user_id = result["id"]
            print(f"Created user {self.current_user_id}")
        return result

    def delete_user(self):
        if not self.ensure_valid_user():
            return {"success": False, "message": "No user is signed in."}
        
        user_id_to_delete = self.current_user_id
        # Sign the user out first
        self.current_user_id = -1
        
        return self._remove_user(user_id_to_delete)

    def get_user_name(self):
        if not self.ensure_valid_user():
            return None
        return self._get_user_name(self.current_user_id)

    def set_user_timezone(self, timezone: str):              
        if not self.ensure_valid_user():
            return
        self._set_user_timezone(self.current_user_id, timezone)

    def add_activity_type(self, activity_type: str, winter: int, spring: int, summer: int, fall: int):
                
        if not self.ensure_valid_user():
            return
        
        activity_type_id = self._create_activity_type(self.current_user_id, activity_type, winter, spring, summer, fall)
        if activity_type_id is not None:
            self._add_user_calculation(self.current_user_id, activity_type_id, 0, 0, 0, True)

    def delete_activity_type(self, activity_type: str):
                
        if not self.ensure_valid_user():
            return
        
        activity_type_id = self._get_activity_type_id(self.current_user_id, activity_type)
        self._remove_activity_type(self.current_user_id, activity_type)

    def get_activity_types(self):
        return self._get_user_activity_types(self.current_user_id)

    def store_strava_tokens(self, user_id, athlete_id, access_token, refresh_token, expires_at):
        return self._store_strava_tokens(user_id, athlete_id, access_token, refresh_token, expires_at)

    def update_strava_tokens(self, access_token, refresh_token, expires_at):
        if not self.ensure_valid_user():
            return {"success": False, "message": "No user is signed in"}
        return self._update_strava_tokens(self.current_user_id, access_token, refresh_token, expires_at)

    def get_strava_tokens(self):
        if not self.ensure_valid_user():
            return None
        return self._get_strava_tokens(self.current_user_id)

    def compute_frequency_averages(self):
                
        if not self.ensure_valid_user():
            return
        
        # 30 Days ago
        local_timestamp = datetime.now()
        rollback = local_timestamp.hour * 3600 + local_timestamp.minute*60 + local_timestamp.second
        difference = timedelta(seconds=(30*24*3600 + rollback))
        thirty_days_ago = datetime.now(timezone.utc) - difference
        
        # Determine current season and set season start date
        user_timezone = self._get_user_timezone(self.current_user_id)
        season_start = self._get_season_start(user_timezone)

        # Setup a counter container for each invalid type in the calculations table
        invalid_calculations = self._get_invalid_user_calculations(self.current_user_id)
        for calculation in invalid_calculations:

            # Get all activities for this type
            total_activity_span = 0
            total_activity_count = 0
            thirty_day_activity_count = 0
            seasonal_activity_count = 0

            activities = self._get_activities_by_type(self.current_user_id, calculation["type_id"])
            for activity in activities:

                # Calculate the total span of the activities
                if total_activity_span == 0:
                    total_activity_span = self._days_ago(activity["time"], user_timezone)

                total_activity_count += 1
                if activity["time"] > thirty_days_ago:
                    thirty_day_activity_count += 1
                if activity["time"] > season_start:
                    seasonal_activity_count += 1

            # Calculate the averages
            total_frequency = -1
            if(total_activity_count > 0):
                total_frequency = round(total_activity_span / total_activity_count, 2)
            thirty_frequency = -1
            if(thirty_day_activity_count > 0):
                thirty_frequency = round(30 / thirty_day_activity_count, 2)
            season_frequency = -1
            if(seasonal_activity_count > 0):
                season_frequency = round(self._days_ago(season_start, user_timezone) / seasonal_activity_count, 2)

            # Update out the averages calculated
            self._update_user_calculation(self.current_user_id, calculation["type_id"], total_frequency, thirty_frequency, season_frequency)
     
    def get_frequencies(self):
                
        if not self.ensure_valid_user():
            return
        
        # Ensure we have the latest averages
        self.compute_frequency_averages()

        frequencies = []
        activity_types = self._get_user_activity_types(self.current_user_id)
        season = self._get_season(datetime.now(pytz.timezone(self._get_user_timezone(self.current_user_id) )))

        for user_calculation in self._get_user_calculations(self.current_user_id):

            type_id = user_calculation["id"]
            total_frequency = user_calculation["total"]
            thirty_frequency = user_calculation["thirty"]
            season_frequency = user_calculation["season"]

            # Find expected frequency
            expected_average_frequency = 0
            expected_frequency = 0

            for activity_type in activity_types:
                if activity_type["id"] == type_id:
                    expected_frequency = activity_type[season]
                    expected_average_frequency = (activity_type["winter"] + activity_type["spring"] + activity_type["summer"] + activity_type["fall"]) / 4
                    break
  
            current_frequency = self.time_of_last_activity(type_id)
            type_name = self._get_activity_type_name(type_id)
            
            frequency = {
                "name": type_name,
                "current_frequency": current_frequency,
                "expected_frequency": expected_frequency,
                "expected_average_frequency": expected_average_frequency,
                "thirty_day_average": thirty_frequency,
                "season_average": season_frequency,
                "running_average": total_frequency
            }
            frequencies.append(frequency)
                
        return {"activities": frequencies}

    def get_recommendations(self):
        
        if not self.ensure_valid_user():
            return
        
        # Ensure we have the latest averages
        self.compute_frequency_averages()

        today = []
        tomorrow = []

        frequencies = self.get_frequencies()
        for frequency in frequencies["activities"]:
            if frequency["current_frequency"] >= frequency["expected_frequency"] or frequency["current_frequency"] < 0:
                today.append(frequency)
            elif frequency["current_frequency"] == frequency["expected_frequency"] - 1:
                tomorrow.append(frequency)

        return {
            "today": today,
            "tomorrow": tomorrow
        }
