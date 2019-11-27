
var Client = (function () {
    //Parameters
    let client = {}
    const s = document.getElementById('faceRec');
    const source_video = s.getAttribute("data-source"); //the source video to use
    const upload_width = s.getAttribute("data-upload_width") || 640; //the width of the upload file
    const mirror = s.getAttribute("data-mirror") || false; //mirror the boundary boxes
    client.detect_threshold = s.getAttribute("data-detect_threshold") || 0.8;
    client.rec_threshold = s.getAttribute("data-rec_threshold") || 0.8;
    const host_type = s.getAttribute("data-api_server")
    const ov_width = 320
    const ov_height = 240

    let proc_type = "gpu"
    client.register_bbox = false
    client.recognize_cbox = false
    let subject_id = ""
    // Variables to be accessed from other modules are added as key-val pairs to client dict
    client.do_face_detect = false
    let log = $("#my-console")[0]
    client.active_subject_name = $('#activeSubject')[0]
    client.register_image_count = 0
    client.active_subject_id = "unset" // indicates that activeSubject is not set
    // Reset initial values
    log.value = ""
    client.active_subject_name.value = ""

    if (host_type == 'localhost') {
        api_server = "http://127.0.0.1:5000" // must be just like this. using 0.0.0.0 for the IP doesn't work!
            resc_mgmt_server = "https://telesens.co/res_mgmt"
    } else {
        api_server = "https://telesens.co/face_det"
            resc_mgmt_server = "https://telesens.co/res_mgmt"
    }

    //Video element selector
    v = document.getElementById(source_video);

    //for starting events
    let is_playing = false,
    got_metadata = false;

    //Canvas setup

    //create a canvas to grab an image for upload
    client.image_canvas = document.createElement('canvas');
    let image_ctx = client.image_canvas.getContext("2d");

    //create a canvas for drawing object boundaries
    let draw_canvas = document.getElementById('drawCanvas');
    let draw_ctx = draw_canvas.getContext("2d");

    //draw boxes and labels on each detected object
    function draw_boxes(objects) {

        //clear the previous drawings
        draw_ctx.clearRect(0, 0, draw_canvas.width, draw_canvas.height);

        //filter out objects that contain a class_name and then draw boxes and labels on each
        objects.filter(object => object.class_name).forEach(object => {

            let rect = draw_canvas.getBoundingClientRect(), // abs. size of element
            scaleX = draw_canvas.width / rect.width, // relationship bitmap vs. element for X
            scaleY = draw_canvas.height / rect.height; // relationship bitmap vs. element for Y

            let x = 2 * object.x;
            let y = 2 * object.y;
            let width = 2 * (object.width);
            let height = 2 * (object.height);

            //flip the x axis if local video is mirrored
            if (mirror) {
                x = draw_canvas.width - (x + width)
            }
            draw_ctx.font = "20px Verdana";
            draw_ctx.fillText(object.class_name + " - " + Math.round(object.score * 100) + "%", x + 5, y - 30)

            if (client.recognize_cbox && 'rec_score' in object) {
                draw_ctx.font = "15px Verdana";
                draw_ctx.fillStyle = "#00ff00";
                draw_ctx.fillText(object.id, x - 5, y - 10);
                draw_ctx.fillText("score: " + object.rec_score.toFixed(2), x + 5, y + 20)
                draw_ctx.fillText("margin: " + object.rec_margin.toFixed(2), x + 5, y + 40)

            }
            draw_ctx.strokeRect(x, y, width, height);
            // Now draw landmarks
            landmarks = object.landmarks
                landmarks.forEach(landmark => {
                    let x = 2 * landmark.x - 5;
                    let y = 2 * landmark.y - 5;
                    //flip the x axis if local video is mirrored
                    if (mirror) {
                        x = draw_canvas.width - (x + 10)
                    }
                    draw_ctx.strokeRect(x, y, 10, 10);
                });

        });
    }
    
    //Add file blob to a form and post
    client.post_file = function(file) {
        if (client.do_face_detect)
        {
            // The FormData interface provides a way to easily construct a set of key/value pairs representing form fields
            // and their values, which can then be easily sent using the XMLHttpRequest.send() method.
            // It uses the same format a form would use if the encoding type were set to "multipart/form-data".
            // See https://developer.mozilla.org/en-US/docs/Web/API/FormData
            let form_data = new FormData()
            form_data.append("image", file) // Image data
            form_data.append("detect_threshold", client.detect_threshold) // face detection threshold
            form_data.append("rec_threshold", client.rec_threshold) // face recognition threshold
            let xhr = new XMLHttpRequest()
            /*
            Send the image data and other parameters to the face detection server endpoint using AJAX
            proc_type: processor type we wish to run our system on (CPU/GPU). Cluster management system can use this info to
                 direct request to the appropriate worker node that supports requested HW
            client.recognize_cbox: should we perform recognition or not
            register_bbox: should the face crops be saved to a database for generating embeddings later. USed to register
                 new subjects
            client.active_subject_id: the subject_id of the current subject. Used during registration.
            */
            xhr.open('POST', api_server + '/detect/' + proc_type + '/' + client.recognize_cbox + '/'
            + client.register_bbox + '/' + client.active_subject_id, true)
            let date = new Date()
            let send_t = date.getTime()
            let this1 = this
            xhr.onload = function () {
                if (this.status === 200) {
                    let date = new Date()
                    let recv_t = date.getTime();
                     // object_data is a nested dictionary of the information returned by the face detection/recognition
                    // system
                    let object_data = JSON.parse(this.response)
                    let log_text = ""
                    // console.log(object_data['server_ip'])
                    log_text += "server# " + object_data['server_ip']
                    proc_time = (object_data.proc_end_time - object_data.proc_start_time)*1000 // in ms
                    rec_time = object_data.rec_time * 1000
                    transmission_time = recv_t - send_t - proc_time

                    // If in register mode, inform the user how many images have been collected
                    if (client.register_bbox && client.active_subject_id != "unset") {
                        log.value += '\n' + 'registering image ' + ++client.register_image_count
                        + ' of subject: ' + client.active_subject_name
                        client.update_scroll(log)
                    }
                    // Update running graphs
                    client.update_charts(proc_time, rec_time, transmission_time)
                    if ('cpu_util' in object_data) {
                        let txt = log.value
                            // log.value = txt + object_data['cpu_util'] + "\n"
                            // log.scroll_top = log.scroll_height
                    }

                    //draw the boxes
                    draw_boxes(object_data.objects);

                    //Save and send the next image
                    image_ctx.drawImage(v, 0, 0, v.videoWidth, v.videoHeight, 0, 0, ov_width, ov_height);
                    client.image_canvas.toBlob(client.post_file, 'image/jpeg');
                } else {
                    console.error(xhr);
                }
            };
            xhr.send(form_data);
        }

        //xhr.send();
    }

    client.update_scroll = function (log) {
        log.scrollTop = log.scrollHeight
    }
    //Start object detection
    function startObjectDetection() {

        console.log("starting Face Recognition");

        //Set canvas sizes based on input video
        draw_canvas.width = v.videoWidth;
        draw_canvas.height = v.videoHeight;

        client.image_canvas.width = ov_width;
        client.image_canvas.height = ov_height;

        //Some styles for the draw_canvas
        draw_ctx.lineWidth = 4;
        draw_ctx.strokeStyle = "cyan";
        draw_ctx.font = "20px Verdana";
        draw_ctx.fillStyle = "cyan";

        //Save and send the first image
        image_ctx.drawImage(v, 0, 0, v.videoWidth, v.videoHeight, 0, 0, ov_width, ov_height);
        let xhr = new XMLHttpRequest();
        let method = api_server + '/init'
            xhr.open('GET', method, true);
        xhr.onload = function () {
            if (this.status === 200) {
                client.image_canvas.toBlob(client.post_file, 'image/jpeg');
            }
        };
        xhr.send()

    }

    client.get_subject_count = function () {
        let xhr = new XMLHttpRequest();
        let dbName = 'faces'
        let collectionName = 'faces'
        let subject_num = 1
        let method = resc_mgmt_server + '/get_count' + '/' + subject_num
        xhr.open('POST', method, true);
        xhr.onload = function () {
            if (this.status === 200) {
                let data = JSON.parse(this.response);
            }
        }
        xhr.send()
    }

    function populate_subject_dropdown(subject_data) {
        let dropdown = $(".dropdown-menu.subjects");
        $(".dropdown-menu.subjects").empty();
        let _this = this
        for (let i = 0; i < subject_data.length; i++) {
            str = "<li class='list-item ExampleCaptionDropDownListItem' data-name='" + subject_data[i].name +
                "' data-id=" + subject_data[i].id + ">"
                 + "<a role='menuitem'  href='#'>" + subject_data[i].name + ": " + subject_data[i].count + "</a>" + "</li>"
                dropdown.append(str);
        }
        $('.ExampleCaptionDropDownListItem').click(function (e) {
            let target = e.currentTarget;
            let name = target.getAttribute("data-name")
            let id = target.getAttribute("data-id")
            log.value += '\n' + 'new active subject: ' + name
            client.update_scroll(log)
            client.active_subject_id = id
            $('#activeSubject')[0].value = name;
        });
    }

    client.get_subject_info = function () {
        let xhr = new XMLHttpRequest();
        let method = resc_mgmt_server + '/get_subject_info'
        xhr.open('POST', method, true);
        xhr.onload = function () {
            if (this.status === 200) {
                let subject_data = JSON.parse(this.response);
                populate_subject_dropdown(subject_data)
            }
        }
        xhr.send()
    }

    client.create_subject = function(subj_name) {
        let this1 = this
        let xhr = new XMLHttpRequest();
        let method = resc_mgmt_server + '/create_subject/' + subj_name
        xhr.open('POST', method, true);
        xhr.onload = function () {
            if (this.status === 200) {
                response = JSON.parse(this.response);
                log.value += '\n' + JSON.stringify(response)
                client.update_scroll(log)
                // Refresh the subject_info listbox
                this1.get_subject_info()
            }
        }
        xhr.send()
    }

    client.generate_embedding = function(subj_id) {
        let this1 = this
        let xhr = new XMLHttpRequest();
        let method = resc_mgmt_server + '/generate_embedding/' + subj_id + '/cpu' + '/' + 160 + '/' + 60
        xhr.open('POST', method, true);
        xhr.onload = function () {
            if (this.status === 200) {
                log.value += '\n' + this.response
                client.update_scroll(log)
            }
        }
        xhr.send()
    }

    client.purge_subject = function(subjId) {
        let this1 = this
        let xhr = new XMLHttpRequest();
        let method = resc_mgmt_server + '/purge_subject/' + subjId
        xhr.open('POST', method, true);
        xhr.onload = function () {
            if (this.status === 200) {
                log.value += '\n' + this.response
                client.update_scroll(log)
            }
        }
        xhr.send()
    }
    //Starting events

    //check if metadata is ready - we need the video size
    v.onloadedmetadata = () => {
        console.log("video metadata ready");
        got_metadata = true;
        if (is_playing) {
            startObjectDetection();
        }
    };

    //see if the video has started playing
    v.onplaying = () => {
        console.log("video playing");
        is_playing = true;
        if (got_metadata) {
            startObjectDetection();
        }
    };

    // uncheck register checkbox
    $('#register_bbox').prop('checked', false);
    // uncheck recognize checkbox
    $('#client.recognize_cbox').prop('checked', false);
    client.get_subject_count()
    client.get_subject_info()

    return client;
}
    ());

