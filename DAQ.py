#DAQ.py 
#Suman Giri  

#program that reads from a data-acquisition card (NI-DAQ 9215)
#and plots the voltage
#lets the user see the information in time and frequency domain
#lets the user save a snapshot, write the data to file, and adjust scales
#while writing, splits the written data into file snippets of 50 Mb csv files 



import ctypes    #library used here for handling/accessing dlls
import numpy     #libarary for list manipulations
import time
from time import *
import os
import pprint
import random
import csv        #for writing data into csv files
import sys  
import wx         #graphics
import matplotlib #library used here for plotting
matplotlib.use('WXAgg')
from matplotlib.figure import *
from matplotlib.backends.backend_wxagg import *
import pylab
from scipy import*
from pylab import *


#this loads the dll for the NIDAQ 
nidaq = ctypes.windll.nicaiu 



# typedefs are setup to correspond to NIDAQmx.h
int32 = ctypes.c_long
uInt32 = ctypes.c_ulong
uInt64 = ctypes.c_ulonglong
float64 = ctypes.c_double
TaskHandle = uInt32
written = int32()
pointsRead = uInt32()

#constants are setup to correspond to NIDAQmx.h
DAQmx_Val_Volts = 10348
DAQmx_Val_Rising = 10280
DAQmx_Val_Cfg_Default = int32(-1)
DAQmx_Val_ContSamps = 10123
DAQmx_Val_ChanForAllLines = 1
DAQmx_Val_RSE = 10083
DAQmx_Val_Volts = 10348
DAQmx_Val_GroupByScanNumber = 1
DAQmx_Val_FiniteSamps = 10178
DAQmx_Val_GroupByChannel = 0



#adapted with info from .NET and C code in
#http://zone.ni.com/devzone/cda/tut/p/id/5409#toc4


# initialize variables
taskHandle = TaskHandle(0)

#range of the DAQ
min1 = float64(-10.0) 
max1 = float64(10.0)
timeout = float64(10.0)
bufferSize = uInt32(10)
pointsToRead = bufferSize
pointsRead = uInt32()

#sampling rate
sampleRate = float64(200.0)
samplesPerChan = uInt64(100)

#specifiy the channels
chan = ctypes.create_string_buffer('Dev1/ai0')
clockSource = ctypes.create_string_buffer('OnboardClock')

#create a list of zeros for data
data = numpy.zeros((1000,),dtype=numpy.float64)


# set up the task in the required channel and
#fix sampling through internal clock
def SetupTask():
    nidaq.DAQmxCreateTask("",ctypes.byref(taskHandle))
    nidaq.DAQmxCreateAIVoltageChan(taskHandle,chan,"",
                                   DAQmx_Val_Cfg_Default,
                                   min1,max1,DAQmx_Val_Volts,None)
    nidaq.DAQmxCfgSampClkTiming(taskHandle,clockSource,sampleRate,
        DAQmx_Val_Rising,DAQmx_Val_ContSamps,samplesPerChan)
    nidaq.DAQmxCfgInputBuffer(taskHandle,200000)

#Start Task
def StartTask():
    nidaq.DAQmxStartTask (taskHandle)

#Read Samples
def ReadSamples(points):
    bufferSize = uInt32(points)
    pointsToRead = bufferSize
    data = numpy.zeros((points,),dtype=numpy.float64)
    nidaq.DAQmxReadAnalogF64(taskHandle,pointsToRead,timeout,
            DAQmx_Val_GroupByScanNumber,data.ctypes.data,
            uInt32(2*bufferSize.value),ctypes.byref(pointsRead),None)
    return data

#stop and clear
def StopAndClearTask():
    if taskHandle.value != 0:
        nidaq.DAQmxStopTask(taskHandle)
        nidaq.DAQmxClearTask(taskHandle)

#On specifying the number of points to be sampled, it gets
#the voltage value and returns it as a list data
def get(points=100):
    SetupTask()
    StartTask()
    data = ReadSamples(points)
    StopAndClearTask()
    return data


#received info from
#http://matplotlib.sourceforge.net/examples/axes_rid/index.html

class Samples(object):
#Samples from the DAQ card for plotting
    
    def __init__(self, init=100): 
        self.data = self.init = 0
        
    def getAnotherBatch(self):
    #gets the next 100 points each time it is called
        return get()
    
    def Transform(self):
    #gets the FFT of 1000 points when called
        return abs(fft(get(100)))

class Scaling(wx.Panel):
#subclass
#an object to create the framework to
#autoscale/manually scale the plot
    
    def __init__(self, other, ID, label, value):
        wx.Panel.__init__(self, other, ID)
        self.value = value
        box = wx.StaticBox(self, -1, label)
        
        #to resize the box accordingly
        sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        
        #radio buttons for options of scaling
        self.radioAuto = wx.RadioButton(self, -1, 
            label="Auto Scale", style=wx.RB_GROUP)
        self.radioManual = wx.RadioButton(self, -1,
            label="Manual Scale")
        
        #input box for manual scaling
        self.text = wx.TextCtrl(self, -1, 
            size=(35,-1),
            value=str(value),                           
            style=wx.TE_PROCESS_ENTER) 

        #call self.text upon value update
        self.Bind(wx.EVT_UPDATE_UI, self.updatemanual, self.text)
        self.Bind(wx.EVT_TEXT_ENTER, self.textmanual, self.text)
        
        manualBox = wx.BoxSizer(wx.HORIZONTAL)
        manualBox.Add(self.radioManual, flag=wx.ALIGN_CENTER_VERTICAL)
        manualBox.Add(self.text, flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.radioAuto, 0, wx.ALL, 10)
        sizer.Add(manualBox, 0, wx.ALL, 10)
        self.SetSizer(sizer)
        sizer.Fit(self)
        
    def updateauto(self):
    #when the auto radio button is updated
        return self.radioAuto.GetValue()

    def manual_value(self):
        return self.value
    
    def updatemanual(self, event):
    #when the manual radio button is updated
        self.text.Enable(self.radioManual.GetValue())
    
    def textmanual(self, event):
    #when a text is entered
        self.value = self.text.GetValue()
        
  


class Window(wx.Frame):
# The window object for the plot
# subclass of wx.Frame
    
    
    def __init__(self):
        wx.Frame.__init__(self, None, -1, 'Real-Time Voltage') #frame title
        
        self.paused = False
        self.transform=False
        self.write=False
        self.filenum=1            #counter for time domain files
        self.filenum1=1           #counter for freq domain files 
        self.filesize=50*1024*1024 #size that files need to be split to
        self.samples = Samples()
        
        #get 100 points in an array
        self.data = self.samples.getAnotherBatch()
        
        #create a menubar with ability to save plots
        self.makeMenubar()
        self.makeStatusbar()
        self.makeMainPanel()

        #initialize timer
        self.timerFired = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.goTimerFired, self.timerFired)        
        self.timerFired.Start(0.00001)

    def makeMenubar(self):
    #create a menubar with ability to save plots   
        self.menubar = wx.MenuBar()
        
        menu = wx.Menu()
        #save
        m_expt = menu.Append(-1, "&Save plot\tCtrl-S", "Save plot to file")
        self.Bind(wx.EVT_MENU, self.saveMenu, m_expt)
        menu.AppendSeparator()
        #exit
        m_exit = menu.Append(-1, "&Exit\tCtrl-C", "Exit")
        self.Bind(wx.EVT_MENU, self.exitMenu, m_exit)
        #menu        
        self.menubar.Append(menu, "&Menu")
        self.SetMenuBar(self.menubar)

    def makeMainPanel(self):
    #fill in the objects inside the mainpanel
        self.panel = wx.Panel(self)

        self.prepareGraph()
        #load canvas from wx library
        self.canvas = FigureCanvasWxAgg(self.panel, -1, self.fig)
        

        self.xmin = Scaling(self.panel, -1, "X min", 0)
        self.xmax = Scaling(self.panel, -1, "X max", 100)
        self.ymin = Scaling(self.panel, -1, "Y min", 0)
        self.ymax = Scaling(self.panel, -1, "Y max", 100)

        #create Pause button
        self.pauseButton = wx.Button(self.panel, -1, "Pause")
        self.Bind(wx.EVT_BUTTON, self.pausePressed, self.pauseButton)
        self.Bind(wx.EVT_UPDATE_UI, self.pauseUpdate, self.pauseButton)
       
        self.hbox1 = wx.BoxSizer(wx.HORIZONTAL)
        self.hbox1.Add(self.pauseButton, border=5,
                       flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL)

        #create Transform button
        self.transformButton = wx.Button(self.panel, -1, "Transform")
        self.Bind(wx.EVT_BUTTON, self.transformPressed, self.transformButton)
        self.Bind(wx.EVT_UPDATE_UI, self.transformUpdate, self.transformButton)
        self.hbox1.Add(self.transformButton, border=5,
                       flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL)

        #create Write button
        self.writeButton = wx.Button(self.panel, -1, "Write")
        self.Bind(wx.EVT_BUTTON, self.writePressed, self.writeButton)
        self.Bind(wx.EVT_UPDATE_UI, self.writeUpdate, self.writeButton)
        self.hbox1.Add(self.writeButton, border=5,
                       flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL)
        
        
        #layout management using sizers for xmin,ymin,xmax,ymax
        self.hbox2 = wx.BoxSizer(wx.HORIZONTAL)
        self.hbox2.Add(self.xmin, border=5, flag=wx.ALL)
        self.hbox2.Add(self.xmax, border=5, flag=wx.ALL)
        self.hbox2.AddSpacer(24)
        self.hbox2.Add(self.ymin, border=5, flag=wx.ALL)
        self.hbox2.Add(self.ymax, border=5, flag=wx.ALL)
        
        self.vbox = wx.BoxSizer(wx.VERTICAL)
        self.vbox.Add(self.canvas, 1, flag=wx.LEFT | wx.TOP | wx.GROW)        
        self.vbox.Add(self.hbox1, 0, flag=wx.ALIGN_LEFT | wx.TOP)
        self.vbox.Add(self.hbox2, 0, flag=wx.ALIGN_LEFT | wx.TOP)
        
        self.panel.SetSizer(self.vbox)
        self.vbox.Fit(self)
    
    def makeStatusbar(self):
        self.statusbar = self.CreateStatusBar()

    def prepareGraph(self):
        #prepares the frame and the axes
        self.dpi = 120
        self.fig = Figure((2.5, 2.5), dpi=self.dpi)

        self.axes = self.fig.add_subplot(110)
        self.axes.set_axis_bgcolor('white')
        self.axes.set_title('Voltage Information', size=14)
        
        pylab.setp(self.axes.get_xticklabels(), fontsize=8)
        pylab.setp(self.axes.get_yticklabels(), fontsize=8)

        #plot the first batch of points
        self.plot_data = self.axes.plot(
            self.data, 
            linewidth=1,
            color='blue',
            )[0]

    def plotPoints(self):
    #plots the points in self.data
        
        #set values for xmin and xmax 
        if self.xmax.updateauto():
            #set a window of 100 for auto for time domain
            if not self.transform:
                xmax = len(self.data) if len(self.data) > 100 else 100
            else:
            #set the max of the harmonics for auto in freq domain
                xmax =max(sampleRate.value*
                                     r_[0:len(self.data)/2]/len(self.data))
        else:
            xmax = int(self.xmax.manual_value())
            
        if self.xmin.updateauto():            
            if not self.transform:
                xmin = xmax - 100
            else:
                xmin=0
        else:
            xmin = int(self.xmin.manual_value())
            
        #set values for ymin and ymax
        #ymax/min is the max/min of all the values in the data set
        
        if self.ymin.updateauto():
            ymin = round(min(self.data), 0) - 1
        else:
            ymin = int(self.ymin.manual_value())
        
        if self.ymax.updateauto():
            ymax = round(max(self.data), 0) + 1
        else:
            ymax = int(self.ymax.manual_value())

        self.axes.set_xbound(lower=xmin, upper=xmax)
        self.axes.set_ybound(lower=ymin, upper=ymax)
        
        
        pylab.setp(self.axes.get_xticklabels(), 
            visible=True)
        
        if not self.transform:
        #for time domain set the x-axis to be a list of time points
            self.plot_data.set_xdata(numpy.arange(len(self.data)))
            self.plot_data.set_ydata(numpy.array(self.data))
        else:
        #for frequency domain x-axis has to be dependent on the sample rate
            self.plot_data.set_xdata(sampleRate.value*
                                     r_[0:len(self.data)/2]/len(self.data))
            self.plot_data.set_ydata(numpy.array(self.data[0:len(self.data)/2]))
        
        self.canvas.draw()
    
    def pausePressed(self, event):
    #if pause is pressed update accordingly
        self.paused = not self.paused
        self.pauseUpdate(event)

    def transformPressed (self,event):
    #if the transform button is pressed, update accordingly
        self.transform=not self.transform
        self.transformUpdate(event)

    def writePressed (self,event):
    #if the write button is pressed, update accordingly
        self.write=not self.write
        self.writeUpdate(event)


    
    def pauseUpdate(self, event):
    #change the text in the pause button
        if self.paused:
            txt = "Collect"
        else:
            txt=  "Pause"
        self.pauseButton.SetLabel(txt)

    def transformUpdate(self, event):
    #change the text in the transform button
        if self.transform:
            txt="Time Domain"
        else:
            txt="Freq. Domain"
        self.transformButton.SetLabel(txt)

    def writeUpdate(self, event):
    #change the text in the write button
        if self.write:
            txt="Stop Writing"
        else:
            txt="Start Writing"
        self.writeButton.SetLabel(txt)


    def goTimerFired(self, event):
    #if not paused get data
        if not self.paused:
            if not self.transform:
                self.data=(self.samples.getAnotherBatch())
            else:
                self.data=self.samples.Transform()
        if self.write:
            #module to write on file
            self.writeFiles()
            
        self.plotPoints()
            
    def writeFiles(self):
    #writes data into filesizes of 50Mb
        if not self.transform:
            self.timeWrite()
        else:
            self.frequencyWrite()
            


    def timeWrite(self):
    #if time domain data is being written
    #create a file time-domain-data.csv
        ofile  = open("time-domain-data%d.csv"% self.filenum, "a")
        writer = csv.writer(ofile, delimiter='\t', quotechar='"',
                            quoting=csv.QUOTE_ALL)
        
        #while the file size is less than 50 Mb
        while os.path.getsize("time-domain-data%d.csv"%
                              self.filenum)<self.filesize:
            xvalue=0
            #store x and y coordinates and timestamps
            for yvalue in self.data:
                writer.writerow([xvalue, yvalue,
                                 strftime("%Y-%m-%d %H:%M:%S")])
                xvalue=xvalue+1
            #self.plotPoints()
                
        ofile.close()
        self.filenum+=1
        

    def frequencyWrite(self):
    #if frequency domain data is being written
    #create a file frequency domain data.csv
        
        ofile  = open("frequency-domain-data%d.csv"% self.filenum1, "a")
        writer = csv.writer(ofile, delimiter='\t', quotechar='"',
                            quoting=csv.QUOTE_ALL)
        
        #while the file size is less than 50 Mb
        while os.path.getsize("frequency-domain-data%d.csv"%
                              self.filenum1)<self.filesize:
            
            xvalues = (sampleRate.value*
                r_[0:len(self.data)/2]/len(self.data))
            yvalues = (numpy.array(self.data[0:len(self.data)/2]))
            timestamp=strftime("%Y-%m-%d %H:%M:%S")
            coordinates=zip(xvalues,yvalues)
            
            #store x and y coordinates and timestamps
            for coordinate in coordinates:
                writer.writerow(coordinate+(timestamp,))
        ofile.close()
        self.filenum1+=1
        
    def exitMenu(self, event):
    #on pressing exit: close
        self.Destroy()
    
    def saveMenu(self, event):
    #save the file as pdf
        file_choices = "PDF (*.pdf)|*.pdf"
        
        dlg = wx.FileDialog(
            self, 
            message="Save plot as...",
            defaultDir=os.getcwd(),
            defaultFile="plot.pdf",
            wildcard=file_choices,
            style=wx.SAVE)
        
    #confirmation message after the file is saved
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            self.canvas.print_figure(path, dpi=self.dpi)
            self.confirmation("Saved to %s" % path)
    

    
    def confirmation(self, msg, flash_len_ms=1500):                             
    #confirmation message upon saving file
        self.statusbar.SetStatusText(msg)
        self.timeroff = wx.Timer(self)
        self.Bind(
            wx.EVT_TIMER, 
            self.erase,
            
            self.timeroff)
        self.timeroff.Start(flash_len_ms, oneShot=True)
    
    def erase(self, event):
    #erase the message
        self.statusbar.SetStatusText('Voltage')


if __name__ == '__main__':
    app = wx.PySimpleApp()
    app.frame = Window()
    app.frame.Show()
    app.MainLoop()




