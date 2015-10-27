from random import randint
import sys, traceback, threading, socket

from VideoStream import VideoStream
from RtpPacket import RtpPacket


class ServerWorker:

	SETUP_REQ = "Setup"
	PLAY_REQ = "Play"
	PAUSE_REQ = "Pause"
	TEARDOWN_REQ = "Teardown"

	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT

	OK_200 = 0
	FILE_NOT_FOUND_404 = 1
	CON_ERR_500 = 2

	clientInfo = {}
	clientAddr = None
	

	def __init__(self, clientInfo):
		self.clientInfo = clientInfo
		self.clientrtpPort = 0
		self.rtpSocket = None
		
	def run(self):
		threading.Thread(target = self.recvRtspRequest).start()

	def recvRtspRequest(self):
		connSocket, (clientAddr, clientPort) = self.clientInfo['rtspSocket']
		self.clientAddr = clientAddr
		while True:
			data = connSocket.recv(1024)
			if data:
				print "\nData Recieve\n" + data
				#get the info from the data
				content = data.split("\n")
				array_1 = content[0].split(" ")
				# requst type: setup, play, pause, teardown
				reqType = array_1[0]
				# the filename 
				filename = array_1[1]
				# seq number
				seq = content[1].split(" ")[1]

				if reqType == self.SETUP_REQ:
					if self.state == self.INIT:
						print "set up the movie"
						array_3 = content[2].split(" ")
						# get hte rtp port number
						self.clientrtpPort = int(array_3[3])
						try:
							self.clientInfo['videoStream'] = VideoStream(filename)
						except:
							self.replyRtsp(self.FILE_NOT_FOUND_404,seq)

						self.state = self.READY
						self.session = randint(111, 777)
						self.replyRtsp(self.OK_200,seq)
						
				elif reqType == self.PLAY_REQ:
					if self.state == self.READY:
						self.state = self.PLAYING
						print "playing the movie"
						self.replyRtsp(self.OK_200,seq)
						# when get the play movie socket, establish the socket and be ready to send the video data
						if self.rtpSocket == None:
							self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
							self.rtpSocket.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,65535)
						# start a even to control the action of playing, pausing and teardown
						self.event_trigger = threading.Event()
						self.event_trigger.clear()
						# start a thread to send the video data
						threading.Thread(target = self.sendRtp).start()
					
				elif reqType == self.PAUSE_REQ:
					if self.state == self.PLAYING:
						print "pause the move"
						self.replyRtsp(self.OK_200,seq)
						# stop send the video to the client
						self.event_trigger.set()
						self.state = self.READY
						
				elif reqType == self.TEARDOWN_REQ:
					print "close the movie"
					self.replyRtsp(self.OK_200,seq)
					# stop send the video to the client
					self.event_trigger.set()
					self.state = self.INIT

	def sendRtp(self):
		while True:
			if self.event_trigger.isSet():
				break
			# It then sends the frame to the client over UDP every 50 milliseconds
			self.event_trigger.wait(0.05)
			# get the video source
			video = self.clientInfo['videoStream'].nextFrame()
			if video:
				videoNum = self.clientInfo['videoStream'].frameNbr()
				try:
					rtpParket = RtpPacket()
					# follow the format of RTP packet and establish the packet
					rtpParket.encode(2,0,0,0,videoNum,0,26,0,video)
					# send the data over UDP
					self.rtpSocket.sendto(rtpParket.getPacket(),(self.clientAddr,self.clientrtpPort))
				except:
					if self.rtpSocket == None:
						self.rtpSocket.shutdown(socket.SHUT_RDWR)
						self.rtpSocket.close()
					traceback.print_exc(file = sys.stdout)	
			else:
				print "Finish the playing"	
				break
		
			
	def replyRtsp(self, code, seq):
		if code == self.OK_200:
			reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq + '\nSession: ' + str(self.session)
			connSocket = self.clientInfo['rtspSocket'][0]
			connSocket.send(reply)
        # Error messages
		elif code == self.FILE_NOT_FOUND_404:
			print "404 NOT FOUND"
			reply = 'RTSP/1.0 404 OK'
			connSocket = self.clientInfo['rtspSocket'][0]
			connSocket.send(reply)
		elif code == self.CON_ERR_500:
			print "500 CONNECTION ERROR"
			reply = 'RTSP/1.0 500 OK'
			connSocket = self.clientInfo['rtspSocket'][0]
			connSocket.send(reply)
       
		




		

		
		

