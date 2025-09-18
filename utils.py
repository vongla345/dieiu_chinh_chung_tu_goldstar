import os
import io
import fitz
import re
import numpy as np
import cv2
import datetime
import pdfplumber
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def create_text(
    text: str,
    font_path: str,
    font_size: int = 12,
    is_year: bool = False,
    output_path: str = None
):
    """
    1. Tạo PDF tạm thời với text tiếng Việt
    2. Chuyển thành ảnh PNG đã crop vùng cần thiết
    3. Trả về path ảnh để Streamlit có thể hiển thị
    """

    font_name = os.path.splitext(os.path.basename(font_path))[0]
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_pdf = f"/tmp/temp_text_{timestamp}.pdf"
    output = output_path or f"/tmp/text_output_{timestamp}.png"

    try:
        # 1. Đăng ký font
        pdfmetrics.registerFont(TTFont(font_name, font_path))

        # 2. Vẽ vào PDF tạm
        c = canvas.Canvas(temp_pdf, pagesize=A4)
        c.setFont(font_name, font_size)
        c.drawString(100, 500, text)  # vị trí chữ
        c.save()

        # 3. Chuyển PDF => ảnh bằng PyMuPDF
        overlay = fitz.open(temp_pdf)
        page = overlay[0]
        pix = page.get_pixmap(dpi=300)

        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)

        # 4. Crop ảnh theo tọa độ
        if is_year:
            x0, x1, top, bottom = 420, 580, 1370, 1440
        else:
            x0, x1, top, bottom = 400, 480, 1370, 1440

        crop = img[int(top):int(bottom), int(x0):int(x1)]

        # 5. Lưu ảnh
        cv2.imwrite(output, crop)

        # Clean
        if os.path.exists(temp_pdf):
            os.remove(temp_pdf)

        return output

    except Exception as e:
        print(f"✗ Lỗi: {str(e)}")
        if os.path.exists(temp_pdf):
            os.remove(temp_pdf)
        return None

def insert_patch_all_pages(doc, patch_path, pixel_coords, dpi=300, pages=None):
    """
    Insert an image patch into all pages (or specified pages) of a PDF.
    
    Args:
        pdf_bytes: PDF file as bytes
        output_path: Output PDF file path
        patch_path: Image patch file path
        pixel_coords: Tuple of (x0, x1, top, bottom) in pixel coordinates
        dpi: DPI used when extracting the image (default 300)
        pages: List of page numbers to process (0-based). If None, process all pages.
    """
    # Unpack and convert coordinates
    x0_px, x1_px, top_px, bottom_px = pixel_coords
    scale_factor = 72.0 / dpi
    
    x0_pt = x0_px * scale_factor
    x1_pt = x1_px * scale_factor
    top_pt = top_px * scale_factor
    bottom_pt = bottom_px * scale_factor
    
    rect = fitz.Rect(x0_pt, top_pt, x1_pt, bottom_pt)
    
    
    # Determine which pages to process
    if pages is None:
        pages_to_process = range(len(doc))
    else:
        pages_to_process = pages
    
    processed_count = 0
    
    # Process each page
    for page_num in pages_to_process:
        if page_num < len(doc):
            page = doc[page_num]
            
            # Draw white rectangle to cover existing text
            page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
            
            # Insert the image patch
            page.insert_image(rect, filename=patch_path)
            
            processed_count += 1
    
    # Return the modified document
    return doc

def get_date(pdf_bytes, type):
    """
    Lấy số ngày từ text có dạng 'Ngày/Date: XX'
    Return: số ngày dạng string, đã được pad zero (01, 02, etc.)
    """
    # Tìm số sau Ngày/Date:
    
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = pdf.pages[0].extract_text()
    
    if type == 'thu_tien':
        day_pattern = r"Ngày/Date:\s*(\d+)"
        month_pattern = r"Tháng/Month:\s*(\d+)"
        year_pattern = r"Năm/Year:\s*(\d+)"
        
        # Tìm các số
        day = re.search(day_pattern, text)
        month = re.search(month_pattern, text)
        year = re.search(year_pattern, text)
        
        # Trích xuất các giá trị
        day = int(day.group(1)) if day else None
        month = int(month.group(1)) if month else None
        year = int(year.group(1)) if year else None
        if day and month and year:
            date = datetime.date(year, month, day)
        else:
            date = None
    elif type == 'xuat_kho':
        date_pattern = r"Ngày xuất/\s*Posting date:\s*(\d{2})-(\d{2})-(\d{4})"
        date = re.search(date_pattern, text)
        if date:
            day, month, year = date.groups()
            date = datetime.date(int(year), int(month), int(day))
        else:
            date = None

    return date