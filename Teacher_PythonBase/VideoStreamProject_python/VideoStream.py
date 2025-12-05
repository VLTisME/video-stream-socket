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
		self.total = 0
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
	# def getFrames(self):
	# 	"""Get next frame."""
	# 	# Dùng Lock để đảm bảo không ai tua file khi đang đọc frame này
	# 	while self.file.seekable():
	# 		data = self.file.read(5)
	# 		self.timestamp += 3000
	# 		if data: 
	# 			framelength = int(data)
	# 			data = self.file.seek(framelength, 1)
	# 			self.total += 1
	# 	return self.total
		
	def getTotalFrame(self):
		self.total = 0
		with self.lock:
			self.file.seek(0)
			while True:
				try:
					data = self.file.read(5)
					if not data: break
					length = int(data)
					self.file.seek(length, 1)
					self.total += 1
				except: break
			self.file.seek(0)
		return self.total
	def getTimestamp(self):
		"""Get frame number."""
		return self.frameNum
	
	def getTotalSize(self):
		return self.fileSize
	def getFrames(self):
		return self.frameNum
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
