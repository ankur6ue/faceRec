# We name the `base` stage so we can refence it in multiple later
# stages but only need to update it in one place if we change it
FROM ubuntu:16.04
FROM python:3.7 AS base
COPY requirements.txt /

# For pytorch
RUN apt-get update && apt-get install -y \
    libsm6 \
    libxext6 \
    libxrender-dev

# for rabbitmq
# Install Erlang + Rabbitmq
# Install the erlang downloader
RUN wget https://packages.erlang-solutions.com/erlang-solutions_1.0_all.deb && \
    dpkg -i erlang-solutions_1.0_all.deb
# Add the rabbitmq source list
RUN echo "deb https://dl.bintray.com/rabbitmq/debian xenial main" | \
    tee /etc/apt/sources.list.d/bintray.rabbitmq.list && \
    wget -O- https://www.rabbitmq.com/rabbitmq-release-signing-key.asc | apt-key add -
# Check which rabbitmq/erlang versions are compatible and isntall:
#       https://www.rabbitmq.com/which-erlang.html
RUN apt-get update && \
    apt-get install rabbitmq-server -y --fix-missing

RUN apt-get install nano

RUN pip3 install -r /requirements.txt \
    && pip3 install torch==1.3.0+cpu torchvision==0.4.1+cpu -f https://download.pytorch.org/whl/torch_stable.html

ARG APPBASEDIR=/opt/bitnami/apps/faceRec
RUN mkdir -p ${APPBASEDIR}/server
COPY / ${APPBASEDIR}/server/
WORKDIR ${APPBASEDIR}/server/

CMD ["gunicorn", "-b", "0.0.0.0:5000", "mtcnn_pytorch_serv"]
