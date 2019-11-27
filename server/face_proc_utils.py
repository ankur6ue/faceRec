
from mtcnn_pytorch.src import MTCNN2
from models.inception_resnet_v1 import InceptionResnetV1
import torchvision.transforms.functional as F
import torch
from rmq import MongoDb
import config_db as env
import numpy as np
from cache import cache
import onnx
import onnxruntime


# Initializes the Face Detection NN. Return 0 if success, -1 otherwise
def init_fd(logger, dev = 'cpu'):
    try:
        device = 'cpu'
        mtcnn = MTCNN2()
        cache['mtcnn'] = mtcnn
        logger.info('successfully initialized MTCNN')
        return 0
    except Exception as e:
        logger.info('MTCNN initialization error: %e' % e)
        return -1


def save_to_onnx(model):
    x = torch.randn(1, 3, 160, 160, requires_grad=True)
    # Export the model
    torch.onnx.export(model,  # model being run
                      x,  # model input (or a tuple for multiple inputs)
                      "inception_resnet_v1.onnx",  # where to save the model (can be a file or file-like object)
                      export_params=True,  # store the trained parameter weights inside the model file
                      opset_version=10,  # the ONNX version to export the model to
                      do_constant_folding=True,  # whether to execute constant folding for optimization
                      input_names=['input'],  # the model's input names
                      output_names=['output'],  # the model's output names
                      dynamic_axes={'input': {0: 'batch_size'},  # variable lenght axes
                                    'output': {0: 'batch_size'}})

    # verify results
    torch_out = model(x)
    onnx_model = onnx.load("inception_resnet_v1.onnx")
    onnx.checker.check_model(onnx_model)

    onnx_model = onnx.load("inception_resnet_v1.onnx")
    onnx.checker.check_model(onnx_model)

    ort_session = onnxruntime.InferenceSession("inception_resnet_v1.onnx")

    def to_numpy(tensor):
        return tensor.detach().cpu().numpy() if tensor.requires_grad else tensor.cpu().numpy()

    # compute ONNX Runtime output prediction
    ort_inputs = {ort_session.get_inputs()[0].name: to_numpy(x)}
    ort_outs = ort_session.run(None, ort_inputs)
    # compare ONNX Runtime and PyTorch results
    np.testing.assert_allclose(to_numpy(torch_out), ort_outs[0], rtol=1e-03, atol=1e-05)

    print("Exported model has been tested with ONNXRuntime, and the result looks good!")


# Initializes the Face Recognition NN
def init_fr_model(logger, dev = 'cpu'):
    try:
        FRModel = InceptionResnetV1(pretrained='vggface2').eval().to(dev)
        # FRModel = FRModel.half()
        # onnx_FRModel = onnx.load("inception_resnet_v1.onnx")
        cache['FRModel'] = FRModel
        # save_to_onnx(FRModel)
        return 0
    except Exception as e:
        logger.info('Face Recognition Model initialization error: %e' % e)
        return -1


# Initializes the MongoDB database connection, gets subject embeddings and stores the
# embeddings in the cache. The order in which embeddings are stored are the same as the
# subject_info array (see code below). This is used during recognition when the index of the
# matching embedding is also the index of the corresponding subject in the subject_info array
def init_db(logger):
    try:
        MONGO_URL = 'mongodb://{0}:{1}@{2}:{3}'.format(env.MONGO_ADMIN_UNAME, env.MONGO_PWORD, env.MONGO_HOST,
                                                       env.MONGO_PORT)
        db_conn = MongoDb(MONGO_URL, logger)
        cache['db_conn'] = db_conn
        # Read all subject embeddings
        # Get all embeddings
        subjects = db_conn.moConn['subjects']['name_id_map'].find({})
        subject_info = []
        embs = torch.Tensor()
        for subject in subjects:
            if 'embedding' in subject: # not all subjects may have an embedding
                subject_info.append({'name': subject['name'], 'id': subject['id']})
                embs = torch.cat((embs, torch.Tensor(subject['embedding']).unsqueeze(1)), 1)
        cache['db_embs'] = embs
        cache['subject_info'] = subject_info
        return 0
    except Exception as e:
        logger.info('DB initialization error: %e' % e)
        return -1


# Perform face recognition
def do_face_rec(faces, use_onnx = 1):
    # Get the Recognition model from the cache. The model takes an image and outputs an embedding vector which
    # can be compared against the data.base of embeddings.
    FRModel = cache['FRModel']
    # embedding database
    embds_db = cache['db_embs']
    if use_onnx:
        if 'ort_session' not in cache:
            ort_session = onnxruntime.InferenceSession("inception_resnet_v1.onnx")
            cache['ort_session'] = ort_session
        else:
            ort_session = cache['ort_session']

        ort_inputs = {ort_session.get_inputs()[0].name: faces}
        ort_outs = ort_session.run(None, ort_inputs)
        embd = torch.Tensor(ort_outs).squeeze(0)
    else:
        faces_pt = torch.Tensor()  # pt: Pytorch
        # faces_pt = torch.HalfTensor()
        # Create an Tensor of faces [numFaces x width x height x color_channels]
        for face in faces:
            face = face.transpose(1, 2, 0)
            face = F.to_tensor(np.asarray(face, 'float32')).unsqueeze(0)
            # face.half() # pytorch doesn't support half precision FP on CPUs unfortunately
            faces_pt = torch.cat((faces_pt, face), 0)
        # Run through model and get embeddings [numFaces x embedding_size]
        # embd = FRModel(faces_pt)

    # compute ONNX Runtime output prediction
    # Compute the distance of each face embedding against embedding database [numFaces x numSubjects]
    dist = torch.mm(embd, embds_db)
    # Sort the distances, so for each detected face we can identify the best matching subject
    sorted_dist, sort_idx = torch.sort(dist, 1, descending=True)
    return sorted_dist, sort_idx
