import requests
import json

# Configuration
sonarr_url = 'http://<sonarr_host>:<sonarr_port>/api/v3/queue'
sonarr_api_key = '<sonarr_api_key>'

transmission_url = 'http://<transmission_host>:<transmission_port>/transmission/rpc'
transmission_username = '<transmission_username>'
transmission_password = '<transmission_password>'


# Fetch the current Sonarr download queue
sonarr_headers = {'X-Api-Key': sonarr_api_key}
response = requests.get(sonarr_url, headers=sonarr_headers)
downloads_data = response.json()

# Now access the 'records' key from the response, which contains the actual download records
downloads = downloads_data.get('records', [])

# Function to get the torrent session id from Transmission (needed for all requests)
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
    else:
        print(f"Error fetching torrent files: {response.text}")
        return None

# Function to remove a torrent and delete its files
def remove_torrent(transmission_session_id, torrent_hash):
    payload = {
        "method": "torrent-remove",
        "arguments": {
            "ids": [torrent_hash],
            "delete-local-data": True  # Set to True to also delete the files on disk
        }
    }
    
    headers = {
        'X-Transmission-Session-Id': transmission_session_id,
        'Content-Type': 'application/json'
    }
    
    response = requests.post(transmission_url, headers=headers, json=payload, auth=(transmission_username, transmission_password))
    
    if response.status_code == 200:
        print(f"Successfully removed torrent {torrent_hash} and deleted its files.")
    else:
        print(f"Error removing torrent: {response.text}")

# Get Transmission session ID
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
            remove_torrent_flag = False  # Flag to indicate if the torrent should be removed

            # Check each file in the torrent
            for torrent in torrent_files:
                for file in torrent['files']:
                    filename = file['name']
                    
                    # Check if the file extension is .zipx or .lnk
                    if filename.endswith('.zipx') or filename.endswith('.lnk'):
                        print(f"Identified suspicious file: {filename}. Removing torrent...")
                        remove_torrent_flag = True
                        break  # Exit the loop since we found a file to trigger removal
                
                if remove_torrent_flag:
                    break

            # If a suspicious file was found, remove the torrent and delete the files
            if remove_torrent_flag:
                remove_torrent(transmission_session_id, download_id)
        else:
            print(f"Failed to fetch torrent info for {series_title}")
else:
    print("Unexpected data structure from Sonarr API. Expected a list.")
