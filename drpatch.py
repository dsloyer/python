#
# Hotfix items have the following form
#    <item name="SP6a SRP/Q299444">
#        <descr></descr>
#        <product name="XP-x86">
#            <trigger type=HOTFIX>Q299444</trigger>
#            <cmd>q299444i.exe</cmd>
#            <options>-m -z</options>
#            <at>xp-x86-hf</at>
#        </product>
#    </item>
#
# Products:
#   Special product-name values: "ALL" apply to all products.
#
# The following trigger types are supported:
# WIN6FIX       If the item has already been installed, the subkey can be
#               found in the standard location in the 2k8/vista/win7 Registry --
#               HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\Packages
# HOTFIX        If the item has already been installed, the subkey can be
#               found in the standard location in the Win2K/XP Registry
#               (HKLM\SOFTWARE\Microsoft\Updates)
# HOTFIX-X86    As with HOTFIX, but the installer is 32-bit, so the key
#               shows up in the Wow6432Node area on 64-bit systems.
#               (HKLM\SOFTWARE\Wow6432Node\Microsoft\Updates
# HKLM_KEY      If the item has already been installed, the key provides
#               the full path in HKLM to the desired key
# DR_SUBKEY     If the item has already been installed, the subkey can be
#               found in the standard location in the registry used by
#               DR Systems (HKLM\SOFTWARE\DR Systems\Updates).
# SUBSTR        Item is deemed "installed" if the supplied string is
#               found at the indicated regkey location(not implemented)
# FILE          If the item has already been installed, the file will exist.
# ALWAYS        These items are always installed (subject to -t override)
# COND          These items are conditional, and only installed via the -s command
#               (not implemented)
#
# The default (normal) behaviour when a trigger is NOT found is to trigger the item's cmd.

# note: DR Systems\Updates may not exist, and will need to be created, as necessary.

import string
import os                   # environ(), system()
import os.path              # import path.split(), path.splitext(), stat()
import sys                  # exit()
import stat                 # ST_MTIME
import _winreg              # Windows registry processing
import getopt			    # argument processing
import time                 # localtime(), sleep()

import xml.sax              # XML parsing module

import drlog
import wininfo

argv = []
pgm = ""
verbose = 0
veryVerbose = 0
quiet = 0
force = 0
test = 0
datafile = "hotfixes.xml"
justThis = 0
justThisList = []           # list of specific items to install
drive = ""
locs = {}                   # dictionary to hold item directory paths
cnt = 0                     # Count of items installed (or WOULD install)
logfile = ""

strOs       = ""
strSp       = ""

itemName    = ""
prodName    = ""
item        = ""            # item is the full trigger string
strType     = ""
installer   = ""
opt         = ""
at          = ""

inTrigger   = 0
inCmd       = 0
inOpt       = 0
inAt        = 0
chars       = ""

bExit = 0                   # Flag will be set if there's a keyboard interrupt

RegLoc = {}                 # dictionary of hotfix registry locations
RegLoc["WIN6"]   = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Component Based Servicing\\Packages\\"
RegLoc["NT"]     = "SOFTWARE\\Microsoft\\Updates\\"
RegLoc["NT-WOW"] = "SOFTWARE\\Wow6432Node\\Microsoft\\Updates\\"
RegLoc["DR"]     = "SOFTWARE\\DR Systems\\Updates\\"
RegLoc["DR-WOW"] = "SOFTWARE\\Wow6432Node\\DR Systems\\Updates\\"
    
log = drlog.Log()           # Open logfile

# print string, unless mode == quiet
def prn(str):
    if not quiet:
        strOut = "%s: %s" % (pgm, str)
        print strOut

# print string, also write to log
def prnLog(str, sev = log.LOG_INFO):
    strOut = "%s: %s" % (pgm, str)
    print strOut
    log.write(strOut, sev)

# print string, write to log, and exit
def prnLogExit(str):
    strOut = "%s: %s" % (pgm, str)
    print strOut
    log.write(strOut, log.LOG_ERR)
    sys.exit(2)

class XmlHandler(xml.sax.ContentHandler):
    """
        Parse, and process, hotfixes.xml
    """
    
    def startElement(self, name, attrs):
        global itemName, prodName, strType, installer, at, opt, item
        global inCmd, inTrigger, inOpt, inAt

        if name == "updates":
            ver = attrs.get("ver", "")
            if ver == "":
                strOut = "Error: can't retrieve ver attribute from <updates> item"
                prnLogExit(strOut)
        elif name == "location":
            name = attrs.get("name", "")
            dir  = attrs.get("dir", "")
            locs[name] = dir
            # print "\"%s\" commands can be found in \"%s\""  % (name, locs[name])
        elif name == "item":
            itemName = attrs.get("name", "")
            # print "itemName: %s" % itemName
        elif name == "product":
            prodName = attrs.get("name", "")
            # print "  product:  %s" % prodName
        elif name == "trigger":
            inTrigger = 1
            strType = attrs.get("type", "")
        elif name == "cmd":
            inCmd = 1
            # print "  installer:  %s" % installer
        elif name == "options":
            inOpt = 1
        elif name == "at":
            inAt = 1

    def characters(self, characters):
        global chars
        global inCmd, inTrigger, inOpt, inAt

        str = ""

        if inCmd == 1:
            chars += characters
            # str = 'characters(): inCmd, chars = "' + chars + '"'
            # print str
        elif inTrigger == 1:
            chars += characters
            # str = 'characters(): inTrigger, chars = "' + chars + '"'
            # print str
        elif inOpt == 1:
            chars += characters
            # str = 'characters(): inOpt, chars = "' + chars + '"'
            # print str
        elif inAt == 1:
            chars += characters
            # str = 'characters(): inAt, chars = "' + chars + '"'
            # print str

        
    def endElement(self, name):
        global installer, opt, at, strType, item, itemName, chars, drive
        global inTrigger, inCmd, inOpt, inAt

        identity = string.maketrans('','')

        strOut  = ""
        if name == "product":
            # At product end, we have all the current XML information on the item
            self.MatchProduct(installer, opt, at, strType, item, itemName)
            # print "end product"
        elif name == "trigger":
            item = chars.strip()
            chars = ""
            # strOut = 'end trigger. item: "' + item + '"'
            # print strOut
            inTrigger = 0
        elif name == "cmd":
            installer = chars.strip()
            chars = ""
            # strOut = 'end cmd. installer: "' + installer + '"'
            # print strOut
            inCmd = 0
        elif name == "options":
            opt = chars.strip()
            opt = opt.replace("%DRIVE%", drive)
            chars = ""
            # strOut = 'end options. opt: "' + opt + '"'
            # print strOut
            inOpt = 0
        elif name == "at":
            at = chars.strip()
            chars = ""
            # strOut = 'end at. at: "' + at + '"'
            # print strOut
            inAt = 0

    def MatchProduct(self, installer, opt, at, strType, item, itemName):
        # print "MatchProduct: cmd: \"%s\", opt: \"%s\", at: \"%s\", strType: \"%s\", strId: \"%s\", strName: \"%s\""\
        #       % (installer, opt, at, strType, item, itemName)

        if bExit:
            strOut = "MatchProduct: Exit flag detected.  Exiting now."
            prnLogExit(strOut)

        bGotThis = 0

        # Examine the current itemName against the justThisList.
        # If there's a match, proceed further, else exit.
        if justThis:
            # loop through the justThisList
            for this in justThisList:
                if itemName.lower().find(this.lower()) == -1:
                    # print "item, \"%s\", doesn't match \"%s\"" % (itemName, this)
                    continue            # skip items we're not interested in
                else:
                    # current item 
                    # print "item, \"%s\", matches \"%s\"" % (itemName, this)
                    bGotThis = 1
                    
                    # itemName matches.  Now, check for product match
                    # need to check the current product for match (strOs contains the current prodName)
                    #  or
                    # prodName is "ALL", so item is installed if not already installed,
                    #        or is installed if the force option is specified
                    if (not strOs.find(prodName) == -1) or prodName == "ALL":
                        # print "\nfound item with product element for this product: "
                        if strType == "ALWAYS":
                            # always install these items
                            # print "ALWAYS install item (subject to '-t' override): %s" % itemName
                            self.InstallItem(installer, opt, at, strType, item, itemName)
	                elif self.IsInstalled(strType, item, itemName):
	                    if force:
	                        # print "forced install (subject to '-t' override): %s" % itemName
	                        self.InstallItem(installer, opt, at, strType, item, itemName)
	                else:
	                        # item not installed.  install item
	                        # print "install item (subject to '-t' override): %s" % itemName
	                        self.InstallItem(installer, opt, at, strType, item, itemName)
                    else:
                        # No match on the product.  This is normal.  The script supports several
                        # different products
                        # print "prodName(%s) doesn't match product(%s)" % (prodName, strOs)
                        pass
                    break
        else:
            # need to check the current product for match (strOs contains the current prodName)
            #  or
            # prodName is "ALL", so item is installed if not already installed,
            #        or is installed if the force option is specified
            if (not strOs.find(prodName) == -1) or prodName == "ALL":
                # print "\nfound matching item.  prodName: %s" % prodName
                if strType == "ALWAYS":
                    # always install these items
                    # print "ALWAYS install item (subject to '-t' override): %s" % itemName
                    self.InstallItem(installer, opt, at, strType, item, itemName)
                elif self.IsInstalled(strType, item, itemName):
                    if force:
                        # print "forced install (subject to '-t' override): %s" % itemName
                        self.InstallItem(installer, opt, at, strType, item, itemName)
                else:
                        # item not installed.  install item
                        # print "install item (subject to '-t' override): %s" % itemName
                        self.InstallItem(installer, opt, at, strType, item, itemName)
            else:
                # No match on the product.  This is normal.  The script supports several
                # different products
                # print "prodName(%s) doesn't match product(%s)" % (prodName, strOs)
                pass

    def IsInstalled(self, strType, strId, strName):
        # This function is used to check whether a particular item has been installed.  The strType
        # parameter indicates where the strId subkey can be found.
        # strType, "FILE", uses a file to determine whether a item has already been installed.
        
        # This function accepts a string identifying the item; the string points
        # to the key under HKLM\SOFTWARE\Microsoft\Updates where the key can be found.
        # That is, the passed string is a specific path to the key that appears whenever
        # this specific item has been installed.
	global verbose, RegLoc
        
        # print "IsInstalled: strType: \"%s\", strId: \"%s\", strName: \"%s\"" % (strType, strId, strName)

        bIns = 0        # flag indicating whether item was found to be installed
        bIsKeyType = 0  # flag indicating the item is found to be installed using a regkey
        strKey = []     # array of potential locations in registry where the subkey may be found
        strFound = ""   # Save the key when an item is found
    
        # check registry.  Get a handle for HKLM
        hReg = _winreg.ConnectRegistry(None, _winreg.HKEY_LOCAL_MACHINE)
        
        if strType == "WIN6FIX":
            strKey.append(RegLoc["WIN6"] + strId)
            bIsKeyType = 1
        elif strType == "HOTFIX":
            strKey.append(RegLoc["NT"]     + strId)
            strKey.append(RegLoc["NT-WOW"] + strId)
            bIsKeyType = 1
        elif strType == "DR_SUBKEY":
            strKey.append(RegLoc["DR"]     + strId)
            strKey.append(RegLoc["DR-WOW"] + strId)
            bIsKeyType = 1
        elif strType == "HKLM_KEY":
            strKey.append(strId)
            strKey.append(strId.replace("SOFTWARE", "SOFTWARE\\Wow6432Node"))
            bIsKeyType = 1

        if bIsKeyType:
            # Open key for read.
            for key in strKey:
                try:
                    hKey = _winreg.OpenKey(hReg, key, 0, _winreg.KEY_READ)
                    if verbose:
                        strOut = "key, \"%s\", for item, \"%s\", was found." % (key, strName)
                        prnLog(strOut)
                    bIns = 1
                    _winreg.CloseKey(hKey)      # close write-key handle
                except EnvironmentError:
                    if verbose:
                        strOut = "key, \"%s\", for item, \"%s\", was not found." % (key, strName)
                        prnLog(strOut)
    
            _winreg.CloseKey(hReg)              # close registry when all done looping
        elif strType == "FILE":
            # This item uses a file (or directory) to indicate whether the item has been installed
            if os.path.exists(strId):
                if verbose:
                    strOut = "item, \"%s\", is installed" % strName
                    prnLog(strOut)
                bIns = 1
            else:
                if verbose:
                    strOut = "item, \"%s\", is not installed" % strName
                    prnLog(strOut)

            _winreg.CloseKey(hKey)     # close write-key handle
            _winreg.CloseKey(hReg)     # close registry        
        return bIns


    def InstallItem(self, installer, options, at, strType, strId, strName):
        global cnt, bExit, RegLoc
        pause = 0
        
        # check whether the previous install command was interrupted
        if bExit:
            strOut = "InstallItem: Exit flag found set.  Exiting now."
            prnLog(strOut)
        
        # print "InstallItem: cmd: \"%s\", opt: \"%s\", at: \"%s\", strType: \"%s\", strId: \"%s\", strName: \"%s\""\
        #       % (installer, options, at, strType, strId, strName)
        try:
            cmdPath = "%s%s\\%s" % (drive, locs[at], installer)
        except:
            print "'at' is invalid: %s" % at
            cmdPath = installer
            
        # check for installer existence        
        if  not os.path.isfile(cmdPath):
            # installer doesn't exist
            strOut = "Error: installer not found: \"%s\" for item \"%s\"" % (cmdPath, strName)
            prnLog(strOut)
            return

        # check for .BAT and .PY files.  These files need to run in a command shell
        # print "installer: \"%s\".  tail: \"%s\"" % (cmdPath, cmdPath[-4:])
        if cmdPath[-4:].lower() == ".bat" or\
           cmdPath[-3:].lower() == ".py":
            cmdPath = "start /wait \"%s\" cmd /wait /c %s" % (installer, cmdPath)
            # print "cmdPath: " + cmdPath
            pause = 0

        if options:
            cmd = "\"%s %s\"" % (cmdPath, options)
        else:
            cmd = "\"%s\"" % cmdPath
            # print "cmd: %s" % cmd
         
        # cnt is incremented whenever we will/would install something, exc when it's always installed
        if not strType == "ALWAYS":
            cnt += 1
        if test:
            strOut = "would install \"%s\"" % strName
            prnLog(strOut)
        else:
            strOut = "Installing item: \"%s\"" % strName
            prnLog(strOut)

            # Run the installer
            if strType == "DR_SUBKEY":
                # create the necessary key in the DR Systems area of the registry
                # get a handle for HKLM
                hReg = _winreg.ConnectRegistry(None, _winreg.HKEY_LOCAL_MACHINE)
                try:
                    # See whether "DR Systems" key exists.
                    strKey = r"SOFTWARE\DR Systems"
                    hKey = _winreg.OpenKey(hReg, strKey, 0, _winreg.KEY_ALL_ACCESS)
                    # strOut = "DR Systems regkey, \"%s\", exists" % strKey
                    # prnLog(strOut)

                    _winreg.CloseKey(hKey)     # close key handle
                except:
                    # Create DR Systems regkey
                    # strOut = "DR Systems key, \"%s\", doesn't exist" % strKey
                    # prnLog(strOut)
                    try:
                        hKey = _winreg.CreateKey(hReg, strKey)
                        _winreg.CloseKey(hKey)     # close write-key handle
                        # strOut = "Created DR Systems regkey, \"%s\"" % strKey
                        # prnLog(strOut)
                    except:
                        # couldn't create key
                        _winreg.CloseKey(hReg)     # close registry
                        strOut = "Error creating DR Updates regkey, \"%s\"" % strKey
                        prnLogExit(strOut)
                # assert: DR Systems key exists                    

                try:
                    # See whether DR Updates subkey exists.
                    hKey = _winreg.OpenKey(hReg, RegLoc["DR"], 0, _winreg.KEY_ALL_ACCESS)
                    # strOut = "DR Updates regkey, \"%s\", exists" % RegLoc["DR"]
                    # prnLog(strOut)

                    _winreg.CloseKey(hKey)     # close key handle
                except:
                    # Create DR Updates regkey
                    # strOut = "DR Updates key, \"%s\", doesn't exist" % RegLoc["DR"]
                    # prnLog(strOut)
                    try:
                        hKey = _winreg.CreateKey(hReg, RegLoc["DR"])
                        _winreg.CloseKey(hKey)     # close write-key handle
                        # strOut = "Created DR Updates regkey, \"%s\"" % RegLoc["DR"]
                        # prnLog(strOut)
                    except:
                        # couldn't create key
                        _winreg.CloseKey(hReg)     # close registry        
                        strOut = "Error creating DR Updates regkey, \"%s\"" % RegLoc["DR"]
                        prnLogExit(strOut)
                # assert: DR Updates key exists                    

                strNewKey = RegLoc["DR"] + strId
                # create a sub-key for this item.  Note: If this key already exists, it is wiped out.
                try:
                    hKey = _winreg.CreateKey(hReg, strNewKey)
                    _winreg.CloseKey(hKey)          # close write-key handle
                except:
                    _winreg.CloseKey(hReg)          # close registry        
                    strOut = "Error creating DR subkey in registry, \"%s\"" % strId
                    prnLogExit(strOut)

            if veryVerbose:
                strOut = "installing: %s" % cmd
                prnLog(strOut)
            try:
                os.popen(cmd)                       # invoke the command
                if pause:
                    time.sleep(30)

            except KeyboardInterrupt:
                # cleanup
                strOut = "Interrupt received.  Exiting at earliest opportunity"
                prnLog(strOut)
                bExit = 1;
            
            # check installation
            if strType == "ALWAYS":
                # Don't check whether "ALWAYS" types have been installed
                pass
            elif not self.IsInstalled(strType, strId, strName):
                strOut = "Hotfix install failure: missing trigger: \"%s\". Type: %s" % (strId, strType)
                prnLog(strOut)
    # end InstallItem()

class DrPatch:
    # Class variables
    global bExit

    def __init__(self, args):
        global argv, log
        
        fpath = ""
        fname = ""
        
        argv = args
        # print "argv: "
        # for arg in argv:
        #     print "arg \"%s\"" % arg
        self.doArgs()                   # parse arguments

        if logfile:
            fpath, fname = os.path.split(logfile)
            #print "path: \"%s\", fname: \"%s\"" % (fpath, fname)
        else:
            # no logfile name supplied -- use our default name, "drupdate.log"
            fname = "drupdate.log"
        
        if fpath or fname:
            # print "drpatch: opening logfile, \"%s\", in directory \"%s\"" % (fname, fpath)
            log = drlog.Log(fname, fpath)       # reopen logfile with appropriate name
        
        self.ParseAndInstall()          # process the XML and install patches


    def getRes(self):
        return cnt

        
    def usage(self):
        print 'usage:'
        print '   %s [-h][-v][-V][-q][-f][-t][-i filename][-s item][-d drive:][-p pgm]' % pgm
        print ''
        print 'where:'
        print '   -h or --help                  display usage'
        print '   -v or --verbose               verbose output'
        print '   -V or --veryVerbose           very verbose output'
        print '   -q or --quiet                 no output'
        print '   -f or --force                 force installation of all items'
        print '   -t or --test                  test only - don\'t apply the fixes'
        print '   -i or --input filename        use \'filename\' as XML-formatted source file'
        print '   -s or --specific              install the specified item. (Can be repeated)'
        print '   -d or --drive drive:          install items from the specified drive'
        print '   -p or --program pgm           use pgm as the program name'
        print '   -l or --logfile filename      use specified logfile name'
        print ''
        print 'examples:'
        print '   To install items from I: onto workstation:'
        print '         %s' % pgm
        print ''
        print 'default:'
        print ''
        print 'This program identifies the OS, service pack(if any), and checks a list'
        print 'of items defined in an accompanying XML file, "hotfixes.xml".  Any'
        print 'items identified as applying to the OS, and not yet installed, are'
        print 'installed.'
        print ''
        print 'The OS and Service Pack requirements are hard-coded in this script,'
        print 'as are the Internet Explorer(IE) requirements.'
        print 'Win2K systems must be running SP4, and XP must be running SP3.'
        print ''
        print 'The version of Internet Explorer must be IE8 or IE9, depending on the OS version.'
        print ''
        print 'Specifying particular items can be achieved by providing one or more \'-s\' options'
        print 'The pattern supplied with the \'-s\' option will match with any item whose name'
        print 'contains the pattern.  This is not case-sensitive.  Multiple \'-s\' options can'
        print 'be supplied -- the program builds a list of patterns to look for.  Specified items'
        print 'that are found to be already installed will be skipped, unless \'-f\' is specified'
        print 'as well.'
        sys.exit(2)
    

    def doArgs(self):
        # argv[0] is the full program name with path and extension.
        # Let's trim it down to just the program name.
        
        global logfile, pgm, verbose, veryVerbose, quiet, force, test, datafile, justThis, justThisList, drive
        
        pgmPath, pgmName = os.path.split(argv[0])   # separate pgmname from path
        pgm, ext = os.path.splitext(pgmName)        # separate extension from pgmname

        # check arguments
        try:
            opts, args = getopt.getopt(argv[1:], "hvVqfti:s:d:p:l:",
                ["help", "verbose", "veryVerbose", "force", "test", "input=", "specific=", "drive=", "program=", "logfile=-"])
        except:
            self.usage()                            # print help information and bail
    
        for o, a in opts:
            if o in ("-h", "--help"):
                self.usage()
            elif o in ("-v", "--verbose"):
                verbose = 1
                quiet = 0
            elif o in ("-V", "--veryVerbose"):
                veryVerbose = 1
                verbose = 1
                quiet = 0
            elif o in ("-q", "--quiet"):
                veryVerbose = 0
                verbose = 0
                quiet = 1
            elif o in ("-f", "--force"):
                force = 1
            elif o in ("-t", "--test"):
                test = 1
            elif o in ("-i", "--input"):
                datafile = a
            elif o in ("-s", "--specific"):
                justThis = 1
                justThisList.append(a)
            elif o in ("-d", "--drive"):
                drive = a
            elif o in ("-p", "--program"):
                pgm = a
            elif o in ("-l", "--logfile"):
                logfile = a
            else:
                self.usage()
    # end doArgs()
    
    def ParseAndInstall(self):
        global drive, strOs, strSp
        
        dfFullPath = ""         # full path to datafile
        
        if drive:
            # drive specified on the command line
            # strOut = 'using drive from args: "%s"' % drive
            # prn(strOut)
            pass
        else:
            # no path supplied.  See if drs_drive is defined
            try:
                drsDrv  = os.environ["DRS_DRIVE"]
                drive = drsDrv
            except:
                strOut = "error: no drive supplied, and DRS_DRIVE is undefined."
                prnLogExit(strOut)
        
        # get Python version
        verInfo = sys.version_info
        
        oWinInfo = wininfo.WinInfo()
        # Check OS and Service Pack
        strOs, strSp = oWinInfo.GetOsInfo()

        if strOs == "XP-x86":
            if not strSp == "Service Pack 3":
                strOut = "XP items assume SP3, which is not yet installed"
                if test:
                    prnLog(strOut)
                else:
                    prnLogExit(strOut)
        elif strOs == "XP-x64" or strOs == "2K3-x86" or strOs == "2K3-x64":
            if not strSp == "Service Pack 2":
                strOut = "XP-x64, 2K3-x86, and 2K3-x64 items assume SP2, which is not yet installed"
                if test:
                    prnLog(strOut)
                else:
                    prnLogExit(strOut)
        elif strOs == "Vista-x64" or strOs == "Vista-x86" or strOs == "2K8-x86" or strOs == "2K8-x64":
            if not strSp == "Service Pack 2":
                strOut = "Vista and Server 2008 items assume SP2, which is not yet installed"
                if test:
                    prnLog(strOut)
                else:
                    prnLogExit(strOut)
        elif strOs == "Win7-x64" or strOs == "2K8R2-x64":
            if not strSp == "Service Pack 1":
                strOut = "Windows7 and 2K8R2 items assume SP2, which is not yet installed"
                if test:
                    prnLog(strOut)
                else:
                    prnLogExit(strOut)
        elif strOs == "Win8-x64" or strOs == "2K12-x64":
            pass
        elif strOs == "Win8.1-x64" or strOs == "2K12R2-x64":
            pass
        elif not test:
            strOut = "Unrecognized OS."
            prnLogExit(strOut)
            
        # ASSERT: os, service packs, are all OK -- or else we're testing
       
        # dfFullPath is the path to the datafile
        dfFullPath = os.path.join(drive, '\drs', 'utils', datafile)
        # print "dfFullPath: %s" % dfFullPath
        if not os.path.isfile(dfFullPath):
            strOut = "Error: datafile, \"%s\", not found. Exiting program" % datafile
            prnLogExit(strOut)

        # fetch date of datafile
        nFdate = os.stat(dfFullPath)[stat.ST_MTIME]
        strFdate = time.strftime("%m/%d/%y %H:%M:%S", time.localtime(nFdate))
        strOut = "Installing %s (%s)" % (dfFullPath, strFdate)
        prnLog(strOut)
        
        xh = XmlHandler()
        parser = xml.sax.make_parser()
        parser.setContentHandler(xh)
        parser.parse(open(dfFullPath))
    # end ParseAndInstall()

if __name__ == "__main__":
    this = DrPatch(sys.argv)
