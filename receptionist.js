// ================================
// RECEPTIONIST DASHBOARD (BACKEND)
// ================================

const API_BASE = "http://127.0.0.1:5000";
const token = localStorage.getItem("token");

// 🔐 Login check
if (!token) {
  alert("Please login first");
  window.location.href = "login.html";
}

// ================================
// HELPER: TODAY DATE
// ================================
function getTodayDate() {
  return new Date().toISOString().split("T")[0];
}

// ================================
// UPDATE NOW SERVING TOKEN
// ================================
function updateNowServing() {
  const tokenNumber = document.getElementById("nowServingToken").value;

  if (!tokenNumber) {
    alert("Enter token number");
    return;
  }

  fetch(`${API_BASE}/set_now_serving`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + token
    },
    body: JSON.stringify({
      date: getTodayDate(),
      now_serving_token: parseInt(tokenNumber)
    })
  })
    .then(res => res.json())
    .then(data => {
      if (data.error) {
        alert(data.error);
      } else {
        document.getElementById("nowServingToken").value = "";
        loadLiveQueue();
      }
    })
    .catch(() => alert("Server error"));
}

// ================================
// MARK EMERGENCY
// ================================
function markEmergency() {
  const tokenNumber = document.getElementById("actionToken").value;

  if (!tokenNumber) {
    alert("Enter token number");
    return;
  }

  fetch(`${API_BASE}/mark_emergency`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + token
    },
    body: JSON.stringify({
      date: getTodayDate(),
      token_no: parseInt(tokenNumber)
    })
  })
    .then(res => res.json())
    .then(data => {
      if (data.error) {
        alert(data.error);
      } else {
        document.getElementById("actionToken").value = "";
        loadLiveQueue();
      }
    })
    .catch(() => alert("Server error"));
}

// ================================
// LOAD LIVE QUEUE (TABLE VERSION)
// ================================
function loadLiveQueue() {
  fetch(`${API_BASE}/get_live_queue?date=${getTodayDate()}`, {
    headers: {
      "Authorization": "Bearer " + token
    }
  })
    .then(res => res.json())
    .then(data => {

      const tableBody = document.getElementById("liveQueue");
      tableBody.innerHTML = "";

      if (!data.queue || data.queue.length === 0) {
        tableBody.innerHTML = `
          <tr>
            <td colspan="3" class="py-4 text-center text-gray-500">
              No tokens yet
            </td>
          </tr>
        `;
        return;
      }

      let emergencyCount = 0;
      let admittedCount = 0;

      data.queue.forEach(item => {

        if (item.priority === "emergency") emergencyCount++;
        if (item.status === "admitted") admittedCount++;

        // Status color
        let statusColor = "bg-gray-100 text-gray-600";

        if (item.status === "waiting")
          statusColor = "bg-yellow-100 text-yellow-700";

        if (item.status === "in_service")
          statusColor = "bg-green-100 text-green-700";

        if (item.status === "completed")
          statusColor = "bg-gray-200 text-gray-700";

        if (item.status === "admitted")
          statusColor = "bg-purple-100 text-purple-700";

        // Priority badge
        let priorityBadge = item.priority === "emergency"
          ? `<span class="px-2 py-1 text-xs rounded-full bg-red-100 text-red-600">Emergency</span>`
          : `<span class="px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-600">Normal</span>`;

        // Row highlight if admitted
        let rowClass = item.status === "admitted"
          ? "bg-gray-50"
          : "hover:bg-gray-50";

        const row = `
          <tr class="border-b ${rowClass}">
            <td class="py-3 font-medium">#${item.token_no}</td>
            <td class="py-3">
              <span class="px-3 py-1 text-xs rounded-full ${statusColor}">
                ${item.status.replace("_", " ")}
              </span>
            </td>
            <td class="py-3">${priorityBadge}</td>
          </tr>
        `;

        tableBody.innerHTML += row;
      });

      // Update Summary Cards
      document.getElementById("totalTokens").innerText = data.queue.length;
      document.getElementById("emergencyCount").innerText = emergencyCount;
      document.getElementById("admittedCount").innerText = admittedCount;
    })
    .catch(() => console.log("Queue load error"));
}

// ================================
// AUTO LOAD
// ================================
window.onload = function () {
  loadLiveQueue();
  setInterval(loadLiveQueue, 5000);
};
