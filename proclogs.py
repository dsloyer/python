#!/usr/bin/python

file=open("test.log", "r")
str="status="       # assume error code immed follows first occurrence of this string in a line of text
offset = len(str)   # to skip past the marker string, to start of error code
errLen = 3          # assume 3-character error code

lErr = []           # list of errors seen
lCnt = []           # count of errors seen

for line in file:
    col = line.find(str)
    if col == -1:
        # Current line in log does not contain an error code
        continue

    col += offset           # skip to start of error code
    err = line[col:col+errLen]

    # See if this is a new, or recurring, error
    found = 0
    for i in range(0, len(lErr)):
        if err == lErr[i]:
            # recurrence of existing error. Bump counter for this error
            found = 1
            lCnt[i] += 1
    if not found:
        # 1st occurrence of this error. add err number to lErr, add new counter set to 1
        lErr.append(err)
        lCnt.append(1)

# dump results
for i in range(0, len(lErr)):
    print "%s occurred %d times" % (lErr[i], lCnt[i])
