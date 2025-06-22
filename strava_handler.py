import requests
from datetime import datetime
import time
import urllib.parse

# https://developers.strava.com/docs/reference/


class StravaHandler:

    # Class attributes
    client_id = '163992'
    client_secret = '21c3f77a95317e2a60c592c3ed0fa9971da32d69'
    redirect_uri = 'http://127.0.0.1:8000/strava/callback'
    auth_url = 'https://www.strava.com/oauth/authorize'
    token_url = 'https://www.strava.com/oauth/token'

    def __init__(self):
        pass
    
    
    def _fetch_strava_activities(self, access_token: str, since: str = None):
        if not access_token:
            return []

        url = 'https://www.strava.com/api/v3/athlete/activities'
        headers = {'Authorization': f'Bearer {access_token}'}
        
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

    def _get_authorization_url(self):
        # The user_id will be passed back in the `state` parameter to identify the user
        # This is a security measure to prevent CSRF attacks
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "activity:read_all",
        }
        return f"{self.auth_url}?{urllib.parse.urlencode(params)}"

    def get_authorization_url(self):
        return self._get_authorization_url()

    def exchange_code_for_tokens(self, code):
        return self._exchange_code_for_tokens(code)

    def _exchange_code_for_tokens(self, code):
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
        }
        response = requests.post(self.token_url, data=payload)
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "message": "Failed to exchange code for tokens."}

    def refresh_access_token(self, refresh_token: str):
        # This will be used later if the access token expires
        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
        response = requests.post(self.token_url, data=payload)
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            response.raise_for_status() # Raise an exception if refresh fails

    def _refresh_access_token(self):
        # This will be used later if the access token expires
        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token
        }
        response = requests.post(self.token_url, data=payload)
        response.raise_for_status()
        self.access_token = response.json()['access_token']
        self.refresh_token = response.json()['refresh_token']
        