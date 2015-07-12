from bs4 import BeautifulSoup
from praw import Reddit
from random import choice
import requests


def get_image_links_from_imgur(imgur_url):
    """
    Given an imgur URL, return a list of image URLs from it.
    """
    if 'imgur.com' not in imgur_url:
        raise ValueError('given URL does not appear to be an imgur URL')
    urls = []
    response = requests.get(imgur_url)
    if response.status_code != 200:
        raise ValueError('there was something wrong with the given URL')
    soup = BeautifulSoup(response.text, 'html5lib')
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


class RedditCommand(object):
    """
    /reddit

    Provides a command that pulls a random top image from one of the allowed
    subreddits.
    """
    error_message = "I can't find a suitable image. Try again later!"
    reddit_user_agent = ('{platform}:{app_id}:{version} '
                         '(by /u/{reddit_username})').format(
        platform='python',
        app_id='telegram-eyebleach',
        version='1',
        reddit_username='killarny',
    )
    subreddits = ['aww']

    def _cmd_reddit(self, caption=None, bot=None, update=None):
        """
        Find and send a random image from a random subreddit containing
        images.
        """
        if not (bot and update):
            return
        bot.send_chat_action(update.message.chat.id)
        # choose a random subreddit to pull image from
        subreddit = choice(self.subreddits)
        # grab submissions from the subreddit
        reddit = Reddit(user_agent=self.reddit_user_agent)
        submissions = reddit.get_subreddit(subreddit).get_hot(limit=50)
        # skip non-imgur links, animated images, and choose a random submission
        submission = choice([sub.url for sub in submissions
                             if 'imgur.com' in sub.url])
        # find all the image links in the submission, and choose a random one
        image_url = choice(get_image_links_from_imgur(submission))
        # get the image content
        response = requests.get(image_url)
        if response.status_code != 200:
            bot.send_message(update.message.chat.id, self.error_message)
            return
        image_content = response.content
        bot.send_photo(update.message.chat.id, image_content,
                       reply_to_message_id=update.message.id,
                       caption=image_url)
    # allow subclasses to change the command
    command_reddit = _cmd_reddit


class GetCommand(object):
    """
    /get <search terms>

    Provides a command that searches for a random image on google matching
    a search term.
    """
    def _cmd_get(self, *search_terms, caption=None, bot=None, update=None):
        if not (search_terms and bot and update):
            return
        bot.send_chat_action(update.message.chat.id)
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
            bot.send_message(update.message.chat.id,
                             'I can\'t find an image '
                             'for "{}"'.format(' '.join(search_terms)))
            return
        image_content = requests.get(image_url).content
        bot.send_photo(update.message.chat.id, image_content,
                       reply_to_message_id=update.message.id,
                       caption=image_url)
    # allow subclasses to change the command
    command_get = _cmd_get
