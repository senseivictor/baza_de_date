<?php
if (isset($_GET['userId'])) {
    header('Content-Type: application/json; charset=utf-8');

    $userId = intval($_GET['userId']);

    try {
        $dbPath = __DIR__ . '/db.sqlite';
        if (!file_exists($dbPath)) {
            throw new Exception("Database file not found at $dbPath");
        }

        $db = new SQLite3(__DIR__ . 'db.sqlite');

        $result = $db->exec("
            SELECT
                tasks.task_id AS taskId,
                orders.order_public_id AS orderPublicId,
                tasks.task_type AS taskType,
                tasks.result_id AS resultId,
                tasks.created_at AS createdAt,
                tasks.task_status AS taskStatus
            FROM tasks
            INNER JOIN orders
                ON tasks.order_public_id = orders.order_public_id
            WHERE orders.user_id = :userId
        ");

        $data = [];
        while ($row = $result->fetchArray()) {
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

  <script>
    document.getElementById('searchBtn').addEventListener('click', async () => {
      const userId = document.getElementById('userId').value.trim();
      const resultBox = document.getElementById('result');
      
      if (!userId) {
        resultBox.textContent = "Vă rugăm să introduceți ID-ul utilizatorului.";
        return;
      }

      resultBox.textContent = "Se caută comenzile utilizatorului...";

      try {
        const response = await fetch(`?userId=${encodeURIComponent(userId)}`);
        if (!response.ok) throw new Error("Eroare la comunicarea cu serverul.");
        const data = await response.json();
        resultBox.textContent = JSON.stringify(data, null, 2);
      } catch (error) {
        resultBox.textContent = "A apărut o eroare: " + error.message;
      }
    });
  </script>
</body>
</html>
