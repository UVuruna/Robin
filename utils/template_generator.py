# utils/template_generator.py
"""
Template Generator - Alat za kreiranje template slika iz screenshot-ova.
Koristi se jednom da se kreiraju template slike za brzi OCR.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
import json
import logging
from dataclasses import dataclass
import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image, ImageTk


@dataclass
class TemplateRegion:
    """Region sa karakterom za template"""
    character: str
    x: int
    y: int
    width: int
    height: int


class TemplateGenerator:
    """
    Generator template slika za OCR.
    
    Workflow:
    1. Učitaj screenshot sa brojevima
    2. Označi svaku cifru
    3. Sačuvaj kao template
    """
    
    def __init__(self, output_dir: str = "data/ocr_templates"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.output_dir / "digits").mkdir(exist_ok=True)
        (self.output_dir / "special").mkdir(exist_ok=True)
        
        self.logger = logging.getLogger("TemplateGenerator")
        
        # Current working data
        self.current_image = None
        self.current_regions = []
        
    def extract_digit_templates(self, 
                               screenshot_path: str,
                               auto_detect: bool = True) -> List[TemplateRegion]:
        """
        Ekstraktuj template regione iz screenshot-a.
        
        Args:
            screenshot_path: Putanja do screenshot-a
            auto_detect: Pokušaj automatsku detekciju
            
        Returns:
            Lista template regiona
        """
        # Load image
        self.current_image = cv2.imread(screenshot_path)
        if self.current_image is None:
            raise ValueError(f"Cannot load image: {screenshot_path}")
        
        gray = cv2.cvtColor(self.current_image, cv2.COLOR_BGR2GRAY)
        
        if auto_detect:
            # Try automatic detection
            regions = self._auto_detect_digits(gray)
            if regions:
                self.logger.info(f"Auto-detected {len(regions)} regions")
                return regions
        
        # Manual selection
        self.logger.info("Starting manual region selection...")
        regions = self._manual_select_regions()
        
        return regions
    
    def _auto_detect_digits(self, gray_image: np.ndarray) -> List[TemplateRegion]:
        """
        Pokušaj automatsku detekciju cifara.
        
        Uses:
        - Thresholding
        - Contour detection
        - Size filtering
        """
        regions = []
        
        try:
            # Preprocess
            _, binary = cv2.threshold(gray_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Find contours
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Filter and sort contours
            valid_contours = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                
                # Filter by size (adjust these values based on your font)
                if 10 < w < 50 and 15 < h < 60:
                    # Check aspect ratio
                    aspect = h / w
                    if 0.5 < aspect < 3.0:
                        valid_contours.append((x, y, w, h))
            
            # Sort by x coordinate (left to right)
            valid_contours.sort(key=lambda c: c[0])
            
            # Create regions (user needs to assign characters)
            for i, (x, y, w, h) in enumerate(valid_contours):
                regions.append(TemplateRegion(
                    character="?",  # To be assigned
                    x=x, y=y, width=w, height=h
                ))
            
            return regions
            
        except Exception as e:
            self.logger.error(f"Auto-detection failed: {e}")
            return []
    
    def _manual_select_regions(self) -> List[TemplateRegion]:
        """Manual region selection using GUI"""
        regions = []
        
        # Create GUI for selection
        selector = ManualRegionSelector(self.current_image)
        regions = selector.select_regions()
        
        return regions
    
    def save_templates(self, regions: List[TemplateRegion], prefix: str = ""):
        """
        Sačuvaj template slike.
        
        Args:
            regions: Lista regiona sa karakterima
            prefix: Prefix za ime fajla
        """
        if self.current_image is None:
            raise ValueError("No image loaded")
        
        saved_count = 0
        
        for region in regions:
            # Extract region from image
            roi = self.current_image[
                region.y:region.y + region.height,
                region.x:region.x + region.width
            ]
            
            # Determine output directory
            if region.character.isdigit():
                output_dir = self.output_dir / "digits"
                filename = f"{prefix}{region.character}.png"
            else:
                output_dir = self.output_dir / "special"
                # Map special characters to safe filenames
                char_map = {
                    '.': 'dot',
                    ',': 'comma',
                    '/': 'slash',
                    'x': 'x',
                    'X': 'X'
                }
                safe_name = char_map.get(region.character, f"char_{ord(region.character)}")
                filename = f"{prefix}{safe_name}.png"
            
            output_path = output_dir / filename
            
            # Save template
            cv2.imwrite(str(output_path), roi)
            self.logger.info(f"Saved template: {output_path}")
            saved_count += 1
        
        self.logger.info(f"Saved {saved_count} templates")
        
        # Save metadata
        self._save_metadata(regions, prefix)
    
    def _save_metadata(self, regions: List[TemplateRegion], prefix: str):
        """Sačuvaj metadata o template slikama"""
        metadata = {
            'prefix': prefix,
            'templates': []
        }
        
        for region in regions:
            metadata['templates'].append({
                'character': region.character,
                'x': region.x,
                'y': region.y,
                'width': region.width,
                'height': region.height
            })
        
        metadata_path = self.output_dir / f"{prefix}metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        self.logger.info(f"Saved metadata: {metadata_path}")
    
    def generate_from_video_frames(self, video_path: str, sample_rate: int = 30):
        """
        Generiši template iz video snimka.
        
        Args:
            video_path: Putanja do videa
            sample_rate: Uzmi frame svake N frame-ova
        """
        cap = cv2.VideoCapture(video_path)
        frame_count = 0
        templates_collected = set()
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            
            # Sample frames
            if frame_count % sample_rate != 0:
                continue
            
            # Process frame
            # ... extract digits and add to templates_collected
            
        cap.release()
        
        self.logger.info(f"Processed {frame_count} frames")


class ManualRegionSelector:
    """GUI za manuelnu selekciju regiona"""
    
    def __init__(self, image: np.ndarray):
        self.image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        self.regions = []
        self.current_rect = None
        self.start_point = None
        
        # Create GUI
        self.root = tk.Tk()
        self.root.title("Template Region Selector")
        
        # Setup UI
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup GUI komponente"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Instructions
        instructions = ttk.Label(
            main_frame,
            text="1. Click and drag to select a digit\n"
                 "2. Enter the character in the popup\n"
                 "3. Repeat for all digits\n"
                 "4. Click 'Done' when finished"
        )
        instructions.grid(row=0, column=0, columnspan=2, pady=5)
        
        # Canvas for image
        self.canvas = tk.Canvas(main_frame, width=800, height=400)
        self.canvas.grid(row=1, column=0, columnspan=2, pady=5)
        
        # Display image
        self.photo = ImageTk.PhotoImage(Image.fromarray(self.image))
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        
        # Bind mouse events
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        
        # Buttons
        ttk.Button(main_frame, text="Clear All", command=self.clear_all).grid(row=2, column=0, pady=5)
        ttk.Button(main_frame, text="Done", command=self.done).grid(row=2, column=1, pady=5)
        
        # Region list
        self.region_listbox = tk.Listbox(main_frame, height=10)
        self.region_listbox.grid(row=1, column=2, padx=10, sticky=(tk.N, tk.S))
        
    def on_mouse_down(self, event):
        """Mouse button pressed"""
        self.start_point = (event.x, event.y)
        
        # Delete previous rectangle if exists
        if self.current_rect:
            self.canvas.delete(self.current_rect)
        
    def on_mouse_drag(self, event):
        """Mouse dragged"""
        if self.start_point:
            # Delete previous rectangle
            if self.current_rect:
                self.canvas.delete(self.current_rect)
            
            # Draw new rectangle
            self.current_rect = self.canvas.create_rectangle(
                self.start_point[0], self.start_point[1],
                event.x, event.y,
                outline='red', width=2
            )
    
    def on_mouse_up(self, event):
        """Mouse button released"""
        if self.start_point:
            # Calculate region
            x1, y1 = self.start_point
            x2, y2 = event.x, event.y
            
            # Ensure correct order
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)
            
            # Minimum size check
            if (x2 - x1) > 5 and (y2 - y1) > 5:
                # Ask for character
                char = self.ask_character()
                
                if char:
                    # Add region
                    region = TemplateRegion(
                        character=char,
                        x=x1, y=y1,
                        width=x2 - x1,
                        height=y2 - y1
                    )
                    self.regions.append(region)
                    
                    # Update list
                    self.region_listbox.insert(tk.END, f"{char}: ({x1},{y1}) {x2-x1}x{y2-y1}")
                    
                    # Keep rectangle visible
                    self.canvas.itemconfig(self.current_rect, outline='green')
                    self.current_rect = None
            
            self.start_point = None
    
    def ask_character(self) -> Optional[str]:
        """Ask user for character"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Enter Character")
        
        ttk.Label(dialog, text="Enter the character for this region:").pack(pady=5)
        
        entry = ttk.Entry(dialog, width=10)
        entry.pack(pady=5)
        entry.focus()
        
        result = {'char': None}
        
        def ok():
            result['char'] = entry.get()
            dialog.destroy()
        
        ttk.Button(dialog, text="OK", command=ok).pack(pady=5)
        
        # Bind Enter key
        entry.bind('<Return>', lambda e: ok())
        
        # Wait for dialog
        dialog.wait_window()
        
        return result['char']
    
    def clear_all(self):
        """Clear all regions"""
        self.regions.clear()
        self.region_listbox.delete(0, tk.END)
        
        # Clear all rectangles from canvas
        for item in self.canvas.find_all():
            if item != self.canvas.find_withtag("image")[0]:
                self.canvas.delete(item)
    
    def done(self):
        """Finish selection"""
        self.root.quit()
        self.root.destroy()
    
    def select_regions(self) -> List[TemplateRegion]:
        """Start selection process"""
        self.root.mainloop()
        return self.regions


class BatchTemplateProcessor:
    """
    Batch processor za kreiranje template-a iz više screenshot-ova.
    Koristi se kada imaš folder sa screenshot-ovima.
    """
    
    def __init__(self, input_dir: str, output_dir: str = "data/ocr_templates"):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.generator = TemplateGenerator(output_dir)
        self.logger = logging.getLogger("BatchProcessor")
    
    def process_directory(self, auto_mode: bool = False):
        """
        Procesira sve slike u direktorijumu.
        
        Args:
            auto_mode: Ako True, pokušava automatsku detekciju
        """
        image_files = list(self.input_dir.glob("*.png")) + \
                     list(self.input_dir.glob("*.jpg")) + \
                     list(self.input_dir.glob("*.jpeg"))
        
        self.logger.info(f"Found {len(image_files)} images to process")
        
        all_templates = {}  # {character: [images]}
        
        for img_path in image_files:
            self.logger.info(f"\nProcessing: {img_path.name}")
            
            try:
                # Extract templates
                regions = self.generator.extract_digit_templates(
                    str(img_path),
                    auto_detect=auto_mode
                )
                
                # Collect unique templates
                for region in regions:
                    if region.character not in all_templates:
                        all_templates[region.character] = []
                    
                    # Extract template image
                    img = cv2.imread(str(img_path))
                    template = img[
                        region.y:region.y + region.height,
                        region.x:region.x + region.width
                    ]
                    all_templates[region.character].append(template)
                
            except Exception as e:
                self.logger.error(f"Error processing {img_path}: {e}")
        
        # Save best template for each character
        self._save_best_templates(all_templates)
    
    def _save_best_templates(self, templates: Dict[str, List[np.ndarray]]):
        """
        Sačuvaj najbolji template za svaki karakter.
        
        Najbolji = najoštriji/najčistiji
        """
        for char, images in templates.items():
            if not images:
                continue
            
            # Find best quality image (using Laplacian variance as sharpness metric)
            best_score = -1
            best_image = None
            
            for img in images:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
                score = cv2.Laplacian(gray, cv2.CV_64F).var()
                
                if score > best_score:
                    best_score = score
                    best_image = img
            
            if best_image is not None:
                # Save template
                if char.isdigit():
                    output_path = self.output_dir / "digits" / f"{char}.png"
                else:
                    char_map = {'.': 'dot', ',': 'comma', '/': 'slash', 'x': 'x'}
                    safe_name = char_map.get(char, f"char_{ord(char)}")
                    output_path = self.output_dir / "special" / f"{safe_name}.png"
                
                output_path.parent.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(output_path), best_image)
                
                self.logger.info(f"Saved template for '{char}' (sharpness: {best_score:.2f})")


def quick_template_setup():
    """
    Quick setup za kreiranje template-a.
    Interaktivni wizard za korisnika.
    """
    print("\n" + "="*60)
    print("TEMPLATE GENERATOR - QUICK SETUP")
    print("="*60)
    
    print("\nOvaj wizard će ti pomoći da kreiraš template slike za brzi OCR.")
    print("Trebaće ti screenshot-ovi sa svim ciframa (0-9) iz Aviator-a.\n")
    
    # Ask for input method
    print("Kako želiš da učitaš slike?")
    print("1. Pojedinačni screenshot")
    print("2. Folder sa više screenshot-ova")
    print("3. Video snimak")
    
    choice = input("\nIzbor (1-3): ").strip()
    
    generator = TemplateGenerator()
    
    if choice == "1":
        # Single screenshot
        root = tk.Tk()
        root.withdraw()
        
        file_path = filedialog.askopenfilename(
            title="Izaberi screenshot",
            filetypes=[("Images", "*.png *.jpg *.jpeg"), ("All files", "*.*")]
        )
        
        if file_path:
            print(f"\nProcessing: {file_path}")
            
            # Extract templates
            regions = generator.extract_digit_templates(file_path, auto_detect=True)
            
            if not regions:
                print("\nAutomatska detekcija neuspešna. Prelazim na manuelnu selekciju...")
                regions = generator.extract_digit_templates(file_path, auto_detect=False)
            
            if regions:
                # Save templates
                generator.save_templates(regions, prefix="aviator_")
                print(f"\n✅ Uspešno kreirano {len(regions)} template-a!")
            else:
                print("\n❌ Nije pronađen nijedan region.")
    
    elif choice == "2":
        # Batch processing
        root = tk.Tk()
        root.withdraw()
        
        dir_path = filedialog.askdirectory(title="Izaberi folder sa screenshot-ovima")
        
        if dir_path:
            processor = BatchTemplateProcessor(dir_path)
            processor.process_directory(auto_mode=True)
            print("\n✅ Batch processing završen!")
    
    elif choice == "3":
        # Video processing
        print("\n⚠️  Video processing još nije implementiran.")
    
    else:
        print("\n❌ Nevaljan izbor.")
    
    print("\n" + "="*60)
    print("Template-i su sačuvani u: data/ocr_templates/")
    print("="*60)


def verify_templates():
    """Verifikuj da li su svi potrebni template-i kreirani"""
    template_dir = Path("data/ocr_templates")
    
    print("\n" + "="*60)
    print("TEMPLATE VERIFICATION")
    print("="*60)
    
    # Check digits
    print("\n📁 Checking digit templates:")
    digits_dir = template_dir / "digits"
    
    for digit in range(10):
        template_path = digits_dir / f"{digit}.png"
        if template_path.exists():
            img = cv2.imread(str(template_path))
            h, w = img.shape[:2]
            print(f"  ✅ {digit}.png ({w}x{h})")
        else:
            print(f"  ❌ {digit}.png - MISSING!")
    
    # Check special characters
    print("\n📁 Checking special character templates:")
    special_dir = template_dir / "special"
    
    special_chars = {
        'dot': '.',
        'comma': ',',
        'slash': '/',
        'x': 'x'
    }
    
    for filename, char in special_chars.items():
        template_path = special_dir / f"{filename}.png"
        if template_path.exists():
            img = cv2.imread(str(template_path))
            h, w = img.shape[:2]
            print(f"  ✅ {filename}.png ('{char}') ({w}x{h})")
        else:
            print(f"  ❌ {filename}.png ('{char}') - MISSING!")
    
    print("\n" + "="*60)


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Template Generator for OCR")
    parser.add_argument('--mode', choices=['quick', 'verify', 'batch'], 
                       default='quick',
                       help='Operating mode')
    parser.add_argument('--input', type=str, help='Input directory or file')
    parser.add_argument('--output', type=str, default='data/ocr_templates',
                       help='Output directory')
    parser.add_argument('--auto', action='store_true',
                       help='Use automatic detection')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
    )
    
    if args.mode == 'quick':
        quick_template_setup()
    
    elif args.mode == 'verify':
        verify_templates()
    
    elif args.mode == 'batch':
        if not args.input:
            print("Error: --input required for batch mode")
            return
        
        processor = BatchTemplateProcessor(args.input, args.output)
        processor.process_directory(auto_mode=args.auto)
    
    else:
        print(f"Unknown mode: {args.mode}")


if __name__ == "__main__":
    main()