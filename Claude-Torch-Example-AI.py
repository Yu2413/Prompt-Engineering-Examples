import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import models, transforms
from PIL import Image
from pathlib import Path
import requests
import random

# --------------------------
# 1. Download & extract dataset (FIXED)
# --------------------------
url = "https://s3.amazonaws.com/fast-ai-imageclas/oxford-iiit-pet.tgz"
root = Path("data/pets")
img_path = root / "images"

if not img_path.exists():
    print("Downloading dataset...")
    root.mkdir(parents=True, exist_ok=True)
    tgz_file = root / "pets.tgz"
    
    # Download
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        total_size = int(r.headers.get('content-length', 0))
        downloaded = 0
        with open(tgz_file, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    print(f"Downloaded: {downloaded/1024/1024:.1f}MB / {total_size/1024/1024:.1f}MB", end='\r')
    
    print("\nExtracting...")
    import tarfile
    with tarfile.open(tgz_file, "r:gz") as tar:
        tar.extractall(root)
    
    # Check what was extracted
    print(f"Contents of {root}:")
    for item in root.rglob("*"):
        if item.is_dir():
            print(f"  DIR: {item.relative_to(root)}")
    
    # Find the images directory (it might be in a subdirectory)
    possible_paths = [
        root / "images",
        root / "oxford-iiit-pet" / "images",
        root / "oxford-iiit-pet",
    ]
    
    for path in possible_paths:
        if path.exists() and list(path.glob("*.jpg")):
            img_path = path
            print(f"Found images at: {img_path}")
            break
    else:
        # If images are in root, use that
        if list(root.glob("*.jpg")):
            img_path = root
            print(f"Found images at: {img_path}")

# --------------------------
# 2. Define cat vs dog rule
# --------------------------
def is_cat(fname):
    return fname.name[0].isupper()

# --------------------------
# 3. Custom Dataset
# --------------------------
class PetsDataset(Dataset):
    def __init__(self, files, transform=None):
        self.files = files
        self.transform = transform
    
    def __len__(self):
        return len(self.files)
    
    def __getitem__(self, idx):
        f = self.files[idx]
        img = Image.open(f).convert("RGB")
        label = 1 if is_cat(f) else 0
        if self.transform:
            img = self.transform(img)
        return img, label

# --------------------------
# 4. Transforms + Train/Valid Split
# --------------------------
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
])

files = list(img_path.glob("*.jpg"))
print(f"Total files found: {len(files)}")

if len(files) == 0:
    print(f"\nERROR: No .jpg files found in {img_path}")
    print("Please check the directory structure:")
    for item in root.rglob("*.jpg")[:5]:  # Show first 5 jpg files
        print(f"  Found: {item}")
    exit(1)

# Manual split with shuffling
random.seed(42)
random.shuffle(files)
train_len = int(0.8 * len(files))
train_files = files[:train_len]
valid_files = files[train_len:]

print(f"Training files: {len(train_files)}")
print(f"Validation files: {len(valid_files)}")

train_ds = PetsDataset(train_files, transform)
valid_ds = PetsDataset(valid_files, transform)

train_dl = DataLoader(train_ds, batch_size=32, shuffle=True)
valid_dl = DataLoader(valid_ds, batch_size=32)

# --------------------------
# 5. Create ResNet34 (pretrained)
# --------------------------
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

model = models.resnet34(weights="IMAGENET1K_V1")
model.fc = nn.Linear(model.fc.in_features, 2)
model = model.to(device)

criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=3e-4)

# --------------------------
# 6. Training loop (1 epoch)
# --------------------------
print("Training...")
model.train()
for batch_idx, (imgs, labels) in enumerate(train_dl):
    imgs, labels = imgs.to(device), labels.to(device)
    optimizer.zero_grad()
    preds = model(imgs)
    loss = criterion(preds, labels)
    loss.backward()
    optimizer.step()
    
    if batch_idx % 10 == 0:
        print(f"Batch {batch_idx}/{len(train_dl)}, Loss: {loss.item():.4f}")

# --------------------------
# 7. Evaluate (error rate)
# --------------------------
print("\nEvaluating...")
model.eval()
correct = 0
total = 0
with torch.no_grad():
    for imgs, labels in valid_dl:
        imgs, labels = imgs.to(device), labels.to(device)
        preds = model(imgs)
        _, predicted = preds.max(1)
        total += labels.size(0)
        correct += (predicted == labels).sum().item()

accuracy = correct / total
error_rate = 1 - accuracy
print(f"Accuracy: {accuracy:.4f}")
print(f"Error rate: {error_rate:.4f}")