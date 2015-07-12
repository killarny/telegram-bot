FROM python:onbuild
RUN pip install --upgrade pip
CMD ["python", "bot.py"]