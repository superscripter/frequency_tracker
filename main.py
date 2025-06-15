# main.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from frequency_tracker import FrequencyTracker, Activity
from typing import List
import sqlite3
from datetime import datetime, timezone, timedelta

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.get("/")
def read_root():
    return {"Hello": "World"}

# Only run this if executed as `python main.py`, not via `uvicorn main:app`
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

frequency_tracker = FrequencyTracker() 
frequency_tracker.compute_frequency_averages()

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
        return frequency_tracker.update_timezone(timezone)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------- GET METHODS ----------------------------- 

@app.get("/frequencies/")
def get_recommendations():
    return frequency_tracker.view_frequencies()

@app.get("/user_timezone/")
def get_user_timezone():
    try:
        return frequency_tracker.get_user_timezone()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/recommendations/")
def get_recommendations():
    return frequency_tracker.view_recommendations()

@app.get("/activity_table/")
def get_activity_table():
    try:
        return frequency_tracker.get_activity_table()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/goal_frequencies/")
def get_goal_frequencies():
    try:
        return frequency_tracker.get_goal_frequencies()
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

#http://127.0.0.1:8000/
#uvicorn main:app --reload  
#npx tailwindcss -i ./input.css -o ./output.css --watch

# curl -X POST "http://127.0.0.1:8000/activity/?activity_type=Chess"
# curl -X POST "http://127.0.0.1:8000/sync/"
# curl -X GET "http://127.0.0.1:8000/frequencies/"
# curl -X GET "http://127.0.0.1:8000/recommendations/"
# curl -X DELETE http://127.0.0.1:8000/activity/424

