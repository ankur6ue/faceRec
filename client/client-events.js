
var Client = (function (client) {
    let this1 = this;

    $('#subjectsDropdownList').on('show.bs.dropdown', function () {
        // Refresh subject info list
        client.get_subject_info()
    })
    $("#slider1").slider({
        max: 1,
        step: 0.1,
        value: 0.8,
        slide: function (event, ui) {
            client.detect_threshold = ui.value
        }
    });
    $("#slider2").slider({
        max: 1,
        step: 0.1,
        value: 0.8,
        slide: function (event, ui) {
            client.rec_threshold = ui.value
        }
    });

    $('#registerBbox').change(function () {
        if ($(this).prop('checked')) {
            client.register_bbox = true;
        } else {
            client.register_bbox = false;
            // reset register_image_count
            client.register_image_count = 0
        }
        client.active_subject_id = 'unset'
        // Set active_subject_id
        client.active_subject_name = $('#activeSubject')[0].value
        let xhr = new XMLHttpRequest();
        let method = resc_mgmt_server + '/get_subject_id/' + client.active_subject_name
        xhr.open('POST', method, true);
        xhr.onload = function () {
            if (this.status === 200) {
                client.active_subject_id = this.response
            }
        }
        xhr.send()
    })

    $('#recognizeCbox').change(function () {
        if ($(this).prop('checked')) {
            client.recognize_cbox = true;
        } else {
            client.recognize_cbox = false;
        }
    })

    $('#videoCtrlBtn').click(function () {
       let prevVal = this.innerHTML
        if (prevVal == 'Play') {
            this.innerHTML = 'Stop'
            client.do_face_detect = true;
            client.image_canvas.toBlob(client.post_file, 'image/jpeg');
        } else {
            this.innerHTML = 'Play'
            client.do_face_detect = false;
        }
    })

    $('#createBtn').click(function () {
        // check to see if the value is already in the subject list, if so, don't create new subject
        subj_name = $('#activeSubject').val()
        {
            client.create_subject(subj_name)
        }
    })

    $('#purgeBtn').click(function () {
        let this1 = this
        client.active_subject_name = $('#activeSubject')[0].value
        let xhr = new XMLHttpRequest();
        let method = resc_mgmt_server + '/get_subject_id/' + client.active_subject_name
        xhr.open('POST', method, true);
        xhr.onload = function () {
            if (this.status === 200) {
                client.active_subject_id = this.response
                    if (client.active_subject_id != 'unset') {
                        client.purge_subject(client.active_subject_id)
                    } else {
                        log.value += '\n' + client.active_subject_name + 'not found in database'
                        client.update_scroll(log)
                    }
            }
        }
        xhr.send()
    })

    $('#genEmbed').click(function () {
        let this1 = this
        let active_subj_name = $('#activeSubject')[0].value
        let xhr = new XMLHttpRequest();
        let method = resc_mgmt_server + '/get_subject_id/' + active_subj_name
        xhr.open('POST', method, true);
        xhr.onload = function () {
            if (this.status === 200) {
                active_subject_id = this.response
                if (active_subject_id != 'unset') {
                    client.generate_embedding(active_subject_id)
                } else {
                    log.value += '\n' + active_subj_name + 'not found in database'
                    client.update_scroll(log)
                }
            }
        }
        xhr.send()
    })
    return client;
}(Client || {}));