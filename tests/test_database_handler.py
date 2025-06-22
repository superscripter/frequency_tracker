import os
import pytest
import datetime
from database_handler import DatabaseHandler
from dotenv import load_dotenv

load_dotenv()

dummy_user_email = "test@example.com"

@pytest.fixture(scope="module")
def db_handler():

    test_db_url = os.environ.get("DATABASE_URL")
    handler = DatabaseHandler(db_url = test_db_url)
    handler._initialize_tables()

    # Purge the dummy user
    purge_dummy_user(handler)

    # Optionally: create tables here if not auto-created
    yield handler
    # Optionally: teardown/cleanup code here

def purge_dummy_user(db_handler):
    result = db_handler._find_user_by_email(email=dummy_user_email)
    if result is not None:
        db_handler._remove_user(id=result["id"])

def test_user_table(db_handler):

    # Add a user
    user_count_1 = db_handler._get_user_count()
    result = db_handler._create_user(email=dummy_user_email, name="Test", timezone="America/Denver")
    assert result["success"] == True
    user_id = result["id"]
    user_count_2 = db_handler._get_user_count()
    assert user_count_2 == user_count_1 + 1

    # Add a duplicate user
    result = db_handler._create_user(email=dummy_user_email, name="Test2", timezone="America/New_York")
    assert result["success"] == False
    assert user_count_2 == db_handler._get_user_count()

    # Get user timezone
    result = db_handler._get_user_timezone(id=user_id)
    assert result == "America/Denver"

    # Find user by email
    result = db_handler._find_user_by_email(email=dummy_user_email)
    assert result is not None
    assert result["email"] == dummy_user_email
    assert result["name"] == "Test"
    assert result["timezone"] == "America/Denver"

    # Remove a user
    result = db_handler._remove_user(result["id"])
    assert db_handler._get_user_count() == user_count_1

def test_activity_types_table(db_handler):
    
    # Add a dummy user
    user_count_1 = db_handler._get_user_count()
    result = db_handler._create_user(email=dummy_user_email, name="Test", timezone="America/Denver")
    assert result["success"] == True
    user_id = result["id"]

    # Add an activity type
    result = db_handler._create_activity_type(user_id=user_id, type="Running", winter=1, spring=2, summer=3, fall=4)
    assert result is not None

    # Get the activity type id
    activity_type_id = db_handler._get_activity_type_id(user_id=user_id, type="Running")
    assert activity_type_id is not None

    # Get the activity types
    result = db_handler._get_user_activity_types(user_id=user_id)
    assert result is not None
    assert result[0][0] == activity_type_id
    assert result[0][1] == "Running"
    assert result[0][2] == 1
    assert result[0][3] == 2
    assert result[0][4] == 3
    assert result[0][5] == 4

    # Add a duplicate activity type
    result = db_handler._create_activity_type(user_id=user_id, type="Running", winter=1, spring=1, summer=1, fall=1)
    assert result is None

    # Add a second activity type
    result = db_handler._create_activity_type(user_id=user_id, type="Swimming", winter=1, spring=2, summer=3, fall=4)
    assert result is not None

    # Get the activity types
    result = db_handler._get_user_activity_types(user_id=user_id)
    assert len(result) == 2

    # Remove the second activity type
    db_handler._remove_activity_type(user_id=user_id, type="Swimming")

    # Get the activity types
    result = db_handler._get_user_activity_types(user_id=user_id)
    assert len(result) == 1

    # Remove the dummy user
    db_handler._remove_user(user_id)
    assert db_handler._get_user_count() == user_count_1

    # Ensure all user activity types are removed    
    result = db_handler._get_user_activity_types(user_id=user_id)
    assert result == []

def test_activities_table(db_handler):
    
    # Add a dummy user
    user_count_1 = db_handler._get_user_count()
    result = db_handler._create_user(email=dummy_user_email, name="Test", timezone="America/Denver")
    assert result["success"] == True
    user_id = result["id"]

    # Add an activity type
    result = db_handler._create_activity_type(user_id=user_id, type="Running", winter=1, spring=2, summer=3, fall=4)
    assert result is not None
    activity_type_id = result

    # Add an activity and duplicate
    db_handler._add_activity(user_id=user_id, type_id=activity_type_id, time="2025-01-01 12:00:00")
    db_handler._add_activity(user_id=user_id, type_id=activity_type_id, time="2025-01-01 12:00:00")

    # Get the activities
    result = db_handler._get_activities(user_id=user_id)
    assert len(result) == 1
    assert result[0][1] == user_id
    assert result[0][2] == activity_type_id
    assert result[0][3] == datetime.datetime.strptime("2025-01-01 12:00:00", "%Y-%m-%d %H:%M:%S")
    
    # Remove the activity
    db_handler._remove_activity(user_id=user_id, type_id=activity_type_id, time="2025-01-01 12:00:00")
    result = db_handler._get_activities(user_id=user_id)
    assert len(result) == 0

    # Add a second activity 
    db_handler._add_activity(user_id=user_id, type_id=activity_type_id, time="2025-01-01 12:00:00")

    # Remove the dummy user
    db_handler._remove_user(user_id)
    assert db_handler._get_user_count() == user_count_1

    # Ensure all user activities are removed
    result = db_handler._get_activities(user_id=user_id)
    assert result == []

def test_user_calculations_table(db_handler):
    
    # Add a dummy user
    user_count_1 = db_handler._get_user_count()
    result = db_handler._create_user(email=dummy_user_email, name="Test", timezone="America/Denver")
    assert result["success"] == True
    user_id = result["id"]

    # Add an activity type
    result = db_handler._create_activity_type(user_id=user_id, type="Running", winter=1, spring=2, summer=3, fall=4)
    assert result is not None
    activity_type_id = result

    # Add a user calculation
    db_handler._add_user_calculation(user_id=user_id, type_id=activity_type_id, total=100, thirty=10, season=10, valid=True)
    
    # Add a duplicate user calculation
    db_handler._add_user_calculation(user_id=user_id, type_id=activity_type_id, total=100, thirty=10, season=10, valid=True)
    
    # Get the user calculations
    result = db_handler._get_user_calculations(user_id=user_id)
    assert len(result) == 1
    assert result[0]["user_id"] == user_id
    assert result[0]["type_id"] == activity_type_id
    assert result[0]["total"] == 100
    assert result[0]["thirty"] == 10
    assert result[0]["season"] == 10
    assert result[0]["valid"] == True

    # Remove the dummy user
    db_handler._remove_user(user_id)
    assert db_handler._get_user_count() == user_count_1

    # Ensure all user calculations are removed
    result = db_handler._get_user_calculations(user_id=user_id)
    assert result == []
