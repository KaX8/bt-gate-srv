from flask import Flask, request, jsonify
import logging
import pandas as pd
from datetime import datetime

# Настройка логирования для консоли
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Настройка логирования для файла
file_handler = logging.FileHandler("phone-calls.log")
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter("%(message)s")
file_handler.setFormatter(file_formatter)

file_logger = logging.getLogger("file_logger")
file_logger.setLevel(logging.INFO)
file_logger.addHandler(file_handler)

app = Flask(__name__)

@app.route('/exist', methods=['POST'])
def check_phone():
    data = request.get_json()
    phone = data.get('phone')
    table_num = data.get('table')

    if phone is None:
        logger.warning("No phone number provided in request")
        return jsonify({"error": "No phone number provided"}), 400

    try:
        phone = int(phone)
        table_num = int(table_num)
    except ValueError:
        logger.warning(f"Invalid phone or table number: phone={phone}, table={table_num}")
        return jsonify({"error": "Invalid phone or table number"}), 400

    table_path = f"tables/table-{table_num}.xlsx"

    try:
        # Проверяем наличие номера телефона в таблице
        df = pd.read_excel(table_path, sheet_name='members')
        record = df[df['Телефон'] == phone]
        exists = not record.empty
        fio = record['ФИО'].values[0] if exists else "Null"
        aparts = record['Квартира'].values[0] if exists else "Null"

        # Запись в лог файл
        log_message = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {fio} - {aparts} - {phone} - {table_num} - {'True' if exists else 'False'}"
        file_logger.info(log_message)

        # Логи в консоли
        logger.info(f"Checked phone {phone} in table {table_num}: exists={exists}")

        return jsonify({"exists": exists})
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({"error": "Error processing request"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
