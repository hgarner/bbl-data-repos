import os
import sys
import shutil
#import config.config as config
import config as config
import yaml
import pwd
from datetime import datetime, timedelta
import subprocess
import re
from pprint import pprint
import configparser
import argparse

def addUser(username, access, users_file_path):
  tab = '    '
  if not os.path.exists(users_file_path):
    #create users file if not existing
    users_file = open(users_file_path, 'w')
    #set permissions
    os.chmod(users_file_path, 0o700)
    #add start of file
    users_file.write('---\n')
    users_file.close()

  users_file = open(users_file_path, 'r')

  #check username exists
  try:
    user_details = pwd.getpwnam(username)
  except KeyError as e:
    print('(addUser) username {} not found'.format(username))
    raise e

  try:
    users = yaml.load(users_file)
    users_file.close()
  except Exception as e:
    print('(addUser) error processing users file ({})'.format(str(e)))
    raise e

  #if nothing returned from yaml, set users to be empty dict
  if users is None:
    users = {}

  #if user_details already present, do nothing
  if user_details[0] not in users.items():
    #otherwise if user not present
    #add username
    now = datetime.now()
    users[user_details[0]] = {
      'pid': user_details[2],
      'datasets': [],
      'added_date': now.strftime('%Y-%m-%d'),
      'expiry_date': (now + timedelta(days=30)).strftime('%Y-%m-%d'),
    }

    #save file
    users_file = open(users_file_path, 'w')
    yaml.dump(users, users_file)

  return users

def setAccess(target_collection, users_file_path, access_level):

  #check users file and target collection exist
  if not os.path.exists(target_collection):
    print('(setAccess) target_collection does not appear to exist')
    raise ValueError('(setAccess) target_collection does not appear to exist')

  try:
    users_file = open(users_file_path, 'r')
    users = yaml.load(users_file)
    users_file.close()
  except Exception as e:
    print('(addUser) error processing users file ({})'.format(str(e)))
    raise e

  #go through users 
  for username, user_access in users.items():
    #check username exists
    try:
      user_details = pwd.getpwnam(username)
    except KeyError as e:
      print('(addUser) username {} not found'.format(username))
      raise e

    #check that expiry date not passed
    expiry_date = datetime.strptime(user_access['expiry_date'], '%Y-%m-%d')
    if expiry_date < datetime.now():
      #remove user from acl
      for subdir in config.access_levels[access_level]['dirs']:
        setfacl_result = subprocess.call('setfacl', '-R -x u:{} {}'.format(user_details[2], os.path.join(target_collection,subdir)))
        if setfacl_result != 0:
          e = '(setAccess) error, setfacl returned {} when trying to set the acl for user {} path {}'.format(setfacl_result, username, os.path.join(target_collection,subdir))
          print(e)
          raise SystemError(e)
    else:
      #add user to acl
      for subdir in config.access_levels[access_level]['dirs']:
        setfacl_result = subprocess.call('setfacl', '-R -m u:{}:{} {}'.format(user_details[2], config.access_levels[access_level]['permissions'], os.path.join(target_collection,subdir)))
        if setfacl_result != 0:
          e = '(setAccess) error, setfacl returned {} when trying to set the acl for user {} path {}'.format(setfacl_result, username, os.path.join(target_collection,subdir))
          print(e)
          raise SystemError(e)


def genPath(rel_path, root):
  if not os.path.exists(root):
    raise ValueError('(genPath) Root path does not exist')

  path_now = root

  for location in rel_path:
    if not os.path.exists(os.path.join(path_now,location)):
      os.mkdir(os.path.join(path_now,location))

def chmod_rec(permissions, current_path, target_path):
  for root, dirs, files in os.path.join(current_path,target_path):
    os.chmod(root, permissions)
    for d in dirs:
      chmod_rec(permissions, root, d)

def setCoreAccess(target_path):
  if not os.path.exists(target_path):
    raise ValueError('(setCoreAccess) target_path does not exist')

  for dev_path in config.dev_only_paths:
    try:
      for root, dirs, files in os.walk(target_path,dev_path):
        os.chmod(root, 0o700)
        for f in files:
          os.chmod(os.path.join(root,f), 0o700)
    except:
      print('(setCoreAccess) Unable to lock down path {}/{}'.format(target_path,dev_path))
      exit(0)

  for ro_path in config.read_only_paths:
    try:
      for root, dirs, files in os.walk(target_path,ro_path):
        os.chmod(root, 0o750)
        for f in files:
          os.chmod(os.path.join(root,f), 0o750)
    except:
      print('(setCoreAccess) Unable to set to read only path {}/{}'.format(target_path,ro_path))
      exit(0)

def copyTemplate(template_dir, target_path):
  if not os.path.exists(template_dir):
    raise ValueError('(copyTemplate) template_dir does not exist')
  if not os.path.exists(os.path.join(*target_path[:-1])):
    raise ValueError('(copyTemplate) core target_path does not exist (omitting final directory)')

  target_dir = target_path[-1]

  try:
    shutil.copytree(template_dir, target_dir)
  except:
    print('(copyTemplate) Error copying template directory')
    exit(0)

def processStructureFile(dir_structure_file):
  # process dir_structure_file
  # this uses placeholders for project/dataset names
  # e.g. 
  # {project}:
  #   data:
  #     {dataset}:
  #       - raw
  #       - dev
  #       - release
  if not os.path.exists(os.path.abspath(dir_structure_file)):
    raise ValueError('processStructureFile: dir_structure_file does not exist')
  
  with open(dir_structure_file, 'r') as dsf_open:
    try:
      dir_structure = yaml.load(dsf_open)
    except Exception as e:
      print('processStructureFile: dir_structure_file yaml processing failed')
      raise e

  return dir_structure

def copyFile(src_file_dir, target_location, src_filename, target_filename = ''):
  if not os.path.exists(src_file_dir):
    raise ValueError('(copyFile) src_file_dir does not exist')

  if not os.path.exists(target_location):
    raise ValueError('(copyFile) target_location does not exist')

  if os.path.exists(os.path.join(target_location, target_filename if target_filename != '' else src_filename)):
    raise ValueError('(copyFile) target file {target_file} already exists at {target_location}'.format(target_file = target_filename if target_filename != '' else src_filename, target_location = target_location))

  try:
    if os.path.exists(os.path.join(src_file_dir, src_filename)):
      copy = shutil.copy(os.path.join(src_file_dir, src_filename), os.path.join(target_location, target_filename))
      return copy
    else:
      raise ValueError('(copyFile) file does not exist in src_file_dir')
  except Exception as e:
    raise e

def genStructure(target_location, dir_structure, src_file_dir, **kwargs):

  if not os.path.exists(target_location):
    raise ValueError('(genStructure) target_location does not exist')

  try:
    current_path = os.path.split(target_location)

    # if it's a list, convert to a dict
    if isinstance(dir_structure, list):
      dir_structure = {index_val[1]: index_val[0] for index_val in enumerate(dir_structure)}
    
    # if it's a string, convert to a dict with the string as the key
    # and None as the value
    if isinstance(dir_structure, str):
      dir_structure = {dir_structure: None}

    for directory, contents in dir_structure.items():

      # first, see if the 'directory' key matches a file specifier
      # if so, get the file and copy into current_path
      file_match = re.search('\[([a-z0-9_A-Z\-\.]+)?\]([a-z0-9_A-Z\-\.]+)?', directory)
      if file_match is not None and src_file_dir is not None and src_file_dir != '':
        try:
          if len(file_match.groups()) > 0:
            copyFile(src_file_dir, target_location, file_match.group(1), file_match.group(2) if len(file_match.groups()) > 1 else '')
        except Exception as e:
          print('Error copying file {src_file} into {target}: {err}'.format(src_file=file_match.group(1), target=target_location,err=str(e)))
          pass
      else:
        # now see if one of the kwargs matches a placeholder
        # if so, replace
        placeholder_match = re.search('\{([a-z0-9_A-Z\-]+)?\}', directory)
        try:
          if placeholder_match is not None and len(placeholder_match.groups()) > 0:
            #directory.format_map(kwargs)
            for kw, val in kwargs.items():
              if kw == placeholder_match.groups(1)[0]:
                directory = directory.format(**{kw: val})
                break
            else:
              # if no match, remove the {} to use the default placeholder name
              directory = placeholder_match.groups(1)[0]
        except IndexError:
          pass

        new_path = current_path + (directory,)

        # now create dir if not existing
        if not os.path.exists(os.path.join(*new_path)):
          os.mkdir(os.path.join(*new_path))

        if isinstance(contents, list) or isinstance(contents, dict) or (isinstance(contents, str) and contents != ''):
          genStructure(os.path.join(*new_path), contents, src_file_dir, **kwargs)

  except Exception as e:
    raise e

def loadConfig(config_filename = './config/config.ini', config = None):
  if config is None:
    config = configparser.ConfigParser()
  config.read(os.path.abspath(config_filename))
  return config

if __name__=="__main__":
  # load config
  # get args
  # as minimum, project name is required
  # get yaml structure file and process
  
  global config 

  parser = argparse.ArgumentParser(description='Generate directory structure and user stuff for projects and datasets')
  parser.add_argument('--structure_file', dest='structure_file', action='store', help='yaml file describing structure to create')
  parser.add_argument('--target_dir', dest='target_dir', action='store', help='location to put new directory tree')
  parser.add_argument('--src_file_dir', dest='src_file_dir', action='store', help='location to get files required (if needed)')
  parser.add_argument('--config', dest='config_filename', action='store', help='optional config .ini file')
  parser.add_argument('--dirnames', dest='dirnames', nargs='*', action='store', help='Dirnames to match placeholders in the structure file. These should be of the form placeholder:value, e.g. project:bigproject dataset:bigdata')
  global args
  args = parser.parse_args()
  try:
    config = loadConfig(args.config_filename, config)
  except:
    pass

  if args.structure_file is not None:
    structure_file = args.structure_file
  else:
    print('Please specify a yaml structure file to use')
    exit(1)

  target_dir = os.getcwd()
  if args.target_dir is not None:
    if os.path.exists(os.path.abspath(args.target_dir)):
      target_dir = os.path.abspath(args.target_dir)
    else:
      print('target_dir does not appear to exist')
      exit(1)

  src_file_dir = ''
  if args.src_file_dir is not None:
    if os.path.exists(os.path.abspath(args.src_file_dir)):
      src_file_dir = os.path.abspath(args.src_file_dir)
    else:
      print('src_file_dir does not appear to exist')
      exit(1)

  # process structure_file
  try:
    structure = processStructureFile(structure_file)
  except:
    print('Unable to process structure file')
    exit(1)

  # process dirnames (placeholders and values for template)
  # would be better really to check template and require
  # all placeholders to be present here
  replacement_names = {}
  if args.dirnames is not None:
    for dir_val in args.dirnames:
      placeholder = dir_val.split(':')
      replacement_names[placeholder[0]] = placeholder[1]

  # call genStructure to create dirs
  # pass replacement_names as placeholders
  try:
    genStructure(target_dir, structure, src_file_dir, **replacement_names)
    print(
      'Success: structure generated in {target_dir}'
      .format(
        target_dir=target_dir
      )
    )
    exit(0)
  except Exception as e:
    print('Error: genStructure failed')
    pprint(e)
    exit(1)







        



  
