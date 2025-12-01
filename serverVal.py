from flask import Flask, request, send_from_directory, jsonify, url_for, render_template
import os, glob, subprocess, time

#This file hosts the flask webserver, which is our user interface.

#define where we should pull our images from
app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def list_files_sorted():
    files = sorted(
        os.listdir(app.config["UPLOAD_FOLDER"]),
        key=lambda x: os.path.getmtime(os.path.join(app.config["UPLOAD_FOLDER"], x)),  # Changed from ctime to mtime
        reverse=True
    )
    # Filter to images only
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
    return [f for f in files if os.path.splitext(f)[1].lower() in exts]



#These various app routes call different functions and scripts depending on user input
@app.route("/1", methods=["GET"])    #old homepage, not used anymore
def index():
    files = list_files_sorted()
    html = "<h2>Manual Upload</h2>"
    html += '''
    <form method="POST" action="/upload" enctype="multipart/form-data">
        <input type="file" name="image" accept="image/*">
        <input type="submit" value="Upload">
    </form>
    </br>

    <h3>Remote Scan</h3>
    <form method="POST" action="/capture">
        <input type="submit" value="Start Scan">
    </form>
    <br>

    <h3>Database</h3>
    '''
    if files:
        for filename in files:
            image_url = f"/uploads/{filename}"
            html += f'<p><a href="{image_url}">{filename}</a></p>'
            html += f'<img src="{image_url}" width="200"><br><br>'
    else:
        html += "No images uploaded yet."
    return html

@app.route("/api/images", methods=["GET"])   
#this function takes the list of fresh images and assigns them all the 
#'raw' tag in a json api. The function skips any images that begin with
#result_ because that is what the images from the jetson nano are called after they have
#been labeled with faults. This function is called so the jetson knows what images have
#not been processed yet.
def api_images():
    
    only = request.args.get("only", "raw")
    files = list_files_sorted()
    if only == "raw":
        files = [f for f in files if not f.startswith("result_")]
    
    items = []
    for fn in files:
        fpath = os.path.join(app.config["UPLOAD_FOLDER"], fn)
        try:
            # Verify file is readable and has content
            file_size = os.path.getsize(fpath)
            if file_size > 0:
                items.append({
                    "filename": fn,
                    "url": url_for("uploaded_file", filename=fn, _external=True),
                    "size": file_size
                })
        except (OSError, IOError):
            # Skip files that can't be accessed
            pass
    
    return jsonify(items), 200

#This function uploads images to the webserver, with a manual option as well 
#for debugging
@app.route("/upload", methods=["POST"])
def upload():
    if "image" not in request.files:
        return "No file part", 400
    file = request.files["image"]
    if file.filename == "":
        return "No selected file", 400
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(filepath)
    
    # Force filesystem sync and verify file was written
    try:
        os.sync()
        time.sleep(0.2)
        if os.path.getsize(filepath) > 0:
            return "Image uploaded successfully. <a href='/raw'>View Images</a>"
        else:
            return "File upload failed - file is empty", 400
    except Exception as e:
        return f"Error verifying upload: {e}", 500

#This function clears all images in the database manually, by deleting the images
#in the uploads folder. It also connects to the jetson nano via SSH to ensure we clear the
#'seen.txt' file, which keeps track of what images it has processed.
@app.route("/delete-all", methods=["POST"])
def delete_all_images():
    exts = ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.gif", "*.webp")
    deleted = 0
    subprocess.run(["ssh", "-tt", "team9capstone@10.249.93.211", "> /home/team9capstone/pcb_worker/seen.txt"])
    
    print("deleted seen.txt?")
    for ext in exts:
        for img in glob.glob(os.path.join(app.config["UPLOAD_FOLDER"], ext)):
            os.remove(img)
            deleted += 1
    return jsonify({"message": f"Deleted {deleted} images"}), 200


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    import os
    folder = app.config["UPLOAD_FOLDER"]
    full_path = os.path.join(folder, filename)
    
    return send_from_directory(folder, filename)

#This route triggers a medium size pcb scan by entering terminal commands to 
#connect to our printrun interface
@app.route("/scanmedium", methods=["POST"])
def trigger_capture():
    
    try:
        subprocess.Popen(["python3", "/home/imvx02/scanmedium.py"])
        subprocess.Popen(["python3", "/home/imvx02/CaptureImageMODIFIED.py"])
        return "Scan started! Please wait until finished <a href='/'>Back to Home</a>"
    except Exception as e:
        return f"Error: {e}", 500

#This triggers a small sized scan
@app.route("/scansmall", methods=["POST"])
def trigger_capture_small():
    try:
        subprocess.Popen(["python3", "/home/imvx02/scansmall.py"])
        subprocess.Popen(["python3", "/home/imvx02/CaptureImageMODIFIED.py"])
        return "Scan started! Please wait until finished <a href='/'>Back to Home</a>"
    except Exception as e:
        return f"Error: {e}", 500        

#Triggers a large size pcb scan
@app.route("/scanlarge", methods=["POST"])
def trigger_capture_large():
    try:
        subprocess.Popen(["python3", "/home/imvx02/scanlarge.py"])
        subprocess.Popen(["python3", "/home/imvx02/CaptureImageMODIFIED.py"])
        return "Scan started! Please wait until finished <a href='/'>Back to Home</a>"
    except Exception as e:
        return f"Error: {e}", 500  

#Home page for the webserver
@app.route('/')
def home():
    return render_template("home.html")

@app.route('/raw')
def raw():
    files = list_files_sorted()
    raw_files = [f for f in files if not f.startswith("result_")]
    return render_template("raw.html", files=raw_files,)

@app.route('/processed')
def processed():
    files = list_files_sorted()
    processed_files = [f for f in files if f.startswith("result_")]
    return render_template("processed.html", files=processed_files)

#This function connects to the jetson nano via SSH and runs the file that detects and 
#labels the faults in the PCB
@app.route("/processimages", methods=["POST"])
def process_images():
        subprocess.run([
        "ssh", "-tt", "team9capstone@10.249.93.211", "python3 /home/team9capstone/JetsonWorkerLoc.py"])        
        return "Processing started! <a href='/'>Back to Home</a>"
 
 #This route moves the bed of our robot down to allow easier PCB placement
@app.route('/placement', methods = ["POST"])
def placement():
    try:
        subprocess.Popen(["python3", "/home/imvx02/Placement.py"])
        return "Please place PCB once bed has stopped moving <a href='/'>Back to home</a>"
    except Exception as e:
            return f"Error: {e}", 500    
        
#This function centers the camera above the origin of our system
@app.route('/align', methods = ["POST"])
def align():
    try:
        subprocess.Popen(["python3", "/home/imvx02/Align.py"])
        return "Aligning camera with board <a href='/'>Back to home</a>"
    except Exception as e:
            return f"Error: {e}", 500       



if __name__ == "__main__":
    # run AFTER all @app.route definitions
    app.run(host="0.0.0.0", port=5000, debug=True)
