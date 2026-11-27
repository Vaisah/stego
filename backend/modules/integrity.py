#!/usr/bin/python3
# -*- encoding: utf-8 -*-

from PIL import Image, ImageChops, ImageStat
import numpy as np
import math
import base64
from io import BytesIO

class ImageAnalyzer:
    def __init__(self):
        pass
    
    def calculate_mse(self, img1, img2):
        """Calculate Mean Squared Error between two images"""
        arr1 = np.array(img1)
        arr2 = np.array(img2)
        return np.mean((arr1 - arr2) ** 2)
    
    def calculate_psnr(self, img1, img2):
        """Calculate Peak Signal-to-Noise Ratio"""
        mse = self.calculate_mse(img1, img2)
        if mse == 0:
            return float('inf')
        max_pixel = 255.0
        return 20 * math.log10(max_pixel / math.sqrt(mse))
    
    def calculate_ssim_simple(self, img1, img2):
        """Simplified SSIM calculation using PIL ImageStat"""
        stat1 = ImageStat.Stat(img1)
        stat2 = ImageStat.Stat(img2)
        
        # Calculate means
        mean1 = sum(stat1.mean) / len(stat1.mean)
        mean2 = sum(stat2.mean) / len(stat2.mean)
        
        # Calculate variances (approximation)
        var1 = sum(stat1.var) / len(stat1.var)
        var2 = sum(stat2.var) / len(stat2.var)
        
        # Simplified SSIM calculation
        c1 = (0.01 * 255) ** 2
        c2 = (0.03 * 255) ** 2
        
        numerator = (2 * mean1 * mean2 + c1) * (2 * math.sqrt(var1 * var2) + c2)
        denominator = (mean1**2 + mean2**2 + c1) * (var1 + var2 + c2)
        
        return numerator / denominator if denominator != 0 else 0
    
    def get_image_hash(self, image):
        """Calculate perceptual hash of image"""
        # Convert to grayscale and resize for hashing
        hash_img = image.convert('L').resize((8, 8), Image.Resampling.LANCZOS)
        pixels = list(hash_img.getdata())
        avg = sum(pixels) / len(pixels)
        
        # Create binary hash
        hash_bits = []
        for pixel in pixels:
            hash_bits.append('1' if pixel > avg else '0')
        
        return ''.join(hash_bits)
    
    def analyze_histogram_similarity(self, img1, img2):
        """Compare color histograms of two images"""
        hist1 = img1.histogram()
        hist2 = img2.histogram()
        
        # Calculate histogram correlation
        sum_sq1 = sum(x*x for x in hist1)
        sum_sq2 = sum(x*x for x in hist2)
        sum_mult = sum(x*y for x, y in zip(hist1, hist2))
        
        if sum_sq1 == 0 or sum_sq2 == 0:
            return 0
        
        correlation = sum_mult / math.sqrt(sum_sq1 * sum_sq2)
        return correlation * 100
    
    def image_to_base64(self, image):
        """Convert PIL Image to base64 string for display"""
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    
    def compare_images(self, orig_path, clean_path):
        """Main method to compare two images and return detailed analysis"""
        # Open and process images
        img1 = Image.open(orig_path).convert("RGB")
        img2 = Image.open(clean_path).convert("RGB")
        
        # Basic image info
        result = {
            "original_size": img1.size,
            "cleaned_size": img2.size,
            "original_format": img1.format or "Unknown",
            "cleaned_format": img2.format or "Unknown"
        }
        
        # Check if images have same dimensions
        if img1.size != img2.size:
            # Resize smaller image to match larger one for comparison
            if img1.size[0] * img1.size[1] < img2.size[0] * img2.size[1]:
                img1 = img1.resize(img2.size, Image.Resampling.LANCZOS)
                result["note"] = "Original image was resized to match cleaned image dimensions"
            else:
                img2 = img2.resize(img1.size, Image.Resampling.LANCZOS)
                result["note"] = "Cleaned image was resized to match original image dimensions"
        
        # Calculate pixel differences
        diff = ImageChops.difference(img1, img2)
        pixels = img1.size[0] * img1.size[1]
        
        # Count different pixels
        diff_gray = diff.convert("L")
        diff_pixels = sum(1 for x in diff_gray.getdata() if x > 0)
        
        # Calculate similarity percentage
        pixel_similarity = max(0, 100 - (diff_pixels / pixels * 100))
        
        # Advanced metrics
        mse = self.calculate_mse(img1, img2)
        psnr = self.calculate_psnr(img1, img2)
        ssim = self.calculate_ssim_simple(img1, img2)
        histogram_similarity = self.analyze_histogram_similarity(img1, img2)
        
        # Perceptual hashes
        hash1 = self.get_image_hash(img1)
        hash2 = self.get_image_hash(img2)
        hash_similarity = sum(1 for a, b in zip(hash1, hash2) if a == b) / len(hash1) * 100
        
        # Overall integrity score (weighted average)
        integrity_score = (
            pixel_similarity * 0.3 +
            (psnr / 50 * 100 if psnr != float('inf') else 100) * 0.2 +
            ssim * 100 * 0.2 +
            histogram_similarity * 0.15 +
            hash_similarity * 0.15
        )
        integrity_score = min(100, max(0, integrity_score))
        
        # Generate difference visualization
        diff_enhanced = ImageChops.multiply(diff, Image.new('RGB', diff.size, (3, 3, 3)))
        
        # Basic compatibility with original template
        result.update({
            "match": diff_pixels == 0,  # Perfect match
            "integrity": round(integrity_score, 2),  # Overall integrity score
            
            # Extended metrics
            "perfect_match": diff_pixels == 0,
            "different_pixels": diff_pixels,
            "total_pixels": pixels,
            "pixel_similarity": round(pixel_similarity, 2),
            "mse": round(mse, 2),
            "psnr": round(psnr, 2) if psnr != float('inf') else "Perfect",
            "ssim": round(ssim, 4),
            "histogram_similarity": round(histogram_similarity, 2),
            "perceptual_hash_similarity": round(hash_similarity, 2),
            "overall_integrity": round(integrity_score, 2),
            "original_preview": self.image_to_base64(img1.resize((300, 300), Image.Resampling.LANCZOS)),
            "cleaned_preview": self.image_to_base64(img2.resize((300, 300), Image.Resampling.LANCZOS)),
            "difference_map": self.image_to_base64(diff_enhanced.resize((300, 300), Image.Resampling.LANCZOS))
        })
        
        # Interpretation
        if integrity_score >= 99:
            result["interpretation"] = "Excellent - Images are virtually identical"
        elif integrity_score >= 95:
            result["interpretation"] = "Very Good - Minor differences detected"
        elif integrity_score >= 90:
            result["interpretation"] = "Good - Some noticeable differences"
        elif integrity_score >= 80:
            result["interpretation"] = "Fair - Significant differences present"
        else:
            result["interpretation"] = "Poor - Major differences detected"
        
        return result