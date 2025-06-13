from datetime import datetime, timezone, timedelta
import math

class CalculationHandler:

    def __init__(self):
        self

    def days_ago(self, timestamp):

        today = datetime.now(timezone.utc)
        difference = today - datetime.fromisoformat(timestamp)

        # What 'today' and 'yesterday' are, is relative to the users time zone and specfically time since midnight last night
        local_timestamp = datetime.now()
        rollback = local_timestamp.hour * 3600 + local_timestamp.minute*60 + local_timestamp.second
        hours_difference =  (difference.total_seconds() - rollback) / 3600

        return math.ceil(hours_difference /  24)