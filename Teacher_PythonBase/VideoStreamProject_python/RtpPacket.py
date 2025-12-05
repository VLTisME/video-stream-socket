import sys
from time import time

class RtpPacket:	
	HEADER_SIZE = 12
	header = bytearray(HEADER_SIZE)
	
	def __init__(self):
		pass
		
	def encode(self, version, padding, extension, cc, marker, pt, seqnum, timestamp, ssrc, payload):
		"""Encode the RTP packet with header fields and payload."""
		# timestamp = int(time())
		header = bytearray(self.HEADER_SIZE)
		#--------------
		# TO COMPLETE
		#--------------
		# Fill the header bytearray with RTP header fields
		header[0] = (version << 6 | padding << 5 | extension << 4 | cc) & 0xFF
		header[1] = (marker << 7 | pt) & 0xFF
		#Seqnum

		header[2] = (seqnum >> 8) & 0xFF
		header[3] = (seqnum) & 0xFF
		
		# [SỬA] Gán timestamp từ tham số
		header[4] = (timestamp >> 24) & 0xFF
		header[5] = (timestamp >> 16) & 0xFF
		header[6] = (timestamp >> 8) & 0xFF
		header[7] = (timestamp) & 0xFF
		
		header[8] = (ssrc >> 24) & 0xFF
		header[9] = (ssrc >> 16)& 0xFF
		header[10] = (ssrc >> 8) & 0xFF
		header[11] = (ssrc) & 0xFF
		
		self.payload = payload
		self.header = header
		return self.header + self.payload

	def decode(self, byteStream):
		"""Decode the RTP packet."""
		self.header = bytearray(byteStream[:self.HEADER_SIZE])
		self.payload = byteStream[self.HEADER_SIZE:]
	
	def version(self):
		return int(self.header[0] >> 6)
	
	def marker(self):
		return int(self.header[1] >> 7)
	
	def seqNum(self):
		seqNum = self.header[2] << 8 | self.header[3]
		return int(seqNum)
	
	def timestamp(self):
		timestamp = self.header[4] << 24 | self.header[5] << 16 | self.header[6] << 8 | self.header[7]
		return int(timestamp)
	
	def payloadType(self):
		pt = self.header[1] & 127
		return int(pt)
	
	def getPayload(self):
		return self.payload
		
	def getPacket(self):
		"""Return RTP packet."""
		return self.header + self.payload

class JpegHeader:
	HEADER_SIZE = 8
	def __init__(self):
		self.header = bytearray(self.HEADER_SIZE)
	def encode(self, typeSpecific, offset, type, q, width, height, payload):
		self.header[0] = (typeSpecific<<8) & 0xFFFFFF

		self.header[1] = offset >> 16 & 0xFF
		self.header[2] = offset >> 8 & 0xFF
		self.header[3] = offset & 0xFF

		self.header[4] = type & 0xFF

		self.header[5] = q & 0xFF

		self.header[6] = width/8 & 0xFF

		self.header[7] = height/8 & 0xFF
		
		self.payload = payload
		return self.header + self.payload
	def decode(self, byteStream):
		self.header = bytearray(byteStream[:self.HEADER_SIZE])
		self.payload = byteStream[self.HEADER_SIZE:]

	def offset(self):
		offset = self.header[1]<<16 | self.header[2]<<8 | self.header[3]
		return offset
	def getPayload(self):
		return self.payload
