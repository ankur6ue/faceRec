# Face Detection and Recognition
Algorithm: Uses MTCNN for face bounding box and landmark (left/right eye, nose tip, lip corners) coordinates detection. To perform recognition, the image region corresponding to a detected face is resized to a canonical size (160 * 160 by default) and passed through an Inception V1 NN to produce an embedding vector. Dot product of this embedding vector is then calculated against the embedding vectors for registered subjects in the system. The smallest dot product corresponds to the best match. The difference between the smallest and the next smallest score (called 'margin') reflects the system's robustness.  

## System Architecture
A HTML5/JS client reads image data from a web camera and sends this image data to a REST endpoint (/face_detect) exposed by an Apache web server. This web server then proxies all incoming traffic on this endpoint to an Apache proxy server listening on 8081. This server in turn proxies (through a LoadBalancer) all traffic to a face detection and recognition server that exposes various endpoints to perform detection and recognition. If the IP address of the face detection and recognition server changes (for instance if this server is started on a new AWS EC2 instance that is assigned a new IP address) then the second proxy server can simply be restarted after updating the IP address in the BalancerMember directive of the Apache configuration. The main application server can continue to run and serve the rest of the application traffic without interruption. 

The system can be run in two modes - recognition and registration. In the recognition mode, the embedding corresponding to a face crop is compared against embeddings of registered subjects stored in a MongoDB database. In registration mode allows new subjects can be added to the system. This is done by storing the pixels in the image crop corresponding to each detected face in a database as a base64 string. Once sufficient number of images have been added, each stored image is run through Inception V1 NN and the network outputs are averaged. This averaged embedding serves as a representation embedding for the subject and is then used during recognition. During registration, to prevent contamination from images of non-subjects, only the subject of interest must be in the camera view.

The communication between the face recognition system and the MongoDB database occurs through a RabbitMQ message queuing system. Using a mesasge queue prevents the need for the recognition system to wait for the face crop to be stored in the database.

## Code Organization
- faceRec\client: Contains the JS/HTML files for the application frontend. The frontend is split between client.js, client-chart.js (implements a running plot to show compute and network latencies), client-events.js using the Javascript Module design pattern (http://www.adequatelygood.com/JavaScript-Module-Pattern-In-Depth.html)

- faceRec\server:
  - \data: The model files corresponding to PNet, ONet and RNet, the three components of MTCNN face detection system. 
  - \models: definition of inception_resnet_v1 used during recognition
  - \mtcnn_pytorch: implementation of MTCNN NN
  - \mtcnn_pytorch_serv: Python script that implements the face detection and recognition server
  - \inception_resnet_v1.onnx: The onnx version of inception_resnet_v1 model for faster inference on the CPU.
  - \face_proc_utils.py: Defines methods for initializing connection with the MongoDB database and fetching the subject embeddings to be used during recognition, initializing the face recognition and detection NNs. Used by mtcnn_pytorch.py
  - \rmq_consumer.py: Initializes the RabbitMQ consumer to consume messages sent by the producer (initialized by mrcnn_pytorch_serv) and starts the resource management server as a gunicorn service
  - \build_and_run_docker.sh: Builds and runs the docker container for the face detection and recognition app. 
 
## MongoDB and RabbitMQ Installation Notes
### RabbitMQ install:
note: guest user can't accept connections from other than local host. Must create another username to do that and 
give this user permissions
commands:
sudo rabbitmqctl add_user rabbit rabbit
sudo rabbitmqctl set_permissions -p / rabbit ".*" ".*" ".*"

### MongoDB
follow directions here:
https://docs.mongodb.com/manual/tutorial/install-mongodb-on-ubuntu/

mongod changes
1. Open /etc/mongod.conf
2. change as follows:
// network interfaces
net:
  port: 27017
  bindIp: 0.0.0.0 # listens to all incoming traffic

3. Enable authentication
security:
    authorization: "enabled"
4. 
mongo
use admin
db.createUser(
  {
    user: "myAdmin",
    pwd: "myAdminPword", // or cleartext password
    roles: [ { role: "userAdminAnyDatabase", db: "admin" }, "readWriteAnyDatabase" ]
  }
)

> use faces
> db.createUser(
  {
    user: "faceUser",
    pwd: "faceUserPword",
    roles: [ { role: "readWrite", db: "faces" } ]
  }
)	

4. Restart mongod
sudo service mongod restart 
// may need to give /data/db proper permissions
step1: find out the user as which mongo runs
grep mongo /etc/passwd
step 2: 
sudo chmod -R go+rw /data/db
step3:
sudo chown -R $USER /data/db


