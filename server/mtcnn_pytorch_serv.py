import os
import sys
from flask import Flask, request, Response, jsonify
sys.path.insert(0, os.path.abspath("."))
#from models.mtcnn import MTCNN
from mtcnn_pytorch.src import  MTCNN2
import config
import cv2
import numpy as np
import logging
import socket
from timeit import default_timer as timer
import psutil
from logging.handlers import RotatingFileHandler
from PIL import Image, ImageDraw
application = Flask(__name__)
cache = {}

if (os.name == 'nt'):
    cfg = config.win_cfg
else:
    cfg = config.ubuntu_cfg


handler = RotatingFileHandler(cfg['log_file'], maxBytes=10000, backupCount=1)
frame_count = 0

# for CORS
@application.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST') # Put any other methods you need here
    return response


@application.route('/test')
def test():
    application.logger.setLevel(logging.DEBUG)
    application.logger.addHandler(handler)
    application.logger.info('successfully created log file')
    return Response('MTCNN Face Detection')


@application.route('/local')
def local():
    return Response(open('./static/local.html').read(), mimetype="text/html")


@application.route('/init')
def init():
    application.logger.setLevel(logging.DEBUG)
    application.logger.addHandler(handler)
    try:
        device = 'cpu'
        mtcnn = MTCNN2()
        cache['mtcnn'] = mtcnn
        return Response('successfully initialized MTCNN')
    except Exception as e:
        application.logger.info('MTCNN initialization error: %e' % e)
        return e

@application.route('/detect/<proc_id>', methods=['POST'])
def detect(proc_id):
    try:
        global frame_count
        # record time
        start = timer()
        frame_count = frame_count + 1        
        image_file = request.files['image']  # get the image
        if 'mtcnn' not in cache: # run init
            init()        
        mtcnn = cache['mtcnn']
        
        # Set an image confidence threshold value to limit returned data
        threshold = request.form.get('threshold')
        if threshold is None:
            threshold = cfg['faceDetThreshold']
        else:
            threshold = float(threshold)

        image_file_np = np.fromstring(image_file.read(), np.uint8)
        frame = Image.fromarray(cv2.imdecode(image_file_np, cv2.IMREAD_UNCHANGED))
        boxes, landmarks_ = mtcnn(frame)
        end = timer()
        objects = []
        object_data = {}
        conf = 1
        num_landmarks = 5
        if len(boxes) is not 0:
            for (box, landmark_) in zip(boxes, landmarks_):
                conf = box[4]
                if (conf > threshold):
                    object = {}
                    object['score'] = float(conf)
                    object['class_name'] = 'face'
                    object['x'] = float(box[0])
                    object['y'] = float(box[1])
                    object['width'] = float(box[2]-box[0])
                    object['height'] = float(box[3]-box[1])
                    
                    landmarks = []
                    for i in range(num_landmarks):
                        landmark = {}
                        landmark['x'] = float(landmark_[i])
                        landmark['y'] = float(landmark_[5+i])
                        landmarks.append(landmark)
                    object['landmarks'] = landmarks
                    objects.append(object)
                    
        
        
        object_data["objects"] = objects
        # append host IP
        if 'MY_IPS' in os.environ:
            object_data["server_ip"] = os.environ['MY_IPS']
        object_data["proc_start_time"] = start
        object_data["proc_end_time"] = end
        if frame_count % 5 == 0:
            object_data["cpu_util"] = psutil.cpu_percent()

        return jsonify(object_data)

    except Exception as e:
        print('POST /detect error: %e' % e)
        return e


if __name__ == '__main__':
	# without SSL
    if (os.name == 'nt'):
        application.run(debug=True, host='0.0.0.0')
    # on ubuntu run with ssl
    else:
#        application.run(debug=True, host='0.0.0.0', ssl_context=(cfg['ssl_crt'], cfg['ssl_key']))
        application.run(debug=True, host='0.0.0.0')
