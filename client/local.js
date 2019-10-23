//Get camera video
const constraints = {
    audio: false,
    video: {
        width: {min: 320, ideal: 640, max: 1920},
        height: {min: 240, ideal: 480, max: 1080}
    }
};

navigator.mediaDevices.getUserMedia(constraints)
    .then(stream => {
        document.getElementById("myVideo").srcObject = stream;
        console.log("Got local user video");

    })
    .catch(err => {
        console.log('navigator.getUserMedia error: ', err)
    });
