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
var subjectId = "subject0"
var dps1 = []; 
var dps2 = [];// dataPoints
// for charts:
var xVal = 0;
var yVal = 100; 
var updateInterval = 1000;
var dataLength = 20; // number of dataPoints visible at any point
var do_face_detect = false
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
		//Set options as form data
		let formdata = new FormData();
		formdata.append("image", file);
		formdata.append("detectThreshold", detectThreshold);
		formdata.append("recThreshold", recThreshold);
		let xhr = new XMLHttpRequest();
		xhr.open('POST', apiServer + '/detect/' + procType + '/' + recognizeCbox + '/' + registerBbox + '/' + subjectId, true);
		var date = new Date()
		var send_t = date.getTime();
		xhr.onload = function () {
			if (this.status === 200) {
				var date = new Date()
				var recv_t = date.getTime(); 
				let object_data = JSON.parse(this.response);
				var log_text = ""
				// console.log(object_data['server_ip'])
				log_text += "server# " + object_data['server_ip']
				proc_time = object_data.proc_end_time - object_data.proc_start_time
				rec_time = object_data.rec_time*1000
				transmission_time = recv_t - send_t - proc_time*1000
				fps = 1.0/proc_time
				log_text += "\n" + "FPS: " + fps
				/*
				dps1.push({
					x: xVal,
					y: proc_time*1000
				});
				dps2.push({
					x: xVal,
					y: transmission_time
				});
				dps1.shift();
				dps2.shift();
				*/
				xVal++;
				
				chart1.data.labels.push(xVal);
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
					console.log(object_data['cpu_util'])
					log_text += "\n" + "CPU Util: " + object_data['cpu_util']
				}
				//$("#log").val(log_text);
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
	
	//xhr.send();
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
	var method = rescMgmtServer + '/getCount' + '/' + dbName + '/' + collectionName + '/' + subjectNum
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
		+ "<a role='menuitem'  href='#'>" + subjectData[i].name + "</a>" + "</li>"
		dropdown.append(str);
	}      
	$('.ExampleCaptionDropDownListItem').click(function(e) {
		var target = e.currentTarget;
		var name = target.getAttribute("data-name")
		var id = target.getAttribute("data-id")
		console.log(name);
		console.log(_this.subjectId)
		_this.subjectId = 'subjectId' + id
		$('#activeSubject').val(name);
	});
	
}

function getSubjectInfo()
{
	let xhr = new XMLHttpRequest();
	var dbName = 'subjects'
	var collectionName = 'name_id_map'
	var method = rescMgmtServer + '/getSubjectInfo' + '/' + dbName + '/' + collectionName
    xhr.open('POST', method, true);
	xhr.onload = function () {
        if (this.status === 200) {
			let subjectData = JSON.parse(this.response);
			PopulateSubjectDropdown(subjectData)
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
	} // enable wireframe on all models
	else {
		registerBbox = false;
	}
})
$('#recognizeCbox').change(function () {
	if ($(this).prop('checked')) {
		recognizeCbox = true;
	} // enable wireframe on all models
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
// uncheck register checkbox
$('#registerBbox').prop('checked', false);
// uncheck recognize checkbox
$('#recognizeCbox').prop('checked', false);
getSubjectCount()
getSubjectInfo()


/*

document.addEventListener("DOMContentLoaded", function() {
	$('#ProcList').append($('<option>', {value:"cpu", text:"CPU"}));
	$('#ProcList').append($('<option>', {value:"gpu", text:"GPU"}));
}, false);

$('#ProcList').change(function(){ 
    procType = $(this).val();
	
});
*/
