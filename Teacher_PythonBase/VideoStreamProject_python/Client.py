from tkinter import *
import tkinter.messagebox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

class Client:
    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT
    
    SETUP = 0
    PLAY = 1
    PAUSE = 2
    TEARDOWN = 3
    SET_PARAMETER = 4 # Request type cho đổi quality
 
    RTSP_VER = "RTSP/1.0"
    TRANSPORT = "RTP/UDP"
    
    # Initiation..
    def __init__(self, master, serveraddr, serverport, rtpport, filename):
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.createWidgets()
        self.serverAddr = serveraddr
        self.serverPort = int(serverport)
        self.rtpPort = int(rtpport)
        self.fileName = filename
        self.buffer = {} 
        self.queueRender = []
        self.rtspSeq = 0
        self.sessionId = 0
        self.requestSent = -1
        self.teardownAcked = 0
        self.connectToServer()
        self.frameNbr = 0
        self.currentQuality = "720p" # Mặc định là 720p
        self.PLAY_STR = "PLAY"
        self.PAUSE_STR = "PAUSE"
        self.TEARDOWN_STR = "TEARDOWN"
        self.SETUP_STR = "SETUP"
        self.SET_PARAMETER_STR = "SET_PARAMETER"
        
    def createWidgets(self):
        """Build GUI."""
        # Create Setup button
        self.setup = Button(self.master, width=15, padx=3, pady=3)
        self.setup["text"] = "Setup"
        self.setup["command"] = self.setupMovie
        self.setup.grid(row=1, column=0, padx=2, pady=2)
        
        # Create Play button        
        self.start = Button(self.master, width=15, padx=3, pady=3)
        self.start["text"] = "Play"
        self.start["command"] = self.playMovie
        self.start.grid(row=1, column=1, padx=2, pady=2)
        
        # Create Pause button           
        self.pause = Button(self.master, width=15, padx=3, pady=3)
        self.pause["text"] = "Pause"
        self.pause["command"] = self.pauseMovie
        self.pause.grid(row=1, column=2, padx=2, pady=2)
        
        # Create Teardown button
        self.teardown = Button(self.master, width=15, padx=3, pady=3)
        self.teardown["text"] = "Teardown"
        self.teardown["command"] =  self.exitClient
        self.teardown.grid(row=1, column=3, padx=2, pady=2)
        
        # [NEW] Quality Switcher (Chỉ 720p và 1080p)
        self.qualityVar = StringVar(self.master)
        self.qualityVar.set("720p") 
        qualities = ["720p", "1080p"]
        self.qualityMenu = OptionMenu(self.master, self.qualityVar, *qualities, command=self.changeQuality)
        self.qualityMenu.config(width=10)
        self.qualityMenu.grid(row=1, column=4, padx=2, pady=2)

        # Create a label to display the movie
        self.label = Label(self.master, height=19)
        self.label.grid(row=0, column=0, columnspan=5, sticky=W+E+N+S, padx=5, pady=5) 
    
    def changeQuality(self, value):
        if self.state in [self.READY, self.PLAYING]:
            if value == self.currentQuality:
                return

            self.currentQuality = value
            print(f"[CLIENT] Switching to {value}...")
            
            # Note: clear current buffer works fine // but maybe create new buffer as discussed
            self.buffer.clear()
            self.queueRender.clear()
            
            self.sendRtspRequest(self.SET_PARAMETER)

    def setupMovie(self):
        if self.state == self.INIT:
            self.sendRtspRequest(self.SETUP)
    
    def exitClient(self):
        self.sendRtspRequest(self.TEARDOWN)     
        self.master.destroy() 
        try:
            os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT) 
        except OSError:
            pass

    def pauseMovie(self):
        if self.state == self.PLAYING:
            self.sendRtspRequest(self.PAUSE)
    
    def playMovie(self):
        if self.state == self.READY:
            threading.Thread(target=self.listenRtp).start()
            self.playEvent = threading.Event()
            self.playEvent.clear()
            self.sendRtspRequest(self.PLAY)
    
    def listenRtp(self):        
        while True:
            try:
                data = self.rtpSocket.recv(20480)
                if data:
                    rtpPacket = RtpPacket()
                    rtpPacket.decode(data)
                    
                    currFrameNbr = rtpPacket.seqNum()
                    # print("Current Seq Num: " + str(currFrameNbr))
                                        
                    if currFrameNbr > self.frameNbr: 
                        self.frameNbr = currFrameNbr
                        self.updateMovie(self.writeFrame(rtpPacket.getPayload()))
            except:
                if self.playEvent.isSet(): 
                    break
                if self.teardownAcked == 1:
                    self.rtpSocket.shutdown(socket.SHUT_RDWR)
                    self.rtpSocket.close()
                    break
                    
    def writeFrame(self, data):
        cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
        file = open(cachename, "wb")
        file.write(data)
        file.close()
        return cachename
    
    def updateMovie(self, imageFile):
        photo = ImageTk.PhotoImage(Image.open(imageFile))
        self.label.configure(image = photo, height=288) 
        self.label.image = photo
        
    def connectToServer(self):
        self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.rtspSocket.connect((self.serverAddr, self.serverPort))
        except:
            tkinter.messagebox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' %self.serverAddr)
    
    def sendRtspRequest(self, requestCode):
        # Setup request
        if requestCode == self.SETUP and self.state == self.INIT:
            threading.Thread(target=self.recvRtspReply).start()
            self.rtspSeq += 1
            request = "%s %s %s" % (self.SETUP_STR, self.fileName, self.RTSP_VER)
            request += "\nCSeq: %d" % self.rtspSeq
            request += "\nTransport: %s; port: %d" % (self.TRANSPORT, self.rtpPort)
            self.requestSent = self.SETUP
        
        # Play request
        elif requestCode == self.PLAY and self.state == self.READY:
            self.rtspSeq += 1
            request = "%s %s %s" % (self.PLAY_STR, self.fileName, self.RTSP_VER)
            request += "\nCSeq: %d" % self.rtspSeq
            request += "\nSession: %d" % self.sessionId
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

        elif requestCode == self.SET_PARAMETER:
            self.rtspSeq += 1
            # Format: SET_PARAMETER rtsp://server/stream RTSP/1.0
            request = "%s rtsp://%s/%s %s" % (self.SET_PARAMETER_STR, self.serverAddr, self.fileName, self.RTSP_VER)
            request += "\nCSeq: %d" % self.rtspSeq
            request += "\nSession: %d" % self.sessionId
            request += "\nQuality: %s, time=%s" % (self.currentQuality, str(self.frameNbr))
            
            self.requestSent = self.SET_PARAMETER
        else:
            return
        
        self.rtspSocket.send(request.encode())
        print('\nData sent:\n' + request)
    
    def recvRtspReply(self):
        while True:
            try:
                reply = self.rtspSocket.recv(1024)
                if reply: 
                    self.parseRtspReply(reply.decode("utf-8"))
                
                if self.requestSent == self.TEARDOWN:
                    self.rtspSocket.shutdown(socket.SHUT_RDWR)
                    self.rtspSocket.close()
                    break
            except:
                break
    
    def parseRtspReply(self, data):
        lines = data.split('\n')
        seqNum = int(lines[1].split(' ')[1])
        
        if seqNum == self.rtspSeq:
            session = int(lines[2].split(' ')[1])
            if self.sessionId == 0:
                self.sessionId = session
            
            if self.sessionId == session:
                if int(lines[0].split(' ')[1]) == 200: 
                    if self.requestSent == self.SETUP:
                        self.state = self.READY
                        self.openRtpPort()
                    elif self.requestSent == self.PLAY:
                        self.state = self.PLAYING
                    elif self.requestSent == self.PAUSE:
                        self.state = self.READY
                        self.playEvent.set()
                    elif self.requestSent == self.TEARDOWN:
                        self.state = self.INIT
                        self.teardownAcked = 1 
                    
                    # [NEW] Xác nhận đổi quality
                    elif self.requestSent == self.SET_PARAMETER:
                        print(f"[CLIENT] Server verified switch to {self.currentQuality}")
    
    def openRtpPort(self):
        address = ''
        self.rtpSocket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        try:
            self.rtpSocket.bind((address,self.rtpPort))
            self.rtpSocket.settimeout(0.5)
        except:
            tkinter.messagebox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' %self.rtpPort)

    def handler(self):
        self.pauseMovie()
        if tkinter.messagebox.askokcancel("Quit?", "Are you sure you want to quit?"):
            self.exitClient()
        else:
            self.playMovie()