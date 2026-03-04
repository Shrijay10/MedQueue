const API_BASE = "http://127.0.0.1:5000";

function login() {
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value.trim();
  const role = document.getElementById("role").value;
  const errorBox = document.getElementById("error");
  const button = document.querySelector("button");

  errorBox.innerText = "";

  if (!email || !password || !role) {
    errorBox.innerText = "Please fill all fields";
    return;
  }

  // 🔄 Loading State
  button.disabled = true;
  button.innerText = "Signing in...";

  fetch(`${API_BASE}/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ email, password, role })
  })
    .then(async (res) => {
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Login failed");
      }

      return data;
    })
    .then((data) => {
      // Store auth
      localStorage.setItem("token", data.token);
      localStorage.setItem("role", data.role);

      // Redirect based on role
      redirectUser(data.role);
    })
    .catch((err) => {
      errorBox.innerText = err.message || "Server not responding";
    })
    .finally(() => {
      // Reset button
      button.disabled = false;
      button.innerText = "Sign In";
    });
}

function redirectUser(role) {
  switch (role) {
    case "doctor":
      window.location.href = "doctor.html";
      break;
    case "receptionist":
      window.location.href = "receptionist.html";
      break;
    case "patient":
      window.location.href = "patient.html";
      break;
    default:
      localStorage.clear();
      alert("Invalid role detected");
  }
}
