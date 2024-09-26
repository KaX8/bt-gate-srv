from flask import Flask, request, jsonify
from flask_sock import Sock
import logging
import json
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
sock = Sock(app)

clients = []

@app.route('/send_command', methods=['POST'])
def send_command():
    data = request.get_json()
    command = data.get('command')
    if not command:
        return jsonify({'error': 'No command provided'}), 400

    # Отправляем команду ВСЕМ(пока что) подключенным клиентам
    for ws in clients:
        try:
            ws.send(json.dumps({'command': command}))
        except Exception as e:
            print(f"Error sending message to client: {e}")

    return jsonify({'success': True}), 200


@sock.route('/ws')
def websocket_route(ws):
    print("Client connected")
    clients.append(ws)
    try:
        while True:
            data = ws.receive()
            if data is None:
                break
            try:
                json_data = json.loads(data)
                if 'phone' in json_data and 'table' in json_data:
                    phone = json_data['phone']
                    table_num = json_data['table']
                    handle_phone_check(ws, phone, table_num)
                else:
                    # че нибудь еще
                    pass
            except Exception as e:
                print(f"Error processing message: {e}")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        clients.remove(ws)
        print("Client disconnected")

def handle_phone_check(ws, phone, table_num):
    if phone is None:
        logger.warning("No phone number provided in WebSocket message")
        response = {"error": "No phone number provided"}
        ws.send(json.dumps(response))
        return

    try:
        phone = int(phone)
        table_num = int(table_num)
    except ValueError:
        logger.warning(f"Invalid phone or table number: phone={phone}, table={table_num}")
        response = {"error": "Invalid phone or table number"}
        ws.send(json.dumps(response))
        return

    table_path = f"tables/table-{table_num}.xlsx"
    data_path = f"tables/data_choose.xlsx"

    try:
        df = pd.read_excel(table_path, sheet_name='members')
        record = df[df['Телефон'] == phone]
        exists = not record.empty
        fio = record['ФИО'].values[0] if exists else "Null"
        aparts = record['Квартира'].values[0] if exists else "Null"

        df = pd.read_excel(data_path, sheet_name='data')
        data = df['hexData'].values[0]
        
        # Запись в лог файл
        log_message = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {fio} - {aparts} - {phone} - {table_num} - {'True' if exists else 'False'} - {data}"
        file_logger.info(log_message)

        logger.info(f"Checked phone {phone} in table {table_num}: exists={exists}")

        response = {"exists": exists, "data": data}
        ws.send(json.dumps(response))
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        response = {"error": "Error processing request"}
        ws.send(json.dumps(response))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
