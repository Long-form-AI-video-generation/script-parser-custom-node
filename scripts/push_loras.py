from huggingface_hub import HfApi

api = HfApi()
repo_id = "Repo ID"
token = "Enter your token here " # Use your WRITE token

# List your files here
# Format: (local_path, name_on_huggingface)
files_to_upload = [
    ("path to safe tensors files")
    
]

for local_path, remote_name in files_to_upload:
    print(f"🚀 Uploading {local_path} as {remote_name}...")
    try:
        api.upload_file(
            path_or_fileobj=local_path,
            path_in_repo=remote_name,
            repo_id=repo_id,
            token=token
        )
        print(f"✅ Successfully uploaded {remote_name}")
    except Exception as e:
        print(f"❌ Failed to upload {remote_name}: {e}")

print(f"\n🔗 All done! Check your repo: https://huggingface.co/{repo_id}")