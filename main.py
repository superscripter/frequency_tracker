# main.py
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from frequency_tracker import FrequencyTracker, Activity
from typing import List
import sqlite3
from datetime import datetime, timezone, timedelta
from email_validator import validate_email, EmailNotValidError
import uvicorn
import os

app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
    "null",  # Allow requests from local files
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files from the frequency-tracker-ui directory
app.mount("/static", StaticFiles(directory="frequency-tracker-ui"), name="static")

frequency_tracker = FrequencyTracker()

@app.get("/")
def read_root():
    # Serve the frontend HTML file
    return FileResponse("frequency-tracker-ui/index.html")

# Only run this if executed as `python main.py`, not via `uvicorn main:app`
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

# ----------------------------- POST METHODS ----------------------------- 

@app.post("/add_activity/")
def add_activity(activity_type: str = Query(...), time: str = Query(None)):
    try:
        activity_time = time if time else datetime.now(timezone.utc).isoformat()
        return frequency_tracker.add_activity(Activity(type=activity_type, time=activity_time))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/sync/")
def sync_strava(since: str = Query(None)):
    try:
        return frequency_tracker.sync_strava(since)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/add_activity_type/")
def add_activity_type(
    activity_type: str = Query(...),
    winter: int = Query(...),
    spring: int = Query(...),
    summer: int = Query(...),
    fall: int = Query(...)
):
    try:
        return frequency_tracker.add_activity_type(activity_type, winter, spring, summer, fall)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/update_timezone/")
def update_timezone(timezone: str = Query(...)):
    try:
        return frequency_tracker.set_user_timezone(timezone)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/sign_in/")
def sign_in(email: str = Query(...), password: str = Query(...), response: Response = None):
    try:
        result = frequency_tracker.sign_in(email, password)
        if result["success"]:
            # Ensure we have a response object
            if response is None:
                response = Response()
            # Set a secure cookie
            response.set_cookie(
                key="session",
                value=str(result["id"]),
                httponly=True,
                secure=False,  # Set to True in production with HTTPS
                samesite="lax",
                max_age=3600 * 24 * 7  # 7 days
            )
            print(f"DEBUG: Set cookie for user {result['id']}")
            return result
        else:
            return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/sign_out")
def sign_out(response: Response = None):
    try:
        result = frequency_tracker.sign_out()
        # Ensure we have a response object
        if response is None:
            response = Response()
        # Clear the cookie
        response.delete_cookie(key="session")
        print("DEBUG: Cleared session cookie")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/create_user")
def create_user(email: str = Query(...), password: str = Query(...), name: str = Query(...), timezone: str = Query(...), response: Response = None):
    print(f"--- Received /create_user request ---")
    try:
        # Validate email format
        validate_email(email)
        result = frequency_tracker.create_user(email, password, name, timezone)
        if result["success"]:
            # Ensure we have a response object
            if response is None:
                response = Response()
            # Set a secure cookie
            response.set_cookie(
                key="session", 
                value=str(result["id"]), 
                httponly=True,
                secure=False,  # Set to True in production with HTTPS
                samesite="lax",
                max_age=3600 * 24 * 7  # 7 days
            )
            print(f"DEBUG: Set cookie for new user {result['id']}")
        return result
    except EmailNotValidError as e:
        # Return a specific error for invalid email
        raise HTTPException(status_code=422, detail=f"Invalid email address: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------- GET METHODS ----------------------------- 

@app.get("/check_auth")
def check_auth(request: Request):
    try:
        session_cookie = request.cookies.get("session")
        print(f"DEBUG: Received session cookie: {session_cookie}")
        
        if session_cookie:
            try:
                user_id = int(session_cookie)
                frequency_tracker.current_user_id = user_id
                print(f"DEBUG: Restored session for user {user_id}")
                return {"authenticated": True, "user_id": user_id}
            except ValueError:
                print("DEBUG: Invalid session cookie value")
                return {"authenticated": False}
        else:
            print("DEBUG: No session cookie found")
            return {"authenticated": False}
    except Exception as e:
        print(f"DEBUG: Error checking auth: {str(e)}")
        return {"authenticated": False}

@app.get("/frequencies/")
def get_frequencies():
    return frequency_tracker.get_frequencies()

@app.get("/activity_types/")
def get_activity_types():
    return frequency_tracker.get_activity_types()

@app.get("/user_timezone/")
def get_user_timezone():
    try:
        return frequency_tracker.get_user_timezone()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/user_name/")
def get_user_name():
    return frequency_tracker.get_user_name()

@app.get("/user_id/")
def get_user_id():
    return frequency_tracker.current_user_id

@app.get("/recommendations/")
def get_recommendations():
    return frequency_tracker.get_recommendations()

@app.get("/activity_table/")
def get_activity_table():
    try:
        return frequency_tracker.get_activities()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/delete_activity/")
def delete_activity(activity_type: str = Query(...), time: str = Query(...)):
    try:
        return frequency_tracker.delete_activity(activity_type, time)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/delete_activity_type/")
def delete_activity_type(activity_type: str = Query(...)):
    try:
        return frequency_tracker.delete_activity_type(activity_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/delete_user")
def delete_user(response: Response = None):
    try:
        result = frequency_tracker.delete_user()
        if result["success"]:
            # Clear the cookie
            response.delete_cookie(key="session")
            print("DEBUG: Cleared session cookie after user deletion")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/strava/authorize")
async def strava_authorize(request: Request):
    user_id = frequency_tracker.current_user_id
    if user_id == -1:
        return JSONResponse(status_code=401, content={"message": "Not authenticated"})
    
    auth_url = frequency_tracker.get_authorization_url()
    # Add user_id to the state parameter for later identification
    # This is crucial for linking the Strava account to the correct user
    state = f"user_id:{user_id}"
    return RedirectResponse(url=f"{auth_url}&state={state}")

@app.get("/strava/callback")
async def strava_callback(request: Request, code: str = None, state: str = None, error: str = None):
    if error:
        # User denied access
        # Redirect to frontend with an error message
        return RedirectResponse(url="http://127.0.0.1:8000/?strava_link_error=access_denied")

    if not code or not state:
        return JSONResponse(status_code=400, content={"message": "Invalid callback parameters."})

    # Extract user_id from state
    try:
        user_id = int(state.split(':')[1])
    except (IndexError, ValueError):
        return JSONResponse(status_code=400, content={"message": "Invalid state parameter."})

    token_result = frequency_tracker.exchange_code_for_tokens(code)

    if not token_result["success"]:
        return JSONResponse(status_code=500, content={"message": token_result.get("message")})

    token_data = token_result["data"]
    athlete_id = token_data["athlete"]["id"]
    access_token = token_data["access_token"]
    refresh_token = token_data["refresh_token"]
    expires_at = token_data["expires_at"]

    frequency_tracker.store_strava_tokens(user_id, athlete_id, access_token, refresh_token, expires_at)

    # Redirect user back to the main page with a success message
    return RedirectResponse(url="http://127.0.0.1:8000/?strava_link_success=true")

#http://127.0.0.1:8000/
#uvicorn main:app --reload  
#npx tailwindcss -i ./input.css -o ./output.css --watch

# curl -X POST "http://127.0.0.1:8000/activity/?activity_type=Chess"
# curl -X POST "http://127.0.0.1:8000/sync/"
# curl -X GET "http://127.0.0.1:8000/frequencies/"
# curl -X GET "http://127.0.0.1:8000/recommendations/"
# curl -X DELETE http://127.0.0.1:8000/activity/424

