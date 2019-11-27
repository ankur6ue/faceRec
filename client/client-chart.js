
var Client = (function (client) {
    var xVal = 0
    var dps1 = []
    var dataLength = 20; // number of dataPoints visible at any point
	var ctx = document.getElementById("chart");

	client.chart1 = new Chart(ctx, {
			type: 'line',
			data: {
				datasets: [{
						data: dps1,
						label: "compute",
						borderColor: "#3e95cd",
						fill: false
					}, {
						data: dps1,
						label: "network",
						borderColor: "#8e5ea2",
						fill: false
					}, {
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
								beginAtZero: true,
								suggestedMin: 0,
								suggestedMax: 500
							}
						}
					]
				}
			}
		});

	var count = 20
    for (var j = 0; j < count; j++) {
        yVal = 0
            dps1.push({
                x: xVal,
                y: yVal
            });
        xVal++;
    }
    client.chart1.update();

    client.update_charts = function(proc_time, rec_time, transmission_time)
    {
        this.chart1.data.labels.push(++xVal);
        this.chart1.data.datasets[0].data.push(proc_time);
        this.chart1.data.datasets[1].data.push(transmission_time);
        this.chart1.data.datasets[2].data.push(rec_time);
        this.chart1.data.labels = this.chart1.data.labels.splice(-dataLength);
        this.chart1.data.datasets[0].data = this.chart1.data.datasets[0].data.splice(-dataLength);
        this.chart1.data.datasets[1].data = this.chart1.data.datasets[1].data.splice(-dataLength);
        this.chart1.data.datasets[2].data = this.chart1.data.datasets[2].data.splice(-dataLength);

        this.chart1.update(0)
    }
	return client;
}(Client || {}));