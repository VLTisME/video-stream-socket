from random import randint
import sys, traceback, threading, socket
import time
import math
from VideoStream import VideoStream
from RtpPacket import RtpPacket
from RtpPacket import JpegHeader

CLOCK_RATE = 900000
FRAME_RATE = 30
class ServerWorker:
	SETUP = 'SETUP'
	PLAY = 'PLAY'
	PAUSE = 'PAUSE'
	TEARDOWN = 'TEARDOWN'
	SEEK = 'SEEK'
	SET_PARAMETER = 'SET_PARAMETER'
	FPS = 30
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT

	OK_200 = 0
	FILE_NOT_FOUND_404 = 1
	CON_ERR_500 = 2
	
	clientInfo = {}
	
	def __init__(self, clientInfo):
		self.clientInfo = clientInfo
		
	def run(self):
		threading.Thread(target=self.recvRtspRequest).start()
	
	def recvRtspRequest(self):
		"""Receive RTSP request from the client."""
		connSocket = self.clientInfo['rtspSocket'][0]
		while True:            
			data = connSocket.recv(256)
			if data:
				print("Data received:\n" + data.decode("utf-8"))
				self.processRtspRequest(data.decode("utf-8"))
	
	def processRtspRequest(self, data):
		"""Process RTSP request sent from the client."""
		# Get the request type
		request = data.split('\n')
		line1 = request[0].split(' ')
		requestType = line1[0]
		
		# Get the media file name
		filename = line1[1]
		
		# Get the RTSP sequence number 
		seq = request[1].split(' ')
		
		# Process SETUP request
		if requestType == self.SETUP:
			if self.state == self.INIT:
				# Update state
				print("processing SETUP\n")
				
				try:
					self.clientInfo['videoStream'] = VideoStream(filename)
					
					self.state = self.READY
				except IOError:
					self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1], '')
					return
				# Generate a randomized RTSP session ID
				self.clientInfo['session'] = randint(100000, 999999)
				#Lấy tổng size
				totalSize = self.clientInfo['videoStream'].getTotalSize()
				total = self.clientInfo['videoStream'].getTotalFrame()
		
				#Tạo extra_Header chuẩn RTSP (Range: npt=start-end)
				extra_header = "\nDuration: %f" % (total/self.FPS)
				
				# Send RTSP reply
				self.replyRtsp(self.OK_200, seq[1], extra_header)
				
				# Get the RTP/UDP port from the last line
				self.clientInfo['rtpPort'] = request[2].split(' ')[3]
			
		# Process PLAY request 		
		elif requestType == self.PLAY:
			print("processing PLAY\n")
			
			start_frame = -1
			for line in request:
				if "Range: npt=" in line:
					try:
						# Lấy số giây (VD: npt=10.5-)
						val = line.split("=")[1].split("-")[0]
						start_time = float(val)
						start_frame = int(start_time * 30) # FPS = 30
					except: pass
			
			if start_frame > -1:
				print(f"Server seeking to frame: {start_frame}")
				# Gọi hàm seek_frame của VideoStream
				self.clientInfo['videoStream'].seek_frame(start_frame)
			# ---------------------------

			# --- 2. XỬ LÝ TRẠNG THÁI ---
			if self.state == self.READY:
				# Trường hợp 1: Đang dừng -> Bắt đầu chạy (Tạo Thread mới)
				self.state = self.PLAYING
				
				if 'rtpSocket' not in self.clientInfo:
					self.clientInfo["rtpSocket"] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				
				self.replyRtsp(self.OK_200, seq[1])
				
				self.clientInfo['event'] = threading.Event()
				self.clientInfo['worker']= threading.Thread(target=self.sendRtp) 
				self.clientInfo['worker'].start()
			
			elif self.state == self.PLAYING:
				self.replyRtsp(self.OK_200, seq[1])
		# Process PAUSE request
		elif requestType == self.PAUSE:
			if self.state == self.PLAYING:
				print("processing PAUSE\n")
				self.state = self.READY
				
				self.clientInfo['event'].set()
			
				self.replyRtsp(self.OK_200, seq[1])
		
		# Process TEARDOWN request
		elif requestType == self.TEARDOWN:
			print("processing TEARDOWN\n")

			self.clientInfo['event'].set()
			
			self.replyRtsp(self.OK_200, seq[1])
			
			# Close the RTP socket
			self.clientInfo['rtpSocket'].close()
		elif requestType == self.SEEK:
			pass

		# Process SET_PARAMETER request (quality switching)
		elif requestType == self.SET_PARAMETER:
			print("processing SET_PARAMETER\n")
			
			qualityVal = ""
			client_timestamp = 0
			
			# Parse request to get quality and timestamp
			for line in request:
				if "Quality:" in line:
					try:
						parts = line.split(',')
						qualityVal = parts[0].split(':')[1].strip()
						client_timestamp = int(parts[1].split('=')[1].strip())
					except:
						pass
			
			# 2. Chọn file
			newFileName = ""
			if qualityVal == "480p": newFileName = "movie_480p.Mjpeg"
			elif qualityVal == "720p": newFileName = "movie_720p.Mjpeg"
			elif qualityVal == "1080p": newFileName = "movie_1080p.Mjpeg"
			
			if newFileName != "":
				try:
					# Calculate target frame from timestamp
					target_frame = client_timestamp // 30000
					
					# Create new stream and seek to position
					newStream = VideoStream(newFileName)
					newStream.seek_frame(target_frame)
					
					# Hot-swap the stream
					self.clientInfo['videoStream'] = newStream
					
					self.replyRtsp(self.OK_200, seq[1])
				except Exception as e:
					print(f"Error switching: {e}")
					self.replyRtsp(self.CON_ERR_500, seq[1])
			else:
				self.replyRtsp(self.OK_200, seq[1])

	def sendRtp(self):
		"""Send RTP packets over UDP."""
		while True:
			self.clientInfo['event'].wait(0.003)
			# Stop sending if request is PAUSE or TEARDOWN
			if self.clientInfo['event'].isSet(): 
				break 
				
			stream = self.clientInfo['videoStream']
			frame = stream.nextFrame()
			timestamp = stream.getTimestamp()
			
			if frame:
				PAYLOADSIZE = 1400
				size = len(frame)
				nFragments = math.ceil(size/PAYLOADSIZE)
				try:
					address = self.clientInfo['rtspSocket'][1][0]
					port = int(self.clientInfo['rtpPort'])
					marker = 0
					# Sending fragments
					for i in range(nFragments):
						offset = i*PAYLOADSIZE
						end = 0
						if offset + PAYLOADSIZE >= size:
							end = size
							marker = 1
						else: 
							end = offset+PAYLOADSIZE
						chunk = frame[offset:end]
						packet = JpegHeader()
						typeSpecific = 0
						type_ = 0
						q = 255
						width = 0
						height = 0
						packet.encode(typeSpecific,offset,type_,q,width,height,chunk)
						self.clientInfo['rtpSocket'].sendto(self.makeRtp(packet.getPacket(), i+1, timestamp,marker),(address,port))
				except:
					print("Connection Error")
			else:
				pass
	def makeRtp(self, payload, seqNum, timestamp,marker):
		"""RTP-packetize the video data."""
		version = 2
		padding = 0
		extension = 0
		cc = 0
		pt = 26 # MJPEG type
		ssrc = 0 
		ts = timestamp
		rtpPacket = RtpPacket()

		rtpPacket.encode(version, padding, extension, cc, marker, pt, seqNum, ts, ssrc, payload)
		return rtpPacket.getPacket()
		
	def replyRtsp(self, code, seq, totalTime = ''):
		"""Send RTSP reply to the client."""
		if code == self.OK_200:
			#print("200 OK")
			reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq + '\nSession: ' + str(self.clientInfo['session'])
			reply += totalTime
			connSocket = self.clientInfo['rtspSocket'][0]
			print(reply)
			connSocket.send(reply.encode())

		# Error messages
		elif code == self.FILE_NOT_FOUND_404:
			print("404 NOT FOUND")
		elif code == self.CON_ERR_500:
			print("500 CONNECTION ERROR")
