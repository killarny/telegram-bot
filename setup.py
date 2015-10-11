from setuptools import setup, find_packages

setup(
    name = "telegrambot",
    version = "0.1",
    packages = find_packages(),
    install_requires = [
        'beautifulsoup4==4.4.0',
        'html5lib==0.999999',
        'praw==3.3.0',
        'requests==2.7.0',
    ],
    author = "killarny",
    author_email = "killarny@gmail.com",
    description = "An easily customizable Telegram bot written in Python.",
    license = "MIT",
    keywords = "telegram",
)
