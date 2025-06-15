import requests
from datetime import datetime
import time

# https://developers.strava.com/docs/reference/


class StravaHandler:

    # Class attributes
    client_id = '163992'
    client_secret = '21c3f77a95317e2a60c592c3ed0fa9971da32d69'
    refresh_token = 'f2d152cea1f108f61a17d690a38e3421014e5082'
    code = 'a1d9533cc494e022f436f91798d88b587ef1c04c'
    access_token = ''

    # Create access token on construction
    def __init__(self):
        response = requests.post(
        'https://www.strava.com/oauth/token',
        data={
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token
        }
        )
        response.raise_for_status()
        self.access_token = response.json()['access_token']
    
    
    def fetch_strava_activities(self, since: str = None):
        if not self.access_token:
            return []

        url = 'https://www.strava.com/api/v3/athlete/activities'
        headers = {'Authorization': f'Bearer {self.access_token}'}
        
        # Convert since date to timestamp if provided
        since_timestamp = None
        if since:
            since_timestamp = int(datetime.fromisoformat(since).timestamp())
        
        all_activities = []
        page = 1
        chunk_size = 20  # Fetch 20 activities at a time
        
        while True:
            params = {
                'per_page': chunk_size,
                'page': page
            }
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            activities = response.json()
            
            # If no activities returned, we're done
            if not activities:
                break
                
            # Add activities to our list
            all_activities.extend(activities)
            
            # If we have a since date, check if we've gone far enough back
            if since_timestamp:
                # Check the last activity in this chunk
                last_activity = activities[-1]
                activity_timestamp = int(datetime.fromisoformat(last_activity['start_date'].replace('Z', '+00:00')).timestamp())
                
                # If this activity is before our since date, we can stop
                if activity_timestamp < since_timestamp:
                    break
            
            # Move to next page
            page += 1
            
            # Optional: Add a small delay to avoid hitting rate limits
            time.sleep(0.5)
            
        return all_activities
        