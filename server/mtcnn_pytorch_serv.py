import os
import sys
from flask import Flask, request, Response, jsonify
sys.path.insert(0, os.path.abspath("."))
import config as cfg
import cv2
import numpy as np
import logging
import socket
from timeit import default_timer as timer
import psutil
from logging.handlers import RotatingFileHandler
from PIL import Image, ImageDraw
import base64
import datetime
import json
from rmq import RmqProducer
from mtcnn_pytorch.src.box_utils import get_image_boxes
from face_proc_utils import initFD, initFRModel, initDB, Recognize
from cache import cache

application = Flask(__name__)
handler = RotatingFileHandler(cfg.LOG_FILE, maxBytes=10000, backupCount=1)
frame_count = 0

usingRabbit = True
application.logger.setLevel(logging.DEBUG)
app_logger = application.logger
app_logger.addHandler(handler)
rmqProd = RmqProducer(app_logger)

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
    application.logger.info('In /test')
    return Response('MTCNN Face Detection')

@application.route('/init')
def init():
    application.logger.setLevel(logging.DEBUG)
    application.logger.addHandler(handler)
    if initFD(application.logger, 'cpu') is not 0: return Response('error initializing Face Detector')
    if initDB(application.logger) is not 0: return Response('error initializing Mongo DB Connection')
    if initFRModel(application.logger) is not 0: return Response('error initializing Face Recognition Model')
    return Response('successfully initialized FR system')

def crop_and_enqueue_bboxes(subjectId, im_pil, faces_whitened, boxes, landmarks, cropped_size):

    # To show the image, undo whitening transformation img = (img - 127.5)*0.0078125
    faces = np.array(faces_whitened / 0.0078125 + 127.5).astype(np.uint8)
    face_string = base64.b64encode(faces)
    # just save the first face
    face_ = faces[0].transpose(1, 2, 0)
    face = np.ascontiguousarray(face_)
    # transform the landmark coordinates wrt origin of the bounding box
    face_string = base64.b64encode(face)

    pn = []  # normalized landmark coords wrt bbox origin
    b = boxes[0]  # first bounding box
    p = landmarks[0]
    box_width = b[2] - b[0]
    box_height = b[3] - b[1]
    # get landmark coordinates wrt bbox coordinates
    for i in range(5):
        pn.append((int)((p[i] - b[0]) * cropped_size / box_width))
        pn.append((int)((p[i + 5] - b[1]) * cropped_size / box_height))
    # for drawing
    #for i in range(5):
    #    cv2.rectangle(face, (pn[2 * i] - 2, pn[2 * i + 1] - 2), (pn[2 * i] + 2, pn[2 * i + 1] + 2), (0, 255, 0), 2)

    # cv2.imshow('crop', face)
    landmark_string = base64.b64encode(np.ascontiguousarray(pn))

    face_record = {
        'time_stamp': datetime.datetime.now().timestamp(),
        'subjectId': subjectId,
        'image_b64': np.ascontiguousarray(face_).tolist(),
        'landmarks': pn
    }
    if usingRabbit:
        rmqProd.send(json.dumps(face_record))

"""
proc_id: processor type (CPU/GPU etc)
registerBbox: should the cropped images be saved to a database or not
subjectId: subjectId for the test subject
"""
@application.route('/detect/<proc_id>/<recognize>/<registerBbox>/<subjectId>', methods=['POST'])
def detect(proc_id, recognize, registerBbox, subjectId):

    application.logger.setLevel(logging.DEBUG)
    app_logger = application.logger

    app_logger.addHandler(handler)
    if registerBbox == 'true':
        registerBbox = 1
    else:
        registerBbox = 0

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
        detectThreshold = float(request.form.get('detectThreshold'))
        recThreshold = float(request.form.get('recThreshold'))

        if detectThreshold is None:
            detectThreshold = cfg.FACE_DET_THREHOLD


        # size of the resized + cropped image
        cropped_size = request.form.get('cropped_size')
        if cropped_size is None:
            cropped_size = cfg.CROPPED_SIZE
        else:
            cropped_size = int(cropped_size)
        image_str = image_file.read()
        image_np = np.asarray(bytearray(image_str), dtype="uint8")
        imageBGR = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
        imageRGB = cv2.cvtColor(imageBGR, cv2.COLOR_BGR2RGB)
        frame = Image.fromarray(imageRGB) # PIL Image
        boxes, landmarks_ = mtcnn(frame)
        # round boxes because that's how get_image_boxes expects them
        boxes[:, 0:4] = np.round(boxes[:, 0:4])
        if len(boxes) is not 0:
            faces_whitened = get_image_boxes(boxes, frame, size=cropped_size)
            if recognize == 'true':
                start_rec = timer()
                dists, idxs = Recognize(faces_whitened)
                end_rec = timer()
                rec_time = end_rec - start_rec
            if (registerBbox is 1) and (subjectId is not ""):
                    crop_and_enqueue_bboxes(subjectId, frame, faces_whitened, boxes, landmarks_, cropped_size)

        end = timer()
        subjectInfo = cache['subjectInfo']
        objects = []
        object_data = {}
        num_landmarks = 5  # L/R eye, L/R lip corner, nose tip
        count = 0
        if len(boxes) is not 0:
            for (box, landmark_) in zip(boxes, landmarks_):
                conf = box[4]
                object = {}
                if recognize == 'true':
                    subjIdx = idxs[count]
                    subjDist = dists[count]
                    recScore = float(subjDist[0])
                    if len(subjDist) > 1:
                        margin = subjDist[0] - subjDist[1]
                    else:
                        margin = 0
                    if recScore > recThreshold:
                        object['id'] = subjectInfo[subjIdx[0]]['name']
                    else:
                        object['id'] = "Unknown"
                    object['recScore'] = recScore
                    object['recMargin'] = float(margin)
                    count = count + 1
                if (conf > detectThreshold):
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
        if recognize == 'true':
            object_data["rec_time"] = rec_time

        if frame_count % 5 == 0:
            object_data["cpu_util"] = psutil.cpu_percent()

        return jsonify(object_data)

    except Exception as e:
        app_logger.error('Exception: %s', e.args)
        return e


if __name__ == '__main__':
	# without SSL
    if (os.name == 'nt'):
        application.run(debug=True, host='0.0.0.0')#, ssl_context=(cfg.SSL_CRT, cfg.SSL_KEY))
    # on ubuntu run with ssl
    else:
#        application.run(debug=True, host='0.0.0.0', ssl_context=(cfg.SSL_CRT, cfg.SSL_KEY))
        application.run(debug=True, host='0.0.0.0', port=8081)
