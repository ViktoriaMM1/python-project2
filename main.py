from flask import Flask, render_template, request, jsonify
import requests
import os
from dotenv import load_dotenv
from geopy.geocoders import Nominatim  # Для преобразования городов в координаты
from markupsafe import Markup

# Загрузка переменных окружения
load_dotenv()

app = Flask(__name__)

geolocator = Nominatim(user_agent="weather_app")

# Функция для оценки неблагоприятных погодных условий
def check_bad_weather(temperature, wind_speed, precipitation_probability):
    temp_threshold = (-5, 35)  # Температура ниже -5°C или выше 35°C
    wind_speed_threshold = 50  # Скорость ветра выше 50 км/ч
    precipitation_threshold = 70  # Вероятность осадков выше 70%

    if temperature < temp_threshold[0] or temperature > temp_threshold[1]:
        return True
    if wind_speed > wind_speed_threshold:
        return True
    if precipitation_probability > precipitation_threshold:
        return True

    return False

# Функция для получения ID города по координатам
def get_city_id(api_key, latitude, longitude):
    url = f"http://dataservice.accuweather.com/locations/v1/cities/geoposition/search?apikey={api_key}&q={latitude},{longitude}"
    response = requests.get(url)
    if response.status_code == 200:
        location_data = response.json()
        return location_data.get('Key', None)
    return None

# Функция для получения данных о погоде по ID города
def get_weather_by_city_id(api_key, city_id):
    weather_url = f"http://dataservice.accuweather.com/currentconditions/v1/{city_id}?apikey={api_key}"
    response = requests.get(weather_url)
    if response.status_code == 200:
        return response.json()[0]
    return None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/weather')
def weather():
    api_key = os.getenv("ACC_WEATHER_API_KEY")
    latitude = request.args.get('lat', default=55)  # По умолчанию - Москва
    longitude = request.args.get('lon', default=37)

    city_id = get_city_id(api_key, latitude, longitude)
    if city_id:
        weather_data = get_weather_by_city_id(api_key, city_id)
        if weather_data:
            temperature = weather_data.get('Temperature', {}).get('Metric', {}).get('Value', None)
            wind_speed = weather_data.get('Wind', {}).get('Speed', {}).get('Metric', {}).get('Value', None)
            precipitation_probability = weather_data.get('PrecipitationProbability', 0)

            bad_weather = check_bad_weather(temperature, wind_speed, precipitation_probability)

            return jsonify({
                "Температура (\u00b0C)": temperature,
                "Скорость ветра (км/ч)": wind_speed,
                "Вероятность осадков (%)": precipitation_probability,
                "Неблагоприятные условия": bad_weather
            })
        else:
            return jsonify({"error": "Ошибка при получении данных о погоде"}), 500
    else:
        return jsonify({"error": "Ошибка при получении данных о местоположении"}), 500

@app.route('/check_route_weather', methods=['POST'])
def check_route_weather():
    try:
        start_city = request.form['start']
        end_city = request.form['end']

        start_location = geolocator.geocode(start_city)
        end_location = geolocator.geocode(end_city)

        if not start_location or not end_location:
            return render_template('index.html', result="Не удалось найти координаты для одного из городов")

        start_coords = (start_location.latitude, start_location.longitude)
        end_coords = (end_location.latitude, end_location.longitude)

        # Прописываем логику для получения прогноза
        api_key = os.getenv("ACC_WEATHER_API_KEY")

        start_city_id = get_city_id(api_key, *start_coords)
        end_city_id = get_city_id(api_key, *end_coords)

        if not start_city_id or not end_city_id:
            return render_template('index.html', result="Не удалось получить данные")

        start_weather = get_weather_by_city_id(api_key, start_city_id)
        end_weather = get_weather_by_city_id(api_key, end_city_id)

        start_bad = check_bad_weather(
            start_weather.get('Temperature', {}).get('Metric', {}).get('Value', None),
            start_weather.get('Wind', {}).get('Speed', {}).get('Metric', {}).get('Value', None),
            start_weather.get('PrecipitationProbability', 0)
        )

        end_bad = check_bad_weather(
            end_weather.get('Temperature', {}).get('Metric', {}).get('Value', None),
            end_weather.get('Wind', {}).get('Speed', {}).get('Metric', {}).get('Value', None),
            end_weather.get('PrecipitationProbability', 0)
        )

        # оформляем результат красиво
        result = Markup(f"""
        Начальная точка:<br>
        Температура: {start_weather.get('Temperature', {}).get('Metric', {}).get('Value', 'Нет данных')} °C<br>
        Скорость ветра: {start_weather.get('Wind', {}).get('Speed', {}).get('Metric', {}).get('Value', 'Нет данных')} км/ч<br>
        Вероятность осадков: {start_weather.get('PrecipitationProbability', 0)}%<br>
        Неблагоприятные условия: {'Да' if start_bad else 'Нет'}<br><br>

        Конечная точка:<br>
        Температура: {end_weather.get('Temperature', {}).get('Metric', {}).get('Value', 'Нет данных')} °C<br>
        Скорость ветра: {end_weather.get('Wind', {}).get('Speed', {}).get('Metric', {}).get('Value', 'Нет данных')} км/ч<br>
        Вероятность осадков: {end_weather.get('PrecipitationProbability', 0)}%<br>
        Неблагоприятные условия: {'Да' if end_bad else 'Нет'}<br>
        """)

        return render_template('index.html', result=result)

    except Exception as e:
        return render_template('index.html', result=f"Произошла ошибка: {e}")

@app.route('/route_weather', methods=['POST'])
def route_weather():
    data = request.get_json()
    route = data.get('route', [])
    api_key = os.getenv("ACC_WEATHER_API_KEY")

    results = []
    for point in route:
        latitude, longitude = point
        city_id = get_city_id(api_key, latitude, longitude)
        if city_id:
            weather_data = get_weather_by_city_id(api_key, city_id)
            if weather_data:
                temperature = weather_data.get('Temperature', {}).get('Metric', {}).get('Value', None)
                wind_speed = weather_data.get('Wind', {}).get('Speed', {}).get('Metric', {}).get('Value', None)
                precipitation_probability = weather_data.get('PrecipitationProbability', 0)

                bad_weather = check_bad_weather(temperature, wind_speed, precipitation_probability)

                results.append({
                    "location": point,
                    "weather": {
                        "temperature": temperature,
                        "wind_speed": wind_speed,
                        "precipitation_probability": precipitation_probability,
                    },
                    "bad_weather": bad_weather
                })

    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True)
