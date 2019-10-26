# We name the `base` stage so we can refence it in multiple later
# stages but only need to update it in one place if we change it
FROM python:3.7 AS base
COPY requirements.txt /
RUN apt-get update && apt-get install -y \
    libsm6 \
    libxext6 \
    libxrender-dev \
&& pip3 install -r /requirements.txt \
&& pip3 install torch==1.3.0+cpu torchvision==0.4.1+cpu -f https://download.pytorch.org/whl/torch_stable.html

FROM base AS face-det-app
RUN mkdir -p /home/ubuntu/dev/faceRec/server
ADD mtcnn_pytorch_serv.py /home/ubuntu/dev/faceRec/server
ADD config.py /home/ubuntu/dev/faceRec/server
COPY models /home/ubuntu/dev/faceRec/server/models
COPY data /home/ubuntu/dev/faceRec/server/data

FROM face-det-app AS face-det-serv 
WORKDIR /home/ubuntu/dev/faceRec/server/
CMD ["gunicorn", "-b", "0.0.0.0:5000", "mtcnn_pytorch_serv"]
