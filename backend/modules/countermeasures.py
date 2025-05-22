#!/usr/bin/python3
# -*- encoding: utf-8 -*-

from PIL import Image
import io

def strip_metadata(img: Image.Image) -> Image.Image:
    img = img.convert('RGB')
    clean_img = Image.new(img.mode, img.size)
    clean_img.putdata(list(img.getdata()))
    return clean_img

def reencode_image(img: Image.Image, format='JPEG', quality=85) -> io.BytesIO:
    buffer = io.BytesIO()
    img.save(buffer, format=format, quality=quality)
    buffer.seek(0)
    return buffer
