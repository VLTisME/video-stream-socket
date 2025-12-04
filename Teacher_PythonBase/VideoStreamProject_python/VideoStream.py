import struct
import threading # <--- THÊM THƯ VIỆN NÀY

class VideoStream:
	def __init__(self, filename):
		self.filename = filename
		try:
			self.file = open(filename, 'rb')
		except:
			raise IOError
		self.frameNum = 0
		
		# Tạo khóa để quản lý việc đọc file
		self.lock = threading.Lock() 
		
		# Đếm tổng số frame ngay khi mở file
		self.total_frames = 0
		self._count_frames()

	def _count_frames(self):
		"""Hàm nội bộ chỉ chạy 1 lần lúc đầu, không cần lock vì chưa có thread nào khác."""
		self.file.seek(0)
		while True:
			try:
				data = self.file.read(5)
				if not data: break
				length = int(data)
				self.file.seek(length, 1)
				self.total_frames += 1
			except: break
		self.file.seek(0)

	def nextFrame(self):
		"""Get next frame."""
		# Dùng Lock để đảm bảo không ai tua file khi đang đọc frame này
		with self.lock:
			data = self.file.read(5)
			if data: 
				framelength = int(data)
				data = self.file.read(framelength)
				self.frameNum += 1
			return data
		
	def frameNbr(self):
		"""Get frame number."""
		return self.frameNum
	
	def getTotalframe(self):
		return self.total_frames

	def seek_frame(self, target_frame): 
		"""Tua đến frame chỉ định."""
		# Dùng Lock để chặn luồng gửi RTP lại trong lúc đang tua
		with self.lock:
			# 1. Reset về đầu file
			self.file.seek(0)
			self.frameNum = 0
			
			# 2. Lặp để nhảy cóc đến frame đích
			while self.frameNum < target_frame:
				try:
					data = self.file.read(5)
					if not data: break
					length = int(data)
					self.file.seek(length, 1) # Skip
					self.frameNum += 1
				except:
					break
