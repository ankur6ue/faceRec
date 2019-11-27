/**
 * Client side of PyTorch Detection Web API
 * Initial version taken from webrtcHacks - https://webrtchacks.com
 */



//Parameters
const s = document.getElementById('faceRec');
const sourceVideo = s.getAttribute("data-source");  //the source video to use
const uploadWidth = s.getAttribute("data-uploadWidth") || 640; //the width of the upload file
const mirror = s.getAttribute("data-mirror") || false; //mirror the boundary boxes
var detectThreshold = s.getAttribute("data-detectThreshold") || 0.8;
var recThreshold = s.getAttribute("data-recThreshold") || 0.8;
const hostType = s.getAttribute("data-apiServer")
const ovWidth = 320
const ovHeight = 240


var procType = "gpu"
var registerBbox = false
var recognizeCbox = false
var subject_id = ""
var dps1 = []; 
var dps2 = [];// dataPoints
// for charts:
var xVal = 0;
var yVal = 100; 
var updateInterval = 1000;
var dataLength = 20; // number of dataPoints visible at any point
var do_face_detect = false
var log = $("#my-console")[0]
var activeSubjName = $('#activeSubject')[0]
var registerImageCount = 0
var activeSubjectId = "unset" // indicates that activeSubject is not set
// Reset initial values
log.value = ""
activeSubjName.value = ""

if (hostType == 'localhost')
{
	apiServer = "http://127.0.0.1:5000" // must be just like this. using 0.0.0.0 for the IP doesn't work! 
	rescMgmtServer = "https://telesens.co/res_mgmt"
}
else
{
	apiServer = "https://telesens.co/face_det"
	rescMgmtServer = "https://telesens.co/res_mgmt"
}

//Video element selector
v = document.getElementById(sourceVideo);

//for starting events
let isPlaying = false,
    gotMetadata = false;

//Canvas setup

//create a canvas to grab an image for upload
let imageCanvas = document.createElement('canvas');
let imageCtx = imageCanvas.getContext("2d");

//create a canvas for drawing object boundaries
let drawCanvas = document.getElementById('drawCanvas');
let drawCtx = drawCanvas.getContext("2d");

function UpdateScroll(log)
{
    log.scrollTop = log.scrollHeight
}
//draw boxes and labels on each detected object
function drawBoxes(objects) {

    //clear the previous drawings
    drawCtx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);

    //filter out objects that contain a class_name and then draw boxes and labels on each
    objects.filter(object => object.class_name).forEach(object => {
		
		var rect = drawCanvas.getBoundingClientRect(), // abs. size of element
		scaleX = drawCanvas.width / rect.width,    // relationship bitmap vs. element for X
		scaleY = drawCanvas.height / rect.height;  // relationship bitmap vs. element for Y

        let x = 2*object.x;
        let y = 2*object.y;
        let width = 2*(object.width);
        let height = 2*(object.height);

        //flip the x axis if local video is mirrored
        if (mirror) {
            x = drawCanvas.width - (x + width)
        }
		drawCtx.font = "20px Verdana";
        drawCtx.fillText(object.class_name + " - " + Math.round(object.score * 100) + "%" , x + 5, y-30)
		
		if (recognizeCbox && 'recScore' in object)
		{
			drawCtx.font = "15px Verdana";
			drawCtx.fillStyle = "#00ff00";
			drawCtx.fillText(object.id, x-5, y - 10);
			drawCtx.fillText("score: " + object.recScore.toFixed(2), x+5, y + 20) 
			drawCtx.fillText("margin: " + object.recMargin.toFixed(2), x+5, y + 40)
			
		}
		drawCtx.strokeRect(x, y, width, height);
        // Now draw landmarks
        landmarks = object.landmarks
        landmarks.forEach(landmark => {
            let x = 2*landmark.x - 5;
            let y = 2*landmark.y - 5;   
            //flip the x axis if local video is mirrored
            if (mirror) {
                x = drawCanvas.width - (x + 10)
            }
            drawCtx.strokeRect(x, y, 10, 10);
        });

    });
}

//Add file blob to a form and post
function postFile(file) {

	if (do_face_detect)
	{
		// The FormData interface provides a way to easily construct a set of key/value pairs representing form fields
		// and their values, which can then be easily sent using the XMLHttpRequest.send() method.
		// It uses the same format a form would use if the encoding type were set to "multipart/form-data".
		// See https://developer.mozilla.org/en-US/docs/Web/API/FormData
		let formdata = new FormData();
		formdata.append("image", file); // Image data
		formdata.append("detectThreshold", detectThreshold); // face detection threshold
		formdata.append("recThreshold", recThreshold); // face recognition threshold
		let xhr = new XMLHttpRequest();
		/*
		procType: processor type we wish to run our system on (CPU/GPU). Cluster mgmt system can use this info to
		     direct request to the appropriate worked node that supports requested HW
		recognizeCbox: should we perform recognition or not
		registerBbox: should the face crops be saved to a database for generating embeddings later. USed to register
		     new subjects
		activeSubjectId: the subject_id of the current subject. Used during registration.
		*/
		xhr.open('POST', apiServer + '/detect/' + procType + '/' + recognizeCbox + '/' + registerBbox + '/' + activeSubjectId, true);
		var date = new Date()
		var send_t = date.getTime();
		xhr.onload = function () {
			if (this.status === 200) {
				var date = new Date()
				var recv_t = date.getTime();
				// object_data is a nested dictionary of the information returned by the face detection/recognition
				// system
				let object_data = JSON.parse(this.response);
				var log_text = ""
				// console.log(object_data['server_ip'])
				log_text += "server# " + object_data['server_ip']
				proc_time = object_data.proc_end_time - object_data.proc_start_time
				rec_time = object_data.rec_time*1000
				transmission_time = recv_t - send_t - proc_time*1000
				fps = 1.0/proc_time

				// If in register mode, inform the user how many images have been collected
				if (registerBbox && activeSubjectId != "unset")
				{
				    log.value += '\n' + 'registering image ' + ++registerImageCount + ' of subject: ' + activeSubjName.value
				    UpdateScroll(log)
				}
				// Update running graphs
				chart1.data.labels.push(++xVal);
				chart1.data.datasets[0].data.push(proc_time*1000);
				chart1.data.datasets[1].data.push(transmission_time);
				chart1.data.datasets[2].data.push(rec_time);
				chart1.data.labels = chart1.data.labels.splice(-dataLength);
				chart1.data.datasets[0].data = chart1.data.datasets[0].data.splice(-dataLength);
				chart1.data.datasets[1].data = chart1.data.datasets[1].data.splice(-dataLength);
				chart1.data.datasets[2].data = chart1.data.datasets[2].data.splice(-dataLength);
				chart1.update(0)
				
				if ('cpu_util' in object_data)
				{
				    var txt = log.value
				    // log.value = txt + object_data['cpu_util'] + "\n"
				    // log.scrollTop = log.scrollHeight
				}

				//draw the boxes
				drawBoxes(object_data.objects);

				//Save and send the next image
				imageCtx.drawImage(v, 0, 0, v.videoWidth, v.videoHeight, 0, 0, ovWidth, ovHeight );
				imageCanvas.toBlob(postFile, 'image/jpeg');
			}
			else {
				console.error(xhr);
			}
		};
		xhr.send(formdata);
	}
}

//Start object detection
function startObjectDetection() {

    console.log("starting Face Recognition");
    
    //Set canvas sizes based on input video
    drawCanvas.width = v.videoWidth;
    drawCanvas.height = v.videoHeight;

    imageCanvas.width = ovWidth;
    imageCanvas.height = ovHeight;

    //Some styles for the drawcanvas
    drawCtx.lineWidth = 4;
    drawCtx.strokeStyle = "cyan";
    drawCtx.font = "20px Verdana";
    drawCtx.fillStyle = "cyan";

    //Save and send the first image
    imageCtx.drawImage(v, 0, 0, v.videoWidth, v.videoHeight, 0, 0, ovWidth, ovHeight);
    let xhr = new XMLHttpRequest();
	var method = apiServer + '/init'
    xhr.open('GET', method, true);
	xhr.onload = function () {
        if (this.status === 200) {
			imageCanvas.toBlob(postFile, 'image/jpeg');
		}
	};
	xhr.send()

}

function getSubjectCount()
{
	let xhr = new XMLHttpRequest();
	var dbName = 'faces'
	var collectionName = 'faces'
	var subjectNum = 1
	var method = rescMgmtServer + '/getCount' + '/' + subjectNum
    xhr.open('POST', method, true);
	xhr.onload = function () {
        if (this.status === 200) {
			let data = JSON.parse(this.response);
		}
	}
	xhr.send()
}

function PopulateSubjectDropdown(subjectData)
{
	var dropdown = $(".dropdown-menu.subjects");
	$(".dropdown-menu.subjects").empty();
	var _this = this
	for( var i = 0; i < subjectData.length; i++ )
	{ 
		str = "<li class='list-item ExampleCaptionDropDownListItem' data-name='" + subjectData[i].name + 
		"' data-id=" + subjectData[i].id + ">"
		+ "<a role='menuitem'  href='#'>" + subjectData[i].name + ": " + subjectData[i].count + "</a>" + "</li>"
		dropdown.append(str);
	}      
	$('.ExampleCaptionDropDownListItem').click(function(e) {
		var target = e.currentTarget;
		var name = target.getAttribute("data-name")
		var id = target.getAttribute("data-id")
		log.value += '\n' + 'new active subject: ' + name
		UpdateScroll(log)
		_this.activeSubjectId = 'subject_id' + id
		$('#activeSubject')[0].value = name;
	});
	
}

function getSubjectInfo()
{
	let xhr = new XMLHttpRequest();
	var method = rescMgmtServer + '/getSubjectInfo'
    xhr.open('POST', method, true);
	xhr.onload = function () {
        if (this.status === 200) {
			let subjectData = JSON.parse(this.response);
			PopulateSubjectDropdown(subjectData)
		}
	}
	xhr.send()
}

function createSubject(subjName)
{
    var this1 = this
    let xhr = new XMLHttpRequest();
	var method = rescMgmtServer + '/createSubject/' + subjName
    xhr.open('POST', method, true);
	xhr.onload = function () {
        if (this.status === 200) {
			response = JSON.parse(this.response);
			log.value +=  '\n' + JSON.stringify(response)
            UpdateScroll(log)
			// Refresh the subject_info listbox
			this1.getSubjectInfo()
		}
	}
	xhr.send()
}

function generateEmbedding(subjId)
{
    var this1 = this
    let xhr = new XMLHttpRequest();
	var method = rescMgmtServer + '/generateEmbedding/' + subjId + '/cpu' + '/' + 160 + '/' + 60
    xhr.open('POST', method, true);
	xhr.onload = function () {
        if (this.status === 200) {
			log.value += '\n' + this.response
			UpdateScroll(log)
		}
	}
	xhr.send()
}

function purgeSubject(subjId)
{
    var this1 = this
    let xhr = new XMLHttpRequest();
	var method = rescMgmtServer + '/purgeSubject/' + subjId
    xhr.open('POST', method, true);
	xhr.onload = function () {
        if (this.status === 200) {
			log.value += '\n' + this.response
			UpdateScroll(log)
		}
	}
	xhr.send()
}
//Starting events

//check if metadata is ready - we need the video size
v.onloadedmetadata = () => {
    console.log("video metadata ready");
    gotMetadata = true;
    if (isPlaying)
	{
        startObjectDetection();
	}
};

//see if the video has started playing
v.onplaying = () => {
    console.log("video playing");
    isPlaying = true;
    if (gotMetadata) {
        startObjectDetection();
    }
};
var ctx = document.getElementById("chart");
var chart1 = new Chart(ctx, {
  type: 'line',
  data: {
    datasets: [
		{ 
		data: dps1,
		label: "compute",
		borderColor: "#3e95cd",
		fill: false
		},
		{ 
		data: dps1,
		label: "network",
		borderColor: "#8e5ea2",
		fill: false
		},
		{ 
		data: dps1,
		label: "recognize",
		borderColor: "#00ea00",
		fill: false
		}
	   ]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
        yAxes: [{
            ticks: {
                beginAtZero:true,
				suggestedMin: 0,
				suggestedMax: 500
				}
			}]
		}
	}
});



var count = 20
//setInterval(function(){chart1.update()}, 100);

for (var j = 0; j < count; j++) {
		yVal = 0
		dps1.push({
			x: xVal,
			y: yVal
		});
		xVal++;
	}
chart1.update();


	
var this1 = this;

$('#subjectsDropdownList').on('show.bs.dropdown', function () {
    // Refresh subject info list
    getSubjectInfo()
})
$("#slider1").slider({
	max: 1,
	step: 0.1,
	value: 0.8,
	slide: function (event, ui) {
		detectThreshold = ui.value
	}
});
$("#slider2").slider({
	max: 1,
	step: 0.1,
	value: 0.8,
	slide: function (event, ui) {
		recThreshold = ui.value
	}
});

$('#registerBbox').change(function () {
	if ($(this).prop('checked')) {
		registerBbox = true;
	}
	else {
		registerBbox = false;
		// reset registerImageCount
		registerImageCount = 0
	}
	activeSubjectId = 'unset'
    // Set activeSubjectId
    var activeSubjName = $('#activeSubject')[0].value
    let xhr = new XMLHttpRequest();
    var method = rescMgmtServer + '/getSubjectId/' + activeSubjName
    xhr.open('POST', method, true);
    xhr.onload = function () {
        if (this.status === 200) {
            activeSubjectId = this.response
        }
    }
    xhr.send()
})

$('#recognizeCbox').change(function () {
	if ($(this).prop('checked')) {
		recognizeCbox = true;
	}
	else {
		recognizeCbox = false;
	}
})

$('#videoCtrlBtn').click(function() {
	prevVal = this.innerHTML
	if (prevVal == 'Play')
	{
		this.innerHTML = 'Stop'
		do_face_detect = true;
		imageCanvas.toBlob(postFile, 'image/jpeg');
	}
	else
	{
		this.innerHTML = 'Play'
		do_face_detect = false;
	}
})

$('#createBtn').click(function() {
	subjName = $('#activeSubject').val()
	// check to see if the value is already in the subject list, if so, don't create new subject
	{
		createSubject(subjName)
	}
})
$('#purgeBtn').click(function() {
    var this1 = this
    var activeSubjName = $('#activeSubject')[0].value
    let xhr = new XMLHttpRequest();
	var method = rescMgmtServer + '/getSubjectId/' + activeSubjName
    xhr.open('POST', method, true);
	xhr.onload = function () {
        if (this.status === 200) {
            activeSubjectId = this.response
            if (activeSubjectId != 'unset')
            {
                purgeSubject(activeSubjectId)
            }
            else
            {
                log.value +=  '\n' + activeSubjName + 'not found in database'
                UpdateScroll(log)
            }
		}
	}
	xhr.send()
})

$('#genEmbed').click(function() {
    var this1 = this
    var activeSubjName = $('#activeSubject')[0].value
    let xhr = new XMLHttpRequest();
	var method = rescMgmtServer + '/getSubjectId/' + activeSubjName
    xhr.open('POST', method, true);
	xhr.onload = function () {
        if (this.status === 200) {
            activeSubjectId = this.response
            if (activeSubjectId != 'unset')
            {
                generateEmbedding(activeSubjectId)
            }
            else
            {
                log.value +=  '\n' + activeSubjName + 'not found in database'
                UpdateScroll(log)
            }
		}
	}
	xhr.send()
})

// uncheck register checkbox
$('#registerBbox').prop('checked', false);
// uncheck recognize checkbox
$('#recognizeCbox').prop('checked', false);
getSubjectCount()
getSubjectInfo()

