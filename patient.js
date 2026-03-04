// ================================
// PATIENT DASHBOARD (FINAL CLEAN VERSION)
// ================================

const API_BASE = "http://127.0.0.1:5000";
const token = localStorage.getItem("token");

// 🔐 Protect Route
if (!token) {
  window.location.href = "login.html";
}

// ----------------------------
// Helper: Today's Date
// ----------------------------
function today() {
  return new Date().toISOString().split("T")[0];
}

// =============================
// ON LOAD
// =============================
window.onload = () => {

  const dateInput = document.getElementById("appointmentDate");
  if (dateInput) dateInput.value = today();

  loadDashboardData();
  loadPatientOPDStatus();
  loadPatientHistory();

  // Enter key support for chatbot
  const chatInput = document.getElementById("chatInput");
  if (chatInput) {
    chatInput.addEventListener("keydown", function(e) {
      if (e.key === "Enter") {
        e.preventDefault();
        sendMessage();
      }
    });
  }
};

// =============================
// LOAD DASHBOARD DATA
// =============================
function loadDashboardData() {

  fetch(`${API_BASE}/get_live_queue?date=${today()}`, {
    headers: { "Authorization": "Bearer " + token }
  })
  .then(res => res.json())
  .then(data => {

    if (!data.queue) return;

    document.getElementById("totalOpd").innerText =
      data.queue.length;

    const nowServing = data.now_serving_token || 0;

    document.getElementById("nowServing").innerText =
      nowServing === 0 ? "--" : nowServing;

    updateMyToken(data.queue);

  })
  .catch(() => console.log("Dashboard load error"));
}

// =============================
// LOAD OPD STATUS
// =============================
function loadPatientOPDStatus() {

  fetch(`${API_BASE}/get_opd_status`)
  .then(res => res.json())
  .then(data => {

    const badge = document.getElementById("patientOpdStatus");
    if (!badge) return;

    if (data.status === "closed") {
      badge.innerText = "CLOSED";
      badge.className =
        "inline-block mt-3 px-4 py-1 rounded-full text-sm font-medium bg-red-100 text-red-600";
    } else {
      badge.innerText = "OPEN";
      badge.className =
        "inline-block mt-3 px-4 py-1 rounded-full text-sm font-medium bg-green-100 text-green-600";
    }

  })
  .catch(() => console.log("OPD status load error"));
}

// =============================
// BOOK APPOINTMENT
// =============================
function bookAppointment() {

  const name = document.getElementById("patientName").value.trim();
  const age = document.getElementById("patientAge").value.trim();
  const department = document.getElementById("department").value;
  const date = document.getElementById("appointmentDate").value;
  const messageBox = document.getElementById("appointmentMessage");

  messageBox.innerText = "";

  if (!name || !age || !department || !date) {
    messageBox.innerText = "Please fill all fields.";
    messageBox.className = "mt-4 text-sm text-red-600";
    return;
  }

  fetch(`${API_BASE}/add_appointment`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + token
    },
    body: JSON.stringify({ department, date })
  })
  .then(async (res) => {
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to book");
    return data;
  })
  .then(data => {

    messageBox.innerText =
      `Appointment booked successfully. Token No: ${data.token_no}`;
    messageBox.className = "mt-4 text-sm text-green-600";

    document.getElementById("myToken").innerText =
      data.token_no;

    loadDashboardData();

  })
  .catch(err => {
    messageBox.innerText = err.message;
    messageBox.className = "mt-4 text-sm text-red-600";
  });
}

// =============================
// UPDATE TOKEN STATUS
// =============================
function updateMyToken(queue) {

  const myToken =
    document.getElementById("myToken").innerText;

  if (!myToken || myToken === "--") return;

  const found =
    queue.find(q => String(q.token_no) === myToken);

  if (!found) return;

  setStatusBadge(found.status);

  document.getElementById("estimatedWait").innerText =
    found.estimated_waiting_time_min + " min";
}

// =============================
// STATUS BADGE UI
// =============================
function setStatusBadge(status) {

  const badge = document.getElementById("tokenStatus");
  if (!badge) return;

  badge.className = "text-sm mt-2 font-medium";

  if (status === "waiting") {
    badge.innerText = "Waiting";
    badge.classList.add("text-yellow-600");
  }
  else if (status === "in_service") {
    badge.innerText = "In Service";
    badge.classList.add("text-green-600");
  }
  else if (status === "completed") {
    badge.innerText = "Completed";
    badge.classList.add("text-gray-500");
  }
  else if (status === "admitted") {
    badge.innerText = "Admitted";
    badge.classList.add("text-blue-600");
  }
}

// =============================
// LOAD PATIENT HISTORY
// =============================
function loadPatientHistory() {

  fetch(`${API_BASE}/patient_history`, {
    headers: { "Authorization": "Bearer " + token }
  })
  .then(res => res.json())
  .then(data => {

    const table =
      document.getElementById("historyTable");
    table.innerHTML = "";

    if (!data.history || data.history.length === 0) {
      table.innerHTML = `
        <tr>
          <td colspan="5"
            class="py-4 text-center text-gray-500">
            No history found
          </td>
        </tr>`;
      return;
    }

    data.history.forEach(item => {

      let statusColor = "text-gray-600";

      if (item.status === "waiting")
        statusColor = "text-yellow-600";

      if (item.status === "in_service")
        statusColor = "text-green-600";

      if (item.status === "admitted")
        statusColor = "text-blue-600";

      table.innerHTML += `
        <tr class="border-b">
          <td class="py-3">${item.date}</td>
          <td class="py-3 font-medium">
            #${item.token_no}
          </td>
          <td class="py-3">${item.department}</td>
          <td class="py-3 ${statusColor}">
            ${item.status.replace("_"," ")}
          </td>
          <td class="py-3">
            <button onclick="downloadReport(${item.token_no}, '${item.date}')"
              class="text-blue-600 text-sm hover:underline">
              Download
            </button>
          </td>
        </tr>`;
    });

  })
  .catch(() => console.log("History load error"));
}

// =============================
// DOWNLOAD REPORT
// =============================
function downloadReport(token_no, date) {

  fetch(`${API_BASE}/download_report?token_no=${token_no}&date=${date}`, {
    headers: { "Authorization": "Bearer " + token }
  })
  .then(res => res.blob())
  .then(blob => {

    const link = document.createElement("a");
    link.href = window.URL.createObjectURL(blob);
    link.download = "visit_report.pdf";
    link.click();

  })
  .catch(() => alert("Report download failed"));
}

// =============================
// CHATBOT
// =============================
function sendMessage() {

  const input = document.getElementById("chatInput");
  const chatBox = document.getElementById("chatBox");

  const message = input.value.trim();
  if (!message) return;

  // User Bubble
  chatBox.innerHTML += `
    <div class="flex justify-end mb-2">
      <div class="bg-blue-600 text-white px-3 py-2 rounded-lg text-sm max-w-[70%]">
        ${message}
      </div>
    </div>`;

  input.value = "";
  chatBox.scrollTop = chatBox.scrollHeight;

  fetch(`${API_BASE}/chatbot`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + token
    },
    body: JSON.stringify({ message })
  })
  .then(res => res.json())
  .then(data => {

    chatBox.innerHTML += `
      <div class="flex justify-start mb-2">
        <div class="bg-gray-200 text-gray-800 px-3 py-2 rounded-lg text-sm max-w-[70%]">
          ${data.reply}
        </div>
      </div>`;

    chatBox.scrollTop = chatBox.scrollHeight;

  })
  .catch(() => {
    chatBox.innerHTML += `
      <div class="text-red-600 text-sm">
        Assistant unavailable.
      </div>`;
  });
}

// Toggle Chat
function toggleChat() {

  const widget =
    document.getElementById("chatWidget");
  const floatingBtn =
    document.getElementById("chatFloatingBtn");

  widget.classList.toggle("hidden");

  if (!widget.classList.contains("hidden")) {
    floatingBtn.classList.add("hidden");
  } else {
    floatingBtn.classList.remove("hidden");
  }
}

// =============================
// LOGOUT
// =============================
function logout() {
  localStorage.clear();
  window.location.href = "login.html";
}

// =============================
// AUTO REFRESH
// =============================
setInterval(() => {
  loadDashboardData();
  loadPatientOPDStatus();
  loadPatientHistory();
}, 10000);