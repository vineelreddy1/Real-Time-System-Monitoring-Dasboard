from flask import Flask, jsonify
import psutil

app = Flask(__name__)

@app.route('/')
def index():
    return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>System Monitor</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #f5f5f5;
            margin: 0;
            padding: 0;
        }
        header {
            background-color: #222;
            color: white;
            text-align: center;
            padding: 1em 0;
        }
        .container {
            display: flex;
            flex-wrap: wrap;
            padding: 20px;
            justify-content: space-between;
        }
        .chart-box, .process-list, #alerts {
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.1);
            padding: 20px;
            margin: 10px;
            flex: 1;
            min-width: 300px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 10px;
            border-bottom: 1px solid #ddd;
        }
        th {
            background: #eee;
        }
        button {
            background: crimson;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 4px;
            cursor: pointer;
        }
        button:hover {
            background: darkred;
        }
        #alertList li {
            background: #ffe0e0;
            padding: 10px;
            margin-bottom: 5px;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <header><h1>System Monitoring Dashboard</h1></header>
    <div class="container">
        <div class="chart-box">
            <h2>CPU Usage</h2>
            <canvas id="cpuChart"></canvas>
        </div>
        <div class="chart-box">
            <h2>Memory Usage</h2>
            <canvas id="memoryChart"></canvas>
        </div>
        <div class="process-list">
            <h2>Top Processes</h2>
            <table>
                <thead>
                    <tr>
                        <th>PID</th>
                        <th>Name</th>
                        <th>CPU %</th>
                        <th>Memory %</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody id="processTable"></tbody>
            </table>
        </div>
        <div id="alerts">
            <h2>Alerts</h2>
            <ul id="alertList"></ul>
        </div>
    </div>

<script>
    const cpuCtx = document.getElementById('cpuChart').getContext('2d');
    const memoryCtx = document.getElementById('memoryChart').getContext('2d');

    const cpuChart = new Chart(cpuCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'CPU (%)',
                data: [],
                borderColor: 'blue',
                fill: false
            }]
        },
        options: { scales: { y: { min: 0, max: 100 } } }
    });

    const memoryChart = new Chart(memoryCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Memory (GB)',
                data: [],
                borderColor: 'green',
                fill: false
            }]
        },
        options: { scales: { y: { min: 0 } } }
    });

    function updateDashboard() {
        fetch('/metrics')
            .then(res => res.json())
            .then(data => {
                const now = new Date().toLocaleTimeString();
                cpuChart.data.labels.push(now);
                cpuChart.data.datasets[0].data.push(data.cpu);
                memoryChart.data.labels.push(now);
                memoryChart.data.datasets[0].data.push(data.memory_used);

                if (cpuChart.data.labels.length > 20) {
                    cpuChart.data.labels.shift();
                    cpuChart.data.datasets[0].data.shift();
                    memoryChart.data.labels.shift();
                    memoryChart.data.datasets[0].data.shift();
                }

                cpuChart.update();
                memoryChart.update();

                const tbody = document.getElementById('processTable');
                tbody.innerHTML = '';
                data.processes.forEach(proc => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${proc.pid}</td>
                        <td>${proc.name}</td>
                        <td>${proc.cpu.toFixed(2)}</td>
                        <td>${proc.memory.toFixed(2)}</td>
                        <td><button onclick="terminateProcess(${proc.pid})">Kill</button></td>
                    `;
                    tbody.appendChild(row);
                });

                if (data.cpu > 80) addAlert('High CPU usage: ' + data.cpu + '%');
                if ((data.memory_used / data.memory_total) > 0.9) {
                    addAlert('High Memory usage!');
                }
            });
    }

    function terminateProcess(pid) {
        if (confirm(`Are you sure to kill PID ${pid}?`)) {
            fetch(`/terminate/${pid}`, { method: 'POST' })
                .then(res => res.json())
                .then(resp => {
                    addAlert(resp.message);
                    updateDashboard();
                });
        }
    }

    function addAlert(msg) {
        const alertList = document.getElementById('alertList');
        const li = document.createElement('li');
        li.textContent = `${new Date().toLocaleTimeString()} - ${msg}`;
        alertList.prepend(li);
        if (alertList.children.length > 5) alertList.removeChild(alertList.lastChild);
    }

    updateDashboard();
    setInterval(updateDashboard, 2000);
</script>
</body>
</html>
'''

@app.route('/metrics')
def get_metrics():
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            processes.append({
                "pid": proc.info['pid'],
                "name": proc.info['name'],
                "cpu": proc.info['cpu_percent'],
                "memory": proc.info['memory_percent']
            })
        except psutil.NoSuchProcess:
            continue
    processes.sort(key=lambda x: x['cpu'], reverse=True)
    return jsonify({
        "cpu": cpu,
        "memory_used": memory.used / (1024 ** 3),
        "memory_total": memory.total / (1024 ** 3),
        "processes": processes[:10]
    })

@app.route('/terminate/<int:pid>', methods=['POST'])
def terminate_process(pid):
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        return jsonify({"status": "success", "message": f"Process {pid} terminated"})
    except psutil.NoSuchProcess:
        return jsonify({"status": "error", "message": "Process not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
