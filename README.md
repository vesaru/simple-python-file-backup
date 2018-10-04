## Synopsis

I decided to write simple Python based backup program which uses **rsync** under the hood. The main idea was to do simple helper utility for hard linking based versioned backups to removable devices with "plug-in target device and run" usability. So far this program doesn't have any GUI and the settings are stored in a separate file.

## Motivation

I'm used doing manual backups of all the important data and I want the result to be transparently accessible afterwards. I don't like the idea of using complex software which store backups in their own dump formats.

The transparent way osX / macOS time machine does backups inspired me to experiment with backups.

## Installation

### Prerequisites

Ensure that you have following commands available on your system.

- rsync
- findmnt

Look your partition **UUIDs** for the backup paths.

### Setup

Download the backup_files.py and put **backup.ini** configuration file to the same directory. You can provide the configuration path also from commandline as first agument but otherwise the program looks **backup.ini** by default from the current path.

### Sample configuration

~~~~
# Configuration file use python config parser format.
# Backups are divided to sections which can be named freely.

[Backup1 johndoe]
uuid    = 00000000-1111-2222-3333-aaffbb000000
source  = /home/johndoe
target	= users/johndoe
# Note: The target is from the root of partition hence use the relative path!
# For example here the absolute path could for be something like:
#   /media/johndoe/kingston1/users/johndoe
count 	= 4

[Backup2 os]
uuid    = 20f00267-13f1-a210-3533-a2f6b7302670
source  = /
target  = os/distro
exclude = [ "home/*", "opt/*" ]
# There can be one or multiple excludes. synax uses JSON notation for the lists.
count   = 10
~~~~

### Run

After creating configuration file run the **backup_files.py** and it runs all the backup tasks for the partitions it finds.

You can have multiple devices defined at the same time and plug any of them and the program will determine which are connected and only run those tasks.

### Notes

If you reformat your devices remember to update the **UUID** to configuration.

Also now this program doesn't try to estimate how much data will be transferred and if there's enough space on the target device to do the backup and the execution will halt if the **rsync** runs out of space. In such case the removing the partial backup path is adviced and freeing space from the device if possible before retrying.

## License

[MIT](https://opensource.org/licenses/MIT)

Copyright 2018 Vesa Ruohonen

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
