import requests

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
    
    
    def fetch_strava_activities(self):

        if not self.access_token:
            return []

        url = 'https://www.strava.com/api/v3/athlete/activities'
        headers = {'Authorization': f'Bearer {self.access_token}'}
        params = {'per_page': 200} # Change this to grab more but then it will take longer
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
        