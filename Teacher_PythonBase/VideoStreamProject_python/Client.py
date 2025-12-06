from tkinter import *
import tkinter
import tkinter.messagebox as tkMessageBox
import tkinter.messagebox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os

import io
from queue import Queue
import queue
import time
from RtpPacket import RtpPacket
from RtpPacket import JpegHeader

CLOCK_TICK = 900000

class Frame:
	def __init__(self, timestamp, payload):
		self.timestamp = timestamp
		self.payload = payload
class Client:
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT
	
	SETUP = 0
	PLAY = 1
	PAUSE = 2
	TEARDOWN = 3
	SEEK = 4
	SET_PARAMETER = 5
 
	RTSP_VER = "RTSP/1.0"
	TRANSPORT = "RTP/UDP"
	
	# Initiation..
	def __init__(self, master, serveraddr, serverport, rtpport, filename):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)

		# Quality to filename mapping (allows picking 480p before setup)
		self.quality_files = {
			"480p": "movie_480p.Mjpeg",
			"720p": "movie_720p.Mjpeg",
			"1080p": "movie_1080p.Mjpeg"
		}
		# Default to 720p, but if the provided filename matches a known variant, sync the dropdown
		self.currentQuality = next((q for q, f in self.quality_files.items() if f == filename), "720p")
		self.fileName = self.quality_files[self.currentQuality]

		self.createWidgets()
		self.serverAddr = serveraddr
		self.serverPort = int(serverport)
		self.rtpPort = int(rtpport)

		self.buffer = {} #key: timestamp, value: {seqNum1: payload1, ...}
		self.queueRender = Queue()
		self.queueWork = Queue()
		self.current_render_timestamp = 0  # Track the timestamp of the frame being rendered

		self.movie_frame = 0
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.teardownAcked = 0
		self.totalDuration = 0
		self.start_time = 0.0
		self.pending_seek_time = None 
		self.connectToServer()

		self.is_dragging = False
		self.FPS = 30
		self.delay = 1.0/self.FPS
		self.PLAY_STR = "PLAY"
		self.PAUSE_STR = "PAUSE"
		self.TEARDOWN_STR = "TEARDOWN"
		self.SETUP_STR = "SETUP"
		self.SEEK_STR = "SEEK"
		self.SET_PARAMETER_STR = "SET_PARAMETER"
		self.currentQuality = "720p"
		self.last_rtp_timestamp = 0
		
		# Quality to filename mapping
		self.quality_files = {
			"480p": "movie_480p.Mjpeg",
			"720p": "movie_720p.Mjpeg",
			"1080p": "movie_1080p.Mjpeg"
		}
		
		# Cache for resize parameters to avoid recalculating each frame
		self.resize_cache = {}  # key: (img_width, img_height), value: (new_width, new_height, offset_x, offset_y)

		self.i =0
		
	def createWidgets(self):
		"""Build GUI."""
		# Create Setup button
		self.setup = Button(self.master, width=20, padx=3, pady=3)
		self.setup["text"] = "Setup"
		self.setup["command"] = self.setupMovie
		self.setup.grid(row=1, column=0, padx=2, pady=2)
		

		# Create Play button		
		self.start = Button(self.master, width=20, padx=3, pady=3)
		self.start["text"] = "Play"
		self.start["command"] = self.playMovie
		self.start.grid(row=1, column=1, padx=2, pady=2)
		
		# Create Pause button			
		self.pause = Button(self.master, width=20, padx=3, pady=3)
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.grid(row=1, column=2, padx=2, pady=2)
		
		# Create Teardown button
		self.teardown = Button(self.master, width=20, padx=3, pady=3)
		self.teardown["text"] = "Teardown"
		self.teardown["command"] =  self.exitClient
		self.teardown.grid(row=1, column=3, padx=2, pady=2)

		self.qualityVar = StringVar(self.master)
		self.qualityVar.set(self.currentQuality)
		qualities = ["480p", "720p", "1080p"]
		self.qualityMenu = OptionMenu(self.master, self.qualityVar, *qualities, command=self.changeQuality)
		self.qualityMenu.config(width=10)
		self.qualityMenu.grid(row=1, column=4, padx=2, pady=2)		
  
		#create Slider
		self.timeline_w = 400  # Chiều dài timeline (pixel)
		self.timeline_h = 20   # Chiều cao timeline
		self.canvas = Canvas(self.master, width=self.timeline_w, height=self.timeline_h, bg="#444444", highlightthickness=0)
		self.canvas.grid(row=2, column=0, columnspan=4, padx=10, pady=10)
		self.buffer_rect = self.canvas.create_rectangle(0, 0, 0, self.timeline_h, fill="#888888", width=0)
		self.progress_rect = self.canvas.create_rectangle(0, 0, 0, self.timeline_h, fill="#FF0000", width=0)
		self.canvas.bind("<Button-1>", self.on_timeline_click)
		self.canvas.bind("<B1-Motion>", self.on_timeline_drag)
		self.canvas.bind("<ButtonRelease-1>", self.on_timeline_release)
		
		# Create a frame to contain the video with fixed size
		self.video_frame = tkinter.Frame(self.master, bg="black")
		self.video_frame.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5)
		self.video_frame.grid_propagate(False)  # Prevent frame from resizing
		self.video_frame.config(width=640, height=480)
		
		# Create a label to display the movie inside the fixed frame
		self.label = tkinter.Label(self.video_frame, bg="black")
		self.label.pack(fill=BOTH, expand=True)
		
		# Fixed video dimensions for display
		self.video_width = 640
		self.video_height = 480

	def changeQuality(self, value):
		# Allow pre-setup selection: just sync quality + filename, no network call
		if self.state == self.INIT:
			self.currentQuality = value
			self.fileName = self.quality_files.get(self.currentQuality, self.fileName)
			return

		if self.state in [self.READY, self.PLAYING]:
			if value == self.currentQuality: return
			self.currentQuality = value
			self.fileName = self.quality_files.get(self.currentQuality, self.fileName)
			
			# Clear resize cache when quality changes (new resolution expected)
			self.resize_cache.clear()
			
			# Clear all buffers to prevent mixing old/new quality frames
			with self.queueRender.mutex:
				self.queueRender.queue.clear()
			with self.queueWork.mutex:
				self.queueWork.queue.clear()
			self.buffer.clear()
			
			# Use current rendering timestamp to maintain playback position
			switch_timestamp = self.current_render_timestamp if self.current_render_timestamp > 0 else self.last_rtp_timestamp
			self.sendRtspRequest(self.SET_PARAMETER, timestamp=switch_timestamp)
	
	def setupMovie(self):
		"""Setup button handler."""
		if self.state == self.INIT:
			# Honor current dropdown selection (enables starting directly at 480p)
			self.currentQuality = self.qualityVar.get()
			self.fileName = self.quality_files.get(self.currentQuality, self.fileName)
			self.sendRtspRequest(self.SETUP)
	
	def exitClient(self):
		"""Teardown button handler."""
		self.sendRtspRequest(self.TEARDOWN)		
		self.master.destroy() # Close the gui window

	def pauseMovie(self):
		"""Pause button handler."""
		if self.state == self.PLAYING:
			self.sendRtspRequest(self.PAUSE)
	
	def playMovie(self):
		"""Play button handler."""
		if self.state == self.READY:
			# Create a new thread to listen for RTP packets
			threading.Thread(target=self.listenRtp).start()
			threading.Thread(target=self.processPacket).start()
			self.playEvent = threading.Event()
			self.playEvent.clear()

			self.renderLoop()
			start_time = self.pending_seek_time if self.pending_seek_time is not None else -1.0
			self.sendRtspRequest(self.PLAY, start_time=start_time)
			self.pending_seek_time = None
	
	def renderLoop(self):
		if self.playEvent.is_set() or self.teardownAcked == 1:
			return
		try:
			ms = 30
			timestamp, frame = self.queueRender.get_nowait()
			self.current_render_timestamp = timestamp
			self.movie_frame += 1
			print(self.movie_frame)
			currentTime = self.movie_frame / self.FPS
			self.draw_timeline(currentTime)
			self.updateMovie(frame)
		except queue.Empty:
			pass
		except Exception as e:
			print(f"Error rendering frame: {e}")
		self.master.after(ms,self.renderLoop)

	def listenRtp(self):		
		"""Listen for RTP packets."""
		while True:
			try:
				data = self.rtpSocket.recv(20480)	
				if data:
					rtpPacket = RtpPacket()
					rtpPacket.decode(data)
					self.last_rtp_timestamp = rtpPacket.timestamp()
					self.queueWork.put(rtpPacket)
        
			except:
				pass

			# Stop listening upon requesting PAUSE or TEARDOWN
			if self.playEvent.isSet(): 
				break
			
			# Upon receiving ACK for TEARDOWN request,
			# close the RTP socket
			if self.teardownAcked == 1:
				self.rtpSocket.shutdown(socket.SHUT_RDWR)
				self.rtpSocket.close()
				break
					
	def processPacket(self):
		while True:
			try:
				packet = self.queueWork.get(timeout=0.5)
				ts = packet.timestamp()
				seqNum = packet.seqNum()
				
				if ts not in self.buffer:
					self.buffer[ts] = {}
				
				if seqNum not in self.buffer[ts]:
					payload = packet.getPayload()
					fragment = JpegHeader()
					fragment.decode(payload)
					self.buffer[ts][seqNum] = fragment

				if packet.marker() == 1:
					if self.isComplete(ts,seqNumEnd=seqNum):
						self.reassemble(ts,seqNumEnd= seqNum)
					else: 
						del self.buffer[ts]
			except:
				continue
			if self.playEvent.isSet(): 
				break
			
			if self.teardownAcked == 1:
				break

	def isComplete(self, timestamp, seqNumEnd):
		for seqNum in range(seqNumEnd,0,-1):
			if seqNum not in self.buffer[timestamp]:
				return False
			else:
				if self.buffer[timestamp][seqNum].offset() == 0:
					break
		return True
			
	def reassemble(self, timestamp,seqNumEnd):
		fragments = self.buffer[timestamp]
		frame = bytearray(fragments[seqNumEnd].offset() + len(fragments[seqNumEnd].getPayload()))

		for seqNum in fragments:
			offset = fragments[seqNum].offset()
			payload = fragments[seqNum].getPayload()
			frame[offset:offset+len(payload)] = payload
		
		# Store frame with its timestamp
		self.queueRender.put((timestamp, bytes(frame)))

	def updateMovie(self, data):
		"""Update the image file as video frame in the GUI - FAST VERSION."""
		try:
			# Since server now outputs fixed 640x480 at different qualities,
			# we can display directly without resize
			image = io.BytesIO(data)
			img = Image.open(image)
			photo = ImageTk.PhotoImage(img)
			self.label.configure(image=photo)
			self.label.image = photo
		except Exception as e:
			print(f"Error updating movie frame: {e}")

	def connectToServer(self):
		"""Connect to the Server. Start a new RTSP/TCP session."""
		self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self.rtspSocket.connect((self.serverAddr, self.serverPort))
		except:
			tkMessageBox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' %self.serverAddr)
	
	def sendRtspRequest(self, requestCode, start_time=-1.0, timestamp=0):
		"""Send RTSP request to the server."""	
		#-------------
		# TO COMPLETE
		#-------------
		
		# Setup request
		if requestCode == self.SETUP and self.state == self.INIT:
			threading.Thread(target=self.recvRtspReply).start()
			# Update RTSP sequence number.
			self.rtspSeq += 1
			
			# Write the RTSP request to be sent.
			request = "%s %s %s" % (self.SETUP_STR, self.fileName, self.RTSP_VER)
			request += "\nCSeq: %d" % self.rtspSeq
			request += "\nTransport: %s; port: %d" % (self.TRANSPORT, self.rtpPort)
			
			# Keep track of the sent request.
			self.requestSent = self.SETUP
		
		# Play request
		elif requestCode == self.PLAY and (self.state == self.READY or self.state == self.PLAYING):
			self.rtspSeq += 1
   
			request = "%s %s %s" % (self.PLAY_STR, self.fileName, self.RTSP_VER)
			request += "\nCSeq: %d" % self.rtspSeq
			request += "\nSession: %d" % self.sessionId
			if start_time >= 0:
				request += "\nRange: npt=%.2f-" % start_time
			self.requestSent = self.PLAY
			
		
		# Pause request
		elif requestCode == self.PAUSE and self.state == self.PLAYING:
			self.rtspSeq += 1
   
			request = "%s %s %s" % (self.PAUSE_STR, self.fileName, self.RTSP_VER)
			request += "\nCSeq: %d" % self.rtspSeq
			request += "\nSession: %d" % self.sessionId
   
			self.requestSent = self.PAUSE
			
		# Teardown request
		elif requestCode == self.TEARDOWN and not self.state == self.INIT:
			self.rtspSeq += 1
   
			request = "%s %s %s" % (self.TEARDOWN_STR, self.fileName, self.RTSP_VER)
			request += "\nCSeq: %d" % self.rtspSeq
			request += "\nSession: %d" % self.sessionId
   
			self.requestSent = self.TEARDOWN
		elif requestCode == self.SEEK:
			self.rtspSeq += 1

			request = "%s %s %s" % (self.SEEK_STR, self.fileName, self.RTSP_VER)
			request += "\nCSeq: %d" % self.rtspSeq
			request += "\nSession: %d" % self.sessionId

			self.requestSent = self.SEEK
		# [THÊM] Đoạn xử lý SET_PARAMETER
		elif requestCode == self.SET_PARAMETER:
			self.rtspSeq += 1
			# Lưu ý: Chỗ này sửa lại format string cho đúng
			request = "%s rtsp://%s/%s %s" % (self.SET_PARAMETER_STR, self.serverAddr, self.fileName, self.RTSP_VER)
			request += "\nCSeq: %d" % self.rtspSeq
			request += "\nSession: %d" % self.sessionId
			# Dòng quan trọng gửi timestamp
			request += "\nQuality: %s, timestamp=%d" % (self.currentQuality, int(timestamp))
			
			self.requestSent = self.SET_PARAMETER
		else:
			return
		
		# Send the RTSP request using rtspSocket.
		# ...
		self.rtspSocket.send(request.encode())
		
		print('\nData sent:\n' + request)
	
	def recvRtspReply(self):
		"""Receive RTSP reply from the server."""
		while True:
			reply = self.rtspSocket.recv(1024)
			
			if reply: 
				self.parseRtspReply(reply.decode("utf-8"))
			
			# Close the RTSP socket upon requesting Teardown
			if self.requestSent == self.TEARDOWN:
				self.rtspSocket.shutdown(socket.SHUT_RDWR)
				self.rtspSocket.close()
				break
	
	def parseRtspReply(self, data):
		"""Parse the RTSP reply from the server."""
		lines = data.split('\n')
		seqNum = int(lines[1].split(' ')[1])
		
		# Process only if the server reply's sequence number is the same as the request's
		if seqNum == self.rtspSeq:
			session = int(lines[2].split(' ')[1])
			# New RTSP session ID
			if self.sessionId == 0:
				self.sessionId = session
			
			# Process only if the session ID is the same
			if self.sessionId == session:
				if int(lines[0].split(' ')[1]) == 200: 

					if self.requestSent == self.SETUP:
						self.state = self.READY
						
						if len(lines) >= 4:
							self.totalDuration = (float)(lines[3].split(' ')[1])
						# Open RTP port.
						self.openRtpPort()

					elif self.requestSent == self.PLAY:
						self.state = self.PLAYING
						

					elif self.requestSent == self.PAUSE:
						self.state = self.READY
						# The play thread exits. A new thread is created on resume.
						self.playEvent.set()

					elif self.requestSent == self.TEARDOWN:
						self.state = self.INIT
						
						# Flag the teardownAcked to close the socket.
						self.teardownAcked = 1 
	
	def openRtpPort(self):
		"""Open RTP socket binded to a specified port."""
		address = ''
		# Create a new datagram socket to receive RTP packets from the server
		self.rtpSocket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)

		try:
			# Bind the socket to the address using the RTP port given by the client user
			self.rtpSocket.bind((address,self.rtpPort))
			# Set the timeout value of the socket to 0.5sec
			self.rtpSocket.settimeout(0.5)
		except:
			tkMessageBox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' %self.rtpPort)

	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		self.pauseMovie()
		if tkMessageBox.askokcancel("Quit?", "Are you sure you want to quit?"):
			self.exitClient()
		else: # When the user presses cancel, resume playing.
			self.playMovie()

	def queueClear(queue):
		while True:
			try:
				queue.get_nowait()
			except:
				return

	def on_timeline_click(self, event):
		self.is_dragging = True
		self.on_timeline_drag(event)

	def on_timeline_drag(self, event):
		if self.totalDuration == 0: return
		cur_x = event.x
		if cur_x < 0: cur_x = 0
		if cur_x > self.timeline_w: cur_x = self.timeline_w
		self.canvas.coords(self.progress_rect, 0, 0, cur_x, self.timeline_h)

	def on_timeline_release(self, event):
		if self.totalDuration == 0: return
		
		click_x = event.x
		if click_x < 0: click_x = 0
		if click_x > self.timeline_w: click_x = self.timeline_w
		
		ratio = click_x / float(self.timeline_w)
		target_time = ratio * self.totalDuration
		
		print(f"Seeking to: {target_time}")
		bufferTime = self.queueRender.qsize() / self.FPS
		# with self.queueRender.mutex:
		# 	self.queueRender.queue.clear()
		

		current_time = self.movie_frame / 30

		if target_time <= bufferTime + current_time and target_time >= current_time:
			num_skip_frame = int((target_time - current_time) * 30) 
			for x in range(num_skip_frame):
				try:
					self.queueRender.get_nowait()
				except:
					break
			self.movie_frame += num_skip_frame
			self.is_dragging = False
			return	
	
		with self.queueRender.mutex:
			self.queueRender.queue.clear()
		with self.queueWork.mutex:
			self.queueWork.queue.clear()
		self.buffer.clear()
		self.movie_frame = int(target_time * self.FPS)
		self.pending_seek_time = target_time
		if self.state == self.PLAYING:
			self.sendRtspRequest(self.PLAY, start_time=target_time)
		# 4. Tắt cờ kéo chuột
		self.is_dragging = False

	def draw_timeline(self, current_time):
		if self.is_dragging: return
		if self.totalDuration > 0:
			buffer_seconds = self.queueRender.qsize() / float(self.FPS)
			
			# Điểm cuối của thanh xám
			buffer_end_time = current_time + buffer_seconds

			buff_ratio = buffer_end_time / self.totalDuration
			buff_width = buff_ratio * self.timeline_w
			
			# Giới hạn max width
			if buff_width > self.timeline_w: buff_width = self.timeline_w
			
			# Cập nhật tọa độ
			self.canvas.coords(self.buffer_rect, 0, 0, buff_width, self.timeline_h)

			# 2. VẼ THANH ĐỎ (PROGRESS) - Vẽ đè lên trên thanh xám
			prog_ratio = current_time / self.totalDuration
			prog_width = prog_ratio * self.timeline_w
			
			self.canvas.coords(self.progress_rect, 0, 0, prog_width, self.timeline_h)
