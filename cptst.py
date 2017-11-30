#############################################################
#
# cptst: Copy Test:
#
# Type "cptst -h" or "cptst --help" for help.
#
#
#############################################################

import os                   # import path.split(), path.splitext()
import stat                 # stat()
import getopt			    # argument processing
import string               # atoi()
import tempfile             # tempdir, mktemp()
import shutil               # copy files
import filecmp              # cmp()
import random               # generate random data
import sys                  # path.split()
import msvcrt               # getch()
import time                 # time()

import drlog                # use DR-style logging

#initialize globals
pgm         = ''            # program name (stripped)
kb          = 1000          # 1KB
mb          = kb * kb       # 1MB
cpThreshold = 1 * mb        # when size exceeds this value, use copy cmd rather than Python I/O

srcBase     = ""            # constructed source filename, with path
dstBase     = ""            # constructed destination filename, with path
src         = ""            # constructed source filename, with path and count
dst         = ""            # constructed destination filename, with path and count
fsrc        = []            # array of open src file handles
fdst        = []            # array of open dst file handles
retainSrc   = 0             # don't retain source file
retainDst   = 0             # don't retain destination file
usePyIoOnly = 0             # flag to use only Python I/O
useCopyOnly = 0             # flag to use only copy command
useMaxTime  = 0             # use maxTime variable
maxTime     = 30            # maximum time allowed for program execution (30 seconds)
elapsedtime = 0             # file copy time in seconds
size        = mb            # default to 1MB filesize
maxCnt      = 10            # copy the file no more than ten times
i           = 0             # actual number of copies made
localDir    = ''            # local directory override
path        = ''            # directory path to copy from/to
file        = ''            # filename
compare     = 0             # Compare the copied file w/original
read        = 1             # Copy the file from the specified path
write       = 0             # Copy the file to the specified path
quiet       = 0             # quiet flag
verbose     = 0             # verbose flag
veryVerbose = 0             # very verbose flag

genFile     = 1             # assume we're going to have to generate the file

# Open the logfile
log = drlog.Log()

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

def usage():
    print 'usage:'
    print '   %s [-h][-q][-v][-V][-m][-e][-s size][-c cnt][-t time][-f file][-C][-P][-r | -w][-l local][path]' % pgm
    print ''
    print 'where:'
    print '   -h or --help                  display usage'
    print '   -q or --quiet                 no output'
    print '   -v or --verbose               verbose output'
    print '   -V or --veryVerbose           very verbose output'
    print '   -m or --compare               compare files after each copy'
    print '   -e or --extended              long-running test, with file'
    print '                                 compare, like CopyTest'
    print '   -s or --size                  file size'
    print '   -c or --count                 number of copies'
    print '   -f or --file                  copy specified file name'
    print '   -r or --read                  copy from path'
    print '   -t or --time                  max desired run time (secs)'
    print '   -w or --write                 copy to path'
    print '   -R or --retain                don\'t cleanup src/dst files at end'
    print '   -l or --local                 local path'
    print '   -C or --copy                  use copy command only'
    print '   -P or --pyio                  use Python file I/O only'
    print '   path is the remote directory from/to which data will be copied'
    print ''
    print 'examples:'
    print '   To test read performance from server to workstation:'
    print '         %s'     % pgm
    print ''
    print '   To test write performance to server from workstation:'
    print '         %s -w'  % pgm
    print ''
    print 'default:'
    print '   Copy 1MB file from <DRS_DRIVE>\\drs\\temp to c:\\ 10 times, with no'
    print '   file compare.'
    print ''
    print 'This program copies a file from a source directory to a destination'
    print 'directory many times, reporting the elapsed time and measured throughput'
    print ''
    print 'Expected throughput: On a typical LAN, expect 4 - 8 MBps (32 to 64 Mbps),'
    print 'generally better on newer hardware.  If a duplex mis-match exists, expect'
    print 'throughput to drop below 1 MBps. On T-1 connections, we\'ve measured'
    print '0.16MBps (1.28Mbps), when healthy.'
    print ''
    print 'The program generates and destroys all files it creates, so no file needs'
    print 'to be specified, or cleaned, up after running the program.'
    print ''
    print 'Default behavior on a DR workstation is to to create a temporary 1MB file'
    print 'in i:\\drs\\temp, which is copied 10 times to c:\\.  The elapsed time and'
    print 'throughput are reported on the command line and are logged in'
    print 'i:\\drs\\logs\\statNNN\\system.log, where NNN is the station number.'
    print ''
    print 'The direction of the file copy is normally from server to workstation;'
    print 'this corresponds to the \'-r\' or \'--read\' option.  To reverse the copy'
    print 'direction, specify the \'-w\' or \'--write\' option.'
    print ''
    print 'The size of the copied file can be set using \'-s size\', where size is'
    print 'replaced by the desired size.  The program recognises KB and MB as suffixes,'
    print 'so that a 10 megabyte filesize can be requested using \'-s 10MB\'.'
    print ''
    print 'The program has been modified to copy files in groups, rather than one at a'
    print 'time.  This is done to improve measurement of file copy performance when'
    print 'small files are copied.  The program first determines the number of files'
    print 'needed to exceed a 1 second minimum time threshold (the groupsize).  The'
    print 'program insists on performing an integral number of groupsize file copies.'
    print ''
    print 'The \'-t\' parameter is new, allowing the user to specify the maximum number'
    print 'of seconds the user is willing to wait for the program to complete.  After'
    print 'copying a group of files, the elapsed time is checked.  If a specified time'
    print 'has been exceeded, the program terminates, and reports the results obtained'
    print 'up to that point in time.'
    print ''
    print 'The number of copies is controlled by the \'-c count\' option, where count'
    print 'is replaced by the desired number, e.g. \'-c 1000\'.'
    print ''
    print 'If desired, the copied file can be compared with its source, using the'
    print '\'-m\' or \'--compare\' option.  When comparison is enabled, and no file'
    print 'is explicitly specified, a file of size required is automatically generated,'
    print 'filled with completely random data. The time required to produce the file is'
    print 'not included in the elapsed time calculation.'
    print ''
    print 'The program performs its work quietly, by default, producing no output until'
    print 'it is finished.  If you desire intermediate output, specify the \'-v\' or'
    print '\'--verbose\' option.  If no output at all is desired, specify the \'-q\' or'
    print '\'--quiet\' option.'
    print ''
    print 'If a long test is desired, with file compare (similar to CopyTest.bat),'
    print 'the extended option, \'-e\', or \'--extended\' should be used.  The extended'
    print 'option automatically enables the verbose option, copying a 1.5MB file 500'
    print 'times.'
    print ''
    print 'The \'f\' or \'--file\' option allows a specific file to be copied in the'
    print 'test.  The file must exist in the current directory or have its path fully-'
    print 'specified.  The size of the specified file is used in throughput'
    print 'calculations.'
    print ''
    print 'The \'-l\' or \'--local\' option allows the default local directory, c:\,'
    print 'to be overridden.'
    sys.exit(2)

def doArgs():
    # referenced globals
    global pgm, opts, args, size, maxCnt, path, file, compare, write, read
    global maxTime, useMaxTime
    global quiet, verbose, veryVerbose
    global retainSrc, retainDst
    global usePyIoOnly, useCopyOnly
    global localDir

    # argv[0] is the full program name with path and extension.
    # Let's trim it down to just the program name.
    pgmPath, pgmName = os.path.split(sys.argv[0])   # separate pgmname from path
    pgm, ext = os.path.splitext(pgmName)            # separate extension from pgmname

    # check arguments
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hs:c:ef:mwrqt:vVRl:CP",
            ["help", "size=", "count=", "extended", "file=", "compare", "write", 
             "read", "quiet", "time=", "verbose", "veryVerbose", "retain", "local=",
             "copy", "pyio"])
    except:
        usage()                             # print help information and bail

    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
        elif o in ("-s", "--size"):
            k = 0
            m = 0
            idxSuffix = a.lower().find("k")
            if idxSuffix > 0:
                k = 1
            else:
                idxSuffix = a.lower().find("m")
                if idxSuffix > 0:
                    m = 1

            # truncate the MB/KB suffix        
            if idxSuffix > 0:
                a = a[:idxSuffix]
                
            nSendBytes = string.atoi(a)
            if   k: nSendBytes *= kb
            elif m: nSendBytes *= mb
            # we've now got the total bytes to send/receive
            if nSendBytes < 1:
                str = 'ignoring specified send size: %s. Using default.' % a
                prnLog(str)
                nSendBytes = nSendDflt
            size = nSendBytes
        elif o in ("-c", "--count"):
            maxCnt = string.atoi(a)
        elif o in ("-e", "--extended"):     # like CopyTest (500 iterations on 1.5MB file, compare)
            compare = 1
            size = int(1.5 * mb)
            maxCnt = 500
        elif o in ("-f", "--file"):
            file = a
            genFile = 0                     # no need to generate file
            retainSrc = 1                   # don't delete the file when finished
            if not os.path.isfile(file):
                str = "error: specified file, '%s', does not exist" % file
                prnLogExit(str)
        elif o in ("-m", "--compare"):
            compare = 1
        elif o in ("-w", "--write"):
            read = 0
            write = 1
        elif o in ("-r", "--read"):
            read = 1
            write = 0 
        elif o in ("-q", "--quiet"):
            quiet = 1
            verbose = 0
            veryVerbose = 0
        elif o in ("-t", "--time"):
            useMaxTime = 1
            maxTime = string.atoi(a)
        elif o in ("-v", "--verbose"):
            quiet = 0
            verbose = 1
        elif o in ("-V", "--veryVerbose"):
            quiet = 0
            verbose = 1
            veryVerbose = 1
        elif o in ("-R", "--retain"):
            retainSrc = 1
            retainDst = 1
        elif o in ("-l", "--local"):
            localDir = a
            try:
                mode = os.stat(localDir)[stat.ST_MODE]
                if not stat.S_ISDIR(mode):
                    strOut = "error: local path, '%s', is not a directory" % localDir
                    prnLogExit(strOut)
            except:
                print "error: local path, '%s', does not exist" % localDir
                sys.exit(2)
        elif o in ("-C", "--copy"):
            useCopyOnly = 1
            usePyIoOnly = 0
        elif o in ("-P", "--pyio"):
            useCopyOnly = 0
            usePyIoOnly = 1
        else:
            usage()
        
    if len(args):
        path = args[0]
# end doArgs()

def CopyGrp(grpSize, size):
    global src, dst, srcBase, dstBase, fsrc, fdst, usePyIoOnly, useCopyOnly

    # print 'CopyGrp: grpSize = %d, size = %d' % (grpSize, size)
    
    # generate files, as necessary    
    for cnt in range(0, grpSize):
        src = srcBase + '-%d' % cnt
        dst = dstBase + '-%d' % cnt

        if genFile:
            try:
                f = open(src, 'wb')
                if compare:
                    # generate random data for the file
                    for i in range(0, size):
                        # random() generates a float betw 0 and 1
                        num = int(random.random() * 256)
                        f.write(chr(num))
                else:
                    # use constant data for the source file
                    s = 'x' * kb
                    for i in range(0, (size / kb)):
                        f.write(s)
                f.close()

                # Confirm src file's existence
                if not os.path.isfile(src):
                    strOut =  "error: Generated source file, '%s' doesn't exist." % src
                    prnLogExit(strOut)
                # we have a source file of the specified size

            except:
                strOut = "Error creating source file: '%s'" % src
                prnLogExit(strOut)
    # assert: grpSize source files created

    if usePyIoOnly or ((size <= cpThreshold) and not useCopyOnly):
        fsrc = []
        fdst = []
        s    = []
        
        if veryVerbose:
            strOut = "Using Python file I/O to move data"
            prnLog(strOut)
            
        # perform grpSize file opens
        for cnt in range(0, grpSize):
            src = srcBase + '-%d' % cnt
            dst = dstBase + '-%d' % cnt
    
            f = open(src, 'rb')
            fsrc.append(f)
            
            f = open(dst, 'wb')
            fdst.append(f)
            
        # perform grpSize file copies, capturing the aggregate copy time
        starttime = time.time()
        # print 'starttime: %f' % starttime
        for cnt in range(0, grpSize):
            src = srcBase + '-%d' % cnt
            dst = dstBase + '-%d' % cnt
    
            # read entire file
            # print "read  entire contents of '%s'" % src
            s.append("")
            s[cnt] = fsrc[cnt].read()
            
            if len(s[cnt]) == 0:
                strOut = 'read from source file, "%s", returned no data' % src
                prnLog(strOut)
            # assert: grpSize files read
    
            # print "write entire contents to '%s'" % dst
            fdst[cnt].write(s[cnt])
        # assert: grpSize files read and written
    
        endtime = time.time()
        # print '  endtime: %f' % endtime
    
        # close grpSize files
        for f in fsrc:
            f.close()
            
        for f in fdst:
            f.close()
    else:
        if veryVerbose:
            strOut = "Using copy commmand to move data"
            prnLog(strOut)
            
        src = srcBase + '-0'
        dst = dstBase + '-0'
        # use copy for big files

        # Compose the command to be used to perform the file copies
        cmd = 'copy "%s" "%s"' % (src, dst)
        # print "cmd: '" + cmd + "'"
	
        starttime = time.time()
        os.popen(cmd)
        endtime = time.time()

    cptime = endtime - starttime
    if veryVerbose:
        print 'group copytime is: %.3f secs for grpSize: %d' % (cptime, grpSize)
    # assert: cptime measures the entire group copy time

    for cnt in range(0, grpSize):
        dst = dstBase + '-%d' % cnt

        # Confirm success of copy
        if not os.path.isfile(dst):
            strOut = "error: dst file, '%s', doesn't exist." % dst
            prnLogExit(strOut)

    # compare grpSize files, if needed
    for cnt in range(0, grpSize):
        src = srcBase + '-%d' % cnt
        dst = dstBase + '-%d' % cnt

        # (opt) Compare the src and dst files
        # In the following, 3rd parm is 0 to disable caching of prev compares
        if compare:
            # DEBUG: insert pause here to modify file...
            # c = msvcrt.getch()
            if not filecmp.cmp(src, dst, 0) == 1:
                strOut = "error: src/dst files don't compare! src: %s, dst: %s" % (src, dst)
                prnLog(strOut)
                
                # compare the files, writing the differences to screen & log
                fname = 'cmp.tmp'
                cmpCmd = 'cmp -l "%s" "%s" >%s' % (src, dst, fname)
                os.popen(cmpCmd)
                if os.path.isfile(fname):
                    f = open(fname, 'r')
                    for line in f:
                        print line
                        log.write(line)
                    f.close()
                    os.remove(fname)

                if verbose:
                    strOut = "error: src/dst files compare OK. src: %s, dst: %s" % (src, dst)
                    prnLog(strOut)

    # delete grpSize src and dst files
    for cnt in range(0, grpSize):
        src = srcBase + '-%d' % cnt
        dst = dstBase + '-%d' % cnt

        # delete src file
        if not retainSrc:
            try:
                os.remove(src)
            except:
                # error removing the file
                strOut = "%s: Error removing src file, \"%s\"" % (pgm, src)
                prnLog(strOut, log.LOG_ERR)

            # Confirm removal of src file
            if os.path.isfile(src):
                strOut = "%s: Error: src file, '%s', exists following deletion." % (pgm, src)
                prnLog(strOut)

        # delete dst file
        if not retainDst:
            try:
                os.remove(dst)
            except:
                strOut = "%s: Error removing dst file: '%s'" % (pgm, dst)
                prnLog(strOut)
        
            # Confirm removal of dst file
            if os.path.isfile(dst):
                strOut = "%s: Error: dst file, '%s', exists following deletion." % (pgm, dst)
                prnLog(strOut)
    return cptime

# main:

# Process arguments
# print sys.argv
doArgs()

if localDir:
    # localDir specified on the command line
    if verbose:
        strOut = 'Using localDir from args: %s' % localDir
        prn(strOut)

    if localDir[-1] != '\\':
       localDir = localDir + '\\'
else:
    localDir = 'c:\\'
# assert: have localDir, w/trailing '\'

if path:
    # path specified on the command line
    if path[-1] != '\\':
       path = path + '\\'
else:
    # no path supplied.  See if drs_drive is defined
    try:
        drsDrv  = os.environ["DRS_DRIVE"]
    except:
        strOut = "error: no path supplied, and DRS_DRIVE is undefined."
        prnLogExit(strOut)
    
    if (len(drsDrv) == 2) and drsDrv[0].isalpha() and (drsDrv[-1] == ':'):
        path = drsDrv + '\\drs\\temp\\'
    else:
        strOut = "error: no path supplied, and DRS_DRIVE is defined, but empty."
        prnLogExit(strOut)
# assert: have path (remote dir), w/trailing '\'

# Generate the filename to be used
if file == "":
    tmpfile = tempfile.mktemp('.tmp')
    tmpPath, file = os.path.split(tmpfile)
else:
    # set the copy size from the file size
    size = os.stat(file).st_size        # over-riding size arg, if specified
# assert: have size, and tmp filename

# Compose the complete path for source and destination, based on the direction        
if write:
    # We're copying a local tmp file to a specified destination path
    srcdir  = localDir
    dstdir  = path
    srcBase = srcdir + file
    dstBase = dstdir + file
else:
    # We're copying a tmp file from a specified destination path to the current dir
    srcdir  = path
    dstdir  = localDir
    srcBase = path + file
    dstBase = localDir + file
# assert: have full path to src and dst files, and their directories

if srcdir.lower() == dstdir.lower():
    strOut = 'error: Source and destination directories are the same: %s' % src
    prnLogExit(strOut)
    
# Populate the src file
if not genFile:
    # copy the specified file to the source directory, using a tmp filename
    copyTmpCmd = 'xcopy "%s" "%s" /v' % (file, src)
    # print 'copyTmpCmd: ' + copyTmpCmd
    os.popen(copyTmpCmd)

    # Confirm src file's existence
    if not os.path.isfile(src):
        strOut =  "error: Generated source file, '%s' doesn't exist." % src
        prnLogExit(strOut)
    # we have a source file of the specified size

try:    # try block for catching ctrl-c, etc.
    # Display the relevant parameters of the operation
    if verbose:
        if write:
            print 'Write - copy from local to path'
        if read:
            print 'Read - copy from path to local'
        print 'path:    %s' % path
        print 'local:   %s' % localDir
        print 'size:    %s bytes' % size
        print 'maxCnt:  %d copies' % maxCnt
        print 'maxTime: %d seconds' % maxTime
        print 'file:    %s' % file
        if compare:
            print 'compare files'
        else:
            print 'no file compare'

    pgmStartTime = time.time()

    # establish the approximate copy time.  Use this to establish the number of files to copy
    # as a "group".  Individual file copy times are not measured -- only group times.
    # The goal here is to increase the clock accuracy by measuring a longer interval, since it 
    # seems that Python's time module isn't too accurate for short times.  Try to use a time
    # that spans at least one second.

    MAXGRP = 250                # max group size.  I've seen "too many open file handles" errors
    haveGrpTime = 0             # flag indicating we have a candidate group time
    desiredGrpTime = 1.0        # desired time to copy a group of files
    grpSize = 1                 # number of file copies in a group
    grpTime = 0.0               # expected time to copy a group
    nGrps = 0                   # number of groups to copy
    
    # note: if the grpSize is less than maxCnt, we must either abort, or run long.
    # note: if the grpTime exceeds maxTime, we must either abort, or run long.
    # assume for both of the above cases, we run long when we need to.

    if useCopyOnly or (size > cpThreshold):    
        grpSize = 1
        grpTime = CopyGrp(grpSize, size)
    else:
        if veryVerbose:
            strOut = "Determine correct group size to use"
            prnLog(strOut)

        # perform series of test copies, increasing grpSize until the desiredGrpTime is met    
        while (grpSize < MAXGRP) and (grpTime < desiredGrpTime):
            grpTime = CopyGrp(grpSize, size)
            
            # estimate the next grpSize to test from the CopyGrp results
            if grpTime < desiredGrpTime:
                # still too short
                if grpTime < (desiredGrpTime / 10):
                    # less than one-tenth the desired value -- crank it up
                    grpSize *= 10
                else:
                    # merely double it
                    grpSize *= 2
            
                if grpSize > MAXGRP:
                    grpSize = MAXGRP

    nGrps = (maxCnt + grpSize) / grpSize        # round up, so nGrps is at least 1
    # have grpTime, grpSize, nGrps
    
    if verbose:
        print 'Using grpSize = %d' % grpSize

    for grpCnt in range (0, nGrps):
        grpCpTime = CopyGrp(grpSize, size)
        # assert: CopyGrp() has copied grpSize files
        
        # Copy the file n times, writing a '.' for every 10 copies
        if veryVerbose:
            print '%3d grpCopy: grpCpTime: %.3f secs' % (grpCnt, grpCpTime)
        elif verbose:
            sys.stdout.write('.')
        
        elapsedtime += grpCpTime
        
        if useMaxTime:
            if (time.time() - pgmStartTime) > maxTime:
                strOut = "Time (%d secs) has expired." % maxTime
                prnLog(strOut)
                break
    # End loop
    # assert: grpCpTime counted at least one group of copies

    # number of copies is (grpCnt + 1) * grpSize
    cnt = (grpCnt + 1) * grpSize        # cnt is off by one, since it's 0-based.

    useSize = useKbSize = 0
    kbSize = mbSize = 0
    
    mbSize = (size + 1) / mb
    if mbSize == 0:
        useKbSize = 1
        kbSize = (size + 1) / kb        # e.g. 10000 + 1 /1000
        if kbSize == 0:
            useSize = 1
    
    if useSize:
        strSize = str(size) + " bytes"
    elif useKbSize:
        strSize = "%.1fKB" % float(kbSize)
    else:
        strSize = "%.1fMB" % float(mbSize)
    
    if verbose and not veryVerbose:
        print '\n'                  # newline after dots
    
    strOut = strElapsed = 'Copied %s %d times, from %s to %s. CopyTime: %.2f secs.' % (strSize, cnt, srcdir, dstdir, elapsedtime)
    prnLog(strOut)
    
    if elapsedtime > 0:
        bitsMb = 8 * cnt * float(size) / mb
        Mbps = bitsMb / elapsedtime
        MBps = Mbps / 8
        strThru = 'Throughput: %.2fMbits/sec (%.2fMBps)' % (Mbps, MBps)
    else:
        strThru = 'Time too short to measure'
    prnLog(strThru)                 # print and log results

except KeyboardInterrupt:
    strOut = "Program interrupted.  Preparing to exit"
    prnLog(strOut)

    # cleanup
    # delete dst files
    for i in range(0, grpSize):
        src = srcBase + '-%d' % cnt
        dst = dstBase + '-%d' % cnt

        if not retainDst:
            if os.path.isfile(dst):
                # dst file exists.  Delete it.
                try:
                    os.remove(dst)
                except:
                    strOut = "Error removing dst file: '%s'" % dst
                    prnLog(strOut, log.LOG_ERR)
    
                # Confirm removal of dst file
                if os.path.isfile(dst):
                    strOut = "error. dst file, '%s', exists following deletion." % dst
                    prnLog(strOut, log.LOG_ERR)
    
        if not retainSrc:
            if os.path.isfile(src):
                try:
                    os.remove(src)
                except:
                    # error removing the file
                    strOut = "%s: Error removing src file, \"%s\"" % (pgm, src)
                    prnLog(strOut, log.LOG_ERR)

                # Confirm removal of dst file
                if os.path.isfile(src):
                    strOut = "error. src file, '%s', exists following deletion." % src
                    prnLog(strOut, log.LOG_ERR)
    
    sys.exit(2)
