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

# Configuration for Radarr
radarr_host = 'localhost'  # Update with your actual Radarr host
radarr_port = '7878'  # Update with the actual port where Radarr is running
radarr_url = f'http://{radarr_host}:{radarr_port}/api/v3/queue'
radarr_api_key = 'XXXX'  # Replace with your actual Radarr API key

# Function to fetch the download queue for Sonarr or Radarr
def fetch_queue(api_url, api_key):
    headers = {'X-Api-Key': api_key}
    response = requests.get(api_url, headers=headers)
    return response.json()

# Function to remove and block a download in Sonarr or Radarr
def remove_and_block_download(api_url, api_key, download_id, block_torrent=False):
    params = {
        'removeFromClient': True,
        'blocklist': block_torrent,  # Block the torrent if set to True
        'skipRedownload': True  # If True, skips re-downloading
    }

    delete_url = f'{api_url}/{download_id}'
    headers = {
        'X-Api-Key': api_key,
        'Content-Type': 'application/json'
    }

    response = requests.delete(delete_url, headers=headers, params=params)
    
    if response.status_code == 200:
        print(f"Successfully removed download {download_id} from queue.")
    else:
        # Print detailed error response for debugging
        print(f"Failed to remove download {download_id}. Response: {response.status_code} - {response.text}")

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

# Get the initial Transmission session ID
transmission_session_id = get_transmission_session_id()

# Fetch and process Sonarr and Radarr queues
for app_name, api_url, api_key in [
    ('Sonarr', sonarr_url, sonarr_api_key),
    ('Radarr', radarr_url, radarr_api_key)
]:
    downloads_data = fetch_queue(api_url, api_key)
    downloads = downloads_data.get('records', [])

    if isinstance(downloads, list):
        # Iterate through downloads and get torrent file details from Transmission
        for download in downloads:
            download_id = download['downloadId']  # This is the torrent hash
            title = download['title']
            
            # Fetch torrent file list from Transmission
            torrent_files = get_torrent_files(transmission_session_id, download_id)
            
            if torrent_files:
                print(f"Checking torrent contents for: {title}")
                remove_torrent_flag = False  # Flag to indicate if the torrent should be marked for removal

                # Check each file in the torrent
                for torrent in torrent_files:
                    for file in torrent['files']:
                        filename = file['name']
                        
                        # Check if the file extension is .zipx or .lnk
                        if filename.endswith('.zipx') or filename.endswith('.lnk') or filename.endswith('.arj'):
                            print(f"Identified suspicious file: {filename}. Marking download for removal...")
                            remove_torrent_flag = True
                            break  # Exit the loop since we found a file to trigger removal
                    
                    if remove_torrent_flag:
                        break

                # If a suspicious file was found, remove the torrent and block it
                if remove_torrent_flag:
                    remove_and_block_download(api_url, api_key, download['id'], block_torrent=True)
            else:
                print(f"Failed to fetch torrent info for {title} in {app_name}")
    else:
        print(f"Unexpected data structure from {app_name} API. Expected a list.")

