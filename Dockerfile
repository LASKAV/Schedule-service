FROM python:3.12.1-slim

WORKDIR /app

COPY requirements.txt /app/

RUN apt update && apt install -y \
  git \
  openssh-client

RUN mkdir -p -m 0700 ~/.ssh && ssh-keyscan github.com >> ~/.ssh/known_hosts

RUN --mount=type=ssh pip install -r requirements.txt

COPY . /app/

CMD [ "python", "main.py" ]
