# train_cnn.py
# Treniranje CNN modela za prepoznavanje cifara (0-9)
# Koristi template slike iz data/ocr_templates/score/
# 
# Pokretanje: python train_cnn.py
# Trajanje: ~10 minuta na CPU
# Output: models/digit_cnn.pth (mali model ~50KB)

import os
import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import time

print("=" * 70)
print("AVIATOR DIGIT CNN TRAINER")
print("=" * 70)

# Proveri da li PyTorch radi
print(f"\nPyTorch verzija: {torch.__version__}")
print(f"CUDA dostupna: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Koristiće se: {device}")


# ============================================================================
# CNN ARHITEKTURA
# ============================================================================

class DigitCNN(nn.Module):
    """
    Kompaktan CNN za cifre 0-9.
    
    Arhitektura:
    - 3 Conv sloja (16, 32, 64 filtera)
    - 2 FC sloja (128, 10)
    - Dropout za regularizaciju
    - ~50K parametara
    """
    
    def __init__(self):
        super(DigitCNN, self).__init__()
        
        # Konvolucioni slojevi
        self.conv1 = nn.Conv2d(1, 16, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, padding=1)
        self.conv3 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        
        self.pool = nn.MaxPool2d(2, 2)
        self.dropout = nn.Dropout(0.3)
        
        # Fully connected
        # Posle 3x pooling: 28 -> 14 -> 7 -> 3
        self.fc1 = nn.Linear(64 * 3 * 3, 128)
        self.fc2 = nn.Linear(128, 10)
        
    def forward(self, x):
        # Conv1 + Pool: 28x28 -> 14x14
        x = self.pool(F.relu(self.conv1(x)))
        
        # Conv2 + Pool: 14x14 -> 7x7
        x = self.pool(F.relu(self.conv2(x)))
        
        # Conv3 + Pool: 7x7 -> 3x3
        x = self.pool(F.relu(self.conv3(x)))
        
        # Flatten
        x = x.view(-1, 64 * 3 * 3)
        
        # FC slojevi
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.fc2(x)
        
        return x


# ============================================================================
# DATA AUGMENTATION
# ============================================================================

def augment_digit(img: np.ndarray) -> np.ndarray:
    """
    Augmentacija jedne cifre.
    
    Primenjuje:
    - Rotaciju (-15° do +15°)
    - Translaciju (-4px do +4px)
    - Skaliranje (0.85 do 1.15)
    - Šum
    - Blur (ponekad)
    """
    h, w = img.shape
    
    # Rotacija
    angle = np.random.uniform(-15, 15)
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    img = cv2.warpAffine(img, M, (w, h), borderValue=0)
    
    # Translacija
    tx = np.random.randint(-4, 4)
    ty = np.random.randint(-4, 4)
    M = np.float32([[1, 0, tx], [0, 1, ty]])
    img = cv2.warpAffine(img, M, (w, h), borderValue=0)
    
    # Skaliranje
    scale = np.random.uniform(0.85, 1.15)
    img = cv2.resize(img, None, fx=scale, fy=scale)
    
    # Vrati na originalnu veličinu
    if img.shape[0] < h or img.shape[1] < w:
        # Ako je manji, dodaj padding
        pad_h = max(0, h - img.shape[0])
        pad_w = max(0, w - img.shape[1])
        img = cv2.copyMakeBorder(img, pad_h // 2, pad_h - pad_h // 2,
                                  pad_w // 2, pad_w - pad_w // 2,
                                  cv2.BORDER_CONSTANT, value=0)
    elif img.shape[0] > h or img.shape[1] > w:
        # Ako je veći, crop centar
        y_start = (img.shape[0] - h) // 2
        x_start = (img.shape[1] - w) // 2
        img = img[y_start:y_start + h, x_start:x_start + w]
    
    # Šum
    noise = np.random.normal(0, 15, img.shape)
    img = np.clip(img.astype(float) + noise, 0, 255).astype(np.uint8)
    
    # Blur (50% šanse)
    if np.random.rand() > 0.5:
        img = cv2.GaussianBlur(img, (3, 3), 0)
    
    return img


# ============================================================================
# DATASET
# ============================================================================

class DigitDataset(Dataset):
    """Dataset od template slika + augmentacija"""
    
    def __init__(self, template_folder: str, samples_per_digit: int = 150):
        """
        Args:
            template_folder: Folder sa 0.png, 1.png, ..., 9.png
            samples_per_digit: Koliko augmentovanih sample-a po cifri
        """
        self.samples_per_digit = samples_per_digit
        self.templates = {}
        
        # Učitaj template-e
        for digit in range(10):
            path = os.path.join(template_folder, f"{digit}.png")
            
            if not os.path.exists(path):
                raise FileNotFoundError(f"Template ne postoji: {path}")
            
            # Učitaj kao grayscale
            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            
            # Resize na 28x28
            img = cv2.resize(img, (28, 28))
            
            # Normalizuj
            img = img.astype(np.float32) / 255.0
            
            self.templates[digit] = img
        
        print(f"✅ Učitano {len(self.templates)} template-a")
        
    def __len__(self):
        return 10 * self.samples_per_digit
    
    def __getitem__(self, idx):
        # Odredi koja cifra
        digit = idx // self.samples_per_digit
        
        # Uzmi template
        img = self.templates[digit].copy()
        
        # Denormalizuj za augmentaciju
        img = (img * 255).astype(np.uint8)
        
        # Augmentuj
        img = augment_digit(img)
        
        # Normalizuj nazad
        img = img.astype(np.float32) / 255.0
        
        # Convert to tensor
        img_tensor = torch.from_numpy(img).unsqueeze(0)  # 1x28x28
        
        return img_tensor, digit


# ============================================================================
# TRENIRANJE
# ============================================================================

def train_model(
    template_folder: str = "data/ocr_templates/score",
    output_path: str = "models/digit_cnn.pth",
    epochs: int = 25,
    batch_size: int = 64,
    samples_per_digit: int = 150
):
    """
    Trenira CNN model.
    
    Args:
        template_folder: Folder sa template slikama
        output_path: Gde da sačuva model
        epochs: Broj epoha
        batch_size: Batch size
        samples_per_digit: Koliko augmentovanih sample-a po cifri
    """
    print("\n" + "=" * 70)
    print("POČETAK TRENIRANJA")
    print("=" * 70)
    
    # Kreiraj dataset
    print(f"\nKreiram dataset sa {samples_per_digit} sample-a po cifri...")
    dataset = DigitDataset(template_folder, samples_per_digit)
    
    # Split na train/val (80/20)
    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = torch.utils.data.random_split(
        dataset, [train_size, val_size]
    )
    
    print(f"Training set: {len(train_dataset)} sample-a")
    print(f"Validation set: {len(val_dataset)} sample-a")
    
    # DataLoader-i
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    
    # Model
    print(f"\nInicijalizujem model na {device}...")
    model = DigitCNN().to(device)
    
    # Broj parametara
    total_params = sum(p.numel() for p in model.parameters())
    print(f"Ukupno parametara: {total_params:,}")
    
    # Loss i optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    
    # Training loop
    print(f"\nTreniram {epochs} epoha...")
    print("=" * 70)
    
    best_val_acc = 0.0
    
    for epoch in range(epochs):
        # TRAIN
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0
        
        for inputs, labels in train_loader:
            inputs, labels = inputs.to(device), labels.to(device)
            
            # Forward
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            
            # Backward
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            # Stats
            train_loss += loss.item()
            _, predicted = torch.max(outputs, 1)
            train_total += labels.size(0)
            train_correct += (predicted == labels).sum().item()
        
        train_acc = 100 * train_correct / train_total
        avg_train_loss = train_loss / len(train_loader)
        
        # VALIDATION
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        
        with torch.no_grad():
            for inputs, labels in val_loader:
                inputs, labels = inputs.to(device), labels.to(device)
                
                outputs = model(inputs)
                loss = criterion(outputs, labels)
                
                val_loss += loss.item()
                _, predicted = torch.max(outputs, 1)
                val_total += labels.size(0)
                val_correct += (predicted == labels).sum().item()
        
        val_acc = 100 * val_correct / val_total
        avg_val_loss = val_loss / len(val_loader)
        
        # Print progress
        print(f"Epoch {epoch + 1}/{epochs} | "
              f"Train Loss: {avg_train_loss:.4f} Acc: {train_acc:.2f}% | "
              f"Val Loss: {avg_val_loss:.4f} Acc: {val_acc:.2f}%")
        
        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            
            # Kreiraj folder ako ne postoji
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            torch.save(model.state_dict(), output_path)
            print(f"  → Saved best model (Val Acc: {val_acc:.2f}%)")
    
    print("\n" + "=" * 70)
    print("TRENIRANJE ZAVRŠENO!")
    print("=" * 70)
    print(f"✅ Best validation accuracy: {best_val_acc:.2f}%")
    print(f"✅ Model sačuvan: {output_path}")
    
    # Veličina fajla
    file_size = os.path.getsize(output_path) / 1024
    print(f"✅ Veličina modela: {file_size:.1f} KB")
    
    return model


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    start_time = time.time()
    
    # Proveri da li template folder postoji
    template_folder = "data/ocr_templates/score"
    
    if not os.path.exists(template_folder):
        print(f"\n❌ GREŠKA: Folder ne postoji: {template_folder}")
        print("\nKreirati folder i dodati template slike:")
        print("  data/ocr_templates/score/0.png")
        print("  data/ocr_templates/score/1.png")
        print("  ...")
        print("  data/ocr_templates/score/9.png")
        exit(1)
    
    # Proveri da li ima svih 10 template-a
    missing = []
    for digit in range(10):
        path = os.path.join(template_folder, f"{digit}.png")
        if not os.path.exists(path):
            missing.append(digit)
    
    if missing:
        print(f"\n❌ GREŠKA: Nedostaju template-i za cifre: {missing}")
        exit(1)
    
    # Treniraj model
    try:
        model = train_model(
            template_folder=template_folder,
            output_path="models/digit_cnn.pth",
            epochs=25,
            batch_size=64,
            samples_per_digit=150  # 150 * 10 = 1500 sample-a
        )
        
        elapsed = time.time() - start_time
        print(f"\n⏱️  Ukupno vreme: {elapsed / 60:.1f} minuta")
        
        print("\n" + "=" * 70)
        print("SLEDEĆI KORACI:")
        print("=" * 70)
        print("1. Testiraj model:")
        print("   python test_cnn.py")
        print("\n2. Integriši u projekat:")
        print("   Model će automatski biti korišćen ako postoji")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ GREŠKA tokom treniranja: {e}")
        import traceback
        traceback.print_exc()