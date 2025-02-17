import requests
import asyncio
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError


ALERTS_API_URL = "https://api.alerts.in.ua/v1/alerts/active.json"  # URL API
ALERTS_API_TOKEN = ""  # Токен доступа API
TELEGRAM_BOT_TOKEN = ""  # Токен Telegram бота
TELEGRAM_CHAT_ID = "@bezpekadnepr"  # ID или @username группы, куда отправлять сообщения
DNIPRO_REGION = "Дніпропетровська область"  # Регион для фильтрации


ALERT_TYPE_TRANSLATIONS = {
    "air_raid": "ВОЗДУШНАЯ ТРЕВОГА",
    "missile_strike": "РАКЕТНЫЙ УДАР",
    "artillery_shelling": "АРТИЛЛЕРИЙСКИЙ ОБСТРЕЛ",
}


bot = Bot(token=TELEGRAM_BOT_TOKEN)


def format_time(iso_time):
    try:
        dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))  # Преобразование ISO времени
        return dt.strftime("%d.%m.%Y %H:%M:%S")  # Формат: день.месяц.год часы:минуты:секунды
    except ValueError:
        return "Неизвестное время"


def get_active_alerts():
    params = {"token": ALERTS_API_TOKEN}  
    try:
        response = requests.get(ALERTS_API_URL, params=params) 
        if response.status_code == 200:
            return response.json().get("alerts", [])
        else:
            print(f"Ошибка API: {response.status_code}, {response.text}")
            return []
    except Exception as e:
        print(f"Произошла ошибка: {e}")
        return []


async def send_alert_message(region_name, alert_type, started_at):

    translated_alert_type = ALERT_TYPE_TRANSLATIONS.get(alert_type, "Неизвестный тип тревоги")


    if region_name == DNIPRO_REGION:
        region_name = "Дніпропетровщина"


    message = (
        f"‼️‼️‼️ ДНЕПР! ‼️‼️‼️\n"
        f"ВОЗДУШНАЯ ТРЕВОГА! ‼️‼️\n"
    )
    print(f"[INFO] Отправка сообщения о начале тревоги: {message}")
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except TelegramError as e:
        print(f"Ошибка при отправке сообщения в Telegram: {e}")

async def send_alert_end_message(region_name, alert_type, finished_at):

    translated_alert_type = ALERT_TYPE_TRANSLATIONS.get(alert_type, "Неизвестный тип тревоги")


    if region_name == DNIPRO_REGION:
        region_name = "Дніпропетровщина"


    message = (
        f"✅✅✅ ОТБОЙ ТРЕВОГИ ✅✅✅\n"
    )
    print(f"[INFO] Отправка сообщения о завершении тревоги: {message}")
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except TelegramError as e:
        print(f"Ошибка при отправке сообщения в Telegram: {e}")


async def main():
    active_alerts = {}
    while True:
        print("[INFO] Запрос активных тревог...")
        alerts = get_active_alerts()
        current_alerts = {alert.get("id"): alert for alert in alerts if alert.get("location_title") == DNIPRO_REGION}

        if not current_alerts:
            print("[INFO] Тревог нет.")
        else:
            print(f"[INFO] Обнаружено {len(current_alerts)} активных тревог.")


        for alert_id, alert in current_alerts.items():
            alert_type = alert.get("alert_type", "Неизвестный тип")
            if alert_id not in active_alerts:
                if alert_type == "artillery_shelling":
                    print(f"[INFO] Пропущена тревога: {alert_type} для региона {alert.get('location_title')}")
                    continue

                print(f"[INFO] Обнаружена новая тревога: ID={alert_id}, Регион={alert.get('location_title')}")
                await send_alert_message(
                    alert.get("location_title", "Неизвестный регион"),
                    alert_type,
                    alert.get("started_at", "Неизвестно")
                )
                active_alerts[alert_id] = alert

        for alert_id in list(active_alerts.keys()):
            if alert_id not in current_alerts:
                finished_alert = active_alerts.pop(alert_id)
                print(f"[INFO] Тревога завершена: ID={alert_id}, Регион={finished_alert.get('location_title')}")
                await send_alert_end_message(
                    finished_alert.get("location_title", "Неизвестный регион"),
                    finished_alert.get("alert_type", "Неизвестный тип"),
                    finished_alert.get("finished_at", "Неизвестно")
                )


        await asyncio.sleep(20)

if __name__ == "__main__":
    asyncio.run(main())
