#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Simple python file backup
License: MIT
"""

__author__     = 'Vesa Ruohonen'
__copyright__  = 'Copyright 2018, Simple python file backup'
__credits__    = ['Vesa Ruohonen']
__license__    = 'MIT'
__version__    = '0.1'
__maintainer__ = 'Vesa Ruohonen'
__email__      = 'vesa.m.ruohonen@gmail.com'
__status__     = 'dev'

#
# Imports
#

import sys, getopt, os, datetime, glob, shutil, subprocess, json
import ConfigParser

from subprocess import call

#
# Variables
#

ROOT_PATH = '/'
BACKUP_SUFFIX = '-backup'

#
# Rsync command
#

"""
Rsync switch note

-a : all files, with permissions, etc..
-v : verbose, mention files
-x : stay on one file system
-h : output numbers in a human-readable format
-H : preserve hard links (not included with -a)
-A : preserve ACLs/permissions (not included with -a)
-X : preserve extended attributes (not included with -a)
-W : copy files whole (w/o delta-xfer algorithm)

Outside recommendation:
	rsync -avxHAXW --numeric-ids --info=progress2
"""

RSYNC_COMMAND = [
	'sudo', # Always run as root
	'rsync',
	'-avxhAX',
	'--numeric-ids',
	'--exclude=lost+found',
	'--delete',
	'--progress'
]
RSYNC_LINKDEST = '--link-dest={0}' # Link destination template
#RSYNC_SOURCE = '.'

#
# Find mount command
#

FIND_MOUNT_COMMAND = ['findmnt', '-rn', '-o', 'TARGET', '-S']
FIND_MOUNT_UUID_TEMPLATE = 'UUID={0}'

#
# Classes
#

class ConfigNotice(Exception):
	"""
	Non fatal notice exception for reading configuration files.
	"""
	pass


class ConfigError(Exception):
	"""
	Error exception for configuration file parsing.
	"""
	pass

#
# Methods
#

def list_backup_directories(path):
	"""
	List backup directories in chronologic order based on the file name.
	"""
	if os.path.isdir(path):
		glob_files = glob.glob(os.path.join(path, '*' + BACKUP_SUFFIX))
		files = filter(os.path.isdir, glob_files)

		# For unknown reason directories won't get proper modification time
		#files.sort(key=lambda x: os.path.getmtime(x))

		# For now use plain alphabetical soring as filenames do the job just fine
		files.sort(key=lambda x: x)

		return [os.path.abspath(f) for f in files]

	else:
		raise IOError('Invalid path {0}'.format(path))


def read_config(cfg_file):
	"""
	Read configuration file for one or more backup operations.
	"""
	operations = []
	notices = set()

	#
	# Prepare configuration reader
	#

	config = ConfigParser.ConfigParser(defaults = {
		'target': None,
		'source': None,
		'count': None,
		'exclude': None,
	})

	#
	# Deserialize configuration from file
	#

	config.read(cfg_file)
	sections = config.sections()

	#
	# Parse backup operations from configuration sections
	#

	for section in sections:
		task = {}
		try:
			# 1. Find device
			backup_device_path = find_mount_by_uuid(config.get(section, 'uuid'))

			# 2. Find source
			task['source_path'] = os.path.expanduser(config.get(section, 'source'))
			if not os.path.exists(task['source_path']):
				raise ConfigError('Error: missing source path "{0}"'.format(task['source_path']))

			# 3. Find target
			task['target_path'] = os.path.expanduser(
				os.path.join(
					backup_device_path, config.get(section, 'target')
				)
			)
			if not os.path.exists(task['target_path']):
				raise ConfigError('Error: missing target path "{0}"'.format(task['target_path']))

			# 4. Set excludes
			exclude = config.get(section, 'exclude')
			if exclude:
				try:
					# Try extracting excludes
					exclude = json.loads(exclude)

					# If exclude was list
					if isinstance(exclude, list):
						task['exclude'] = exclude

					# If exclude was string
					elif isinstance(exclude, str) or isinstance(exclude, unicode):
						task['exclude'] = [exclude]

					else:
						notices.add('[{0}] Exclude: Couldn\'t read excludes'.format(section))

				except Exception as e:
					notices.add('[{0}] Exclude: {1}'.format(section, e))

			# 5. Get backup target directory rotation count
			task['backup_count'] = int(config.get(section, 'count'))

			# 6. Append operation to task list
			operations.append(task)

		#
		# Exception handling for a single task
		#

		# 1. Non-fatal exceptions
		except ConfigParser.NoOptionError as e:
			notices.add('{0}'.format(e))

		except ConfigNotice as e:
			notices.add('{0}'.format(e))

		# 2. Fatal exceptions
		except ConfigError as e:
			print('{0}'.format(e))
			exit(1)

	#
	# Print all notices
	#

	for notice in notices:
		print(notice)

	#
	# Return backup operation list
	#

	return operations


def run_config(cfg_file):
	"""
	Run backup tasks from configuration file.
	"""
	if not cfg_file or not isinstance(cfg_file, str):
		raise ValueError('Invalid configuration file "{0}"'.format(cfg_file))

	for backup_task in read_config(cfg_file):
		take_rotation_backup(**backup_task)


def find_mount_by_uuid(UUID):
	"""
	All partitions have UUID which can be used to indentify mounted disks and
	this method tries to find a partition by given UUID.
	"""
	path = None

	if isinstance(UUID, str): # Find UUID in linux
		find_mount_command = FIND_MOUNT_COMMAND[:] # Copy template
		find_mount_command.append(FIND_MOUNT_UUID_TEMPLATE.format(UUID))

		process = subprocess.Popen(find_mount_command, stdout=subprocess.PIPE) # Run command
		path = process.stdout.readline().strip('\r\n') # Remove end of line characters
		process.stdout.close()

	if not path: # No need to halt execution just skip the job if not found
		raise ConfigNotice('UUID "{0}" not found'.format(UUID))

	# Return absolute path to UUID media
	return path


def get_timestamp(stamp_format = '%Y%m%d_%H%M'):
	"""
	Generate timestamp for the backup path. By default use format:
		{YEAR}{MONTH}{DAY}_{HOUR}{MINUTE}

	This ensures that backups can be taken as often as once per minute without
	overwriting existing backups.
	"""
	return datetime.datetime.now().strftime(stamp_format + BACKUP_SUFFIX)


def take_rotation_backup(source_path,
						 target_path,
						 backup_count = 3,
						 exclude	  = None):
	"""
	Backup routine which takes the backup from source to target using count for
	tracking rolling paths.
	"""

	#
	# Checks input values
	#

	# Check if the paths exist
	if not os.path.isdir(source_path):
		raise IOError('Backup source path "{0}" doesn\'t exist'.format(source_path))

	if not os.path.isdir(target_path):
		raise IOError('Backup target path "{0}" doesn\'t exist'.format(target_path))

	if backup_count < 1:
		raise ValueError('Invalid backup count "{0}"'.format(backup_count))

	# Convert paths to absolute
	source_path = os.path.abspath(os.path.expanduser(source_path))
	target_path = os.path.abspath(os.path.expanduser(target_path))

	# Check if the backup path is not inside target path
	if source_path != ROOT_PATH and (target_path.startswith(source_path)):
		raise IOError('Backup directory is inside target directory!')

	#
	# Take rotation backup
	#

	snapshots = list_backup_directories(target_path)
	next_backup_dir = os.path.join(target_path, get_timestamp())

	# Check that target path is empty
	if os.path.isdir(next_backup_dir):
		raise IOError('Next backup destination directory already exists: "{0}"'.format(next_backup_dir))

	# Create rsync command
	run_rsync_command = RSYNC_COMMAND[:]

	if len(snapshots):
		# Use last backup as hard link reference if available
		run_rsync_command.append(RSYNC_LINKDEST.format(snapshots[-1]))

	# Specify additional excludes
	if isinstance(exclude, list):
		for exclude_path in exclude:
			run_rsync_command.append('--exclude={0}'.format(exclude_path))

	# Specify targets for rsync command
	run_rsync_command.append(source_path + os.path.sep if source_path != ROOT_PATH else source_path)
	run_rsync_command.append(next_backup_dir)

	# Print command
	print(run_rsync_command)

	# Run rsync command
	call(run_rsync_command)

	# Clean extra directories
	clean_backup_path(target_path, backup_count)


def clean_backup_path(target_path, backup_count):
	"""
	Check current backup path count clean oldest paths if the count exceeds
	backup count limit.
	"""
	if not os.path.isdir(target_path):
		raise IOError('Backup target path "{0}" doesn\'t exist'.format(source_path))

	if backup_count < 1:
		raise ValueError('Invalid backup count "{0}"'.format(backup_count))

	# Clean extra backup rotations
	current_snapshots = list_backup_directories(target_path)
	while len(current_snapshots) > backup_count:
		old_snapshot = current_snapshots.pop(0)
		if os.path.isdir(old_snapshot):
			print('Removing "{0}"'.format(old_snapshot))
			shutil.rmtree(old_snapshot)
		else:
			raise IOError('Removing "{0}" failed'.format(old_snapshot))

	print('Done cleaning')

#
# Python main
#

if __name__ == "__main__":
	"""
	Simple python file backup.

	Usage:
		sudo python backup_files.py
		sudo python backup_files.py <backup_cfg_file>
	"""
	if len(sys.argv) > 1 and sys.argv[1]:
		backup_cfg = sys.argv[1]
	else:
		print('Using default configuration "backup.ini"')
		backup_cfg = 'backup.ini'

	# Check configuration file
	if not os.path.exists(backup_cfg):
		print('Missing configuration file "{0}"'.format(backup_cfg))
		sys.exit(1)

	# Read and run configuration file backups only
	run_config(backup_cfg)
