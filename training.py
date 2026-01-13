from ultralytics import YOLO
from pathlib import Path
import shutil
import cv2
import numpy as np
 
# ============================================
# BOOTSTRAP TRAINING + AUTO-ANNOTATION
# ============================================
 
# Configuration
manual_annotations_dir = '../manually_annotated_new'
all_images_dir = '../../failed_annotation/all_images'  # All 1500 images
 
print("🚀 Starting bootstrap automation...\n")
 
# ============================================
# STEP 1: Prepare training dataset
# ============================================
print("Step 1/4: Preparing training dataset...")
 
dataset_path = Path('./bootstrap_dataset')
(dataset_path / 'images' / 'train').mkdir(parents=True, exist_ok=True)
(dataset_path / 'labels' / 'train').mkdir(parents=True, exist_ok=True)
 
for img_file in list(Path(manual_annotations_dir).glob('*.jpg')) + list(Path(manual_annotations_dir).glob('*.png')):
    shutil.copy(img_file, dataset_path / 'images' / 'train' / img_file.name)
   
    txt_file = img_file.with_suffix('.txt')
    if txt_file.exists():
        shutil.copy(txt_file, dataset_path / 'labels' / 'train' / txt_file.name)
 
classes_file = Path(manual_annotations_dir) / 'classes.txt'
if classes_file.exists():
    shutil.copy(classes_file, dataset_path / 'classes.txt')
 
with open(dataset_path / 'data.yaml', 'w') as f:
    f.write(f"""path: {dataset_path.absolute()}
train: images/train
val: images/train
 
nc: 2
names:
  - rim_black
  - cap_black
""")
 
print(f"✅ Training dataset prepared")
 
# ============================================
# STEP 2: Train bootstrap model
# ============================================
print("\nStep 2/4: Training bootstrap model (15-20 min)...")
 
model = YOLO('yolo11s.pt')
model.train(
    data=str(dataset_path / 'data.yaml'),
    epochs=100,
    imgsz=640,
    batch=8,
    mosaic=1.0,
    mixup=0.3,
    copy_paste=0.5,
    degrees=15,
    translate=0.2,
    scale=0.9,
    fliplr=0.5,
    hsv_h=0.02,
    hsv_s=0.7,
    hsv_v=0.4,
    erasing=0.4,
    optimizer='AdamW',
    lr0=0.001,
    device="0",
    workers=4,
    project='runs/bootstrap',
    name='wheel_model',
    exist_ok=True,
    verbose=True
)
 
print("✅ Training complete!")