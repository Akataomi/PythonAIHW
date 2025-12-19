import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import requests
import time
import asyncio
import aiohttp


def calculate_rolling_stats(df, window=30):
    """Вычисляет скользящее среднее и std."""
    df = df.sort_values('timestamp').copy()
    df['temp_rolling_mean'] = df['temperature'].rolling(window=window, center=True).mean()
    df['temp_rolling_std'] = df['temperature'].rolling(window=window, center=True).std()
    return df

def identify_anomalies(df, threshold=2):
    """Определяет аномалии как значения за пределами mean ± threshold * std."""
    lower_bound = df['temp_rolling_mean'] - threshold * df['temp_rolling_std']
    upper_bound = df['temp_rolling_mean'] + threshold * df['temp_rolling_std']
    df['anomaly'] = (df['temperature'] < lower_bound) | (df['temperature'] > upper_bound)
    return df

def analyze_city_data(city_df):
    """Проводит полный анализ для одного города."""
    city_df = calculate_rolling_stats(city_df)
    city_df = identify_anomalies(city_df)
    seasonal_stats = city_df.groupby('season')['temperature'].agg(['mean', 'std']).reset_index()
    seasonal_stats.columns = ['season', 'mean_temp', 'std_temp']
    return city_df, seasonal_stats


def get_current_weather_sync(api_key, city_name):
    """Синхронный запрос к API OpenWeatherMap."""
    url = f"http://api.openweathermap.org/data/2.5/weather"
    params = {
        'q': city_name,
        'appid': api_key,
        'units': 'metric'
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if response.status_code == 401:
             st.error(f"Ошибка API: {response.json().get('message', 'Unauthorized')}")
        else:
            st.error(f"HTTP ошибка: {e}")
    except requests.exceptions.RequestException as e:
        st.error(f"Ошибка запроса: {e}")
    return None

async def get_current_weather_async(session, api_key, city_name):
    """Асинхронный запрос к API OpenWeatherMap."""
    url = f"http://api.openweathermap.org/data/2.5/weather"
    params = {
        'q': city_name,
        'appid': api_key,
        'units': 'metric'
    }
    try:
        async with session.get(url, params=params) as response:
            if response.status == 401:
                json_resp = await response.json()
                st.error(f"Ошибка API: {json_resp.get('message', 'Unauthorized')}")
                return None
            response.raise_for_status()
            return await response.json()
    except aiohttp.ClientResponseError as e:
        st.error(f"HTTP ошибка в асинхронном запросе: {e}")
    except Exception as e:
        st.error(f"Ошибка асинхронного запроса: {e}")
    return None


st.title('Анализ температурных данных и мониторинг')

uploaded_file = st.file_uploader("Загрузите файл CSV с историческими данными (temperature_data.csv)", type="csv")

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    st.header("Анализ исторических данных")
    selected_city = st.selectbox('Выберите город для анализа', df['city'].unique())

    city_data = df[df['city'] == selected_city].copy()
    analyzed_city_data, seasonal_stats = analyze_city_data(city_data)

    st.subheader(f"Статистика по сезонам для {selected_city}")
    st.dataframe(seasonal_stats)

    st.subheader(f"Временной ряд температур для {selected_city} с аномалиями")
    fig_time_series = go.Figure()
    fig_time_series.add_trace(go.Scatter(x=analyzed_city_data['timestamp'], y=analyzed_city['temperature'],
                                         mode='lines', name='Температура'))
    fig_time_series.add_trace(go.Scatter(x=analyzed_city_data['timestamp'], y=analyzed_city['temp_rolling_mean'],
                                         mode='lines', name='Скользящее среднее (30 дней)', line=dict(color='orange')))
    anomalies = analyzed_city_data[analyzed_city_data['anomaly']]
    fig_time_series.add_trace(go.Scatter(x=anomalies['timestamp'], y=anomalies['temperature'],
                                         mode='markers', name='Аномалия', marker=dict(color='red', size=8)))
    fig_time_series.update_layout(xaxis_title='Дата', yaxis_title='Температура (°C)')
    st.plotly_chart(fig_time_series)

    st.subheader(f"Сезонные профили для {selected_city}")
    fig_seasonal = px.box(city_data, x='season', y='temperature',
                          title=f'Распределение температур по сезонам в {selected_city}',
                          labels={'temperature': 'Температура (°C)', 'season': 'Сезон'})
    st.plotly_chart(fig_seasonal)


    st.header("Мониторинг текущей температуры")
    api_key = st.text_input("Введите ваш API-ключ OpenWeatherMap", type="password")

    if api_key:
        st.subheader(f"Текущая погода в {selected_city}")

        st.subheader("Синхронный запрос")
        start_time_sync = time.time()
        current_weather_sync = get_current_weather_sync(api_key, selected_city)
        elapsed_sync = time.time() - start_time_sync
        if current_weather_sync and 'main' in current_weather_sync:
            current_temp_sync = current_weather_sync['main']['temp']
            st.metric(label="Текущая температура (синхронно)", value=f"{current_temp_sync:.2f} °C", delta=None)
            st.write(f"*Время запроса (синхронно): {elapsed_sync:.2f} сек*")

            current_month = datetime.now().month
            if current_month in [12, 1, 2]: current_season = 'winter'
            elif current_month in [3, 4, 5]: current_season = 'spring'
            elif current_month in [6, 7, 8]: current_season = 'summer'
            else: current_season = 'autumn'

            season_row = seasonal_stats[seasonal_stats['season'] == current_season]
            if not season_row.empty:
                mean_temp = season_row.iloc[0]['mean_temp']
                std_temp = season_row.iloc[0]['std_temp']
                lower_limit = mean_temp - 2 * std_temp
                upper_limit = mean_temp + 2 * std_temp

                is_anomaly = current_temp_sync < lower_limit or current_temp_sync > upper_limit
                status = "Аномальная!" if is_anomaly else "В рамках нормы."
                color = "red" if is_anomaly else "green"
                st.markdown(f"<span style='color:{color}; font-size:1.2em; font-weight:bold;'>{status}</span>", unsafe_allow_html=True)
                st.caption(f"Нормальный диапазон ({current_season}): {lower_limit:.2f} °C — {upper_limit:.2f} °C")
            else:
                st.warning("Не удалось определить сезон для текущей даты.")
        else:
            st.warning("Не удалось получить данные синхронного запроса. Проверьте API-ключ и название города.")


        st.subheader("Асинхронный запрос")
        async def fetch_async_weather():
            start_time_async = time.time()
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                current_weather_async_res = await get_current_weather_async(session, api_key, selected_city)
            elapsed_async = time.time() - start_time_async
            if current_weather_async_res and 'main' in current_weather_async_res:
                current_temp_async = current_weather_async_res['main']['temp']
                st.metric(label="Текущая температура (асинхронно)", value=f"{current_temp_async:.2f} °C", delta=None)
                st.write(f"*Время запроса (асинхронно): {elapsed_async:.2f} сек*")
            else:
                st.warning("Не удалось получить данные асинхронного запроса.")

        asyncio.run(fetch_async_weather())

        st.info(
            "**Комментарии по асинхронности:**\n\n"
            "- В этом одиночном запросе разница между синхронным и асинхронным подходом минимальна, "
            "так как нет параллельных вызовов. Время выполнения зависит в основном от скорости отклика API.\n"
            "- Асинхронные запросы особенно полезны, когда нужно выполнить *много* независимых запросов "
            "одновременно (например, получить погоду для 10 разных городов). "
            "В таком случае асинхронный код может быть значительно быстрее синхронного, "
            "который ждал бы каждый запрос по очереди."
        )

else:
    st.info("Пожалуйста, загрузите файл `temperature_data.csv` для начала анализа.")