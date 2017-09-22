#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import time
import sqlite3
import datetime
from dateutil import parser
from threading import Thread

import telebot
from telebot import types

import config


bot = telebot.TeleBot(config.BOT_TOKEN)


def access_paid(uid):
    """
    Check that access to channel paid
    """
    with sqlite3.connect(config.db_name) as db:
        cursor = db.cursor()
        sql = 'SELECT * FROM payments WHERE uid=?'
        res = cursor.execute(sql, (uid,)).fetchone()
        db.commit()
        print('DataBase response: {!s}'.format(res))
        if res:
            return True
        return False


def add_payment(uid, end_date):
    """
    Insert user payment in database
    """
    with sqlite3.connect(config.db_name) as db:
        cursor = db.cursor()
        # Delete previous payment
        sql = 'DELETE FROM payments WHERE uid=?'
        cursor.execute(sql, (uid,))
        # Add new payment
        sql = 'INSERT INTO payments (uid, end_date) VALUES (?, ?)'
        res = cursor.execute(sql, (uid, end_date))
        db.commit()


def kick_user_from_channel(uid):
    """
    Kick user from channel
    """
    try:
        bot.kick_chat_member(config.channel_id, uid)
    except Exception as e:
        print(e)


def send_payment_message(cid):
    prices = [types.LabeledPrice(label='Доступ к каналу Telegram', amount=config.channel_acces_price)]
    return bot.send_invoice(cid, title='Доступ к каналу Telegram',
            description='Оплатите месячную подписку на канал в Telegram.',
            provider_token=config.PROVIDER_TOKEN,
            currency='RUB',
            prices=prices,
            start_parameter='channel-access',
            invoice_payload='HAPPY FRIDAYS COUPON')


def daily_check():
    """
    Check the relevance of user subscriptions 
    and notify is subscription ends
    """
    with sqlite3.connect(config.db_name) as db:
        cursor = db.cursor()
        sql = 'SELECT uid, end_date FROM payments'
        res = cursor.execute(sql).fetchall()
        today = str(datetime.datetime.now()).split(' ')[0]
        after_tomorrow = parser.parse(today) + datetime.timedelta(days=2)
        print(after_tomorrow)
        for user in res:
            if after_tomorrow == parser.parse(str(user[1])):
                text = 'У вас истекает подписка.'
                bot.send_message(user[0], text)
                send_payment_message(user[0])
                time.sleep(0.1)
            if parser.parse(str(user[1])) <= parser.parse(today):
                kick_user_from_channel(user[0])
                text = 'Время действия вашей подписки окончено.'
                bot.send_message(user[0], text)
                send_payment_message(user[0])
                # Delete user from DataBase
                sql = 'DELETE FROM payments WHERE uid=?'
                cursor.execute(sql, (user[0],))
                time.sleep(0.1)
        db.commit()


@bot.message_handler(commands=['start'])
def start_message(message):
    uid = message.from_user.id
    cid = message.chat.id
    # Check payments
    if access_paid(uid):
        # Share channel link
        text = 'Подписка оплачена.'
        markup = types.InlineKeyboardMarkup()
        url_button = types.InlineKeyboardButton(text='На канал', url=config.channel_url)
        markup.add(url_button)
        return bot.send_message(cid, text, reply_markup=markup)
    else:
        send_payment_message(uid)


@bot.message_handler(commands=['id'])
def id_message(message):
    return bot.send_message(message.chat.id, message.chat.id)


@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    return bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True, 
        error_message='Ошибка. Попробуйте оплатить ещё раз.')


@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    cid = message.chat.id
    uid = message.from_user.id
    # Add payment in DataBase
    end_date = datetime.datetime.now() + datetime.timedelta(days=30)
    add_payment(uid, str(end_date).split(' ')[0])
    # Unban user
    try:
        bot.unban_chat_member(config.channel_id, uid)
    except Exception as e:
        print(e)
    # Share channel link
    text = 'Подписка оплачена.'
    markup = types.InlineKeyboardMarkup()
    url_button = types.InlineKeyboardButton(text='На канал', url=config.channel_url)
    markup.add(url_button)
    return bot.send_message(cid, text, reply_markup=markup)


def init_interval():
    """
    Init Daily check
    """
    while True:
        clock = str(datetime.datetime.now()).split(' ')[1][:5]
        print(clock)
        if clock == '00:00': # '00:00'
            daily_check()
        time.sleep(60)


def init_bot():
    """
    Init Telegram Bot
    """
    while True:
        try:
            bot.polling(none_stop=True)
        except KeyboardInterrupt as e:
            sys.exit()
        except Exception as e:
            print(e)
            time.sleep(30)


def main():
    # Deploy database
    with sqlite3.connect(config.db_name) as db:
        cursor = db.cursor()
        sql = '''CREATE TABLE IF NOT EXISTS payments (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            uid INTEGER NOT NULL,
            end_date TEXT NOT NULL)'''
        cursor.execute(sql)
        db.commit()

    # Init threads
    em_thread = Thread(target=init_interval)
    bot_thread = Thread(target=init_bot)

    em_thread.start()
    bot_thread.start()

    em_thread.join()
    bot_thread.join()    


if __name__ == '__main__':
    main()
