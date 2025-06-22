from datetime import datetime, timezone, timedelta
import math
import bcrypt
import pytz

class CalculationHandler:

    def __init__(self):
        self

    def _days_ago(self, timestamp: datetime, user_timezone: str):

        today = datetime.now(timezone.utc)
        difference = today - timestamp

        # What 'today' and 'yesterday' are, is relative to the users time zone and specfically time since midnight last night
        local_timestamp = datetime.now(pytz.timezone(user_timezone))
        rollback = local_timestamp.hour * 3600 + local_timestamp.minute*60 + local_timestamp.second
        hours_difference =  (difference.total_seconds() - rollback) / 3600

        return math.ceil(hours_difference /  24)
    
    def _get_season(self, timestamp: datetime):
        month = timestamp.month
        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8]:
            return "summer"
        else:
            return "fall"
        
    def _get_season_start(self, user_timezone: str):
        current_date = datetime.now(pytz.timezone(user_timezone))
        current_month = current_date.month
        
        if 3 <= current_month < 6:  # Spring (March-May)
            return pytz.timezone(user_timezone).localize(datetime(current_date.year, 3, 1), is_dst=None)
        elif 6 <= current_month < 9:  # Summer (June-August)
            return pytz.timezone(user_timezone).localize(datetime(current_date.year, 6, 1), is_dst=None)
        elif 9 <= current_month < 12:  # Fall (September-November)
            return pytz.timezone(user_timezone).localize(datetime(current_date.year, 9, 1), is_dst=None)
        else:  # Winter (December-February)
            return pytz.timezone(user_timezone).localize(datetime(current_date.year, 12, 1), is_dst=None)
        
    def hash_password(self, plain_password: str) -> str:
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(plain_password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))