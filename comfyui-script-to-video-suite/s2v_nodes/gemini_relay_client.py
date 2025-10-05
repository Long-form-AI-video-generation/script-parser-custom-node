import requests
import json

# --- IMPORTANT ---
# Put the URL that Render gave you here.
# Make sure it ends with /generate
RELAY_SERVER_URL = "https://gemini-relay-bkes.onrender.com/generate"

def ask_gemini_via_relay(prompt: str) -> str:
    """
    Sends a prompt to our relay server, which then asks the Gemini API.

    Args:
        prompt: The text prompt to send to the model.

    Returns:
        The text response from the model, or an error message string.
    """
    headers = {
        "Content-Type": "application/json"
    }
    payload = { 
        "prompt": prompt
    }

    try:
        # Make the POST request to our server on Render with a timeout
        response = requests.post(RELAY_SERVER_URL, headers=headers, data=json.dumps(payload), timeout=120)

        # Check if the request was successful
        if response.status_code == 200:
            # Get the JSON response and return the text part
            return response.json().get("response", "Error: Response JSON was malformed.")
        else:
            # If the relay server returned an error, capture and return it
            error_details = response.json().get("error", "Unknown error from relay server.")
            return f"Error: Relay server responded with status {response.status_code}. Details: {error_details}"

    except requests.exceptions.RequestException as e:
        # Handle network errors (e.g., cannot connect to Render)
        return f"Error: Could not connect to the relay server. Reason: {e}"
    
     