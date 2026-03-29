const API_BASE = import.meta.env.VITE_API_BASE || "";

export async function analyzeSituation(query, language = "uz") {
  const response = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ query, language }),
  });

  if (!response.ok) {
    throw new Error(`Analyze request failed: ${response.status}`);
  }

  return response.json();
}

export async function fetchSuggestions(query) {
  const response = await fetch(`${API_BASE}/suggest?q=${encodeURIComponent(query)}`);

  if (!response.ok) {
    throw new Error(`Suggest request failed: ${response.status}`);
  }

  return response.json();
}

export async function loginUser(credentials) {
  const response = await fetch(`${API_BASE}/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(credentials),
  });

  if (!response.ok) {
    throw new Error(`Login request failed: ${response.status}`);
  }

  return response.json();
}

export async function registerUser(payload) {
  const response = await fetch(`${API_BASE}/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Register request failed: ${response.status}`);
  }

  return response.json();
}

export async function fetchAutofillData(username, formType = "full_application_all", authToken = "") {
  const params = new URLSearchParams({
    username,
    form_type: formType,
  });

  const response = await fetch(`${API_BASE}/autofill?${params.toString()}`, {
    headers: authToken
      ? {
          Authorization: `Bearer ${authToken}`,
        }
      : {},
  });

  if (!response.ok) {
    const error = new Error(`Autofill request failed: ${response.status}`);
    error.status = response.status;
    throw error;
  }

  return response.json();
}

export async function executeService(serviceName, formData) {
  const response = await fetch(`${API_BASE}/execute-service`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      service_name: serviceName,
      form_data: formData,
    }),
  });

  if (!response.ok) {
    throw new Error(`Execute service request failed: ${response.status}`);
  }

  return response.json();
}

export async function getExecutionStatus(executionId) {
  const response = await fetch(`${API_BASE}/execute-service/${executionId}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Get execution status failed: ${response.status}`);
  }

  return response.json();
}

export async function completeService(executionId) {
  const response = await fetch(`${API_BASE}/execute-service/${executionId}/complete`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Complete service request failed: ${response.status}`);
  }

  return response.json();
}

export async function askAssistant(question, language = "uz") {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message: question, language }),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.status}`);
  }

  return response.json();
}
