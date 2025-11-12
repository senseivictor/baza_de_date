<?php
if (isset($_GET['userId'])) {
    header('Content-Type: application/json; charset=utf-8');

    $userId = intval($_GET['userId']);

    try {
        $dbPath = __DIR__ . '/lab1.db';
        if (!file_exists($dbPath)) {
            throw new Exception("Database file not found at $dbPath");
        }

        $db = new SQLite3($dbPath);

        $stmt = $db->prepare("
            SELECT order_id, order_public_id, order_status, products, created_at
            FROM orders
            WHERE user_id = :user_id
        ");
        $stmt->bindValue(':user_id', $userId, SQLITE3_INTEGER);

        $result = $stmt->execute();

        $data = [];
        while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
            // Convert timestamp to readable date for graph grouping
            $row['date'] = date('Y-m-d', $row['created_at']);
            $data[] = $row;
        }

        echo json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
    } catch (Exception $e) {
        echo json_encode(['error' => $e->getMessage()]);
    }

    exit;
}
?>

<!DOCTYPE html>
<html lang="ro">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Caută Comenzi Utilizator</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body {
      font-family: Arial, sans-serif;
      padding: 30px;
      background: #f9f9f9;
    }
    .search-box {
      display: flex;
      flex-direction: column;
      gap: 10px;
      max-width: 400px;
      margin-bottom: 20px;
    }
    input {
      padding: 10px;
      font-size: 16px;
      border: 1px solid #ccc;
      border-radius: 6px;
    }
    button {
      padding: 10px 20px;
      font-size: 16px;
      background-color: #007bff;
      color: white;
      border: none;
      border-radius: 6px;
      cursor: pointer;
    }
    button:hover {
      background-color: #0056b3;
    }
    #result {
      background: white;
      padding: 15px;
      border-radius: 6px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      white-space: pre-wrap;
      margin-bottom: 30px;
    }
    canvas {
      max-width: 600px;
      max-height: 200px;
    }
  </style>
</head>
<body>
  <h2>Caută Comenzi Utilizator</h2>
  <div class="search-box">
    <input type="number" id="userId" placeholder="Introduceți ID-ul utilizatorului">
    <button id="searchBtn">Caută</button>
  </div>

  <div id="result"></div>
  <canvas id="ordersChart"></canvas>

  <script>
    const resultBox = document.getElementById('result');
    const chartCanvas = document.getElementById('ordersChart');
    let ordersChart = null;

    document.getElementById('searchBtn').addEventListener('click', async () => {
      const userId = document.getElementById('userId').value.trim();
      
      if (!userId) {
        resultBox.textContent = "Vă rugăm să introduceți ID-ul utilizatorului.";
        return;
      }

      resultBox.textContent = "Se caută comenzile utilizatorului...";
      chartCanvas.style.display = "none";

      try {
        const response = await fetch(`?userId=${encodeURIComponent(userId)}`);
        if (!response.ok) throw new Error("Eroare la comunicarea cu serverul.");
        const data = await response.json();

        resultBox.textContent = JSON.stringify(data, null, 2);

        const dateCounts = {};
        data.forEach(order => {
          const date = order.date || "Necunoscut";
          dateCounts[date] = (dateCounts[date] || 0) + 1;
        });

        const labels = Object.keys(dateCounts);
        const values = Object.values(dateCounts);

        if (labels.length === 0) {
          resultBox.textContent += "\n\nNu există comenzi pentru acest utilizator.";
          return;
        }

        chartCanvas.style.display = "block";

        if (ordersChart) {
          ordersChart.destroy();
        }

      ordersChart = new Chart(chartCanvas, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: 'Număr comenzi pe dată',
            data: values,
            backgroundColor: '#007bff88',
            borderColor: '#007bff',
            borderWidth: 1
          }]
        },
        options: {
          responsive: true,
          scales: {
            y: {
              beginAtZero: true,
              ticks: {
                stepSize: 1,
                callback: function(value) {
                  if (Number.isInteger(value)) {
                    return value;
                  }
                  return '';
                }
              },
              title: {
                display: true,
                text: 'Număr comenzi'
              }
            },
            x: {
              title: {
                display: true,
                text: 'Data comenzii'
              }
            }
          }
        }
      });


      } catch (error) {
        resultBox.textContent = "A apărut o eroare: " + error.message;
      }
    });
  </script>
</body>
</html>
