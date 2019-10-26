
#!/bin/bash
app="docker.face_det"
version="0.1"
#-rm removes intermediate containers
docker image build --rm --tag ${app} .
#docker system prune
#docker container run -t -i -d -p 5000:5000 ${app}

# push package to github
# login
docker login docker.pkg.github.com -u ankur6ue -p 2885fdef1353250626580e5c9bc2c8826a07e3ce
# tag
docker tag ${app} docker.pkg.github.com/ankur6ue/facerec/${app}:${version}
# push
docker push docker.pkg.github.com/ankur6ue/facerec/${app}:${version}
