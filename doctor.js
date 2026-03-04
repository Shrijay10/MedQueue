// ================================
// DOCTOR DASHBOARD (FINAL CLEAN)
// ================================

const API_BASE = "http://127.0.0.1:5000";
const token = localStorage.getItem("token");

if (!token) {
  alert("Please login first");
  window.location.href = "login.html";
}

// ----------------------------
// Helper: Today Date
// ----------------------------
function today() {
  return new Date().toISOString().split("T")[0];
}

// =============================
// LOAD DOCTOR SUMMARY
// =============================
function loadDoctorSummary() {

  fetch(`${API_BASE}/doctor_summary?date=${today()}`, {
    headers: { Authorization: "Bearer " + token }
  })
    .then(res => res.json())
    .then(data => {

      document.getElementById("dTodayOPD").innerText =
        data.total_opd || 0;

      document.getElementById("dEmergency").innerText =
        data.emergency || 0;

      document.getElementById("dAppointments").innerText =
        data.admitted || 0;

      // Also sync doctor status dropdown
      if (data.doctor_status) {
        document.getElementById("doctorStatus").value =
          data.doctor_status;
      }

    })
    .catch(() => console.log("Summary load error"));
}

// =============================
// LOAD LIVE QUEUE
// =============================
function loadDoctorQueue() {

  fetch(`${API_BASE}/get_live_queue?date=${today()}`, {
    headers: { Authorization: "Bearer " + token }
  })
    .then(res => res.json())
    .then(data => {

      const tableBody = document.getElementById("doctorQueue");
      tableBody.innerHTML = "";

      if (!data.queue || data.queue.length === 0) {
        tableBody.innerHTML = `
          <tr>
            <td colspan="3" class="py-4 text-center text-gray-500">
              No queue data
            </td>
          </tr>
        `;
        return;
      }

      data.queue.forEach(item => {

        let statusColor = "bg-gray-100 text-gray-600";

        if (item.status === "waiting")
          statusColor = "bg-yellow-100 text-yellow-700";

        if (item.status === "in_service")
          statusColor = "bg-green-100 text-green-700";

        if (item.status === "completed")
          statusColor = "bg-gray-200 text-gray-700";

        if (item.status === "admitted")
          statusColor = "bg-purple-100 text-purple-700";

        const priorityBadge =
          item.priority === "emergency"
            ? `<span class="px-2 py-1 text-xs rounded-full bg-red-100 text-red-600">Emergency</span>`
            : `<span class="px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-600">Normal</span>`;

        tableBody.innerHTML += `
          <tr class="border-b hover:bg-gray-50">
            <td class="py-3 font-medium">#${item.token_no}</td>
            <td class="py-3">
              <span class="px-3 py-1 text-xs rounded-full ${statusColor}">
                ${item.status.replace("_", " ")}
              </span>
            </td>
            <td class="py-3">${priorityBadge}</td>
          </tr>
        `;
      });

    })
    .catch(() => console.log("Queue load error"));
}

// =============================
// MARK PATIENT AS ADMITTED
// =============================
function markAdmitted() {

  const tokenNo = document.getElementById("admitToken").value;

  if (!tokenNo) {
    alert("Enter token number");
    return;
  }

  fetch(`${API_BASE}/mark_admitted`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + token
    },
    body: JSON.stringify({
      token_no: parseInt(tokenNo),
      date: today()
    })
  })
    .then(res => res.json())
    .then(data => {

      if (data.error) {
        alert(data.error);
        return;
      }

      document.getElementById("admitToken").value = "";

      loadDoctorQueue();
      loadDoctorSummary();
      loadAdmissionHistory();

    })
    .catch(() => alert("Server error"));
}

// =============================
// OPD STATUS
// =============================
function loadOPDStatus() {

  fetch(`${API_BASE}/get_opd_status`)
    .then(res => res.json())
    .then(data => {

      const badge = document.getElementById("opdStatusBadge");
      if (!badge) return;

      if (data.status === "closed") {
        badge.innerText = "CLOSED";
        badge.className =
          "px-4 py-1 rounded-full text-sm font-medium bg-red-100 text-red-600";
      } else {
        badge.innerText = "OPEN";
        badge.className =
          "px-4 py-1 rounded-full text-sm font-medium bg-green-100 text-green-600";
      }

    })
    .catch(() => console.log("OPD status load error"));
}

function setOPDStatus(status) {

  fetch(`${API_BASE}/set_opd_status`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + token
    },
    body: JSON.stringify({ status })
  })
    .then(res => res.json())
    .then(data => {

      if (data.error) {
        alert(data.error);
        return;
      }

      loadOPDStatus();

    })
    .catch(() => alert("Server error"));
}

// =============================
// LOAD ADMISSION HISTORY
// =============================
function loadAdmissionHistory() {

  fetch(`${API_BASE}/admission_history?date=${today()}`, {
    headers: { Authorization: "Bearer " + token }
  })
    .then(res => res.json())
    .then(data => {

      const list = document.getElementById("admissionList");
      list.innerHTML = "";

      if (!data.admitted_patients ||
          data.admitted_patients.length === 0) {

        list.innerHTML =
          "<li class='text-gray-500'>No admitted patients</li>";
        return;
      }

      data.admitted_patients.forEach(item => {

        const priorityBadge =
          item.priority === "emergency"
            ? "<span class='text-red-600 text-xs'>Emergency</span>"
            : "<span class='text-blue-600 text-xs'>Normal</span>";

        list.innerHTML += `
          <li class="flex justify-between border-b pb-2">
            <span>Token #${item.token_no} (${item.department})</span>
            ${priorityBadge}
          </li>
        `;
      });

    })
    .catch(() => console.log("Admission load error"));
}

// =============================
// UPDATE DOCTOR STATUS
// =============================
function updateDoctorStatus() {

  const status = document.getElementById("doctorStatus").value;

  fetch(`${API_BASE}/set_doctor_status`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + token
    },
    body: JSON.stringify({ status })
  })
    .then(res => res.json())
    .then(data => {

      if (data.error) {
        alert(data.error);
        return;
      }

      // ✅ Immediately set dropdown to selected value
      document.getElementById("doctorStatus").value = status;

      alert("Doctor status updated successfully");

    })
    .catch(() => alert("Server error"));
}


// =============================
// LOAD DOCTOR STATUS (SEPARATE CALL)
// =============================
function loadDoctorStatus() {

  fetch(`${API_BASE}/get_doctor_status`, {
    headers: {
      Authorization: "Bearer " + token
    }
  })
  .then(res => res.json())
  .then(data => {

    if (data.status) {
      document.getElementById("doctorStatus").value = data.status;
    }

  })
  .catch(() => console.log("Doctor status load error"));
}

function loadPeakHourAnalysis() {

  fetch(`${API_BASE}/peak_hour_analysis?date=${today()}`, {
    headers: { Authorization: "Bearer " + token }
  })
    .then(res => res.json())
    .then(data => {

      const list = document.getElementById("analysisSummary");
      list.innerHTML = "";

      if (!data.hourly_distribution) {
        list.innerHTML = "<li>No data available</li>";
        return;
      }

      list.innerHTML += `
        <li>Total Active Hours: ${Object.keys(data.hourly_distribution).length}</li>
        <li>Peak Hour: ${data.peak_hour}:00</li>
        <li>Patients at Peak: ${data.peak_count}</li>
      `;

    })
    .catch(() => console.log("Peak analysis error"));
}

// =============================
// AUTO LOAD
// =============================
document.addEventListener("DOMContentLoaded", () => {

  loadDoctorSummary();
  loadDoctorQueue();
  loadOPDStatus();
  loadAdmissionHistory();
  loadDoctorStatus();
  loadPeakHourAnalysis();

  setInterval(() => {
    loadDoctorQueue();
    loadDoctorSummary();
    loadAdmissionHistory();
    loadPeakHourAnalysis();
  }, 5000);

});