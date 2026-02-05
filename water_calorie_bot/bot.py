import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes,
    ConversationHandler, filters, CallbackQueryHandler
)
from database import Database
from weather_api import WeatherAPI
from nutrition_api import NutritionAPI
from calculator import Calculator

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

(
    WEIGHT, HEIGHT, AGE, GENDER, ACTIVITY, CITY, 
    FOOD_NAME, FOOD_WEIGHT, 
    WORKOUT_TYPE, WORKOUT_DURATION,
    SET_CALORIE_GOAL
) = range(11)

db = Database()
weather_api = WeatherAPI()
nutrition_api = NutritionAPI()
calculator = Calculator()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "Я помогу тебе отслеживать норму воды, калории и активность.\n\n"
        "🔹 /set_profile - Настроить профиль\n"
        "🔹 /log_water - Записать выпитую воду\n"
        "🔹 /log_food - Записать приём пищи\n"
        "🔹 /log_workout - Записать тренировку\n"
        "🔹 /check_progress - Проверить прогресс\n"
        "🔹 /reset_profile - Сбросить профиль"
    )

async def set_profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало настройки профиля"""
    user = update.effective_user
    context.user_data['profile'] = {'user_id': user.id, 'username': user.username or user.first_name}
    
    await update.message.reply_text("👤 Введите ваш вес (в кг):")
    return WEIGHT

async def set_profile_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text.replace(',', '.'))
        if weight < 30 or weight > 300:
            await update.message.reply_text("❌ Вес должен быть от 30 до 300 кг. Попробуйте ещё раз:")
            return WEIGHT
        
        context.user_data['profile']['weight'] = weight
        await update.message.reply_text("📏 Введите ваш рост (в см):")
        return HEIGHT
    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return WEIGHT

async def set_profile_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        height = float(update.message.text.replace(',', '.'))
        if height < 100 or height > 250:
            await update.message.reply_text("❌ Рост должен быть от 100 до 250 см. Попробуйте ещё раз:")
            return HEIGHT
        
        context.user_data['profile']['height'] = height
        await update.message.reply_text("🎂 Введите ваш возраст:")
        return AGE
    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return HEIGHT

async def set_profile_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text)
        if age < 14 or age > 100:
            await update.message.reply_text("❌ Возраст должен быть от 14 до 100 лет. Попробуйте ещё раз:")
            return AGE
        
        context.user_data['profile']['age'] = age
        keyboard = [
            [
                InlineKeyboardButton("Мужской", callback_data='gender_male'),
                InlineKeyboardButton("Женский", callback_data='gender_female')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("⚧ Выберите пол:", reply_markup=reply_markup)
        return GENDER
    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return AGE

async def set_profile_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    gender = 'male' if 'male' in query.data else 'female'
    context.user_data['profile']['gender'] = gender
    
    await query.edit_message_text("⏱ Сколько минут активности у вас в день (в среднем)?")
    return ACTIVITY

async def set_profile_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        activity = int(update.message.text)
        if activity < 0 or activity > 480:
            await update.message.reply_text("❌ Активность должна быть от 0 до 480 минут. Попробуйте ещё раз:")
            return ACTIVITY
        
        context.user_data['profile']['activity_minutes'] = activity
        await update.message.reply_text("🏙 В каком городе вы находитесь? (для учёта погоды)")
        return CITY
    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return ACTIVITY

async def set_profile_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text.strip()
    context.user_data['profile']['city'] = city
    
    temperature = weather_api.get_temperature(city)
    context.user_data['profile']['temperature'] = temperature
    
    profile = context.user_data['profile']
    bmr = calculator.calculate_bmr(
        profile['weight'], 
        profile['height'], 
        profile['age'], 
        profile['gender']
    )
    calorie_goal = calculator.calculate_calorie_goal(bmr, profile['activity_minutes'])
    water_goal = calculator.calculate_water_goal(
        profile['weight'], 
        profile['activity_minutes'], 
        temperature
    )
    
    context.user_data['profile']['calorie_goal'] = calorie_goal
    context.user_data['profile']['water_goal'] = water_goal
    
    db.save_user_profile(
        profile['user_id'],
        profile['username'],
        profile['weight'],
        profile['height'],
        profile['age'],
        profile['gender'],
        profile['activity_minutes'],
        profile['city'],
        calorie_goal,
        water_goal
    )
    
    temp_info = f"\n🌡 Текущая температура в {city}: {temperature}°C" if temperature else ""
    
    await update.message.reply_text(
        f"✅ Профиль настроен!\n\n"
        f"📊 Ваши дневные нормы:\n"
        f"💧 Вода: {water_goal} мл{temp_info}\n"
        f"🔥 Калории: {calorie_goal} ккал\n\n"
        f"Теперь вы можете использовать команды:\n"
        f"/log_water - записать воду\n"
        f"/log_food - записать еду\n"
        f"/log_workout - записать тренировку\n"
        f"/check_progress - проверить прогресс"
    )
    
    return ConversationHandler.END

async def log_water(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Логирование воды: /log_water 500"""
    user_id = update.effective_user.id
    profile = db.get_user_profile(user_id)
    
    if not profile:
        await update.message.reply_text("❌ Сначала настройте профиль командой /set_profile")
        return
    
    if not context.args:
        await update.message.reply_text(
            "💧 Укажите количество воды в мл:\n"
            "Пример: /log_water 300"
        )
        return
    
    try:
        amount = int(context.args[0])
        if amount <= 0 or amount > 2000:
            await update.message.reply_text("❌ Укажите количество от 1 до 2000 мл")
            return
        
        db.log_water(user_id, amount)
        
        profile = db.get_user_profile(user_id)
        consumed = db.get_water_consumed_today(user_id)
        goal = int(profile['water_goal'])
        remaining = max(0, goal - consumed)
        percent = min(100, round(consumed / goal * 100))
        
        bars = '💧' * (percent // 20) + '🥛' * (5 - percent // 20)
        
        await update.message.reply_text(
            f"✅ Записано {amount} мл воды\n\n"
            f"📊 Прогресс по воде:\n"
            f"{bars}\n"
            f"{consumed} мл из {goal} мл ({percent}%)\n"
            f"Осталось: {remaining} мл"
        )
    except ValueError:
        await update.message.reply_text("❌ Введите корректное число")

async def log_food_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало логирования еды"""
    user_id = update.effective_user.id
    profile = db.get_user_profile(user_id)
    
    if not profile:
        await update.message.reply_text("❌ Сначала настройте профиль командой /set_profile")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "🍎 Введите название продукта (например: банан, куриная грудка, гречка):"
    )
    return FOOD_NAME

async def log_food_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поиск продукта в API"""
    product_name = update.message.text.strip()
    context.user_data['food_search'] = product_name
    
    await update.message.reply_text("🔍 Ищу продукт...")
    
    product = nutrition_api.search_product(product_name)
    
    if not product:
        await update.message.reply_text(
            f"❌ Не удалось найти '{product_name}'. Попробуйте другое название или укажите калорийность вручную:\n"
            "Пример: яблоко 52 (калорий на 100г)"
        )
        return FOOD_NAME
    
    context.user_data['food_product'] = product
    
    await update.message.reply_text(
        f"✅ Найден продукт: {product['name']}\n"
        f"🔥 Калорийность: {product['calories_per_100g']} ккал на 100г\n\n"
        f"⚖️ Сколько грамм вы съели?"
    )
    return FOOD_WEIGHT

async def log_food_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запись веса продукта и расчёт калорий"""
    try:
        weight = float(update.message.text.replace(',', '.'))
        if weight <= 0 or weight > 5000:
            await update.message.reply_text("❌ Вес должен быть от 1 до 5000 г. Попробуйте ещё раз:")
            return FOOD_WEIGHT
        
        product = context.user_data.get('food_product')
        if not product:
            await update.message.reply_text("❌ Ошибка: продукт не найден. Начните заново командой /log_food")
            return ConversationHandler.END
        
        calories = round(product['calories_per_100g'] * weight / 100, 1)
        
        user_id = update.effective_user.id
        db.log_food(user_id, product['name'], calories, weight)
        
        profile = db.get_user_profile(user_id)
        consumed = db.get_calories_consumed_today(user_id)
        burned = db.get_calories_burned_today(user_id)
        balance = consumed - burned
        remaining = max(0, profile['calorie_goal'] - balance)
        percent = min(100, round(balance / profile['calorie_goal'] * 100))
        
        await update.message.reply_text(
            f"✅ Записано: {product['name']} ({weight}г) — {calories} ккал\n\n"
            f"📊 Сегодня:\n"
            f"🍽 Потреблено: {consumed} ккал\n"
            f"🔥 Сожжено: {burned} ккал\n"
            f"⚖️ Баланс: {balance} ккал ({percent}% от нормы)\n"
            f"Осталось: {remaining} ккал"
        )
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return FOOD_WEIGHT

async def log_workout_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало логирования тренировки"""
    user_id = update.effective_user.id
    profile = db.get_user_profile(user_id)
    
    if not profile:
        await update.message.reply_text("❌ Сначала настройте профиль командой /set_profile")
        return ConversationHandler.END
    
    keyboard = [
        [
            InlineKeyboardButton("Бег", callback_data='workout_бег'),
            InlineKeyboardButton("Ходьба", callback_data='workout_ходьба'),
            InlineKeyboardButton("Велосипед", callback_data='workout_велосипед')
        ],
        [
            InlineKeyboardButton("Плавание", callback_data='workout_плавание'),
            InlineKeyboardButton("Йога", callback_data='workout_йога'),
            InlineKeyboardButton("Силовая", callback_data='workout_силовая')
        ],
        [
            InlineKeyboardButton("Кардио", callback_data='workout_кардио'),
            InlineKeyboardButton("Танцы", callback_data='workout_танцы')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("🏃 Выберите тип тренировки:", reply_markup=reply_markup)
    return WORKOUT_TYPE

async def log_workout_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    workout_type = query.data.replace('workout_', '')
    context.user_data['workout_type'] = workout_type
    
    await query.edit_message_text(f"⏱ Сколько минут длилась тренировка '{workout_type}'?")
    return WORKOUT_DURATION

async def log_workout_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        duration = int(update.message.text)
        if duration <= 0 or duration > 300:
            await update.message.reply_text("❌ Длительность должна быть от 1 до 300 минут. Попробуйте ещё раз:")
            return WORKOUT_DURATION
        
        workout_type = context.user_data.get('workout_type', 'тренировка')
        user_id = update.effective_user.id
        profile = db.get_user_profile(user_id)
        
        if not profile:
            await update.message.reply_text("❌ Ошибка профиля. Настройте профиль заново.")
            return ConversationHandler.END
        
        calories_burned = calculator.estimate_calories_burned(
            workout_type, duration, profile['weight']
        )
        water_needed = calculator.estimate_water_needed_for_workout(duration)
        
        db.log_workout(user_id, workout_type, duration, calories_burned, water_needed)
        
        profile = db.get_user_profile(user_id)
        burned_today = db.get_calories_burned_today(user_id)
        water_from_workouts = db.get_water_needed_from_workouts_today(user_id)
        
        await update.message.reply_text(
            f"✅ Записана тренировка: {workout_type} ({duration} мин)\n"
            f"🔥 Сожжено: {calories_burned} ккал\n"
            f"💧 Рекомендуется доп. воды: {water_needed} мл\n\n"
            f"📊 Сегодня сожжено всего: {burned_today} ккал\n"
            f"💧 Доп. воды от тренировок: {water_from_workouts} мл"
        )
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return WORKOUT_DURATION

async def check_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка прогресса по воде и калориям"""
    user_id = update.effective_user.id
    profile = db.get_user_profile(user_id)
    
    if not profile:
        await update.message.reply_text("❌ Сначала настройте профиль командой /set_profile")
        return
    
    profile = db.get_user_profile(user_id)
    
    water_consumed = db.get_water_consumed_today(user_id)
    water_from_workouts = db.get_water_needed_from_workouts_today(user_id)
    calories_consumed = db.get_calories_consumed_today(user_id)
    calories_burned = db.get_calories_burned_today(user_id)
    
    water_goal = int(profile['water_goal'])
    water_remaining = max(0, water_goal - water_consumed)
    water_percent = min(100, round(water_consumed / water_goal * 100))
    water_bars = '💧' * (water_percent // 20) + '🥛' * (5 - water_percent // 20)
    
    calorie_goal = profile['calorie_goal']
    calorie_balance = calories_consumed - calories_burned
    calorie_remaining = max(0, calorie_goal - calorie_balance)
    calorie_percent = min(100, round(calorie_balance / calorie_goal * 100))
    calorie_bars = '🔥' * (calorie_percent // 20) + '❄️' * (5 - calorie_percent // 20)
    
    water_status = "✅ Выполнено!" if water_consumed >= water_goal else f"Осталось: {water_remaining} мл"
    calorie_status = "✅ В норме" if calorie_balance <= calorie_goal else "⚠️ Превышение нормы!"
    
    message = (
        f"📊 Прогресс за сегодня ({datetime.now().strftime('%d.%m.%Y')}):\n\n"
        f"💧 ВОДА:\n{water_bars}\n"
        f"{water_consumed} мл из {water_goal} мл ({water_percent}%)\n"
        f"{water_status}\n"
        f"💦 От тренировок: +{water_from_workouts} мл рекомендовано\n\n"
        f"🔥 КАЛОРИИ:\n{calorie_bars}\n"
        f"🍽 Потреблено: {calories_consumed} ккал\n"
        f"🏃 Сожжено: {calories_burned} ккал\n"
        f"⚖️ Баланс: {calorie_balance} ккал ({calorie_percent}%)\n"
        f"{calorie_status}\n"
        f"Осталось: {calorie_remaining} ккал"
    )
    
    await update.message.reply_text(message)

async def reset_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сброс профиля"""
    user_id = update.effective_user.id
    
    await update.message.reply_text(
        "🔄 Профиль сброшен. Настройте его заново командой /set_profile"
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущей операции"""
    await update.message.reply_text("❌ Операция отменена.")
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    await update.message.reply_text(
        "ℹ️ Доступные команды:\n\n"
        "/start - Начать работу с ботом\n"
        "/set_profile - Настроить профиль (вес, рост, возраст и т.д.)\n"
        "/log_water <мл> - Записать выпитую воду\n"
        "/log_food - Записать приём пищи (диалог)\n"
        "/log_workout - Записать тренировку (диалог)\n"
        "/check_progress - Проверить дневной прогресс\n"
        "/reset_profile - Сбросить настройки профиля\n"
        "/help - Показать эту справку\n\n"
        "💡 Советы:\n"
        "• Норма воды рассчитывается с учётом веса, активности и погоды\n"
        "• Калории рассчитываются по формуле Миффлина-Сан Жеора\n"
        "• Для точности указывайте реальные данные в профиле"
    )

def main():
    """Запуск бота"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения")
    
    application = Application.builder().token(token).build()
    
    profile_conv = ConversationHandler(
        entry_points=[CommandHandler('set_profile', set_profile_start)],
        states={
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_profile_weight)],
            HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_profile_height)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_profile_age)],
            GENDER: [CallbackQueryHandler(set_profile_gender, pattern='^gender_')],
            ACTIVITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_profile_activity)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_profile_city)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    food_conv = ConversationHandler(
        entry_points=[CommandHandler('log_food', log_food_start)],
        states={
            FOOD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, log_food_name)],
            FOOD_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, log_food_weight)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    workout_conv = ConversationHandler(
        entry_points=[CommandHandler('log_workout', log_workout_start)],
        states={
            WORKOUT_TYPE: [CallbackQueryHandler(log_workout_type, pattern='^workout_')],
            WORKOUT_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, log_workout_duration)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('log_water', log_water))
    application.add_handler(CommandHandler('check_progress', check_progress))
    application.add_handler(CommandHandler('reset_profile', reset_profile))
    
    application.add_handler(profile_conv)
    application.add_handler(food_conv)
    application.add_handler(workout_conv)
    
    application.add_handler(CommandHandler('cancel', cancel))
    
    logger.info("Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()