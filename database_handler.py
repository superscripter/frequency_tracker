import os
import csv
import sqlite3

class DatabaseHandler:

    # Class attributes
    activities_db = ''
    user_db = ''
    user_calculations_db = ''
    user_frequencies_db = ''

    def __init__(self, activities_db = '', user_db = '', user_calculations_db = '', user_frequencies_db = ''):
        self.activities_db = activities_db
        self.user_db = user_db
        self.user_calculations_db = user_calculations_db
        self.user_frequencies_db = user_frequencies_db

    def activities_connection(self):
        return sqlite3.connect(self.activities_db)

    def user_connection(self):
        return sqlite3.connect(self.user_db)
    
    def user_calculations_connection(self):
        return sqlite3.connect(self.user_calculations_db)
    
    def user_frequencies_connection(self):
        return sqlite3.connect(self.user_frequencies_db)
    
    def initialize_activities_db(self):
        with self.activities_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    time TEXT NOT NULL,  -- e.g., '2025-02-24T20:16:13Z'
                    UNIQUE(time)
                )
            """)
            conn.commit()

    def initialize_user_db(self):
        with self.user_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timezone TEXT NOT NULL
                )
            """)
            conn.commit()

    def initialize_user_frequencies_db(self):
        with self.user_frequencies_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_frequencies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    winter INTEGER NOT NULL,
                    summer INTEGER NOT NULL,
                    spring INTEGER NOT NULL,
                    fall INTEGER NOT NULL
                )
            """)
            conn.commit()

    def initialize_user_calculations_db(self):
        with self.user_calculations_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_calculations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    total INTEGER NOT NULL,
                    thirty INTEGER NOT NULL,
                    season INTEGER NOT NULL
                )
            """)
            conn.commit()

    def initialize(self):
        self.initialize_activities_db()
        self.initialize_user_db()
        self.initialize_user_calculations_db()
        self.initialize_user_frequencies_db()