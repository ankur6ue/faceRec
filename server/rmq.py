from pymongo import MongoClient
from json import loads
import pika
import json
import base64
import numpy as np
import config_db as env
from timeit import default_timer as timer

# TODO: Add exception handling and logging everywhere
class MongoDb(object):

    def __init__(self, mongo_url, logger):
        self.dbname = None
        self.logger = logger
        try:
            self.moConn = MongoClient(mongo_url, serverSelectionTimeoutMS=3)
            self.moConn.server_info()  # force connection on a request as the
            self.dbname = self.moConn[env.MONGO_DB]

        except Exception as e:
            self.logger.error('Exception: %s', e.args)

    def insert(self, collection, data):
        if self.dbname:
            try:
                start = timer()
                result = self.dbname[collection].insert_one(data)
                end = timer()
                print('record {0} inserted in {1:.4f} seconds'.format(result.inserted_id, end - start))
            except Exception as e:
                self.logger.error('Exception: %s', e.args)

    def removeAll(self):
        self.moConn.drop_database(env.MONGO_DB)

    def get(self, subjectId, collection):
        records = None
        if self.dbname:
            records = self.dbname[collection].find({'subjectId': subjectId})
        return records

    def close(self):
        if self.dbname:
            self.moConn.close()

class RmqProducer(object):

    def __init__(self, logger):
        self.connection = None
        self.channel = None
        try:
            self.credentials = pika.PlainCredentials(env.RABBIT_USER, env.RABBIT_PASS)
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(env.RABBIT_HOST, env.RABBIT_PORT, env.RABBIT_VHOST, self.credentials))
            self.channel = self.connection.channel()
            # check if we can make a database connection. If not, not point sending messages to the database
            # connect with mongodb
            mongo_url = 'mongodb://{0}:{1}@{2}:{3}'.format(env.MONGO_ADMIN_UNAME, env.MONGO_PWORD, env.MONGO_HOST,
                                                           env.MONGO_PORT)
            self.mongo = MongoDb(mongo_url, logger)
            self.mongo.close()
        except Exception as e:
            logger.error('Exception: %s', e.args)



    # Send task to queue rabbitmq
    def send(self, message):
        if self.channel: # no point sending anything if no channel
            if self.mongo.dbname: # if we couldn't connect to the mongodb, no point sending anything
                # as messages will simply accumulate on the consumer side of the queue
                self.channel.basic_publish(exchange='', routing_key=env.RABBIT_QUEUE_NAME, body=message)

class RmqConsumer(object):

    def __init__(self, logger):
        self.connection = None
        self.channel = None
        self.mongo = None
        try:
            self.credentials = pika.PlainCredentials(env.RABBIT_USER, env.RABBIT_PASS)
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(env.RABBIT_HOST, env.RABBIT_PORT, env.RABBIT_VHOST, self.credentials))
            self.channel = self.connection.channel()
            # connect with mongodb
            mongo_url = 'mongodb://{0}:{1}@{2}:{3}'.format(env.MONGO_ADMIN_UNAME, env.MONGO_PWORD, env.MONGO_HOST,
                                            env.MONGO_PORT)
            print(mongo_url)
            self.mongo = MongoDb(mongo_url, logger)
        except Exception as e:
            logger.error('Exception: %s', e.args)

    def emptyQueue(self):
        if self.channel:
            self.channel.queue_purge(env.RABBIT_QUEUE_NAME)

    def run(self):
        if self.channel:
            self.channel.queue_declare(env.RABBIT_QUEUE_NAME)
            print ("[*] Waiting for messages. To exit press CTRL+C")

            self.channel.basic_qos(prefetch_count=1)
            # Callback method action queue
            self.channel.basic_consume(queue=env.RABBIT_QUEUE_NAME, on_message_callback=self.callback)
            self.channel.start_consuming()

    # Action queue from rabbitmq
    def callback(self, ch, method, properties, body):

        message = json.loads(body)
        print(" Received message from subject {0}".format(message['subjectId']))

        message['image_b64'] = base64.b64encode(np.ascontiguousarray(message['image_b64']).astype('uint8'))
        if self.mongo:
            self.mongo.insert(env.MONGO_COLLECTIONS, message)
        ch.basic_ack(delivery_tag = method.delivery_tag)
