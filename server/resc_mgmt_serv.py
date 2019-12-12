import time
import config_db as env
import os
import re
import sys
from PIL import Image, ImageDraw
import base64
import numpy as np
import torch
import torchvision.transforms.functional as F
from models.inception_resnet_v1 import InceptionResnetV1
from flask import Flask, request, Response, jsonify
from rmq import MongoDb
import logging
from logging.handlers import RotatingFileHandler

application = Flask(__name__)
cache = {}
handler = RotatingFileHandler('resc_mgmt_serv.txt', maxBytes=10000, backupCount=1)
logger = application.logger
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

frame_count = 0


# for CORS
@application.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST')  # Put any other methods you need here
    return response


@application.route('/test')
def test():
    logger.info('In /test')
    return Response('Resource Mgmt Server Running')


@application.route('/generate_embedding/<subject_id>/<device>/<int:image_size>/<int:n>', methods=['POST'])
def generate_embedding(subject_id, device, image_size, n):
    """
    Generates an average embedding vector by passing last n images of the subject corresponding to
    subject_id through an inceptionResnet. This vector is stored in the subjects collection and
    used during face recognition
    :param subject_id: subject id (1,2,3 etc)
    :param device: (CPU/GPU, not used for now)
    :param image_size: size to which each crop is resized before passing through the inceptionResnet
    network
    :param n: number of images to use. If the number of images for the subject is less than this
    number, an error will be returned
    :return: message indicating whether embedding was created successfully or some error
    was encountered
    """
    if cache['mongo']:
        db_obj = cache['mongo']
        conn_obj = db_obj.moConn[env.MONGO_FACE_DB][env.MONGO_FACE_COLLECTION]
        num_docs = conn_obj.count_documents({"subjectId": subject_id})
        if num_docs < n:
            return Response('Insufficient number of images of subject: {0}.\
                            {1} found, {2} needed'.format(subject_id, num_docs, n))
        # Last N records
        face_records = conn_obj.find({'subjectId': subject_id}).skip(num_docs - n)
        resnet = InceptionResnetV1(pretrained='vggface2').eval().to(device)
        count = 0
        pil_images = []
        for face_record in face_records:
            image_b64 = face_record.get('image_b64')
            landmark = face_record.get('landmarks')

            image_bytes = base64.decodebytes(image_b64)
            image_pil = Image.frombytes('RGB', (image_size, image_size), image_bytes)
            pil_images.append(image_pil)
            count = count + 1

        # now whiten the images
        whitened = []
        with torch.no_grad():
            for image in pil_images:
                # convert to np array and then to tensor
                img = F.to_tensor(np.asarray(image, 'float32'))
                # whiten
                img = (img - 127.5) * 0.0078125
                whitened.append(img)

            whitened = torch.stack(whitened).to(device)
            embeddings = resnet(whitened)
            em_mean = torch.mean(embeddings, 0)
            db_obj.moConn[env.MONGO_SUBJECTS_DB][env.MONGO_SUBJECTS_COLLECTION].update({'id': subject_id},
                                                     {"$set": {"embedding": em_mean.numpy().tolist()}})
            return Response('Embedding successfully created')
    return Response('Error connecting to mongo database')


@application.route('/get_subject_id/<subj_name>', methods=['POST'])
def get_subject_id(subj_name):
    """
    Takes a subject name (eg: Ankur Mohan) and returns the corresponding id
    (0, 1 etc)
    :param subj_name: 
    :return: subject id if the subject name is found in the database, 'unset' otherwise
    """
    if cache['mongo']:
        db_obj = cache['mongo']
        # First remove from the subjects database
        col_obj = db_obj.moConn[env.MONGO_SUBJECTS_DB][env.MONGO_SUBJECTS_COLLECTION]
        document = col_obj.find_one({"name": re.compile(subj_name, re.IGNORECASE)})
        if document is None:  # subj Doesn't exist, create new subject
            # no id found
            return Response('unset')
        return Response(document['id'])
    return Response('Error connecting to mongo database')


@application.route('/purge_subject/<subject_id>', methods=['POST'])
def purge_subject(subject_id):
    """
    Removes the documents corresponding to subject_id from the faces and subject collections
    :param subject_id: 
    :return: number of records removed
    """
    if cache['mongo']:
        db_obj = cache['mongo']
        # First remove from the subjects database
        col_obj = db_obj.moConn[env.MONGO_SUBJECTS_DB][env.MONGO_SUBJECTS_COLLECTION]
        col_obj.delete_many({'id': subject_id})

        # Also clean any images of this subject from the faces database
        col_obj = db_obj.moConn[env.MONGO_FACE_DB][env.MONGO_FACE_COLLECTION]
        res2 = col_obj.delete_many({'subjectId': subject_id})
        res_str = 'removed {0} records for subjectId: {1}'.format(res2.deleted_count, subject_id)
        return Response(res_str)
    return Response('Error connecting to mongo database')


@application.route('/get_count/<subject_id>', methods=['POST'])
def get_count(subject_id):
    """
    Returns the number of images for subject_id
    :param subject_id:
    :return: Number of images
    """
    if cache['mongo']:
        db_obj = cache['mongo']
        col_obj = db_obj.moConn[env.MONGO_FACE_DB][env.MONGO_FACE_COLLECTION]
        # if collection doesn't exist, count will be 0 but code wouldn't crash
        count = col_obj.count_documents({"subjectId": subject_id})
        return jsonify({'subjectId': subject_id, 'count': count})
    return Response('Error connecting to mongo database')


@application.route('/get_subject_info', methods=['POST'])
def get_subject_info():
    """
    Returns all subject names along with their id and the number of images for 
    each subject
    :return: array of subject name, id and number of images
    key value pairs in JSON format
    """
    print('handling request: get_subject_info')
    if cache['mongo']:
        db_obj = cache['mongo']
        col_obj = db_obj.moConn[env.MONGO_SUBJECTS_DB][env.MONGO_SUBJECTS_COLLECTION]
        col_obj_faces = db_obj.moConn[env.MONGO_FACE_DB][env.MONGO_FACE_COLLECTION]
        cursor = col_obj.find({})
        documents = []
        for document in cursor:
            # for each document get the number of images stored
            subject_id = document['id']
            count = col_obj_faces.count_documents({"subjectId": subject_id})
            documents.append({'name': document['name'], 'id': subject_id, 'count': count})
        return jsonify(documents)
    return Response('Error connecting to mongo database')


@application.route('/create_subject/<subj_name>', methods=['POST'])
def create_subject(subj_name):
    """
    Creates entries in the subject and faces collections corresponding to subj_name
    :param subj_name:
    :return: If subject already exists, returns key-value pair
    {'type': 'exists', 'name': document['name'], 'id': document['id'], 'count': count}
    in JSON format
    if not, creates a new subject entry and returns
    {'type': 'new', 'name': subj_name, 'id': max_id} in JSON format
    """
    if cache['mongo']:
        db_obj = cache['mongo']
        col_obj = db_obj.moConn[env.MONGO_SUBJECTS_DB][env.MONGO_SUBJECTS_COLLECTION]
        # do case insensitive search
        document = col_obj.find_one({"name": re.compile(subj_name, re.IGNORECASE)})
        if document is None: # subj Doesn't exist, create new subject
            # get the current maximum id
            # can't do this because mongo will sort by string which returns incorrect results
            # max_id = col_obj.find_one(sort=[("id", -1)])["id"]
            # do brute force for now
            cursor = col_obj.find({})
            max_id = 0
            for document in cursor:
                max_id = max(max_id, int(document['id']))

            max_id = max_id + 1
            col_obj.insert_one({'name': subj_name, 'id': str(max_id)})
            return jsonify({'type': 'new', 'name': subj_name, 'id': max_id})
        else:
            # find how many images of this subject we already have
            col_obj_faces = db_obj.moConn[env.MONGO_FACE_DB][env.MONGO_FACE_COLLECTION]
            subject_id = document['id']
            count = col_obj_faces.count_documents({"subjectId": subject_id})
            return jsonify({'type': 'exists', 'name': document['name'], 'id': document['id'], 'count': count})
    return Response('Error connecting to mongo database')


def init():
    try:
        # connect with mongodb
        mongo_url = 'mongodb://{0}:{1}@{2}:{3}'.format(env.MONGO_ADMIN_UNAME, env.MONGO_PWORD, env.MONGO_HOST,
                                                       env.MONGO_PORT)
        print(mongo_url)
        mongo = MongoDb(mongo_url, logger)
        cache['mongo'] = mongo
        application.logger.info('Successfully initialized database: subjects')
    except Exception as e:
        logger.error('Exception: %s', e.args)


# needed to run automatically from the gunicorn_service.py. Probably
# much better ways to do this..
init()


if __name__ == '__main__':
    # without SSL
    init()
    if os.name == 'nt':
        application.run(debug=True, host='0.0.0.0')  # , ssl_context=(cfg.SSL_CRT, cfg.SSL_KEY))
    # on ubuntu run with ssl
    else:
        #        application.run(debug=True, host='0.0.0.0', ssl_context=(cfg.SSL_CRT, cfg.SSL_KEY))
        application.run(debug=True, host='0.0.0.0', port=8082)
