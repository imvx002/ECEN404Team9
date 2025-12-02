#Jetson_WorkerLoc.py Final Version

# Dependencies
import os, time, requests, json
from datetime import datetime
from pathlib import Path

# BASE IP Address from RPI, interestingly has stayed conistently the same through previous trial runs.
PI_SERVER = "http://10.249.31.33:5000"

# The rstrip is to ensure no trailing slash follows the address such that the endpoints connect correctly
BASE = PI_SERVER.rstrip('/')

# The different endpoints created to list the images within the RPI, RAW and PROCESSED
IMAGES_ENDPOINT = f"{BASE}/api/images?only=raw"
UPLOAD_ENDPOINT = f"{BASE}/upload"

# Where the Jetson stores temp downloads & results 
HOME = Path.home()
WORK_DIR = HOME / "pcb_worker"
DL_DIR = WORK_DIR / "downloads"
OUT_DIR = WORK_DIR / "outputs"
SEEN_FILE = WORK_DIR / "seen.txt"
BBOX_DIR = WORK_DIR / "bbox_data"

# In case, the directories and files have not been made previously
DL_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)
BBOX_DIR.mkdir(parents=True, exist_ok=True)
SEEN_FILE.touch(exist_ok=True)

print("Using:", HOME, DL_DIR, OUT_DIR, SEEN_FILE)

# Linking necessary model parameters for function
MODEL_PATH = "/home/team9capstone/best.pt"  # YOLO file path
IMG_SIZE = 640
CONF = 0.25

# Final sanity check to ensure proper file upload to RPI
os.makedirs(DL_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(BBOX_DIR, exist_ok=True)
SEEN_FILE.touch(exist_ok=True)

# YOLO Implmentation
from ultralytics import YOLO
model = YOLO(MODEL_PATH)

# This function takes the image filename has already been processed and had the model ran on the image. This prevents re-running the model on the IMAGE preventing the infinite loop that can happen.
def has_seen(name: str) -> bool:
    with SEEN_FILE.open("r") as f:
        return name.strip() in {line.strip() for line in f}

# This function takes the image filename and appends it to the seen.txt file
def mark_seen(name: str):
    with SEEN_FILE.open("a") as f:
        f.write(name.strip() + "\n")

#  Given a list of dicts form the PI API:
#      items = [{"filename": "...", "url":, "..."}, ...] (newest first)
#  Return (filename, url) for the first file that is not a raw image & and not been processed through the YOLO model
#  Otherwise, this code should return "None"
def pick_next_image(items):
    
    for it in items:
        fn = it["filename"]
        if fn.startswith("result_"):
            continue
        if not has_seen(fn):
            return fn, it["url"]
    return None

# Download the image from the url and save it to the local path. If any issues occur during the process, HTTP request fails.
def download_image(url: str, local_path: Path):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    local_path.write_bytes(r.content)

# This function returns the bounding box information from the YOLO inference information
# So the function takes input from YOLO result objects from model.predict() function and then outputs the detection id, class, confidence, and the coordiantes in pixels starting from the top left. 
def extract_bbox_data(results):
    bbox_list = []
    
    if results[0].boxes is None or len(results[0].boxes) == 0:
        return bbox_list
    
    for idx, box in enumerate(results[0].boxes):
        # Get box coordinates (xyxy format: x1, y1, x2, y2)
        xyxy = box.xyxy[0].cpu().numpy()
        x1, y1, x2, y2 = xyxy
        
        # Calculate width and height
        width = x2 - x1
        height = y2 - y1
        
        # Get confidence and class
        conf = float(box.conf[0].cpu().numpy())
        cls = int(box.cls[0].cpu().numpy())
        class_name = model.names.get(cls, f"class_{cls}")
        
        bbox_data = {
            "detection_id": idx,
            "class": class_name,
            "confidence": round(conf, 4),
            "coordinates": {
                "x1": round(float(x1), 2),
                "y1": round(float(y1), 2),
                "x2": round(float(x2), 2),
                "y2": round(float(y2), 2),
                "center_x": round(float((x1 + x2) / 2), 2),
                "center_y": round(float((y1 + y2) / 2), 2),
                "width": round(float(width), 2),
                "height": round(float(height), 2)
            }
        }
        bbox_list.append(bbox_data)
    
    return bbox_list

# Prints a readable summary of bounding box detections to the terminal output to the console. 
# This is helpful for debugging and monitoring the Jetson Orin Nano inference on the terminal
def print_bbox_summary(bbox_data):
    if not bbox_data:
        print("  No detections found.")
        return
    
    print(f"  Total detections: {len(bbox_data)}")
    for det in bbox_data:
        print(f"  [{det['detection_id']}] {det['class']} (conf: {det['confidence']:.2%})")
        coords = det['coordinates']
        print(f"      Top-left: ({coords['x1']}, {coords['y1']})")
        print(f"      Bottom-right: ({coords['x2']}, {coords['y2']})")
        print(f"      Center: ({coords['center_x']}, {coords['center_y']})")
        print(f"      Size: {coords['width']} x {coords['height']}")

# Run the actual YOLO model at the input image
# This will perform the detection and saves the annotated image with the drawn bounding boxes.
# This will return the annotated path and the bbox data to the output.
def run_yolo_on_image(in_path: Path) -> tuple[Path, list]:
    # Predict & save annotated image into OUT_DIR
    results = model.predict(
        source=str(in_path),
        imgsz=IMG_SIZE,
        conf=CONF,
        save=True,
        project=str(OUT_DIR),
        name="predict",
        exist_ok=True
    )
    
    # Extract bbox data
    bbox_data = extract_bbox_data(results)
    
    # Find the saved annotated image
    save_dir = Path(results[0].save_dir)
    annotated = save_dir / in_path.name
    if not annotated.exists():
        candidates = list(save_dir.glob(in_path.stem + ".*"))
        if candidates:
            return candidates[0], bbox_data
        raise FileNotFoundError("Annotated image not found")
    
    return annotated, bbox_data

# Saves the bounding box metadata to a timestamped JSON file in the directory BBOX_DIR.
def save_bbox_data(bbox_data, source_name: str):
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_filename = f"bbox_{timestamp}_{source_name.rsplit('.', 1)[0]}.json"
    json_path = BBOX_DIR / json_filename
    
    with json_path.open("w") as f:
        json.dump(bbox_data, f, indent=2)
    
    return json_path

# This function uploads the annotataed images to the RPI's uploded/processed image endpoint
# The function uploads the fiulename with the result_<timestamp> in order to keep track track from the raw source images on the PI
def upload_result(result_path: Path, source_name: str):
    # Prefix the filename so it's clear this is a result
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    result_name = f"result_{timestamp}_{source_name}"
    with result_path.open("rb") as f:
        files = {"image": (result_name, f, "image/jpeg")}
        r = requests.post(UPLOAD_ENDPOINT, files=files, timeout=60)
    r.raise_for_status()
    return r.text


# This is the main loop function
# Will through the RPI API for any available images not seen by the seen.txt file
# When the function finds a new image, it will downloaded it locally and run the YOLOv8 model to generate the results from the annotate image and bbox metadata
# Then the main function will call on the difference functions to print the bbox summary and save the bbox JSON file to the results folder.
# Then uploads the image back to the RPI through the processed image endpoint and mark the image as seen
# Finally, repeats the same process with a short delay when now new images are available
def main_loop():
    print("Jetson worker started. Polling Pi for images…")
    while True:
        try:
            resp = requests.get(IMAGES_ENDPOINT, timeout=10)
            resp.raise_for_status()
            items = resp.json()
            nxt = pick_next_image(items)
            if not nxt:
                time.sleep(2)  # nothing new yet
                continue

            filename, url = nxt
            local_path = DL_DIR / filename
            print(f"Downloading {filename} …")
            download_image(url, local_path)

            print(f"Running YOLO on {filename} …")
            annotated_path, bbox_data = run_yolo_on_image(local_path)
            
            print("Bounding box detections:")
            print_bbox_summary(bbox_data)
            
            print(f"Saving bbox data …")
            json_path = save_bbox_data(bbox_data, filename)
            print(f"Bbox data saved to: {json_path}")

            print(f"Uploading result for {filename} …")
            upload_text = upload_result(annotated_path, filename)
            print("Upload response:", upload_text)

            mark_seen(filename)
        except Exception as e:
            print("Error:", e)
            time.sleep(2)

if __name__ == "__main__":
    main_loop()
