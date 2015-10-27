#! /usr/bin/python

from Tkinter import *
import tkMessageBox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os,time

from RtpPacket import RtpPacket


CACHE_FILE_NAME = "Gong-"
CACHE_FILE_EXT = ".jpg"


class Client:

	SETUP_TAG = "Setup"
        PLAY_TAG = "Play"
        PAUSE_TAG = "Pause"
        TEARDOWN_TAG = "Teardown"

        # STATE
        INIT = 0
        READY = 1
        PLAYING = 2
        state = INIT

        # ACTION
        SETUP = 0
        PLAY = 1
        PAUSE = 2
        TEARDOWN = 3

        # RTSP Data
        RTSP_VER = "RTSP/1.0"
        PROTOCOL = "RTP/UDP"

	def __init__(self, master, serverAddr, serverPort, rtpPort, filename):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW",self.handler)
		self.createWidgets()
                self.serverAddr = serverAddr
                self.serverPort = int(serverPort)
                self.rtpPort = int(rtpPort)
                self.filename = filename
                self.rtspSeq = 0
                self.sessionId = 0
                self.teardownLabel = 0
                self.NowNbr = 0
                self.teardownACK = 0
                
  
        def connectServer(self):
                self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                        self.rtspSocket.connect((self.serverAddr,self.serverPort))
                except:
                        tkMessageBox.showwarning('fail to connect \'%s\''%self.serverAddr)
                        
        # Establish the UI for user                
	def createWidgets(self):
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
                self.teardown["command"] =  self.tearDown
                self.teardown.grid(row=1, column=3, padx=2, pady=2)

                # Create a label to display the movie
                self.label = Label(self.master, height=19)
                self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5)

        def setupMovie(self):
                if self.state == self.INIT:
                        self.connectServer() # connect to the server.
                        self.rtspSeq = self.rtspSeq+1 # the seq number starts at 1
                        # send the request
                        request = "%s %s %s" % (self.SETUP_TAG,self.filename,self.RTSP_VER)
                        request+="\nCSeq: %d" % self.rtspSeq
                        request+="\nTransport: %s; client_port= %d" % (self.PROTOCOL,self.rtpPort)
                        print "\n"+request
                        # send the rtsp request
                        self.rtspSocket.send(request)
                        # track the action
                        self.track = self.SETUP
                        # establish the thread to listen the return rtsp packet from the server
                        threading.Thread(target = self.recvRtspback).start()

        def playMovie(self):
                if self.state == self.READY:
                        self.rtspSeq = self.rtspSeq+1
                        # send the play request
                        request = "%s %s %s" % (self.PLAY_TAG,self.filename,self.RTSP_VER)
                        request+="\nCSeq: %d" % self.rtspSeq
                        request+="\nSession: %d"%self.sessionId
                        print "\n"+request
                        self.rtspSocket.send(request)
                        self.track = self.PLAY
                        # start a thread to control the play, pause and teardown.
                        self.playEvent = threading.Event()
                        self.playEvent.clear()
                        # start a thread to listen to the data from the rtp socket
                        threading.Thread(target = self.getRtp).start()
                        

        def pauseMovie(self):
                if self.state == self.PLAYING:
                        self.rtspSeq = self.rtspSeq + 1
                        # the pause requesst
                        request = "%s %s %s" % (self.PAUSE_TAG,self.filename,self.RTSP_VER)
                        request+="\nCSeq: %d" % self.rtspSeq
                        request+="\nSession: %d"%self.sessionId
                        print "\n"+request
                        # send the rtsp pause socket
                        self.rtspSocket.send(request)
                        self.track = self.PAUSE

        def tearDown(self):
                # we could click the teardown button while the video is playing or pause
                if self.state == self.PLAYING or self.state == self.READY:       
                        self.rtspSeq = self.rtspSeq+1
                        request = "%s %s %s" % (self.TEARDOWN_TAG,self.filename,self.RTSP_VER)
                        request+="\nCSeq: %d" % self.rtspSeq
                        request+="\nSession: %d"%self.sessionId
                        print "\n"+request
                        self.rtspSocket.send(request)
                        self.track = self.TEARDOWN

        def getRtp(self):
                while True:
                        try: 
                                # receive the video data from the server
                                vedio = self.rtpSocket.recv(65535)
                                if vedio:
                                        time.sleep(0.035)
                                        rtpCon = RtpPacket()
                                        rtpCon.decode(vedio)
                                        currFrameNbr = rtpCon.seqNum()

                                        if currFrameNbr > self.NowNbr:
                                                self.NowNbr = currFrameNbr
                                                self.updateMovie(self.writeFrame(rtpCon.getPayload())) 
                                        else:
                                                self.updateMovie(self.writeFrame(rtpCon.getPayload()))

                        except:
                                if self.playEvent.isSet() and self.teardownACK ==1:
                                        self.teardownACK = 0
                                        #close the rtp socket, if the movie is already over, print the text!
                                        try:
                                                self.rtpSocket.shutdown(socket.SHUT_RDWR)
                                                self.rtpSocket.close()
                                        except:
                                                print "fiish playing"
                                        break

                                if self.playEvent.isSet():
                                        break
                                
                                
        def writeFrame(self, data):
                """Write the received frame to a temp image file. Return the image file."""
                if self.teardownACK==0:
                        name = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
                        file = open(name, "wb")
                        file.write(data)
                        file.close()
                self.teardownACK = 0
                return name

        def updateMovie(self, imageFile):
                """Update the image file as video frame in the GUI."""
                photo = ImageTk.PhotoImage(Image.open(imageFile))
                self.label.configure(image=photo, height=288)
                self.label.image = photo

        def recvRtspback(self):
                while True:
                        reply = self.rtspSocket.recv(1024)
                        print reply
                        if reply:
                                content = reply.split('\n')
                                if int(content[0].split(" ")[1]) == 404:
                                        print "Not find the video"
                                        break
                                if int(content[0].split(" ")[1]) == 500:
                                        print "connection error"
                                        break        
                                seqBack = int(content[1].split(" ")[1])
                                if seqBack==self.rtspSeq:
                                        session = int(content[2].split(" ")[1])
                                        if self.sessionId == 0:
                                                self.sessionId = session 
                                        if self.sessionId == session:
                                                if int(content[0].split(" ")[1]) == 200:
                                                        if self.track == self.SETUP:
                                                                self.state = self.READY
                                                                # establish the rtp socket and be ready to receive the video
                                                                self.rtpSocket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
                                                                # set the socket buffer size to 65535 as the mac default is 9k
                                                                self.rtpSocket.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,65535)
                                                                # set the timeout is 0.5s
                                                                self.rtpSocket.settimeout(0.5)
                                                                self.rtpSocket.bind(('', self.rtpPort))
                                                        elif self.track == self.PLAY:
                                                                self.state = self.PLAYING
                                                        elif self.track == self.PAUSE:
                                                                self.playEvent.set()
                                                                self.state = self.READY
                                                        elif self.track == self.TEARDOWN:
                                                                self.playEvent.set()
                                                                # delete the cache picture
                                                                os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)
                                                                self.teardownACK = 1
                                                                self.state = self.INIT
                                                                self.sessionId = 0
                                                                self.rtspSeq = 0
                                                                self.NowNbr = 0
                        # close the rtsp socket  
                        if self.track == self.TEARDOWN:
                                self.rtspSocket.shutdown(socket.SHUT_RDWR)
                                self.rtspSocket.close()
                                break
                                
                                                                                                
        def handler(self):
                self.pauseMovie()
                if tkMessageBox.askokcancel("Are you sure you want to quit?"):
                        self.tearDown()
                        self.master.destroy()
                else:
                        self.playMovie()

                
                                                                




		