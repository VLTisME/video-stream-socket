import struct
import threading # <--- THÊM THƯ VIỆN NÀY
import os

class VideoStream:
	def __init__(self, filename):
		self.filename = filename
		try:
			self.fileSize = os.path.getsize(filename)
			self.file = open(filename, 'rb')
		except:
			raise IOError
		self.frameNum = 0
		self.timestamp = 0
		# Tạo khóa để quản lý việc đọc file
		self.lock = threading.Lock() 

	def nextFrame(self):
		"""Get next frame."""
		# Dùng Lock để đảm bảo không ai tua file khi đang đọc frame này
		with self.lock:
			data = self.file.read(5)
			self.timestamp += 3000
			if data: 
				framelength = int(data)
				data = self.file.read(framelength)
				self.frameNum += 1
			return data
		
	def getTimestamp(self):
		"""Get frame number."""
		return self.timestamp
	
	def getTotalSize(self):
		return self.fileSize

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
