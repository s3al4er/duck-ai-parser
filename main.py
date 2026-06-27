import json
import random
import time
from DrissionPage import ChromiumPage, ChromiumOptions
import requests

# список моделей: "claude-haiku-4-5", "gpt-5.4-mini", "gpt-5.4-nano", "tinfoil/gpt-oss-120b", "mistral-small-2603"

MODEL = "claude-haiku-4-5"
DEBUG = True

co = ChromiumOptions()
co.headless(False) # это не включать ибо тогда duck.ai запалит парсер
co.incognito(True)
co.set_argument("--no-sandbox")

random_port = random.randint(9000, 9999)
co.set_local_port(random_port)
co.set_user_data_path(f"/tmp/drission_user_data_{random_port}")

page = ChromiumPage(co)
captured_headers = None

prompt = input("Промпт: ")

try:
    print(
        f"[Browser] Запускаем браузер на порту {random_port}... (headless=False)"
    )
    page.get("https://duck.ai/")

    page.listen.start("duckchat/v1/chat")

    print("[Browser] Ищем поле ввода с таймаутом 10 сек...")
    input_field = page.ele("@name=user-prompt", timeout=10)

    print("[Browser] Кликаем и пишем текст...")
    input_field.click()
    input_field.input("привет")

    page.wait(0.5)

    print("[Browser] Кликаем по кнопке отправки...")
    submit_btn = page.ele("@type=submit", timeout=5)

    if submit_btn:
        submit_btn.click()
    else:
        print("[Browser] Кнопка не найдена, отправляем через Enter...")
        input_field.input("\n")

    print("[Browser] Ждем, пока фронтенд отправит запрос...")
    res = page.listen.wait(timeout=10)

    if res:
        captured_headers = {
            k: v
            for k, v in res.request.headers.items()
            if not k.startswith(":")
        }
        print("[Browser] Заголовки с x-vqd-hash-1 успешно перехвачены!")
    else:
        print(
            "[Browser] Ошибка: Запрос к /chat не улетел. Даем 5 секунд посмотреть на экран..."
        )
        page.wait(5)

finally:
    page.quit()
    print("[Browser] Браузер закрыт.")

if not captured_headers:
    print("[Критическая ошибка] Нечего отправлять, заголовки пустые.")
else:
    print(
        "\n[Parser] Отправляем промпт напрямую через собранную сессию..."
    )

    CHAT_URL = "https://duck.ai/duckchat/v1/chat"

    payload = {
        "model": MODEL,
        "metadata": {
            "toolChoice": {
                "NewsSearch": False,
                "VideosSearch": False,
                "LocalSearch": False,
                "WeatherForecast": False,
            }
        },
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "canUseTools": True,
        "reasoningEffort": "none",
    }

    if DEBUG:
        print("\n=== [ОТЛАДКА] ИСПОЛЬЗУЕМЫЕ ЗАГОЛОВКИ ===")
        for key, value in captured_headers.items():
            if key.startswith("x-") or key.lower() == "cookie":
                print(f"{key}: {value[:60]}...")
        print("=======================================\n")

    with requests.post(
        CHAT_URL, headers=captured_headers, json=payload, stream=True
    ) as r:
        if r.status_code != 200:
            print(
                f"[Ошибка服务器]: Код {r.status_code}, Ответ: {r.text}"
            )
        else:
            print("--- Ответ ---")
            full_response = []
            for line in r.iter_lines():
                if line:
                    decoded_line = line.decode("utf-8")
                    if decoded_line.startswith("data: "):
                        data_str = decoded_line[6:]
                        if data_str == "[DONE]":
                            break
                        if data_str.startswith("[CHAT_TITLE"):
                            continue
                        try:
                            data_json = json.loads(data_str)
                            text_chunk = data_json.get("message", "")
                            if text_chunk:
                                full_response.append(text_chunk)
                                if not DEBUG:
                                    print(text_chunk, end="", flush=True)
                        except json.JSONDecodeError:
                            pass

            if DEBUG:
                print("\n\n--- Финальный собранный текст ---")
                print("".join(full_response))
                print("---------------------------------")
