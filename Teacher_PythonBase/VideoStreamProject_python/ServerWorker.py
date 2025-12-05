from random import randint
import sys, traceback, threading, socket

from VideoStream import VideoStream
from RtpPacket import RtpPacket

CLOCK_TICK = 900000
class ServerWorker:
	SETUP = 'SETUP'
	PLAY = 'PLAY'
	PAUSE = 'PAUSE'
	TEARDOWN = 'TEARDOWN'
	SET_PARAMETER = 'SET_PARAMETER'
	
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
				print("processing SETUP\n")
				try:
					self.clientInfo['videoStream'] = VideoStream(filename)
					self.state = self.READY
				except IOError:
					self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])
                
				self.clientInfo['session'] = randint(100000, 999999)
				self.replyRtsp(self.OK_200, seq[1])
				self.clientInfo['rtpPort'] = request[2].split(' ')[3]
        
        # Process PLAY request      
		elif requestType == self.PLAY:
			if self.state == self.READY:
				print("processing PLAY\n")
				self.state = self.PLAYING
				self.clientInfo["rtpSocket"] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				self.replyRtsp(self.OK_200, seq[1])
				self.clientInfo['event'] = threading.Event()
				self.clientInfo['worker']= threading.Thread(target=self.sendRtp) 
				self.clientInfo['worker'].start()
        
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
			self.clientInfo['rtpSocket'].close()
            
		elif requestType == self.SET_PARAMETER:
			print("processing SET_PARAMETER")
            
			for line in request:
				if "Quality:" in line:
					try:
						params = line.split(',')
                        # params[0] la "Quality: 1080p" -> lay "1080p"
						qualityVal = params[0].split(':')[1].strip() 
                        # params[1] la " time=51" -> lay "51"
						timeVal = int(params[1].split('=')[1].strip()) 
                        
						print(f"Request Quality: '{qualityVal}', Time: {timeVal}")
                        
						newFileName = ""
						if qualityVal == "720p":
							newFileName = "movie.Mjpeg"
						elif qualityVal == "1080p":
							newFileName = "movie_1080p.Mjpeg" 
                        
						if newFileName != "":
							print(f"Server switching to file: {newFileName}")
                            # Đổi luồng video
							self.clientInfo['videoStream'] = VideoStream(newFileName)
							self.clientInfo['videoStream'].seekFrame(timeVal)
							self.replyRtsp(self.OK_200, seq[1])
						else:
							print(f"Unknown quality value: {qualityVal}")
                            
					except Exception as e:
						print(f"Error switching quality: {e}")
                        # Nếu lỗi (ví dụ file không thấy), vẫn giữ nguyên luồng cũ
			
	def sendRtp(self):
		"""Send RTP packets over UDP."""
		while True:
			self.clientInfo['event'].wait(0.05) 
			
			# Stop sending if request is PAUSE or TEARDOWN
			if self.clientInfo['event'].isSet(): 
				break 
				
			data = self.clientInfo['videoStream'].nextFrame()
			if data: 
				frameNumber = self.clientInfo['videoStream'].frameNbr()
				try:
					address = self.clientInfo['rtspSocket'][1][0]
					port = int(self.clientInfo['rtpPort'])
					
					self.clientInfo['rtpSocket'].sendto(self.makeRtp(data, frameNumber),(address,port))
				except:
					print("Connection Error")
					#print('-'*60)
					#traceback.print_exc(file=sys.stdout)
					#print('-'*60)

	def makeRtp(self, payload, frameNbr):
		"""RTP-packetize the video data."""
		version = 2
		padding = 0
		extension = 0
		cc = 0
		marker = 0
		pt = 26 # MJPEG type
		seqnum = frameNbr
		ssrc = 0 
		
		rtpPacket = RtpPacket()
		
		rtpPacket.encode(version, padding, extension, cc, seqnum, marker, pt, ssrc, payload)
		
		return rtpPacket.getPacket()
		
	def replyRtsp(self, code, seq):
		"""Send RTSP reply to the client."""
		if code == self.OK_200:
			#print("200 OK")
			reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq + '\nSession: ' + str(self.clientInfo['session'])
			connSocket = self.clientInfo['rtspSocket'][0]
			connSocket.send(reply.encode())
		
		# Error messages
		elif code == self.FILE_NOT_FOUND_404:
			print("404 NOT FOUND")
		elif code == self.CON_ERR_500:
			print("500 CONNECTION ERROR")
