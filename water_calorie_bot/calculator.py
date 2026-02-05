class Calculator:
    @staticmethod
    def calculate_bmr(weight, height, age, gender='male'):
        """
        Расчёт базового метаболизма по формуле Миффлина-Сан Жеора
        """
        if gender.lower() == 'male':
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age - 161
        return bmr
    
    @staticmethod
    def calculate_calorie_goal(bmr, activity_minutes=0):
        """
        Расчёт дневной нормы калорий с учётом активности
        """
        if activity_minutes < 30:
            activity_factor = 1.2
        elif activity_minutes < 60:
            activity_factor = 1.375
        elif activity_minutes < 90:
            activity_factor = 1.55
        else:
            activity_factor = 1.725
        
        extra_calories = min(activity_minutes * 5, 400)
        
        return round(bmr * activity_factor + extra_calories)
    
    @staticmethod
    def calculate_water_goal(weight, activity_minutes=0, temperature=None):
        """
        Расчёт дневной нормы воды:
        - База: 35 мл на кг веса
        - +250 мл за каждые 30 минут активности
        - +300-800 мл при температуре > 25°C
        """
        base_water = weight * 35
        
        activity_water = (activity_minutes // 30) * 250
        
        weather_water = 0
        if temperature and temperature > 25:
            weather_water = min(300 + (temperature - 25) * 20, 800)
        
        total = base_water + activity_water + weather_water
        return round(min(max(total, 1500), 5000))
    
    @staticmethod
    def estimate_calories_burned(workout_type, duration_minutes, weight):
        """
        Оценка сожжённых калорий за тренировку
        """
        calories_per_minute = {
            'бег': 12,
            'ходьба': 5,
            'велосипед': 8,
            'плавание': 10,
            'йога': 4,
            'силовая': 8,
            'кардио': 10,
            'танцы': 7
        }
        
        base_cals = calories_per_minute.get(workout_type.lower(), 6)
        adjusted = base_cals * (weight / 70)
        
        return round(adjusted * duration_minutes)
    
    @staticmethod
    def estimate_water_needed_for_workout(duration_minutes):
        """
        Расчёт дополнительной потребности в воде во время тренировки
        """
        return (duration_minutes // 30) * 200 + 100