import time
import config_db as env
import os
import sys
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

@application.route('/getCount/<db_name>/<collection>/<int:subjectId>', methods=['POST'])
def getCount(db_name, collection, subjectId):
    if cache['mongo']:
        # convert to string because subjectIds are stored as subject1, subject2 etc in the database
        subjectIdStr = 'subject{0}'.format(subjectId)
        db_obj = cache['mongo']
        col_obj = db_obj.moConn[db_name][collection]
        # if collection doesn't exist, count will be 0 but code wouldn't crash
        count = col_obj.count_documents({"subjectId": subjectIdStr})
        return(jsonify({'subjectId': subjectId, 'count': count}))
    return Response('Error connecting to mongo database')

@application.route('/getSubjectInfo/<db_name>/<collection>', methods=['POST'])
def getSubjectInfo(db_name, collection):
    if cache['mongo']:
        db_obj = cache['mongo']
        col_obj = db_obj.moConn[db_name][collection]
        cursor = col_obj.find({})
        documents = []
        for document in cursor:
            documents.append({'name': document['name'], 'id': document['id']})
        return(jsonify(documents))
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
