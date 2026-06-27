import json
import random
import time
from DrissionPage import ChromiumPage, ChromiumOptions

# доступные модели: "claude-haiku-4-5", "gpt-5.4-mini", "gpt-5.4-nano", "tinfoil/gpt-oss-120b", "mistral-small-2603"
MODEL = "tinfoil/gpt-oss-120b"

co = ChromiumOptions()
co.headless(False) # это не включать ибо тогда duck.ai запалит парсер
co.incognito(True)
co.set_argument("--no-sandbox")

random_port = random.randint(9000, 9999)
co.set_local_port(random_port)
co.set_user_data_path(f"/tmp/drission_user_data_{random_port}")

prompt = input("Промпт: ")

page = ChromiumPage(co)

try:
    page.get("https://duck.ai/")

    print("[Browser] Открываем меню выбора модели...")
    model_btn = page.ele("@data-testid=model-select-button", timeout=10)
    model_btn.click()
    page.wait(0.5)

    print(f"[Browser] Кликаем по радио-кнопке/label для {MODEL}...")
    model_label = page.ele(f"xpath://label[@for='{MODEL}']", timeout=5)
    if model_label:
        model_label.click()
    else:
        model_radio = page.ele(f"@id={MODEL}", timeout=5)
        model_radio.click(by_js=True)
    page.wait(0.5)

    print("[Browser] Нажимаем кнопку 'Начать чат' для подтверждения...")
    confirm_btn = page.ele(
        "xpath://button[contains(text(), 'Начать чат') or contains(text(), 'Start')]",
        timeout=5,
    )
    if confirm_btn:
        confirm_btn.click()
    else:
        confirm_btn_alt = page.ele("xpath://form//button[@type='submit']")
        if confirm_btn_alt:
            confirm_btn_alt.click()
    page.wait(1.0)

    print("[Browser] Ищем поле ввода сообщения...")
    input_field = page.ele("@name=user-prompt", timeout=10)
    input_field.click()
    input_field.input(prompt)
    page.wait(0.5)

    print("[Browser] Кликаем по кнопке отправки промпта...")
    submit_btn = page.ele("xpath://form//button[@type='submit']", timeout=5)
    if submit_btn:
        submit_btn.click()
    else:
        input_field.input("\n")

    print("[Browser] Отслеживаем генерацию текста...")
    page.wait(1.0)

    start_wait = time.time()
    last_text_len = 0
    no_change_count = 0

    while time.time() - start_wait < 30:
        page.wait(0.4)

        chat_container = page.ele(
            "xpath://div[contains(@class, 'space-y-4') and .//p]"
        )
        if chat_container:
            current_text = page.run_js(
                "return arguments[0].innerText;", chat_container
            )
            current_len = len(current_text.strip())

            if current_len > 0 and current_len == last_text_len:
                no_change_count += 1
            else:
                no_change_count = 0

            if current_len > 0:
                last_text_len = current_len

        btn = page.ele("xpath://form//button[@type='submit']")
        if (btn and btn.attr("disabled") is None and last_text_len > 0) or (
            no_change_count >= 3
        ):
            break

    print("\n--- Ответ ---")
    chat_container = page.ele(
        "xpath://div[contains(@class, 'space-y-4') and .//p]"
    )
    if chat_container:
        final_text = page.run_js(
            "return arguments[0].innerText;", chat_container
        )
        print(final_text.strip())
    else:
        print("[Error] Не удалось найти блок с ответом в DOM.")
    print("\n-----------------")

finally:
    page.quit()
