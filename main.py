import logging
from threading import Thread
import srv
import tg_bot

def start_srv():
    srv.main_srv()

def start_tg():
    tg_bot.main()

t_srv = Thread(target=start_srv, args=(), daemon=True)
t_tg = Thread(target=start_tg, args=(), daemon=True)

t_srv.start()
t_tg.start()
