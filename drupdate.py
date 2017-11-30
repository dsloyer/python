import os                       # import path.split(), path.splitext()
import sys                      # argv[], version
import time                     # sleep()
import getopt			        # argument processing
import msvcrt                   # kbhit()
import string
from _winreg import *

import restart                  # RebootSystem()
import drlog                    # DR-style logging
import wininfo                  # OS, IE version information
import scrnsaver                # Screensaver on, off

import drpatch                  # parse XML file, and install patches

## global vars
pgm         = ""                # this program's name
cnt         = 0                 # count of items installed
bootCnt     = 0                 # count of estimated reboots required
spInstalled = 0	                # flag indicating that a service pack or IE was installed
quiet       = 0                 # no output
verbose     = 0                 # much output
veryVerbose = 0                 # much more output
force       = 0                 # force reinstall of all hotfixes
forceSp     = 0                 # force reinstall of OS Service Pack
forceIeSp   = 0                 # force reinstall of IE
test        = 0                 # Don't do anything -- just tell me what WOULD be done
no_reboot   = 0                 # don't reboot at end
force_reboot = 0                # just reboot the system; nothing will be installed
startup     = 0                 # create a caller to this program in the startup folder
rmStartup   = 0                 # remove caller from startup folder

datafile    = "hotfixes.xml"    # hotfix datafile name
logfile     = ""                # name of desired logfile
drive       = ""                # source drive letter
strOs       = ""                # current OS
strSp       = ""                # current OS service pack level
strSpecific = []                # specific items to install

log = drlog.Log()           # Open the logfile (reopened later)

## global functions
def prn(str):
    if not quiet:
        print str

# print string, also write to log
def prnLog(str, sev = log.LOG_INFO):
    strOut = "%s: %s" % (pgm, str)
    prn(strOut)
    log.write(strOut, sev)

# print string, write to log, and exit
def prnLogExit(str):
    strOut = "%s: %s" % (pgm, str)
    prn(strOut)
    log.write(strOut, log.LOG_ERR)
    sys.exit(2)

def usage():
    print 'usage:'
    print '   %s [-h][-v][-V][-q][-k][-e][-f][-t][-z][-p][-m][-i filename][-d drive:][-l logfile][-s item]' % pgm
    print ''
    print 'where:'
    print '   -h or --help                  display usage'
    print '   -v or --verbose               verbose output'
    print '   -V or --veryVerbose           very verbose output'
    print '   -q or --quiet                 no output'
    print '   -k or --servicepack           force re-install of service pack'
    print '   -e or --ie                    force re-install of IE'
    print '   -f or --force                 force re-install of all hotfixes'
    print '   -t or --test                  test only - don\'t apply any Service Pack'
    print '   -z or --noreboot              don\'t reboot at end'
    print '   -r or --forcereboot           reboot even if there\'s nothing to install'
    print '   -p or --startup               place call to drupdate in startup folder'
    print '   -m or --remove                remove call to drupdate from startup folder'
    print '   -i or --input filename        specify hotfix filename'
    print '   -d or --drive drive:          install hotfixes from the specified drive'
    print '   -l or --logfile filename      use specified logfile name'
    print '   -s or --specific item         install specified item'
    print ''
    print 'default:'
    print 'The default behavior is to use the file, <DRS_DRIVE>\drs\utils\hotfixes.xml'
    print ' for the list of items to install, look in <DRS_DRIVE>\drs\device\ms area'
    print ' for the the items to install, and log to '
    print ' where <nnnn> is the stationId.'
    print 'If an alternate filename is specified without any path information, logging will'
    print ' take place in the default log location,'
    print '     <DRS_DRIVE>\drs\logs\stat<nnnn>\drupdate.log.'
    print ' If the alternate filename also provides path information, logging will take place'
    print ' in the specified location.'
    print ''
    print 'Specifying particular items can be achieved by providing one or more \'-s\' options'
    print 'The pattern supplied with the \'-s\' option will match with any item whose name'
    print 'contains the pattern.  This is not case-sensitive.  Multiple \'-s\' options can'
    print 'be supplied -- the program builds a list of patterns to look for.  Specified items'
    print 'that are found to be already installed will be skipped, unless \'-f\' is specified'
    print 'as well.'
    print ''
    print 'examples:'
    print ' To install hotfixes from DRS_DRIVE to workstation/server:'
    print '         %s' % pgm
    print ''
    print ' To test which hotfixes and service packs are not yet installed:'
    print '         %s -t' % pgm
    print ''
    print ' To install hotfixes from CD (F:):'
    print '         %s -d f:' % pgm
    sys.exit(2)

def doArgs():
    # modified globals
    global pgm, verbose, veryVerbose, force, forceSp, forceIeSp, quiet, test, datafile
    global drive, log, logfile, no_reboot, force_reboot, startup, rmStartup, strSpecific

    # argv[0] is the full program name with path and extension.
    # Let's trim it down to just the program name.
    pgmPath, pgmName = os.path.split(sys.argv[0])   # separate pgmname from path
    pgm, ext = os.path.splitext(pgmName)            # separate extension from pgmname

    # check arguments
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hvVqfketzrpmi:d:l:s:",
            ["help", "verbose", "veryVerbose", "quiet", "force", "servicepack", "ie",
             "test", "noreboot", "forcereboot", "startup", "remove", "input=", "drive=", "logfile=",
             "specific="])
    except:
        usage()                             # print help information and bail

    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
        elif o in ("-v", "--verbose"):
            veryVerbose = 0
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
        elif o in ("-k", "--servicepack"):
            forceSp = 1
        elif o in ("-e", "--ie"):
            forceIeSp = 1
        elif o in ("-t", "--test"):
            test = 1
        elif o in ("-z", "--noreboot"):
            no_reboot = 1
        elif o in ("-r", "--forcereboot"):
            force_reboot = 1
        elif o in ("-p", "--startup"):
            startup = 1
        elif o in ("-m", "--remove"):
            rmStartup = 1
        elif o in ("-i", "--input"):
            datafile = a
        elif o in ("-d", "--drive"):
            drive = a
        elif o in ("-l", "--logfile"):
            logfile = a
        elif o in ("-s", "--specific"):
            strSpecific.append(a)
        else:
            usage()
# end doArgs()

def DRRebootSystem(seconds):
    # function will call RebootSystem with the parameters specified
    # and output some command line messages.

    if seconds < 3:
        strOut = "DRRebootSystem: Too few seconds specified in call: %d" % seconds
        prnLogExit(strOut)
        
    strOut = "Rebooting in 10 seconds. Hit any key in the COMMAND PROMPT window to abort."
    print(strOut)
    restart.RebootSystem(strOut, seconds, 1, 1)
    for i in range(seconds - 2):
        time.sleep(1)
        if msvcrt.kbhit():
            restart.AbortReboot()
            strOut = "Shutdown Aborted"
            print(strOut)
            break
            
#end DRRebootSystem()    

def SetRegKeyVal(reg, strKey, strValName, nType, val):
    # function will create the key if reg\strLoc key does not already exist.
    # it appears that XP SP2 doesn't create the "Security Center" key
    # until it reboots following the SP2 installation -- too late for drUpdate.
    
    # get a handle for registry (e.g. HKLM)
    hReg = ConnectRegistry(None, reg)

    try:
        # See whether key exists.
        # Open Environment key for read/write.
        hKey = OpenKey(hReg, strKey, 0, KEY_ALL_ACCESS)
        # strOut = "Regkey, \"%s\", exists" % strKey
        # prnLog(strOut)
    except:
        # strOut = "Key, \"%s\", doesn't exist" % strKey
        # prnLog(strOut)
        # Create strKey
        try:
            hKey = CreateKey(hReg, strKey)
            strOut = "Created regkey: \"%s\"" % strKey
            prnLog(strOut)
        except:
            # couldn't create key
            CloseKey(hReg)     # close registry        
            strOut = "Error creating regkey, \"%s\"" % strKey
            prnLogExit(strOut)
    # assert: strKey key exists and is open

    # create a sub-key value for this item.
    # Note: If the value already exists, it is over-written.
    try:
        SetValueEx(hKey, strValName, 0, nType, val)
    except:
        CloseKey(hKey)          # close write-key handle
        CloseKey(hReg)          # close registry        
        strOut = "Error setting value: \"%s\", to key \"%s\"" % (val, strValName)
        prnLogExit(strOut)
        
    CloseKey(hKey)     # close write-key handle
    CloseKey(hReg)     # close registry
# end SetRegKeyVal()


def SecurityCtrConfig():
    Reg     = HKEY_LOCAL_MACHINE
    strKey  = r"SOFTWARE\Microsoft\Security Center"
    nType   = REG_DWORD
    val     = 0x01
    
    SetRegKeyVal(Reg, strKey, "FirstRunDisabled",       nType, val)
    SetRegKeyVal(Reg, strKey, "AntiVirusDisableNotify", nType, val)
    SetRegKeyVal(Reg, strKey, "FirewallDisableNotify",  nType, val)
    SetRegKeyVal(Reg, strKey, "UpdatesDisableNotify",   nType, val)
# end SecurityCtrConfig()


def SetMessenger():
    # get a handle for HKLM
    hReg = ConnectRegistry(None, HKEY_LOCAL_MACHINE)

    # Open Environment key for read/write.
    hKey = OpenKey(hReg, r"SYSTEM\CurrentControlSet\Services\Messenger", 0, KEY_ALL_ACCESS)

    # Set the type
    val = 0x20
    try:
        SetValueEx(hKey, "Type", 0, REG_DWORD, val)
        
        # confirm result
        try:
            gval = QueryValueEx(hKey, "Type")[0]
            if not gval == val:
                print "error: Unsuccessful attempt to set Messenger Service Type"
        except EnvironmentError:
            print "error: Messenger Service Type value not found in registry"
    except EnvironmentError:                                          
        print "error: Error setting Messenger Service Type value."

    # Set the Start
    val = 2
    try:
        SetValueEx(hKey, "Start", 0, REG_DWORD, val)
        
        # confirm result
        try:
            gval = QueryValueEx(hKey, "Start")[0]
            if not gval == val:
                print "error: Unsuccessful attempt to set Messenger Service Start"
        except EnvironmentError:
            print "error: Messenger Service Start value not found in registry"
    except EnvironmentError:                                          
        print "error: Error setting Messenger Service Start value."

    CloseKey(hKey)     # close write-key handle
    CloseKey(hReg)     # close registry
# end SetMessenger()

def InstallXpSp3():
    # note: -n means no backup, -u means unattended mode, -z means no reboot
    cmd = r'%s\drs\device\ms\xp\sp3\WindowsXP-KB936929-SP3-x86-ENU.exe /passive /norestart' % drive

    oScrnSaver = scrnsaver.ScrnSaver()

    oScrnSaver.off()
    os.popen(cmd)
    oScrnSaver.on()

    # Enable Messenger Service
    # SetMessenger()
    
    # Rig the Security Center for silent running
    # SecurityCtrConfig()
#end InstallXpSp3()

def Install2k3x86Sp2():
    # note: -n means no backup, -u means unattended mode, -z means no reboot
    cmd = r'%s\drs\device\ms\2k3\WindowsServer2003-KB914961-SP2-x86-ENU.exe /passive /norestart' % drive

    oScrnSaver = scrnsaver.ScrnSaver()

    oScrnSaver.off()
    os.popen(cmd)
    oScrnSaver.on()
#end Install2k3x86Sp2()

def Install2k3x64Sp2():
    # note: -n means no backup, -u means unattended mode, -z means no reboot
    cmd = r'%s\drs\device\ms\2k3\WindowsServer2003.WindowsXP-KB914961-SP2-x64-ENU.exe /passive /norestart' % drive

    oScrnSaver = scrnsaver.ScrnSaver()

    oScrnSaver.off()
    os.popen(cmd)
    oScrnSaver.on()
#end Install2k3x64Sp2()

def IsInstalledWin6(strId, strName):
    # This function is used to check whether a particular Windows 6 (2k8, vista, win7, k8r2)
    # item has been installed.
    
    # This function accepts a string identifying the item; the string points
    # to the key under HKLM\SOFTWARE\Microsoft\Updates where the key can be found.
    # That is, the passed string is a specific path to the key that appears whenever
    # this specific item has been installed.
    RegLoc = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Component Based Servicing\\Packages\\"

    # print "IsInstalledWin6: strId: \"%s\", strName: \"%s\"" % (strId, strName)

    bIns = 0        # flag indicating whether item was found to be installed
    strKey = ""     # array of potential locations in registry where the subkey may be found
    strFound = ""   # Save the key when an item is found

    # check registry.  Get a handle for HKLM
    hReg = ConnectRegistry(None, HKEY_LOCAL_MACHINE)
    
    strKey = RegLoc + strId
    # Open key for read.
    try:
        hKey = OpenKey(hReg, strKey, 0, KEY_READ)
        if verbose:
            strOut = "key, \"%s\", for item, \"%s\", was found." % (strKey, strName)
            prnLog(strOut)
        bIns = 1
        CloseKey(hKey)      # close write-key handle
    except EnvironmentError:
        if verbose:
            strOut = "key, \"%s\", for item, \"%s\", was not found." % (strKey, strName)
            prnLog(strOut)

    CloseKey(hReg)     # close registry
    return bIns
# End IsInstalledWin6()


# main:
fpath = ""
fname = ""

doArgs()
if logfile:
    fpath, fname = os.path.split(logfile)
    #print "path: \"%s\", fname: \"%s\"" % (fpath, fname)
else:
    # no logfile name supplied -- use our default name, "drupdate.log"
    fname = "drupdate.log"

# Check for Python 2.6 installation in C:\python26
if not os.path.exists(r"c:\python26"):
    strOut = "Python 2.6 not found. Please run Ins6.bat to install it, re-logon, and re-run drUpdate"
    prnLogExit(strOut)

# print "drupdate: opening logfile: %s" % logfile
if fpath or fname:
    # print "drupdate: opening logfile, \"%s\", in directory \"%s\"" % (fname, fpath)
    log = drlog.Log(fname, fpath)       # reopen logfile with appropriate name

# Create object to access OS and Service Pack
oWinInfo = wininfo.WinInfo()

# Fetch OS and SP information
strOs, strSp = oWinInfo.GetOsInfo()
if veryVerbose:
    strOut = 'OS is "%s", SP is "%s".' % (strOs, strSp)
    prnLog(strOut)

if not drive:
    # no path supplied.  See if drs_drive is defined
    try:
        drsDrv  = os.environ["DRS_DRIVE"]
        drive = drsDrv
    except:
        strOut = "error: no drive supplied, and DRS_DRIVE is undefined."
        prnLogExit(strOut)
    
if not ((len(drive) == 2) and drive[0].isalpha() and (drive[-1] == ':')):
    strOut = "error: no path supplied, and DRS_DRIVE is defined, but not a drive letter."
    prnLogExit(strOut)

# Just reboot the system
if force_reboot == 1:
    DRRebootSystem(10)

    sys.exit(0)    

# Clean startup folder if we're told to
if rmStartup:
    # remove caller to self from startup folder.  Assume name is "drupstart.bat"
    if ((strOs.upper().find("VISTA") <> -1) or (strOs.upper().find("2K8") <> -1) or (strOs.find("Win7") <> -1) or (strOs.find("Win8") <> -1) or (strOs.find("2K12") <> -1)):
        # Remove the drupdate scheduled task.
        prnLog("Removing drupdate scheduled task.")
        cmd = r'SchTasks.exe /Delete /TN drupdate /F'
        os.popen(cmd)

    elif os.path.exists(r"c:\Documents and Settings\All Users\Start Menu\Programs\startup\drupstart.bat"):
        prnLog("Startup file found in startup folder.  Removing it now.")
        os.remove(r"c:\Documents and Settings\All Users\Start Menu\Programs\startup\drupstart.bat")

    sys.exit(0)

if startup:
    strStartup = "%s -d %s" % (sys.argv[0], drive)
    # create caller to self from startup folder.  Name is "drupstart.bat"
    if not strOs.upper().find("NT4") == -1:
        strOut = "Installing startup program in startup folder"
        prnLog(strOut)

        # NT4-class system
        try:
            file = open(r"c:\winnt\profiles\all users\start menu\programs\startup\drupstart.bat", "w")
            file.write(strStartup)
            file.close()
        except:
            strOut = "Error creating drstartup.bat in the NT system startup folder"
            prnLog(strOut)

    elif (strOs.upper().find("VISTA") <> -1) or (strOs.upper().find("2K8") <> -1) or (strOs.find("Win7") <> -1) or (strOs.find("Win8") <> -1) or (strOs.find("2K12") <> -1):
            strOut = "Creating 'drupdate' scheduled task to execute at next logon"
            prnLog(strOut)

            # Create a scheduled task to complete the drupdate process.
            cmd = r'SchTasks.exe /create /SC ONLOGON /TN drupdate /TR "%s\drs\utils\drupdate.py -d %s" /IT /F /RL HIGHEST /DELAY 0000:30' % (drive, drive)
            os.popen(cmd)

    else:
        try:
            file = open(r"c:\Documents and Settings\All Users\Start Menu\Programs\startup\drupstart.bat", "w")
            file.write(strStartup)
            file.close()
        except:
            strOut = "Error creating drstartup.bat in system startup folder"
            prnLog(strOut)

# Display the relevant parameters of the operation
if veryVerbose:
    strOut = 'drive:     %s' % drive
    prnLog(strOut)
    strOut = 'datafile:  %s' % datafile
    prnLog(strOut)
    strOut = 'force:     %s' % force
    prnLog(strOut)
    strOut = 'forceSp:   %s' % forceSp
    prnLog(strOut)
    strOut = 'forceIeSp: %s' % forceIeSp
    prnLog(strOut)
    strOut = 'test:      %s' % test
    prnLog(strOut)
    for str in strSpecific:
        strOut = 'specific item: %s' % str
        prnLog(strOut)

if strOs == "XP-x86":
    if not strSp == "Service Pack 3":
        bootCnt += 1
        # Installing XP SP3
        if test:
            strOut = "Would install XP SP3"
            prnLog(strOut)
        else:
            strOut = "Installing XP SP3"
            prnLog(strOut)
            InstallXpSp3()
            spInstalled = 1
    elif forceSp:
        bootCnt += 1
        # has SP3, but we're forcing a re-install
        if test:
            strOut = "Would reinstall XP SP3"
            prnLog(strOut)
        else:
            strOut = "Reinstalling XP SP3"
            prnLog(strOut)
            InstallXpSp3()
            spInstalled = 1
elif strOs == "2K3-x86":
    if not strSp == "Service Pack 2":
        strOut = "OS is %s, SP is %s.  This program requires 2K3 SP2" % (strOs, strSp)
        prnLog(strOut)
        bootCnt += 1

        # Install 2K3 SP2
        if test:
            strOut = "Would install 2K3 SP2"
            prnLog(strOut)
        else:
            strOut = "Installing 2K3 SP2"
            prnLog(strOut)
            Install2k3x86Sp2()
            spInstalled = 1
    elif forceSp:
        bootCnt += 1
        if test:
            strOut = "Would reinstall 2K3 SP2"
            prnLog(strOut)
        else:
            strOut = "Reinstalling 2K3 SP2"
            prnLog(strOut)
            Install2k3x86Sp2()
            spInstalled = 1
elif strOs == "2K3-x64" or strOs == "XP-x64":
    # we have 64-bit 2K3 or XP
    if not strSp == "Service Pack 2":
        strOut = "OS is %s, SP is %s.  This program requires SP2 for x64 XP/2K3" % (strOs, strSp)
        prnLog(strOut)
        bootCnt += 1

        # Install SP2 for x64 XP/2K3
        if test:
            strOut = "Would install SP2 for x64 XP/2K3"
            prnLog(strOut)
        else:
            strOut = "Installing SP2 for x64 XP/2K3"
            prnLog(strOut)
            Install2k3x64Sp2()
            spInstalled = 1
    elif forceSp:
        bootCnt += 1
        if test:
            strOut = "Would reinstall SP2 for x64 XP/2K3"
            prnLog(strOut)
        else:
            strOut = "Reinstalling SP2 for x64 XP/2K3"
            prnLog(strOut)
            Install2k3x64Sp2()
            spInstalled = 1
elif strOs == "Vista-x86":
    if not strSp == "Service Pack 2":
        strOut = "OS is %s, SP is %s.  This program requires SP2 for x86 Vista" % (strOs, strSp)
        prnLogExit(strOut)
elif strOs == "Vista-x64" or strOs == "2K8-x64":
    if not strSp == "Service Pack 2":
        strOut = "OS is %s, SP is %s.  This program requires SP2 for x64 Vista/2K8" % (strOs, strSp)
        prnLogExit(strOut)
elif strOs == "Win7-x64" or strOs == "2K8R2-x64":
    if not strSp == "Service Pack 1":
        strOut = "OS is %s, SP is %s.  This program requires SP1 for 2K8R2/Windows7" % (strOs, strSp)
        prnLogExit(strOut)
    pass
elif strOs == "Win8-x64" or strOs == "2K12-x64":
    pass
elif strOs == "Win8.1-x64" or strOs == "2K12R2-x64":
    pass
else:
    strOut = "Unrecognized OS: \"%s\"" % strOs
    prnLogExit(strOut)
    
# Fetch IE information
cmdIE11Win7X64 = r'%s\drs\device\ms\ie\ie11\IE11-Windows6.1-x64-en-us.exe     /passive /norestart /update-no' % drive
cmdIE92K8X64   = r'%s\drs\device\ms\ie\ie9\IE9-WindowsVista-x64-enu.exe       /passive /norestart /update-no' % drive

# IE8 installers
cmdIE82K8X64   = r'%s\drs\device\ms\ie\ie8\IE8-WindowsVista-x64-enu.exe       /passive /norestart /update-no' % drive
cmdIE82K8X86   = r'%s\drs\device\ms\ie\ie8\IE8-WindowsVista-x86-enu.exe       /passive /norestart /update-no' % drive
cmdIE82K3X64   = r'%s\drs\device\ms\ie\ie8\IE8-WindowsServer2003-x64-enu.exe  /passive /norestart /update-no' % drive
cmdIE82K3X86   = r'%s\drs\device\ms\ie\ie8\IE8-WindowsServer2003-x86-enu.exe  /passive /norestart /update-no' % drive
cmdIE8XPX86    = r'%s\drs\device\ms\ie\ie8\IE8-WindowsXP-x86-enu.exe          /passive /norestart /update-no' % drive

# IE9 prerequisites
cmdKB971512    = r'%s\drs\device\ms\ie\ie9\Windows6.0-KB971512-x64.msu        /quiet   /norestart' % drive
cmdKB2117917   = r'%s\drs\device\ms\ie\ie9\Windows6.0-KB2117917-x64.msu       /quiet   /norestart' % drive

# IE11 prerequisites
cmdKB2533623   = r'%s\drs\device\ms\ie\ie11\Windows6.1-KB2533623-x64.msu      /quiet   /norestart' % drive
cmdKB2639308   = r'%s\drs\device\ms\ie\ie11\Windows6.1-KB2639308-x64.msu      /quiet   /norestart' % drive
cmdKB2670838   = r'%s\drs\device\ms\ie\ie11\Windows6.1-KB2670838-x64.msu      /quiet   /norestart' % drive
cmdKB2729094   = r'%s\drs\device\ms\ie\ie11\Windows6.1-KB2729094-v2-x64.msu   /quiet   /norestart' % drive
cmdKB2731771   = r'%s\drs\device\ms\ie\ie11\Windows6.1-KB2731771-x64.msu      /quiet   /norestart' % drive
cmdKB2786081   = r'%s\drs\device\ms\ie\ie11\Windows6.1-KB2786081-x64.msu      /quiet   /norestart' % drive
cmdKB2834140   = r'%s\drs\device\ms\ie\ie11\Windows6.1-KB2834140-v2-x64.msu   /quiet   /norestart' % drive
cmdKB2888049   = r'%s\drs\device\ms\ie\ie11\Windows6.1-KB2888049-x64.msu      /quiet   /norestart' % drive
cmdKB2882822   = r'%s\drs\device\ms\ie\ie11\Windows6.1-KB2882822-x64.msu      /quiet   /norestart' % drive

ieVersion = oWinInfo.GetIeInfo()
# print 'ieVersion: \"%s\"' % ieVersion
if (strOs == "2K12R2-x64" or strOs == "Win8.1-x64"):
    if (ieVersion == "IE11"):
        strOut = "IE version: \"%s\"." % ieVersion
        prnLog(strOut)
    else:
        # Not current
        strOut = "IE version: \"%s\" (NOT CURRENT)." % ieVersion
        prnLog(strOut)
elif (strOs == "2K12-x64" or strOs == "Win8-x64"):
    if (ieVersion == "IE10"):
        strOut = "IE version: \"%s\"." % ieVersion
        prnLog(strOut)
    else:
        # Not current
        strOut = "IE version: \"%s\" (NOT CURRENT)." % ieVersion
        prnLog(strOut)
elif (strOs == "2K8R2-x64" or strOs == "Win7-x64"):
    if (not ieVersion == "IE11"):
        # Not current
        strOut = "IE version: \"%s\" (NOT CURRENT)." % ieVersion
        prnLog(strOut)
        if bootCnt == 0:
            bootCnt += 1
    
        if test:
            strOut = "Would install IE11"
            prnLog(strOut)
        else:
            # install IE11
            if (not IsInstalledWin6("Package_2_for_KB2888049~31bf3856ad364e35~amd64~~6.1.1.1", "KB2888049")):
                # Install two hotfixes first: 2533623, 2639308, 2670838, 2729094, 2731771, 2786081, 2834140, 2888049, 2882822
                cmd = cmdKB2533623
                strOut = "Installing KB needed by IE11: KB2533623"
                prnLog(strOut)
                os.popen(cmd)
                
                cmd = cmdKB2639308
                strOut = "Installing KB needed by IE11: KB2639308"
                prnLog(strOut)
                os.popen(cmd)
                
                cmd = cmdKB2670838
                strOut = "Installing KB needed by IE11: KB2670838"
                prnLog(strOut)
                os.popen(cmd)
                
                cmd = cmdKB2729094
                strOut = "Installing KB needed by IE11: KB2729094"
                prnLog(strOut)
                os.popen(cmd)
                
                cmd = cmdKB2731771
                strOut = "Installing KB needed by IE11: KB2731771"
                prnLog(strOut)
                os.popen(cmd)
                
                cmd = cmdKB2786081
                strOut = "Installing KB needed by IE11: KB2786081"
                prnLog(strOut)
                os.popen(cmd)
                
                cmd = cmdKB2834140
                strOut = "Installing KB needed by IE11: KB2834140"
                prnLog(strOut)
                os.popen(cmd)
                
                cmd = cmdKB2882822
                strOut = "Installing KB needed by IE11: KB2882822"
                prnLog(strOut)
                os.popen(cmd)
                
                cmd = cmdKB2888049
                strOut = "Installing KB needed by IE11: KB2888049"
                prnLog(strOut)
                os.popen(cmd)
                
                DRRebootSystem(10)
       
            strOut = "Installing IE11 for 2K8R2/Win7 x64"
            prnLog(strOut)
            cmd = cmdIE11Win7X64
                
            # print "cmd: \"%s\"" % cmd
            spInstalled = 1
            os.popen(cmd)
elif (strOs == "2K8-x64" or strOs == "Vista-x64"):
    if (not ieVersion == "IE9"):
        # Not current
        strOut = "IE version: \"%s\" (NOT CURRENT)." % ieVersion
        prnLog(strOut)
        if bootCnt == 0:
            bootCnt += 1
    
        if test:
            if (not IsInstalledWin6("Package_100_for_KB2117917~31bf3856ad364e35~amd64~~6.0.1.5", "KB2117917")):
                strOut = "Would install KB971512 and KB2117971 (needed by IE9)"
                prnLog(strOut)
            strOut = "Would install IE9"
            prnLog(strOut)
        else:
            # Install IE9
            if (not IsInstalledWin6("Package_100_for_KB2117917~31bf3856ad364e35~amd64~~6.0.1.5", "KB2117917")):
                # Install two hotfixes first: KB971512, KB2117917
                cmd = cmdKB971512
                strOut = "Installing KB needed by IE9: KB971512"
                prnLog(strOut)
                os.popen(cmd)
                
                cmd = cmdKB2117917
                strOut = "Installing KB needed by IE9: KB2117917"
                prnLog(strOut)
                os.popen(cmd)
                
                DRRebootSystem(10)

            strOut = "Installing IE9 for 2K8/Vista x64"
            prnLog(strOut)
            
            cmd = cmdIE92K8X64
            # print "cmd: \"%s\"" % cmd
            spInstalled = 1
            os.popen(cmd)
elif (not ieVersion == "IE8"):
    # Not current
    strOut = "IE version: \"%s\" (NOT CURRENT)." % ieVersion
    prnLog(strOut)
    if bootCnt == 0:
        bootCnt += 1

    if test:
        strOut = "Would install IE8"
        prnLog(strOut)
    else:
        # Install IE8
        if strOs == "XP-x86":
            strOut = "Installing IE8 for XP x86"
            prnLog(strOut)
            cmd = cmdIE8XPX86
        elif strOs == "2K3-x86":
            strOut = "Installing IE8 for 2K3 x86"
            prnLog(strOut)
            cmd = cmdIE82K3X86
        elif strOs == "2K3-x64" or strOs == "XP-x64":
            strOut = "Installing IE8 for 2K3/XP x64"
            prnLog(strOut)
            cmd = cmdIE82K3X64
        elif strOs == "2K8-x86" or strOs == "Vista-x86":
            strOut = "Installing IE8 for 2K8/Vista x86"
            prnLog(strOut)
            cmd = cmdIE82K8X86
        elif strOs == "2K8R2-x86" or strOs == "Win7-x86" or strOs == "2K8R2-x64" or strOs == "Win7-x64":
            strOut = "No installer exists for IE8 on Win7/2k8R2"
            prnLogExit(strOut)

        # print "cmd: \"%s\"" % cmd
        spInstalled = 1
        os.popen(cmd)
elif forceIeSp:
    # Forced re-install
    if bootCnt == 0:
        bootCnt += 1

    if test:
        strOut = "Would reinstall IE8"
        prnLog(strOut)
    else:
        # Re-install IE8
        if strOs == "XP-x86":
            strOut = "Installing IE8 for XP x86"
            prnLog(strOut)
            cmd = cmdIE8XPX86
        elif strOs == "2K3-x86":
            strOut = "Installing IE8 for 2K3 x86"
            prnLog(strOut)
            cmd = cmdIE82K3X86
        elif strOs == "2K3-x64" or strOs == "XP-x64":
            strOut = "Installing IE8 for 2K3/XP x64"
            prnLog(strOut)
            cmd = cmdIE82K3X64
        elif strOs == "2K8-x86" or strOs == "Vista-x86":
            strOut = "Installing IE8 for 2K8/Vista x86"
            prnLog(strOut)
            cmd = cmdIE82K8X86
        elif strOs == "2K8-x64" or strOs == "Vista-x64":
            strOut = "Installing IE8 for 2K8/Vista x64"
            prnLog(strOut)
            cmd = cmdIE82K8X64
        elif strOs == "2K8R2-x86" or strOs == "Win7-x86":
            strOut = "No installer for IE8 on Win7/2k8 R2 x86"
            prnLog(strOut)
            cmd = cmdIE82K8R2X86
        elif strOs == "2K8R2-x64" or strOs == "Win7-x64":
            strOut = "No installer for IE8 on Win7/2k8 R2 x64"
            prnLog(strOut)
            cmd = cmdIE11Win7X64
            
        # print "cmd: \"%s\"" % cmd
        spInstalled = 1
        os.popen(cmd)
else:
    if veryVerbose:
        prnLog("IE is current.")

if test:
    pass
elif bootCnt == 0:
    prnLog("Service Packs are up-to-date.")
else:
    if veryVerbose:
        strOut = "%d Service Pack items installed." % bootCnt
        prnLog(strOut)
    if not no_reboot:
        DRRebootSystem(10)

# print "spInstalled = %d" % spInstalled
if test or (spInstalled == 0):
    # Construct call to apply hotfixes
    patchCmd = []
    patchCmd.append(r".\drpatch")
    patchCmd.append("-p")               # tell drpatch to use our program name
    patchCmd.append(pgm)
    patchCmd.append("-d")               # tell drpatch to use our drive letter
    patchCmd.append(drive)
    if force:                           
        patchCmd.append("-f")
    if test:
        patchCmd.append("-t")
    if verbose:
        patchCmd.append("-v")
    if veryVerbose:
        patchCmd.append("-V")
    if quiet:
        patchCmd.append("-q")
    if datafile:
        patchCmd.append("-i")
        patchCmd.append(datafile)
    if logfile:
        patchCmd.append("-l")
        patchCmd.append(logfile)
    for str in strSpecific:
        patchCmd.append("-s")
        patchCmd.append(str)

    oScrnSaver = scrnsaver.ScrnSaver()

    oScrnSaver.off()
    # strOut = "Calling drUpdate using: \"%s\"" % patchCmd
    # prnLog(strOut)
    oDrPatch = drpatch.DrPatch(patchCmd)    # call drPatch to apply all defined items
    cnt = oDrPatch.getRes()                 # returns a count of items(or items that would be) installed
    if cnt:
        bootCnt += 1                        # bootCnt indicates number of estimated re-boots
    oScrnSaver.on()

    # Clean startup folder if there were no updates, or if we're told to
    if cnt == 0:
        prnLog("System is up-to-date.  All items are installed.")
    
        # Remove drupdate scheduled task.
        if ((strOs.upper().find("VISTA") <> -1) or\
            (strOs.upper().find("WIN7") <> -1)  or\
            (strOs.upper().find("2K8") <> -1)):
            prnLog("Removing drupdate scheduled task.")
            time.sleep(5)
            cmd = r'SchTasks.exe /Delete /TN drupdate /F'
            os.popen(cmd)

        # remove caller to self from startup folder.  Assume name is "drupstart.bat"
        elif os.path.exists(r"c:\Documents and Settings\All Users\Start Menu\Programs\startup\drupstart.bat"):
            prnLog("Startup file found in startup folder.  Removing it now.")
            time.sleep(5)
            os.remove(r"c:\Documents and Settings\All Users\Start Menu\Programs\startup\drupstart.bat")

    elif test:
        strOut = "test: %d items would be installed, requiring %d re-boot(s)." % (cnt, bootCnt)
        prnLog(strOut)
    else:
        strOut = "%d items installed." % cnt
        prnLog(strOut)
        if not no_reboot:
            DRRebootSystem(10)

