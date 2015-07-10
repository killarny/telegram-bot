FROM ubuntu:latest
RUN apt-get update && apt-get -qqy dist-upgrade && \
  apt-get install -qqy python3-pip
RUN pip3 install beautifulsoup4 praw requests
RUN mkdir /telegram-bot
WORKDIR /telegram-bot
ADD . /telegram-bot/
CMD ["python3", "/telegram-bot/bot.py"]