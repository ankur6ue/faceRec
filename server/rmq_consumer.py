from rmq import RmqConsumer
import config as cfg
import logging
from gunicorn_service import Quit, start

logger = logging.getLogger('RMQ Consumer')
logger.setLevel(logging.ERROR)
handler = logging.FileHandler(cfg.LOG_FILE)
logger.addHandler(handler)
# stop and restart gunicorn server for managing registered users
Quit()
start()
rmq_c = RmqConsumer(logger)
rmq_c.emptyQueue()
rmq_c.run()