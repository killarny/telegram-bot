from io import BytesIO
import logging
from os import environ
from bs4 import BeautifulSoup
from PIL import Image
from praw import Reddit
from random import choice
import requests

logger = logging.getLogger('commands')


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
        try:
            urls.append(soup.select('.image a')[0]['href'])
        except IndexError:
            pass
    # clean up image URLs
    urls = [url.strip('/') for url in urls]
    urls = ['http://{}'.format(url) if not url.startswith('http') else url
            for url in urls]
    return urls

    
def make_thumbnail(image_content):
    """
    Create a thumbnail version of the image_content, and return it.
    """
    image = Image.open(BytesIO(image_content))
    image.thumbnail((250, 250))
    return image.tobytes()


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
        app_id='telegram-reddit-command',
        version='1',
        reddit_username='killarny',
    )
    subreddits = ['aww']

    def __init__(self):
        self.command_map = {
            'reddit': self.random_reddit_image,
        }

    def random_reddit_image(self, caption=None, bot=None, update=None):
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
        try:
            image_url = choice(get_image_links_from_imgur(submission))
        except (IndexError, ValueError):
            # no image found, so try again
            return self.random_reddit_image(caption=caption, bot=bot,
                                            update=update)
        # get the image content
        logger.info('"/{command}" from {user}: posting image at {url}'.format(
            command=' '.join([update.command] + update.command_args),
            user=update.message.user.username,
            url=image_url,
        ))
        response = requests.get(image_url)
        if response.status_code != 200:
            bot.send_message(update.message.chat.id, self.error_message)
            return
        # image_content = make_thumbnail(response.content)
        image_content = response.content
        bot.send_photo(update.message.chat.id, image_content,
                       reply_to_message_id=update.message.id,
                       caption=image_url)


class GetCommand(object):
    """
    /get <search terms>

    Provides a command that searches for a random image on google matching
    a search term.
    """
    def __init__(self):
        self.command_map = {
            'get': self.search,
        }
        # Google CSE ID required: https://cse.google.com/
        self.cse_id = environ.get('GOOGLE_CSE_ID', None)
        if not self.cse_id:
            logger.critical('No Google CSE ID specified! Set the '
                            'GOOGLE_CSE_ID environment variable.')
            logger.warning('{classname} will not be available until a '
                           'CSE ID is provided.'.format(
                classname=self.__class__.__name__,
            ))
            return
        # Google Search API key required: https://console.developers.google.com/apis/api/customsearch
        self.api_key = environ.get('GOOGLE_API_KEY', None)
        if not self.api_key:
            logger.critical('No Google Search API key specified! Set the '
                            'GOOGLE_SEARCH_API_KEY environment variable.')
            logger.warning('{classname} will not be available until an '
                           'API key is provided.'.format(
                classname=self.__class__.__name__,
            ))
            return

    def search(self, *search_terms, caption=None, bot=None, update=None):
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
        response_status = response.get('responseStatus', '???')
        response_data = response.get('responseData', 'no response data')
        if response_status == 200:
            try:
                result = choice(response_data.get('results', []))
            except IndexError:
                image_url = None
            else:
                image_url = result.get('unescapedUrl')
        else:
            logger.error('{status}: {data}'.format(
                status=response_status,
                data=response_data,
            ))
        if not image_url:
            bot.send_message(update.message.chat.id,
                             'I can\'t find an image '
                             'for "{}"'.format(' '.join(search_terms)))
            return
        logger.info('"/{command}" from {user}: posting image at {url}'.format(
            command=' '.join([update.command] + update.command_args),
            user=update.message.user.username,
            url=image_url,
        ))
        image_content = requests.get(image_url).content
        bot.send_photo(update.message.chat.id, image_content,
                       reply_to_message_id=update.message.id,
                       caption=image_url)