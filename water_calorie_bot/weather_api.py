import requests
import os
from dotenv import load_dotenv

load_dotenv()

class WeatherAPI:
    def __init__(self):
        self.api_key = os.getenv('OPENWEATHER_API_KEY')
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"
    
    def get_temperature(self, city):
        """Получает текущую температуру в городе в градусах Цельсия"""
        if not self.api_key:
            return None
        
        params = {
            'q': city,
            'appid': self.api_key,
            'units': 'metric'
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            return data['main']['temp']
        except requests.RequestException as e:
            print(f"Ошибка получения погоды: {e}")
            return None