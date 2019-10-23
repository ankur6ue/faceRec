import os
import sys
from PIL import Image
from flask import Flask, request, Response, jsonify
sys.path.insert(0, os.path.abspath("."))
from models.mtcnn import MTCNN
import cv2
import numpy as np
import logging
from logging.handlers import RotatingFileHandler
app = Flask(__name__)
cache = {}
# for CORS
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST') # Put any other methods you need here
    return response


@app.route('/')
def index():
    return Response('MTCNN Face Detection')


@app.route('/local')
def local():
    return Response(open('./static/local.html').read(), mimetype="text/html")


@app.route('/init')
def init():
    if (os.name == 'posix'):
        handler = RotatingFileHandler('/home/bitnami/apps/faceRec/mesg.log', maxBytes=10000, backupCount=1)
    if (os.name == 'nt'):
        handler = RotatingFileHandler('C:\Telesens\web\\faceRec\client\mesg.log', maxBytes=10000, backupCount=1)
    app.logger.setLevel(logging.DEBUG)
    app.logger.addHandler(handler)
    try:
        device = 'cpu'
        mtcnn = MTCNN(keep_all=True, device=device)
        cache['mtcnn'] = mtcnn
        return Response('successfully initialized openvino')
    except Exception as e:
        app.logger.info('openvino initialization error: %e' % e)
        return e

@app.route('/detect/<proc_id>', methods=['POST'])
def detect(proc_id):
    try:
        image_file = request.files['image']  # get the image
        mtcnn = cache['mtcnn']

        # Set an image confidence threshold value to limit returned data
        threshold = request.form.get('threshold')
        if threshold is None:
            threshold = 0.5
        else:
            threshold = float(threshold)

        image_file_np = np.fromstring(image_file.read(), np.uint8)
        frame = cv2.imdecode(image_file_np, cv2.IMREAD_UNCHANGED)
        boxes, confs = mtcnn.detect(frame)
        objects = []
        object_data = {}
        conf = 1
        if boxes[0] is not None:
            for (box, conf) in zip(boxes[0], confs[0]):
                if (conf > threshold):
                    object = {}
                    object['score'] = float(conf)
                    object['class_name'] = 'face'
                    object['x'] = float(box[0])
                    object['y'] = float(box[1])
                    object['width'] = float(box[2]-box[0])
                    object['height'] = float(box[3]-box[1])
                    objects.append(object)

        object_data["objects"] = objects
        return jsonify(object_data)

    except Exception as e:
        print('POST /detect error: %e' % e)
        return e


if __name__ == '__main__':
	# without SSL
    app.run(debug=True, host='0.0.0.0')

	# with SSL
    #app.run(debug=True, host='0.0.0.0', ssl_context=('ssl/server.crt', 'ssl/server.key'))
