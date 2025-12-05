# CreateHQVideo.py
# Tool này dùng để tạo file movie_1080p.Mjpeg đúng chuẩn từ file gốc
import sys
from PIL import Image, ImageDraw, ImageFont
import io

def create_1080p_file(input_file="movie.Mjpeg", output_file="movie_1080p.Mjpeg"):
    try:
        f_in = open(input_file, 'rb')
        f_out = open(output_file, 'wb')
        
        frame_count = 0
        print(f"Dang xu ly tu '{input_file}' sang '{output_file}'...")
        
        while True:
            # 1. Doc header 5 byte do dai cu
            data = f_in.read(5)
            if not data: break # Het file
            
            try:
                length = int(data)
            except:
                print("Gap loi khi doc file goc. Ket thuc.")
                break
                
            # 2. Doc du lieu anh JPEG
            img_data = f_in.read(length)
            
            # 3. Xu ly anh: Ve chu "1080p" vao
            try:
                # Load anh tu binary
                image = Image.open(io.BytesIO(img_data))
                
                # Ve chu len anh
                draw = ImageDraw.Draw(image)
                # Tu dong chon font mac dinh
                try:
                    # Co gang dung font lon neu co
                    font = ImageFont.truetype("arial.ttf", 40)
                except:
                    font = ImageFont.load_default()
                
                # Ve chu mau do
                draw.text((10, 10), "--- 1080p HQ MODE ---", fill="red", font=font)
                draw.rectangle([(0,0), (image.width, 10)], fill="red") # Ve them cai vien do
                
                # 4. Save anh moi ra binary
                output = io.BytesIO()
                image.save(output, format="JPEG")
                new_img_data = output.getvalue()
                
                # 5. Tinh do dai moi va tao header 5 byte
                new_length = len(new_img_data)
                # Format header thanh chuoi 5 ky tu (VD: 04500)
                header = "{:05d}".format(new_length).encode()
                
                # 6. Ghi vao file moi
                f_out.write(header)
                f_out.write(new_img_data)
                
                frame_count += 1
                if frame_count % 50 == 0:
                    print(f"Da xu ly {frame_count} frames...")
                    
            except Exception as e:
                print(f"Loi xu ly frame: {e}")
                break
                
        f_in.close()
        f_out.close()
        print(f"XONG! Da tao file {output_file} thanh cong voi {frame_count} frames.")
        print("Hay chay lai Server va Client de test.")
        
    except FileNotFoundError:
        print(f"LOI: Khong tim thay file '{input_file}'. Hay dam bao no nam cung thu muc.")

if __name__ == "__main__":
    create_1080p_file()