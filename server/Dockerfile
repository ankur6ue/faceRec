FROM python:3.7
RUN apt-get update && apt-get install -y \
    libsm6 \
    libxext6 \
    libxrender-dev
COPY requirements.txt /

RUN pip3 install -r /requirements.txt
RUN pip3 install torch==1.3.0+cpu torchvision==0.4.1+cpu -f https://download.pytorch.org/whl/torch_stable.html
RUN mkdir -p /home/ubuntu/dev/faceRec/server
ADD mtcnn_pytorch_serv.py /home/ubuntu/dev/faceRec/server
ADD config.py /home/ubuntu/dev/faceRec/server
COPY models /home/ubuntu/dev/faceRec/server/models
COPY ssl /home/ubuntu/dev/faceRec/server/ssl
WORKDIR /home/ubuntu/dev/faceRec/server/
CMD ["gunicorn", "-b", "0.0.0.0:5000", "mtcnn_pytorch_serv"]
