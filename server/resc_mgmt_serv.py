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

@application.route('/generateEmbedding/<subjectId>/<device>/<int:image_size>/<int:N>', methods=['POST'])
def generateEmbedding(subjectId, device, image_size, N):
    if cache['mongo']:
        db_obj = cache['mongo']
        connObj = db_obj.moConn[env.MONGO_FACE_DB][env.MONGO_FACE_COLLECTION]
        numDocs = connObj.count_documents({"subjectId": subjectId})
        if (numDocs < N):
            return Response('Insufficient number of images of subject: {0}.\
                            {1} found, {2} needed'.format(subjectId, numDocs, N))
        # Last N records
        face_records = connObj.find({'subjectId': subjectId}).skip(numDocs - N)
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
            _, subjNum = subjectId.split('subjectId')  # to get the number of subject (2, 3 etc)
            db_obj.moConn[env.MONGO_SUBJECTS_DB][env.MONGO_SUBJECTS_COLLECTION].update({'id': subjNum},
                                                             {"$set": {"embedding": em_mean.numpy().tolist()}})
            return Response('Embedding successfully created')
    return Response('Error connecting to mongo database')


@application.route('/getSubjectId/<subjName>', methods=['POST'])
def getSubjectId(subjName):
    if cache['mongo']:
        db_obj = cache['mongo']
        # First remove from the subjects database
        col_obj = db_obj.moConn[env.MONGO_SUBJECTS_DB][env.MONGO_SUBJECTS_COLLECTION]
        document = col_obj.find_one({"name": re.compile(subjName, re.IGNORECASE)})
        if document is None:  # subj Doesn't exist, create new subject
            # no id found
            return Response('unset')
        return Response('subjectId{0}'.format(document['id']))
    return Response('Error connecting to mongo database')

@application.route('/purgeSubject/<subjectId>', methods=['POST'])
def purgeSubject(subjectId):
    if cache['mongo']:
        db_obj = cache['mongo']
        # First remove from the subjects database
        col_obj = db_obj.moConn[env.MONGO_SUBJECTS_DB][env.MONGO_SUBJECTS_COLLECTION]

        # extract number from subjectId
        _, subjNum = subjectId.split('subjectId')  # to get the number of subject (2, 3 etc)
        res1 = col_obj.delete_many({'id': subjNum})

        # Also clean any images of this subject from the faces database
        col_obj = db_obj.moConn[env.MONGO_FACE_DB][env.MONGO_FACE_COLLECTION]
        res2 = col_obj.delete_many({'subjectId': subjectId})
        res_str = 'removed {0} records for subjectId: {1}'.format(res2.deleted_count, subjectId)
        return Response(res_str)
    return Response('Error connecting to mongo database')

@application.route('/getCount/<int:subjectId>', methods=['POST'])
def getCount(subjectId):
    if cache['mongo']:
        # convert to string because subjectIds are stored as subjectId1, subjectId2 etc in the database
        subjectIdStr = 'subjectId{0}'.format(subjectId)
        db_obj = cache['mongo']
        col_obj = db_obj.moConn[env.MONGO_FACE_DB][env.MONGO_FACE_COLLECTION]
        # if collection doesn't exist, count will be 0 but code wouldn't crash
        count = col_obj.count_documents({"subjectId": subjectIdStr})
        return(jsonify({'subjectId': subjectId, 'count': count}))
    return Response('Error connecting to mongo database')

@application.route('/getSubjectInfo', methods=['POST'])
def getSubjectInfo():
    if cache['mongo']:
        db_obj = cache['mongo']
        col_obj = db_obj.moConn[env.MONGO_SUBJECTS_DB][env.MONGO_SUBJECTS_COLLECTION]
        cursor = col_obj.find({})
        documents = []
        for document in cursor:
            # for each document get the number of images stored
            col_obj_faces = db_obj.moConn[env.MONGO_FACE_DB][env.MONGO_FACE_COLLECTION]
            # convert 0 to subject0 etc.
            subjectIdStr = 'subjectId{0}'.format(document['id'])
            count = col_obj_faces.count_documents({"subjectId": subjectIdStr})
            documents.append({'name': document['name'], 'id': document['id'], 'count': count})
        return(jsonify(documents))
    return Response('Error connecting to mongo database')


@application.route('/createSubject/<subjName>', methods=['POST'])
def createSubject(subjName):
    if cache['mongo']:
        db_obj = cache['mongo']
        col_obj = db_obj.moConn[env.MONGO_SUBJECTS_DB][env.MONGO_SUBJECTS_COLLECTION]
        # do case insensitive search
        document = col_obj.find_one({"name": re.compile(subjName, re.IGNORECASE)})
        if document is None: # subj Doesn't exist, create new subject
            # get the current maximum id
            max_id = col_obj.find_one(sort=[("id", -1)])["id"]
            max_id = int(max_id) + 1
            col_obj.insert_one({'name': subjName, 'id': str(max_id)})
            return jsonify({'type': 'new', 'name': subjName, 'id': max_id})
        else:
            # find how many images of this subject we already have
            col_obj_faces = db_obj.moConn[env.MONGO_FACE_DB][env.MONGO_FACE_COLLECTION]
            subjectIdStr = 'subjectId{0}'.format(document['id'])
            count = col_obj_faces.count_documents({"subjectId": subjectIdStr})
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
init()

if __name__ == '__main__':
    # without SSL
    init()
    if (os.name == 'nt'):
        application.run(debug=True, host='0.0.0.0')  # , ssl_context=(cfg.SSL_CRT, cfg.SSL_KEY))
    # on ubuntu run with ssl
    else:
        #        application.run(debug=True, host='0.0.0.0', ssl_context=(cfg.SSL_CRT, cfg.SSL_KEY))
        application.run(debug=True, host='0.0.0.0', port=8082)
