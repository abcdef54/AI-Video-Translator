from faster_whisper import download_model

print("Downloading 'medium' model to ./models/medium ...")

# This downloads the model files to a folder named 'models' inside your project
model_path = download_model("medium", output_dir="./models/medium")

print(f"Model downloaded successfully to: {model_path}")
print("You can now run backend.py!")