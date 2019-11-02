from rmq import RmqConsumer
import config as cfg
import logging

logger = logging.getLogger('RMQ Consumer')
logger.setLevel(logging.ERROR)
handler = logging.FileHandler(cfg.LOG_FILE)
logger.addHandler(handler)
rmq_c = RmqConsumer(logger)
rmq_c.emptyQueue()
rmq_c.run()