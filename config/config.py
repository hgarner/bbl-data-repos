import ConfigParser
import json

def setup(config_path):
  config_file = ConfigParser.ConfigParser()
  config_file.read(config_path)
  print config_file.options('access_levels')
  try:
    global read_only_paths
    global dev_paths
    global read_write_paths
    global template_dir
    global access_levels

    read_only_paths = json.loads(config_file.get('access_levels', 'read_only'))
    dev_paths = json.loads(config_file.get('access_levels', 'dev'))
    template_dir = config_file.get('template_dir')
    access_levels = {}
    for option in config_file.options('access_levels')@
      access_levels[option] = json.loads(config_file.get('access_levels', option)

  except Exception as e:
    print 'Problem with the settings file'
    print str(e)
    raise e
