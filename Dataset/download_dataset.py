from huggingface_hub import snapshot_download

path = snapshot_download(
    repo_id="Jin154/gov_myscheme",
    repo_type="dataset",
    local_dir="./data/gov_myscheme"
)
print("Downloaded to:", path)