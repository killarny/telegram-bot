from datetime import datetime
from random import choice, randrange
import tempfile
from time import sleep
import requests


reddit_user_agent = ('{platform}:{app_id}:{version} '
                     '(by /u/{reddit_username})').format(
                        platform='python',
                        app_id='telegram-bot',
                        version='1',
                        reddit_username='killarny',
                     )


def get_image_links_from_imgur(imgur_url):
    """
    Given an imgur URL, return a list of image URLs from it.
    """
    if 'imgur.com' not in imgur_url:
        raise ValueError('given URL does not appear to be an imgur URL')
    urls = []
    response = requests.get(imgur_url)
    if response.get('responseStatus') != 200:
        raise ValueError('there was something wrong with the given URL')
    soup = BeautifulSoup(response.text)
    # this is an album
    if '/a/' in imgur_url:
        matches = soup.select('.album-view-image-link a')
        urls += [x['href'] for x in matches]
    # directly linked image
    elif 'i.imgur.com' in imgur_url:
        urls.append(imgur_url)
    # single-image page
    else:
        urls.append(soup.select('.image a')[0]['href'])
    return urls

    
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

    def handle(self, bot_class):
        if not self.message.text:
            return

        bot = bot_class()
        commands = [x.strip('command_') for x in dir(bot) 
                    if x.startswith('command_')]
        if self.command not in commands:
            raise CommandNotSupported(self.command)

        func = getattr(bot, 'command_{}'.format(self.command))
        if not func:
            raise CommandNotSupported(self.command)
        
        try:
            if self.command_args:
                return func(*self.command_args, update=self)
            return func(update=self)
        except Exception as e:
            # print traceback for exceptions, but don't allow them to 
            #  halt the bot
            print(e.traceback)
            bot.send_message(self.message.chat.id, 
                             'There was an error with the /{command} '
                             'command. Sorry!'.format(command=self.command)))


class TelegramBot(object):
    base_url = 'https://api.telegram.org/bot{bot_id}'
    bot_id = None
    complain_about_invalid_commands = False
    command_not_supported_message = "That's not a valid command."
    
    def __init__(self):
        if not self.bot_id:
            raise RuntimeError('No bot_id supplied.')

    @property
    def url(self):
        return self.base_url.format(bot_id=self.bot_id)

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
        
    def command_eyebleach(self, caption=None, update=None,
                           subreddits=['stacked']):
        """
        Find and send a random image from a random subreddit containing 
        "eyebleach" images.
        """
        if not update:
            return
        self.send_chat_action(update.message.chat.id)
        # choose a random subreddit to pull image from
        subreddit = choice(subreddits)
        # grab submissions from the subreddit
        reddit = praw.Reddit(user_agent=reddit_user_agent)
        submissions = reddit.get_subreddit(subreddit).get_hot(limit=25)
        # skip non-imgur links, and choose a random submission
        submission = choice([sub.url for sub in submissions 
                             if 'imgur.com' in sub.url])
        # find all the image links in the submission, and choose a random one
        image_url = choice(get_image_links_from_imgur(submission))
        # get the image content
        response = requests.get(image_url)
        if response.get('responseStatus') != 200:
            self.send_message(update.message.chat.id,
                              'I can\'t find a suitable eyebleach image. '
                              'Try again later!',
            )
            return
        image_content = response.content
        self.send_photo(udpate.message.chat.id, image_content,
                        reply_to_message_id=update.message.id,
                        caption=image_url)

    def command_get(self, *search_terms, caption=None, update=None):
        if not search_terms or not update:
            return
        self.send_chat_action(update.message.chat.id)
        url = 'https://ajax.googleapis.com/ajax/services/search/images'
        response = requests.get(url, params={
            'q': '+'.join(search_terms),
            'v': '1.0',
            'imgsz': 'medium',
            'imgtype': 'photo',
            'as_filetype': 'png',
            'start': 0,
            'num': 10,
            'safe': 'off',
        }).json()
        image_url = None
        if response.get('responseStatus') == 200:
            response_data = response.get('responseData')
            try:
                result = choice(response_data.get('results', []))
            except IndexError:
                image_url = None
            else:
                image_url = result.get('unescapedUrl')
        if not image_url:
            self.send_message(update.message.chat.id,
                              'I can\'t find an image '
                              'for "{}"'.format(' '.join(search_terms)))
            return
        image_content = requests.get(image_url).content
        self.send_photo(update.message.chat.id, image_content, 
                        reply_to_message_id=update.message.id,
                        caption=image_url,
        )


def main(bot_class=TelegramBot):
    print('Starting Telegram bot..')
    last_update = 1
    while True:
        sleep(2)
        bot = bot_class()
        response = requests.get('{}/getupdates'.format(bot.url), params={
            'offset': last_update+1,
        })
        if not response.status_code == 200:
            print('Bad status code: {}'.format(response.status_code))
            continue
        if not response.json().get('ok'):
            raise ValueError('Error: {error}'.format(
                error=response.json().get('description', 
                                          'no error description.'),
            ))
        updates = [Update(u) for u in response.json().get('result', [])]
        updates.sort(key=lambda x: x.id)
        last_update = max([u.id for u in updates]) if updates else 0
        for update in updates:
            try:
                update.handle(bot_class)
            except CommandNotSupported:
                if not bot.complain_about_invalid_commands:
                    continue
                bot.send_message(update.message.chat.id, 
                                 bot.command_not_supported_message.format(
                                    command=update.command))

            
if __name__ == '__main__':
    main()