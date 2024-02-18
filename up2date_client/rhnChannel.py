#!/usr/bin/python

# all the crap that is stored on the rhn side of stuff
# updating/fetching package lists, channels, etc

import os
import time
import random

from . import up2dateAuth
from . import up2dateErrors
from . import config
from . import up2dateLog
from . import rpcServer
#import sourcesConfig
from . import urlMirrors
from rhn import rpclib





global channel_blacklist
channel_blacklist = []


# FIXME?
# change this so it doesnt import sourceConfig, but
# instead sourcesConfig imports rhnChannel (and repoDirector)
# this use a repoDirector.repos.parseConfig() or the like for
# each line in "sources", which would then add approriate channels
# to rhnChannel.selected_channels and populate the sources lists
# the parseApt/parseYum stuff would move to repoBackends/*Repo.parseConfig()
# instead... then we should beable to fully modularize the backend support


# heh, dont get much more generic than this...
class rhnChannel:
    # shrug, use attributes for thetime being
    def __init__(self, **kwargs):
        self.dict = {}

        for kw in list(kwargs.keys()):
            self.dict[kw] = kwargs[kw]
               
    def __getitem__(self, item):
        return self.dict[item]

    def __setitem__(self, item, value):
        self.dict[item] = value

    def keys(self):
        return list(self.dict.keys())

    def values(self):
        return list(self.dict.values())

    def items(self):
        return list(self.dict.items())

class rhnChannelList:
    def __init__(self):
        # probabaly need to keep these in order for
        #precedence
        self.list = []

    def addChannel(self, channel):
        self.list.append(channel)


    def channels(self):
        return self.list

    def getByLabel(self, channelname):
        for channel in self.list:
            if channel['label'] == channelname:
                return channel
    def getByName(self, channelname):
        return self.getByLabel(channelname)

    def getByType(self, type):
        channels = []
        for channel in self.list:
            if channel['type'] == type:
                channels.append(channel)
        return channels

# for the gui client that needs to show more info
# maybe we should always make this call? If nothing
# else, wrapper should have a way to show extended channel info
def getChannelDetails():

    channels = []
    sourceChannels = getChannels()

    useRhn = None
    for sourceChannel in sourceChannels.channels():
        if sourceChannel['type'] == "up2date":
            useRhn = 1

    if useRhn:
        s = rpcServer.getServer()
        up2dateChannels = rpcServer.doCall(s.up2date.listChannels, up2dateAuth.getSystemId())

    for sourceChannel in sourceChannels.channels():
        if sourceChannel['type'] != 'up2date':
            # FIMXE: kluge since we dont have a good name, maybe be able to fix
            sourceChannel['name'] = sourceChannel['label']
            sourceChannel['description'] = "%s channel %s from  %s" % (sourceChannel['type'],
                                                                           sourceChannel['label'],
                                                                           sourceChannel['url'])
            channels.append(sourceChannel)
            continue
    
        if useRhn:
            for up2dateChannel in up2dateChannels:
                if up2dateChannel['label'] != sourceChannel['label']:
                    continue
                for key in list(up2dateChannel.keys()):
                    sourceChannel[key] = up2dateChannel[key]
                channels.append(sourceChannel)
            

    return channels

def getMirror(source,url):

    mirrors = urlMirrors.getMirrors(source,url)

#    print "mirrors: %s" % mirrors
    length  = len(mirrors)
    # if we didnt find any mirrors, return the
    # default
    if not length:
        return url
    random.seed(time.time())
    index = random.randrange(0, length)
    randomMirror = mirrors[index]
    print("using mirror: %s" % randomMirror)
    return randomMirror
    

cmdline_pkgs = []

global selected_channels
selected_channels = None
def getChannels(force=None, label_whitelist=None):
    cfg = config.initUp2dateConfig()
    log = up2dateLog.initLog()
    global selected_channels
    #bz:210625 the selected_chs is never filled
    # so it assumes there is no channel although
    # channels are subscribed
    selected_channels=label_whitelist
    if not selected_channels and not force:

        ### mrepo: hardcode sources so we don't depend on /etc/sysconfig/rhn/sources
        # sources = sourcesConfig.getSources()
        sources = [{'url': 'https://xmlrpc.rhn.redhat.com/XMLRPC', 'type': 'up2date'}]
        useRhn = 1

        if 'cmdlineChannel' in cfg:
            sources.append({'type':'cmdline', 'label':'cmdline'}) 

        selected_channels = rhnChannelList()
        cfg['useRhn'] = useRhn

        li = up2dateAuth.getLoginInfo()
        # login can fail...
        if not li:
            return []
        
        tmp = li.get('X-RHN-Auth-Channels')
        if tmp == None:
            tmp = []
        for i in tmp:
            if label_whitelist and i[0] not in label_whitelist:
                continue
                
            channel = rhnChannel(label = i[0], version = i[1],
                                 type = 'up2date', url = cfg["serverURL"])
            selected_channels.addChannel(channel)

        if len(selected_channels.list) == 0:
            raise up2dateErrors.NoChannelsError("This system may not be updated until it is associated with a channel.")

    return selected_channels
            

def setChannels(tempchannels):
    global selected_channels
    selected_channels = None
    whitelist = dict([(x,1) for x in tempchannels])
    return getChannels(label_whitelist=whitelist)



def subscribeChannels(channels,username,passwd):
    s = rpcServer.getServer()
    try:
        channels = rpcServer.doCall(s.up2date.subscribeChannels,
                          up2dateAuth.getSystemId(),
                          channels,
                          username,
                          passwd)
    except rpclib.Fault as f:
        if f.faultCode == -36:
            raise up2dateErrors.PasswordError(f.faultString)
        else:
            raise up2dateErrors.CommunicationError(f.faultString)

def unsubscribeChannels(channels,username,passwd):
    s = rpcServer.getServer()
    try:
        channels = rpcServer.doCall(s.up2date.unsubscribeChannels,
                          up2dateAuth.getSystemId(),
                          channels,
                          username,
                          passwd)
    except rpclib.Fault as f:
        if f.faultCode == -36:
            raise up2dateErrors.PasswordError(f.faultString)
        else:
            raise up2dateErrors.CommunicationError(f.faultString)

