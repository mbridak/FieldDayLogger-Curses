#!/usr/bin/env python3
import sqlite3
from sqlite3 import Error
fdbands = ('160', '80', '40', '20', '15', '10', '6', '2', '222', '432', 'SAT')




def getBandModeTally(band, mode):
	database = "WFD_Curses.db"
	conn = ""
	conn = sqlite3.connect(database)
	c = conn.cursor()
	c.execute("select count(*) as tally, MAX(power) as mpow from contacts where band = '"+band+"' AND mode ='"+mode+"'")
	return c.fetchone()

def getbands():
	bandlist=[]
	database = "WFD_Curses.db"
	conn = ""
	conn = sqlite3.connect(database)
	c = conn.cursor()
	c.execute("select DISTINCT band from contacts")
	x=c.fetchall()
	if x:
		for count in x:
			bandlist.append(count[0])
		return bandlist
	return []

def generateBandModeTally():
	blist = getbands()
	print("\t\tCW\tPWR\tDI\tPWR\tPH\tPWR")
	print("-"*60)
	for b in fdbands:
		if b in blist:
			cwt = getBandModeTally(b,"CW")
			dit = getBandModeTally(b,"DI")
			pht = getBandModeTally(b,"PH")
			print("Band:\t%s\t%s\t%s\t%s\t%s\t%s\t%s" % (b, cwt[0], cwt[1], dit[0], dit[1], pht[0], pht[1]))
			print("-"*60)

generateBandModeTally()