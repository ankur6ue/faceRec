
#!/bin/bash
app="docker.face_det"
version="0.1"

# read github access token from file
input="github_token.txt"
token=$(head -n 1 $input)
#token = ""
echo "$token"

# stop all running containers
docker container stop $(sudo docker ps -a -q)

#-rm removes intermediate containers
docker image build --rm --tag ${app} .
docker system prune
docker container run -t -i -d -p 5000:5000 --env MY_IPS=$(hostname) ${app}

# if token exists then try to upload to github
if [ -n "$token" ]; then
    # push package to github
    # login
    docker login docker.pkg.github.com -u ankur6ue -p $token
    # tag
    docker tag ${app} docker.pkg.github.com/ankur6ue/facerec/${app}:${version}
    # push
    docker push docker.pkg.github.com/ankur6ue/facerec/${app}:${version}
fi
