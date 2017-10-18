# bbl-data-repos
Data repo creation for BBL

Creates simple directory structure from a yaml input file (see example_structure.yaml).
e.g.

```
"{project}":
  data:
    raw:
      "raw_{dataset}"
    dev:
      "{dataset}":
        "[readme.txt]readme.txt"
    release:
  users:

```

Each key/element is created as a directory. Placeholders, denoted using {}, allow keyword subsitutions passed from command line.

Files can also be added by enclosing the filename in []. The rest of the text in the key (if provided) allows for the file to be renamed.

**Usage**
Call from terminal:

```
python3 genStructure.py --target_dir=./ --structure_file=./example_structure.yaml --src_file_dir=./files --dirnames project:verybigproject dataset:verybigdata
```

**Args**
***Required***

  - target_dir: the target location to place the generated dir structure
  - structure_file: yaml file specifying structure to create
  
***Optional***

  - src_file_dir: location of dir containing any files to be copied into new structure
  - dirnames: placeholder:replacement_text, separated by spaces
