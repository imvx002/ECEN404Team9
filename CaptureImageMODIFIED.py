from picamera2 import Picamera2
import time
import os
import requests
import subprocess
import socket


#this function grabs the rpis local ip, since we are using the tamu guest wifi the ip is not always static.
def get_private_ip():
	try:
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		s.connect(("8.8.8.8", 80))
		private_ip = s.getsockname()[0]
		s.close()
		return private_ip
	except Exception as e:
		print(f"Error getting ip: {e}")
		return None


# this section defines server url and where to save our images
SERVER_URL = f"http://{get_private_ip()}:5000/upload"  # Your Flask server's IP
print(f"URL: {SERVER_URL}")
SAVE_DIR = "/home/imvx02/uploads"
os.makedirs(SAVE_DIR, exist_ok=True)

# Function to generate the next sequential filename(image0, image1, etc)
def get_next_filename(index):
    return os.path.join(SAVE_DIR, f"image_{index:03d}.jpg")

# Function to capture images using rpicam-still
def capture_image(filepath):
    command = [
        "rpicam-still",
        "-o", filepath,
        "-q", "100",
        "--width", "3280", "--height", "2464",
        "--brightness", "0.06",  # Use daylight white balance
        "-n",  # Disable preview
        "--timeout", "100"
    ]
    print(f"Capturing: {filepath}")
    subprocess.run(command, check=True)

    os.sync()
    time.sleep(0.5)

# Function to upload images to the Flask server
def upload_image(image_path):
    with open(image_path, "rb") as img_file:
        files = {"image": img_file}
        response = requests.post(SERVER_URL, files=files)
    if response.status_code == 200:
        print(f"Uploaded: {image_path}")
    else:
        print(f"Failed to upload {image_path}: {response.status_code} {response.text}")

# Main loop: capture the images
if __name__ == "__main__":
    total_time = 2.0     #26 for medium, 10 for small, 50 for large
    interval = 0.1   
    num_photos = int(total_time / interval)

    print(f"Starting capture: {num_photos} images over {total_time} seconds")

    for i in range(num_photos):
        filepath = get_next_filename(i)
        capture_image(filepath)
        
    print("Capture complete. Starting upload...")
    time.sleep(2)
    
    # Uploads all images we just captured to the webserver
    for filename in sorted(os.listdir(SAVE_DIR)):
        if filename.endswith(".jpg"):
            upload_image(os.path.join(SAVE_DIR, filename))

    print("All images uploaded.")
