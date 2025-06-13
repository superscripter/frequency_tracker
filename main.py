# main.py
from fastapi import FastAPI, HTTPException, Query
from frequency_tracker import FrequencyTracker, Activity
from typing import List
import sqlite3
from datetime import datetime, timezone, timedelta

app = FastAPI()

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

@app.post("/activity/")
def add_activity(activity_type: str = Query(...)):
    try:
        return frequency_tracker.add_activity( Activity(type=activity_type, time=datetime.now(timezone.utc).isoformat()))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/sync/")
def sync_strava():
    try:
        return frequency_tracker.sync_strava()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------- GET METHODS ----------------------------- 

@app.get("/activities/", response_model=List[Activity])
def get_activities():
    try:
        with frequency_tracker.create_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT type, time FROM activities")
            rows = cursor.fetchall()
            return [Activity(type=row[0], time=row[1]) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/frequencies/")
def get_recommendations():
    return frequency_tracker.view_frequencies()

@app.get("/recommendations/")
def get_recommendations():
    return frequency_tracker.view_recommendations()

@app.delete("/activity/{activity_id}")
def delete_activity(activity_id: int):
    try:
        return frequency_tracker.delete_activity_by_id(activity_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

#http://127.0.0.1:8000/
#uvicorn main:app --reload  
# curl -X POST "http://127.0.0.1:8000/activity/?activity_type=Chess"
# curl -X POST "http://127.0.0.1:8000/sync/"
# curl -X GET "http://127.0.0.1:8000/frequencies/"
# curl -X GET "http://127.0.0.1:8000/recommendations/"
# curl -X DELETE http://127.0.0.1:8000/activity/424

