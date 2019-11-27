import os
import sys
from flask import Flask, request, Response, jsonify
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
from face_proc_utils import init_fd, init_fr_model, init_db, do_face_rec
from cache import cache

sys.path.insert(0, os.path.abspath("."))

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
    if init_fd(application.logger, 'cpu') is not 0: return Response('error initializing Face Detector')
    if init_db(application.logger) is not 0: return Response('error initializing Mongo DB Connection')
    if init_fr_model(application.logger) is not 0: return Response('error initializing Face Recognition Model')
    return Response('successfully initialized FR system')


def crop_and_enqueue_bboxes(subject_id, im_pil, faces_whitened, boxes, landmarks, cropped_size):

    # To show the image, undo whitening transformation img = (img - 127.5)*0.0078125
    faces = np.array(faces_whitened / 0.0078125 + 127.5).astype(np.uint8)
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
    # for i in range(5):
    #    cv2.rectangle(face, (pn[2 * i] - 2, pn[2 * i + 1] - 2), (pn[2 * i] + 2, pn[2 * i + 1] + 2), (0, 255, 0), 2)

    # cv2.imshow('crop', face)
    landmark_string = base64.b64encode(np.ascontiguousarray(pn))

    face_record = {
        'time_stamp': datetime.datetime.now().timestamp(),
        'subjectId': subject_id,
        'image_b64': np.ascontiguousarray(face_).tolist(),
        'landmarks': pn
    }
    if usingRabbit:
        rmqProd.send(json.dumps(face_record))


@application.route('/detect/<proc_id>/<recognize>/<register_bbox>/<subject_id>', methods=['POST'])
def detect(proc_id, recognize, register_bbox, subject_id):
    """
    This function implements the face detection algorithm.
    proc_id: processor type (CPU/GPU etc)
    register_bbox: should the cropped images be saved to a database or not
    subject_id: subject_id for the test subject
    """
    application.logger.setLevel(logging.DEBUG)
    app_logger.addHandler(handler)

    if register_bbox == 'true':
        register_bbox = 1
    else:
        register_bbox = 0

    try:
        global frame_count
        frame_count = frame_count + 1
        # record time
        start = timer()
        frame_count = frame_count + 1        
        image_file = request.files['image']  # get the image
        # alternatively, the user can upload the image to a S3 bucket and provide the URL as a form field (eg.'s3_url').
        # Then one can read the url using request.form.get('s3_url') and read the file using urllib and other Python
        # file APIs.

        # Read the other parameters from the form
        detect_threshold = float(request.form.get('detect_threshold'))
        rec_threshold = float(request.form.get('rec_threshold'))

        if detect_threshold is None:
            detect_threshold = cfg.FACE_DET_THREHOLD

        # Now run the image data through the detection Neural Network
        if 'mtcnn' not in cache: # run init
            init()        
        mtcnn = cache['mtcnn']

        subject_info = cache['subject_info']
        objects = []
        object_data = {}

        # size of the resized + cropped image
        cropped_size = request.form.get('cropped_size')
        if cropped_size is None:
            cropped_size = cfg.CROPPED_SIZE
        else:
            cropped_size = int(cropped_size)
        image_str = image_file.read()
        image_np = np.asarray(bytearray(image_str), dtype="uint8")
        image_bgr = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        frame = Image.fromarray(image_rgb) # PIL Image
        boxes, landmarks_ = mtcnn(frame)

        if len(boxes) is not 0:
            # round boxes because that's how get_image_boxes expects them
            boxes[:, 0:4] = np.round(boxes[:, 0:4])
            faces_whitened = get_image_boxes(boxes, frame, size=cropped_size)
            if recognize == 'true':
                start_rec = timer()
                dists, idxs = do_face_rec(faces_whitened)
                end_rec = timer()
                rec_time = end_rec - start_rec
                object_data["rec_time"] = rec_time

            if (register_bbox is 1) and (subject_id is not "unset"):
                    crop_and_enqueue_bboxes(subject_id, frame, faces_whitened, boxes, landmarks_, cropped_size)

        end = timer()

        num_landmarks = 5  # L/R eye, L/R lip corner, nose tip
        count = 0
        if len(boxes) is not 0:
            for (box, landmark_) in zip(boxes, landmarks_):
                conf = box[4]
                object = {}
                if recognize == 'true':
                    subj_idx = idxs[count]
                    subj_dist = dists[count]
                    rec_score = float(subj_dist[0])
                    if len(subj_dist) > 1:
                        margin = subj_dist[0] - subj_dist[1]
                    else:
                        margin = 0
                    if rec_score > rec_threshold:
                        object['id'] = subject_info[subj_idx[0]]['name']
                    else:
                        object['id'] = "Unknown"
                    object['rec_score'] = rec_score
                    object['rec_margin'] = float(margin)
                    count = count + 1
                if conf > detect_threshold:
                    object['score'] = float(conf)
                    object['class_name'] = 'face'
                    object['x'] = float(box[0])
                    object['y'] = float(box[1])
                    object['width'] = float(box[2]-box[0])
                    object['height'] = float(box[3]-box[1])

                    landmarks = []
                    for i in range(num_landmarks):
                        landmark = dict()  # if I do landmark = {}, pycharm compains..
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
        app_logger.error('Exception: %s', e.args)
        return e


if __name__ == '__main__':
    # without SSL
    if os.name == 'nt':
        application.run(debug=True, host='0.0.0.0')  # ssl_context=(cfg.SSL_CRT, cfg.SSL_KEY))
    # on ubuntu run with ssl
    # application.run(debug=True, host='0.0.0.0', ssl_context=(cfg.SSL_CRT, cfg.SSL_KEY))
    else:
        application.run(debug=True, host='0.0.0.0', port=5000)
