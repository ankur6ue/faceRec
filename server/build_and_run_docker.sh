#!/bin/bash
app="docker.face_det"
docker image build -t ${app} .
docker system prune
docker container run -p 5000:5000 --name face_det ${app}
