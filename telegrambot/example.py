from telegrambot import TelegramBot, main
from telegrambot.commands import GetCommand


class DemoTelegramBot(TelegramBot):
    commands = [GetCommand]


if __name__ == '__main__':
    main(bot_class=DemoTelegramBot)