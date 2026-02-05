FROM python:3.10-slim

WORKDIR /app

COPY water_calorie_bot/requirements.txt ./water_calorie_bot/
RUN pip install --no-cache-dir -r water_calorie_bot/requirements.txt

COPY water_calorie_bot/ ./water_calorie_bot/

RUN touch /app/water_calorie_bot/.env

WORKDIR /app/water_calorie_bot

CMD ["python", "bot.py"]