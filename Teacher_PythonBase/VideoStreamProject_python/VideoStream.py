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
		with self.lock:
			data = self.file.read(5)
			if data: 
				try:
					framelength = int(data)
					data = self.file.read(framelength)
					self.frameNum += 1
					self.timestamp += 30000
				except Exception as e:
					return None
			else:
				# End of file reached - return None to stop playback
				return None
			return data
		
	def getTimestamp(self):
		"""Get frame number."""
		return self.timestamp
	
	def getTotalSize(self):
		return self.fileSize

	def seek_frame(self, target_frame): 
		"""Seek to specified frame position."""
		with self.lock:
			# Reset to beginning of file
			self.file.seek(0)
			self.frameNum = 0
			self.timestamp = 0
			
			# Skip (target_frame - 1) frames so that next nextFrame() returns target_frame
			frames_to_skip = target_frame - 1 if target_frame > 0 else 0
			frames_skipped = 0
			
			while frames_skipped < frames_to_skip:
				try:
					data = self.file.read(5)
					if not data:
						break
					length = int(data)
					self.file.seek(length, 1)  # Skip frame data
					frames_skipped += 1
					self.frameNum += 1
					self.timestamp += 30000
				except:
					break
