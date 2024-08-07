import os
import re
import logging
import pandas as pd
import xlrd

from telegram import (
    ForceReply,
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    PicklePersistence
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

table_admins_path = "tables/admins.xlsx"

class TelegramBot:
    def __init__(self, token):
        self.commands = {}
        self.bot = self.initialize_bot(token)

    async def message_handler(self, update, context):
        print("-----MESSAGE_HANDLER-----")

        user_data = context.user_data

        if await self.check_username(update.message.chat.username):
            if context.user_data.get('awaiting_data') is None:
                message_text = update.message.text
                if message_text.startswith("/"):
                    command = message_text.split()[0][1:]
                    if command in self.commands:
                        await self.commands[command](update, context)
                    else:
                        await update.message.reply_text("Команда не распознана. Попробуйте /help для списка доступных команд.")
                else:
                    await update.message.reply_text("Сообщение не распознано как команда. Попробуйте /help для списка доступных команд.")
            else:
                if context.user_data['action'] == "add":
                    await self.add_member_prep(update, context, context.user_data['table'], update.message.text)
                if context.user_data['action'] == "remove":
                    await self.rem_member(update, context, context.user_data['table'], update.message.text)

        else:
            await update.message.reply_text(f"Нет доступа :(")

    async def check_username(self, username):
        data = pd.read_excel(table_admins_path, sheet_name="users")
        return username in data['USERNAME'].values

    async def check_phone_avail(self, table, phone):
        data = pd.read_excel(f'tables/{table}.xlsx', sheet_name="members")
        return int(phone) in data['Телефон'].values

    async def get_count_members(self, table):
        data = pd.read_excel(f'tables/{table}.xlsx', sheet_name="members")
        return len(data)

    async def add_admin(self, update, context):
        username = update.message.text.split()[-1]
        data = pd.read_excel("tables/admins.xlsx", sheet_name="users")

        if username == "" or username == "/add_admin" or username == None:
            await update.message.reply_text('Введите имя пользователя: /add_admin {username}')
            return

        if username in data['USERNAME'].values:
            await update.message.reply_text(f'{username} уже существует.')
            return

        print(f'username={username}')
        # Добавление новой строки с именем пользователя
        new_row = pd.DataFrame({'USERNAME': [username]})
        data = pd.concat([data, new_row], ignore_index=True)
    
        # Запись обратно в файл Excel
        with pd.ExcelWriter(table_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            data.to_excel(writer, sheet_name='admin', index=False)

        print(f'{username} добавлен в список администраторов.')
        await update.message.reply_text(f'{username} добавлен в список администраторов.')

    async def add_member_prep(self, update, context, table, data):
        data = data.split(' ')
        await self.add_member(update, context, table, data)

    async def add_member(self, update, context, table, data):
        if len(data) == 5:
            if not await self.check_phone_avail(table, data[3]):
                fio = " ".join(data[0:3])
                phone = data[3]
                apartment = data[4]
                
                try:
                    int(phone)
                    int(apartment)
                except ValueError:
                    await update.message.reply_text('Телефон и квартира должны быть числовыми значениями.')
                    return
                
                table_path = f'tables/{table}.xlsx'
                data = pd.read_excel(table_path, sheet_name="members")
                
                new_row = pd.DataFrame({'ФИО': [fio], 'Телефон': [phone], 'Квартира': [apartment]})
                data = pd.concat([data, new_row], ignore_index=True)
                
                try:
                    with pd.ExcelWriter(table_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                        data.to_excel(writer, sheet_name='members', index=False)
                except PermissionError as e:
                    await update.message.reply_text(f'Ошибка доступа. Закройте целевой файл ({table}.xlsx) и повторите попытку')
                    return 
                
                context.user_data['awaiting_data'] = None
                await self.table_menu(update, context, table, f'{fio} добавлен в список членов.')
            else:
                await update.message.reply_text('Данный телефон уже зарегистрирован. Попробуйте другой.')
        else:
            await update.message.reply_text('Введите данные в формате: {Фамилия} {Имя} {Отчество} {Телефон} {Квартира}')

    async def rem_member(self, update, context, table, data_num):
        if re.match("^\\+?[7-8][0-9]{7,14}$", data_num):
            data_num = data_num.removeprefix('+')
            if data_num[0] == '8': data_num = data_num.replace('8','7',1)

            if await self.check_phone_avail(table, data_num):
                table_path = f'tables/{table}.xlsx'
                data = pd.read_excel(table_path, sheet_name="members")
                data = data[data['Телефон'].astype(str) != data_num]
                with pd.ExcelWriter(table_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                    data.to_excel(writer, sheet_name='members', index=False)
                
                context.user_data['awaiting_data'] = None
                await self.table_menu(update, context, table, f'Пользователь с номером телефона {data_num} удален.')
            else:
                await update.message.reply_text('Телефон не найден')
        else:
            await update.message.reply_text('Неверный формат телефона')



    async def send_file(self, update, context, file_path='phone-calls.log'):
        if update.callback_query == None:
            chat_id = update.message.chat.id
        else:
            chat_id = update.callback_query.from_user.id

        try:
            await context.bot.send_document(chat_id=chat_id, document=open(file_path, 'rb'))
        except Exception as e:
            await update.message.reply_text(f'Не удалось отправить файл: {e}')

    async def tables(self, update, context):
        files = [file for file in os.listdir('./tables') if file.startswith("table")]
        context.user_data['files'] = files
        context.user_data['page'] = 0
        await self.send_file_list(update, context)

    async def send_file_list(self, update, context):

        files = context.user_data.get('files', [])
        page = context.user_data.get('page', 0)
        items_per_page = 4  # 3 элемента на строку, 3 строки на страницу

        # Определение диапазона файлов для текущей страницы
        start = page * items_per_page
        end = start + items_per_page
        page_files = files[start:end]

        # Создание клавиатуры
        keyboard = []
        for i in range(0, len(page_files), 2):
            keyboard.append([InlineKeyboardButton(file, callback_data=f'table_{file}') for file in page_files[i:i + 2]])


        # Добавление кнопок для перелистывания
        navigation_buttons = []
        if page > 0:
            navigation_buttons.append(InlineKeyboardButton('<<', callback_data='prev_list_scroll'))
        if end < len(files):
            navigation_buttons.append(InlineKeyboardButton('>>', callback_data='next_list_scroll'))
        if navigation_buttons:
            keyboard.append(navigation_buttons)

        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query:
            await update.callback_query.edit_message_text('Выберите таблицу:', reply_markup=reply_markup)
        else:
            await update.message.reply_text('Выберите таблицу:', reply_markup=reply_markup)

    async def table_menu(self, update, context, table, add_text = "None"):
        table = table.removesuffix('.xlsx')
        msg = f'Таблица {table}, количество жителей {await self.get_count_members(table)}:'
        if add_text != "None":
            msg = f'{add_text}\n\n' + msg

        keyboard = [
            [
                InlineKeyboardButton('Добавить жителя', callback_data=f'tm_add_{table}'),
                InlineKeyboardButton('Удалить жителя', callback_data=f'tm_remove_{table}')
            ],
            [
                InlineKeyboardButton('Скачать таблицу', callback_data=f'tm_get_{table}')
            ],
            [
                InlineKeyboardButton('<< Назад', callback_data=f'tm_back')
            ],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query:
            await update.callback_query.edit_message_text(msg, reply_markup=reply_markup)
        else:
            await update.message.reply_text(msg, reply_markup=reply_markup)

    async def test(self, update, context):
        pass

    async def general_callback_handler(self, update, context):
        query = update.callback_query
        await query.answer()

        data = query.data
        print(f"Общий обработчик клавиатуры. callback={data}")

        if data.endswith("_list_scroll"):
            await self.tables_scroll_handler(update, context, data.removesuffix('_list_scroll'))
        elif data.startswith("table_"):
            await self.table_menu(update, context, data.removeprefix('table_'))
        elif data.startswith("tm_"):
            await self.table_menu_handler(update, context, data.removeprefix('tm_'))

    async def tables_scroll_handler(self, update, context, data):
        if data == 'prev':
            context.user_data['page'] = context.user_data.get('page', 0) - 1
            await self.send_file_list(update, context)
        elif data == 'next':
            context.user_data['page'] = context.user_data.get('page', 0) + 1
            await self.send_file_list(update, context)

    async def table_menu_handler(self, update, context, data):
        query = update.callback_query
        if data != 'back':
            prefix, table = data.split('_')
            if prefix == 'add':
                context.user_data['awaiting_data'] = True
                context.user_data['table'] = table
                context.user_data['action'] = prefix
                await query.edit_message_text(
                    'Для добавления жителя, введите данные в следующем виде:\n'+
                    '\"Фамилия Имя Отчество Номер-Телефона Квартира:\"\n\n'+
                    'Примеры:\n'+
                    'Иванов Иван Иванович 79001113333 25\n'+
                    'Морозов Семен Андреевич 79028568122 146'
                )
                print(prefix)
            elif prefix == 'get':
                await self.send_file(update, context, f'tables/{table}.xlsx')
                await self.table_menu(update, context, table, f'Файл отправлен')
            elif prefix == 'remove':
                context.user_data['awaiting_data'] = True
                context.user_data['table'] = table
                context.user_data['action'] = prefix
                await query.edit_message_text(
                    'Для удаления жителя, введите его номер телефона:\n'+
                    'Примеры:\n'+
                    '89042224444\n'+
                    '+79001113333\n'+
                    '79028568122'
                )
                print(prefix)
        else:
            await self.send_file_list(update, context)
            

    async def start_command(self, update, context):
        print("-----START_COMMAND-----")
        user = update.effective_user
        await update.message.reply_text(
                f"{user.first_name}, добро пожаловать. Снова. \n/help - весь функционал бота.")


    @staticmethod
    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Набор всех команд: \n" +
            "/help - Просмотр команд \n" +
            "/add_admin - Добавить админа\n" +
            # "/add_member - Добавить жителя\n" +
            # "/remove_member - Удалить жителя \n" +
            "/logs - Файл логов звонков\n" +
            "/tables - Меню таблиц\n" +
            "/test - Тест\n" 
        )


    def initialize_bot(self, token):
        # Использование PicklePersistence для сохранения данных между сессиями
        persistence = PicklePersistence(filepath='bot_data')

        application = Application.builder().token(token).persistence(persistence).build()

        application.add_handler(MessageHandler(filters.TEXT, self.message_handler))
        application.add_handler(MessageHandler(filters.COMMAND, self.message_handler))

        self.commands = {
            "start": self.start_command,
            "help": self.help_command,
            "add_admin": self.add_admin,
            "logs": self.send_file,
            "tables": self.tables,
            "test": self.test,
        }

        application.add_handler(CallbackQueryHandler(self.general_callback_handler))

        return application

    def start_bot(self):
        self.bot.run_polling(close_loop=False)


def main():
    token = "7142732303:AAFlHy-0gTmIBCRkM6oILPtDBMcvzH8ttWI"
    bot = TelegramBot(token)
    bot.start_bot()


if __name__ == "__main__":
    main()
    print("Конец.")
