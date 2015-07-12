from argparse import ArgumentParser
from datetime import datetime
import logging
from signal import SIGINT, signal
from signal import SIGTERM
from time import sleep
import requests

logger = logging.getLogger('bot')


class User(object):
    id = 0
    username = None
    first_name = None
    last_name = None

    def __init__(self, contact_data):
        self.id = int(contact_data.get('id'))
        self.username = contact_data.get('username')
        self.first_name = contact_data.get('first_name')
        self.last_name = contact_data.get('last_name')


class GroupChat(object):
    id = 0
    title = None

    def __init__(self, contact_data):
        self.id = int(contact_data.get('id'))
        self.title = contact_data.get('title')


class Message(object):
    id = 0
    chat = None
    user = None
    date = 0
    text = ''
    forward_from = None
    forward_date = 0
    reply_to_message = None
    audio = None
    document = None
    photo = None
    sticker = None
    video = None
    contact = None
    location = None
    new_chat_participant = None
    left_chat_participant = None
    new_chat_title = ''
    new_chat_photo = None
    delete_chat_photo = False
    group_chat_created = False

    def __init__(self, data):
        self.id = int(data.get('message_id'))
        chat = data.get('chat', {})
        self.chat = User(chat) if chat.get('username') else GroupChat(chat)
        self.user = User(data.get('from', {}))
        self.date = datetime.fromtimestamp(data.get('date', 0))
        self.text = data.get('text', '')
        forward_from = data.get('forward_from', {})
        self.forward_from = User(forward_from) if forward_from else None
        self.forward_date = datetime.fromtimestamp(data.get('forward_date', 0))
        reply_to_message = data.get('reply_to_message', {})
        self.reply_to_message = Message(reply_to_message) \
            if reply_to_message else None

    def __str__(self):
        return '<{username}> {text}'.format(
            username=self.user.username, 
            text=self.text,
		)


class CommandNotSupported(Exception):
    pass


class Update(object):
    id = 0
    message = None

    def __init__(self, data):
        self.id = int(data.get('update_id'))
        message = data.get('message', None)
        if message:
            self.message = Message(message)
    
    def __str__(self):
        return 'Update {id}: {message}'.format(
            id=self.id, message=self.message)
            
    @property
    def command(self):
        try:
            return self._command
        except AttributeError:
            if not self.message.text:
                return
            command = self.message.text.split()[0]
            self._command = command.lstrip('/').strip()
        return self._command

    @property
    def command_args(self):
        try:
            return self._cargs
        except AttributeError:
            if not self.message.text:
                return
            args = self.message.text.split()
            if len(args) > 1:
                command, self._cargs = args[0], args[1:]
            else:
                command, self._cargs = args[0], []
        return self._cargs

    def handle(self, bot):
        if not self.message.text:
            return

        commands = [x.strip('command_') for x in dir(bot)
                    if x.startswith('command_')]
        if self.command not in commands:
            raise CommandNotSupported(self.command)

        func = getattr(bot, 'command_{}'.format(self.command))
        if not func:
            raise CommandNotSupported(self.command)
        
        try:
            if self.command_args:
                return func(*self.command_args, bot=bot, update=self)
            return func(bot=bot, update=self)
        except Exception as e:
            # log traceback for exceptions, but don't allow them to
            #  halt the bot
            logger.exception(e)
            bot.send_message(self.message.chat.id, 
                             'There was an error with the /{command} '
                             'command. Sorry!'.format(command=self.command))


class TelegramBot(object):
    base_url = 'https://api.telegram.org/bot{bot_id}'
    bot_id = None
    complain_about_invalid_commands = False
    command_not_supported_message = "That's not a valid command."
    exiting = False
    last_update = 1

    def __init__(self):
        if not self.bot_id:
            raise RuntimeError('No bot_id supplied.')

    @property
    def url(self):
        return self.base_url.format(bot_id=self.bot_id)

    def get_updates(self):
        response = requests.get('{}/getupdates'.format(self.url), params={
            'offset': self.last_update+1,
        })
        if not response.status_code == 200:
            logger.error('Bad status code: {}'.format(response.status_code))
            return
        if not response.json().get('ok'):
            raise ValueError('Error: {error}'.format(
                error=response.json().get('description',
                                          'no error description.'),
            ))
        updates = [Update(u) for u in response.json().get('result', [])]
        updates.sort(key=lambda x: x.id)
        self.last_update = max([u.id for u in updates]) if updates else 0
        for update in updates:
            try:
                update.handle(self)
            except CommandNotSupported:
                if not self.complain_about_invalid_commands:
                    continue
                self.send_message(update.message.chat.id,
                                  self.command_not_supported_message.format(
                                      command=update.command))

    def send_chat_action(self, to_id, action=None):
        if action not in ['typing', 'upload_photo', 'record_video',
                          'upload_video', 'record_audio', 'upload_audio',
                          'upload_document', 'find_location']:
            action = 'typing'
        requests.post('{}/sendchataction'.format(self.url), {
            'chat_id': to_id,
            'action': action,
        })

    def send_message(self, to_id, text):
        requests.post('{}/sendmessage'.format(self.url), {
            'chat_id': to_id,
            'text': text,
        })

    def send_photo(self, to_id, photo_data, reply_to_message_id=None,
                   caption=None):
        files = {'photo': ('image.png', photo_data)}
        params = {
            'chat_id': to_id,
            'caption': caption,
        }
        if reply_to_message_id:
            params.update({
                'reply_to_message_id': reply_to_message_id,
            })
        response = requests.post('{}/sendphoto'.format(self.url),
                                 params=params, files=files)


def main(bot_class=TelegramBot):
    parser = ArgumentParser(description='An easily extensible Telegram bot.')
    args = parser.parse_args()

    # set up logging aparatus
    logging.captureWarnings(True)
    logging_config = dict(
        level=logging.DEBUG,
        datefmt='%Y-%m-%d %H:%M:%S',
        format='%(asctime)-15s %(name)s: %(levelname)s %(message)s',
    )
    logging.basicConfig(**logging_config)
    # suppress logs from the requests library connection pool (they're noisy)
    noise = logging.getLogger('requests.packages.urllib3.connectionpool')
    noise.disabled = True

    logger.info('Starting Telegram bot..')
    bot = bot_class()

    # handle exit conditions gracefully
    def was_force_stopped(signo, stackframe):
        if signo == SIGINT:
            print()
            logger.debug('Bot interrupted via keypress!')
        if signo == SIGTERM:
            logger.debug('Bot was asked to shutdown..')
        logger.info('Shutting down..')
        bot.exiting = True
    signal(SIGINT, was_force_stopped)
    signal(SIGTERM, was_force_stopped)

    while True:
        if bot.exiting:
            break
        sleep(2)
        bot.get_updates()
    parser.exit()

            
if __name__ == '__main__':
    main()