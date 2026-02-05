import sqlite3
from datetime import date, datetime
import json

class Database:
    def __init__(self, db_name="bot_data.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()
    
    def _create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                weight REAL,
                height REAL,
                age INTEGER,
                gender TEXT DEFAULT 'male',
                activity_minutes INTEGER DEFAULT 0,
                city TEXT,
                calorie_goal REAL,
                water_goal REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS water_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount_ml INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS food_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_name TEXT,
                calories REAL,
                weight_grams REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS workout_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                workout_type TEXT,
                duration_minutes INTEGER,
                calories_burned REAL,
                water_needed_ml INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        
        self.conn.commit()
    
    def save_user_profile(self, user_id, username, weight, height, age, gender, activity_minutes, city, calorie_goal, water_goal):
        self.cursor.execute('''
            INSERT OR REPLACE INTO users 
            (user_id, username, weight, height, age, gender, activity_minutes, city, calorie_goal, water_goal)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, weight, height, age, gender, activity_minutes, city, calorie_goal, water_goal))
        self.conn.commit()
    
    def get_user_profile(self, user_id):
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = self.cursor.fetchone()
        if row:
            return {
                'user_id': row[0],
                'username': row[1],
                'weight': row[2],
                'height': row[3],
                'age': row[4],
                'gender': row[5],
                'activity_minutes': row[6],
                'city': row[7],
                'calorie_goal': row[8],
                'water_goal': row[9]
            }
        return None
    
    def log_water(self, user_id, amount_ml):
        self.cursor.execute('INSERT INTO water_logs (user_id, amount_ml) VALUES (?, ?)', (user_id, amount_ml))
        self.conn.commit()
    
    def get_water_consumed_today(self, user_id):
        self.cursor.execute('''
            SELECT SUM(amount_ml) FROM water_logs 
            WHERE user_id = ? AND date(timestamp) = date('now')
        ''', (user_id,))
        result = self.cursor.fetchone()[0]
        return result if result else 0
    
    def log_food(self, user_id, product_name, calories, weight_grams):
        self.cursor.execute('''
            INSERT INTO food_logs (user_id, product_name, calories, weight_grams)
            VALUES (?, ?, ?, ?)
        ''', (user_id, product_name, calories, weight_grams))
        self.conn.commit()
    
    def get_calories_consumed_today(self, user_id):
        self.cursor.execute('''
            SELECT SUM(calories) FROM food_logs 
            WHERE user_id = ? AND date(timestamp) = date('now')
        ''', (user_id,))
        result = self.cursor.fetchone()[0]
        return result if result else 0
    
    def log_workout(self, user_id, workout_type, duration_minutes, calories_burned, water_needed_ml):
        self.cursor.execute('''
            INSERT INTO workout_logs (user_id, workout_type, duration_minutes, calories_burned, water_needed_ml)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, workout_type, duration_minutes, calories_burned, water_needed_ml))
        self.conn.commit()
    
    def get_calories_burned_today(self, user_id):
        self.cursor.execute('''
            SELECT SUM(calories_burned) FROM workout_logs 
            WHERE user_id = ? AND date(timestamp) = date('now')
        ''', (user_id,))
        result = self.cursor.fetchone()[0]
        return result if result else 0
    
    def get_water_needed_from_workouts_today(self, user_id):
        self.cursor.execute('''
            SELECT SUM(water_needed_ml) FROM workout_logs 
            WHERE user_id = ? AND date(timestamp) = date('now')
        ''', (user_id,))
        result = self.cursor.fetchone()[0]
        return result if result else 0
    
    def close(self):
        self.conn.close()