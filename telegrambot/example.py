from telegrambot import TelegramBot, main
from telegrambot.commands import GetCommand


class DemoTelegramBot(TelegramBot, GetCommand):
    pass


if __name__ == '__main__':
    main(bot_class=DemoTelegramBot)