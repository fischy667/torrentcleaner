import requests
import json

# Configuration
sonarr_host = 'XXXX'  # Update with your actual Sonarr host (e.g., 'localhost', '192.168.1.10', etc.)
sonarr_port = '8989'  # Update with the actual port where Sonarr is running
sonarr_url = f'http://{sonarr_host}:{sonarr_port}/api/v3/queue'
sonarr_api_key = 'XXXX'  # Replace with your actual Sonarr API key

transmission_url = 'http://XXXX:9091/transmission/rpc'  # Replace with your Transmission host and port
transmission_username = 'username'  # If Transmission has authentication
transmission_password = 'password'

# Fetch the current Sonarr download queue
sonarr_headers = {'X-Api-Key': sonarr_api_key}
response = requests.get(sonarr_url, headers=sonarr_headers)
downloads_data = response.json()

# Now access the 'records' key from the response, which contains the actual download records
downloads = downloads_data.get('records', [])

# Function to get the Transmission session ID (if necessary)
def get_transmission_session_id():
    response = requests.post(transmission_url, auth=(transmission_username, transmission_password))
    if 'X-Transmission-Session-Id' in response.headers:
        return response.headers['X-Transmission-Session-Id']
    return None

# Function to get the list of files for a torrent in Transmission
def get_torrent_files(transmission_session_id, torrent_hash):
    payload = {
        "method": "torrent-get",
        "arguments": {
            "fields": ["files"],
            "ids": [torrent_hash]
        }
    }

    headers = {
        'X-Transmission-Session-Id': transmission_session_id,
        'Content-Type': 'application/json'
    }

    response = requests.post(transmission_url, headers=headers, json=payload, auth=(transmission_username, transmission_password))
    
    if response.status_code == 200:
        return response.json().get('arguments', {}).get('torrents', [])
    elif response.status_code == 409:
        # If we get a 409 error, we need to get a new session ID and retry the request
        new_session_id = get_transmission_session_id()
        headers['X-Transmission-Session-Id'] = new_session_id
        response = requests.post(transmission_url, headers=headers, json=payload, auth=(transmission_username, transmission_password))
        if response.status_code == 200:
            return response.json().get('arguments', {}).get('torrents', [])
        else:
            print(f"Error fetching torrent files: {response.text}")
            return None
    else:
        print(f"Error fetching torrent files: {response.text}")
        return None

# Function to delete the download from Sonarr's queue and optionally block it
def remove_and_block_download(sonarr_download_id, block_torrent=False):
    # Set the query parameters for the DELETE request
    params = {
        'removeFromClient': True,
        'blocklist': block_torrent,  # Block the torrent if set to True
        'skipRedownload': True  # If True, skips re-downloading
    }
    
    # Send the DELETE request to remove the torrent
    delete_url = f'http://{sonarr_host}:{sonarr_port}/api/v3/queue/{sonarr_download_id}'
    headers = {
        'X-Api-Key': sonarr_api_key,
        'Content-Type': 'application/json'
    }

    response = requests.delete(delete_url, headers=headers, params=params)
    
    if response.status_code == 200:
        print(f"Successfully removed download {sonarr_download_id} from Sonarr's queue.")
    else:
        # Print detailed error response for debugging
        print(f"Failed to remove download {sonarr_download_id}. Response: {response.status_code} - {response.text}")

# Get the initial Transmission session ID
transmission_session_id = get_transmission_session_id()

# Ensure 'downloads' is now a list of records
if isinstance(downloads, list):
    # Iterate through downloads and get torrent file details from Transmission
    for download in downloads:
        download_id = download['downloadId']  # This is the torrent hash
        series_title = download['title']
        
        # Fetch torrent file list from Transmission
        torrent_files = get_torrent_files(transmission_session_id, download_id)
        
        if torrent_files:
            print(f"Checking torrent contents for: {series_title}")
            remove_torrent_flag = False  # Flag to indicate if the torrent should be marked for removal

            # Check each file in the torrent
            for torrent in torrent_files:
                for file in torrent['files']:
                    filename = file['name']
                    
                    # Check if the file extension is .zipx or .lnk
                    if filename.endswith('.zipx') or filename.endswith('.lnk'):
                        print(f"Identified suspicious file: {filename}. Marking download for removal...")
                        remove_torrent_flag = True
                        break  # Exit the loop since we found a file to trigger removal
                
                if remove_torrent_flag:
                    break

            # If a suspicious file was found, remove the torrent from Sonarr and block it
            if remove_torrent_flag:
                remove_and_block_download(download['id'], block_torrent=True)
        else:
            print(f"Failed to fetch torrent info for {series_title}")
else:
    print("Unexpected data structure from Sonarr API. Expected a list.")
