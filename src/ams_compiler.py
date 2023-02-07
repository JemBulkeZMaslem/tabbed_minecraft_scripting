import warnings

def main():
    import json
    import argparse

    parser = argparse.ArgumentParser(
        prog = 'ams',
        description = 'Compiles ams into mcfunction.')

    parser.add_argument('-v', '--verbose', action='store_true', help='Show more information.')
    parser.add_argument('-d', '--debug', action='store_true', help='Show debug information.')
    parser.add_argument('-c', dest='config', help='Provide a config file.')
    parser.add_argument('-i', type=str, nargs='+', default=[], metavar='FILE', help='Provide input file.')
    parser.add_argument('-o', type=str, nargs='+', default=[], metavar='FILE', help='Provide an output file.')
    parser.add_argument('-dirs', type=str, nargs='+', default=[], metavar=('INPUT_DIR', 'OUTPUT_DIR'), help='Provide pairs of input and output directories.')
    parser.add_argument('-e', '--extension', type=str, help='Provide extension filter for input directory/directories.')
    parser.add_argument('-p', '--createproject', dest='project', type=str, help='Creates project file.')
    parser.add_argument('-a', '--define', dest='alias', type=str, nargs=3, metavar=('KEY', 'VALUE', 'PROJECT'), help='Defines an alias in an existing project.')

    args = parser.parse_args()

    # check arguments
    if args.i and args.o and len(args.i) != len(args.o):
        print("ERROR: Number of input files must match output files.")
        exit(1)
    if args.dirs and len(args.dirs) % 2 == 1:
        print("ERROR: Provided parameters to -dir option aren't pairs.")
        exit(1)

    config = {
        'ifiles': args.i,
        'ofiles': args.o,
        'dirs': args.dirs,
        'define': {}
    }

    if args.project:
        new_project = {}
        # add directories to project if any
        if args.dirs:
            new_project['dirs'] = args.dirs
        # add files to project if any
        if args.i and args.o:
            new_project['ifiles'] = args.i
            new_project['ofiles'] = args.o
        # write to file
        with open(args.project, 'w', encoding='utf-8') as f:
            json.dump(new_project, f, indent=4)
        exit()
    
    if args.config:
        try:
            with open(args.config, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                # verify given config
                if "ifiles" in loaded_config:
                    if "ofiles" in loaded_config:
                        if len(loaded_config["ifiles"]) != len(loaded_config["ofiles"]):
                            print("ERROR: Number of input files must match output files.")
                            exit(1)    
                    else:
                        print("ERROR: Config file must provide both ifiles and ofiles.")
                        exit(1)
                elif "ofiles" in loaded_config:
                    print("ERROR: Config file must provide both ifiles and ofiles.")
                    exit(1)
                if "dirs" in loaded_config and len(loaded_config['dirs']) % 2 == 1:
                    print("ERROR: Dirs in config file must be pairs of directories.")
                    exit(1)
                config = loaded_config
                config.setdefault('ifiles', [])
                config.setdefault('ofiles', [])
                config.setdefault('dirs', [])
        except FileNotFoundError:
            print("ERROR: Provided config file could not be found.")
            exit(1)
    if args.alias:
        from os.path import isfile
            
        key, value, path = args.alias
        if not isfile(path):
            print(f"\"{path}\" is not a file.")
            exit(1)

        try:
            with open(path, "r") as f:
                content_dict = json.load(f)
        except:
            print(f"Failed to read json at \"{path}\"\nPlease create a valid file first. (See -h)")
            return

        # Create definition if it does not exist
        if not "define" in content_dict:
            content_dict["define"] = dict()

        if key in content_dict["define"]:
            print(f"{key} already exists: {content_dict['define'][key]}.")

            while True:
                answer = input("Would you like to overwrite? (Y/N): ")

                if answer == "N" or answer == "n":
                    print("Aborting.")
                    return
                elif answer == "Y" or answer == "y":
                    break
                else:
                    print("Invalid answer.\n")

            content_dict["define"][key] = value

        else:
            content_dict["define"][key] = value

        with open(path, "w") as f:
            json.dump(content_dict, f, indent=2)
    

    def compile_file(in_file, out_file, verbose):
        if verbose:
            print(f"Compiling {in_file}...")

        with open(in_file, "r", encoding="utf-8") as inf:
            in_text = inf.read()

        if "define" in config:
            for alias in config["define"]:
                in_text = in_text.replace(alias, config["define"][alias])

        in_text = in_text.split("\n")

        tree_list = build_tree(in_text, debug=args.debug)

        out_text = compile_tree_list(tree_list)

        with open(out_file, "w", encoding="utf-8") as out:
            out.write(out_text)
        if verbose:
            print("DONE!\n")

    # Read and compile each file in config.
    if args.debug:
        print("Config:\n")
        print(json.dumps(config, indent = 2))

    for i in range(len(config["ifiles"])):
        in_file = config["ifiles"][i]
        out_file = config["ofiles"][i]
        compile_file(in_file, out_file, args.verbose)
    
    # Collect files from directories in config.
    import os
    for i in range(0, len(config['dirs']), 2):
        input_dir = config['dirs'][i]
        output_dir = config['dirs'][i+1]
        input_files = []
        # list all input files
        for root, dirs, files in os.walk(input_dir, topdown=False):
            for name in files:
                input_files.append(os.path.join(root, name))
            for name in dirs:
                path = os.path.join(output_dir, name)
                # create dir if it doesn't exists in output dir
                if not os.path.exists(path):
                    os.makedirs(path)
                    if args.debug:
                        print(f"Created directory {path} in output dir.")
        # filter files with right extension
        if not args.extension is None:
            input_files = list(filter(lambda name: name.endswith(args.extension), input_files))
        
        # generate output file list
        output_files = [ os.path.join(output_dir, os.path.relpath(path, input_dir)) for path in input_files ]
        if args.debug:
            print("input", input_files)
            print("output", output_files)
        # Read and compile all of them.
        for i in range(len(input_files)):
            compile_file(input_files[i], output_files[i], args.verbose)


def build_tree(file, debug = False):
    """
    Takes in a list of strings and builds a command tree from it.
    Each child gets defined with one indent (Tab) more than it's parent. Example:

    execute if condition1
        if condition2
            run command 1
            run command 2
        if condition3
            run command 1
            run command 2
    """

    line = 0
    tree_list = []

    while line < len(file):
        # Get current command
        command = file[line]

        # SKip empty and comments
        if len(command.strip()) == 0:
            line += 1
            continue

        next_tree, line = __build_element__(file, line, debug = debug)

        tree_list.append(next_tree)

    return tree_list


def __build_element__(file, line, debug = False):
    """
    Look at given line of file. If it's a comment create marker, if empty skip it and if neither create node.

    Then look at all following lines. If the indent is greater than the current on, execute __build_element__ on the next line and add the returned element as a child. The returned line is the next line to be checked.

    If the indent is equal or smaller return
    """
    # Get current command
    command = file[line]

    #If empty return
    if len(command.strip()) == 0:
        return None, line

    # Count indents and cast to node
    #indent = command.count(indent_marker)
    indent = __count_indents__(command)

    if command.strip().startswith("#"):
        current_element = marker(command.strip())
    else:
        current_element = node(command.strip())

    next_line = line+1

    #As long as you have not reached end of file
    while next_line != len(file):
        if debug:
            print("Line: ", next_line, "\t", file[next_line])

        # Add all children
        next_command = file[next_line]

        if len(next_command.strip()) == 0:
            next_line += 1
            continue

        next_indent = __count_indents__(next_command)

        if next_indent > indent:
            next_child, next_line = __build_element__(file, next_line, debug)
            current_element.add_child(next_child)
        else:
            break



    return current_element, next_line


def compile_tree_list(tree_list):
    """
    Compiles node.compile for each element in the list and
    compiles the string to be pasted into the file.
    """
    compiled_list = []
    for tree in tree_list:
        compiled_list += tree.compile()

    compiled_string = ""
    for element in compiled_list:
        compiled_string += element+"\n"

    return compiled_string


def __count_indents__(string):
    # Accept either "\t" or " " as indent.

    indent_chars = ["\t", " "]

    indents = 0
    for char in string:
        if char in indent_chars:
            indents += 1
        else:
            break

    return indents

class marker:
    def __init__(self, string):
        self.string = string

    def add_child(self, child):
        warnings.warn(f"Cannot add child to comment.")

    def to_str(self, n=1):
        return self.string

    def compile(self, parent = ""):
        """
        Returns marker as while stacktrace.
        parent
            marker

        compiles to:
        [
            \"marker\"
        ]
        """
        return [self.string]

class node:
    """
    Tree Node for command tree.
    """

    def __init__(self, string):
        self.string = string
        self.children = []

    def add_child(self, child):
        """
        Accepts either Strings or cmd_node objects. Adds child to children list
        """

        if type(child) == str:
            child = node(child)

        self.children.append(child)

    def to_str(self, n=1):
        """
        Bakes String of self and all children
        """
        #print(n)
        ret_str = self.string
        for child in self.children:
            ret_str += "\n"+"\t"*n+child.to_str(n+1)

        return ret_str

    def compile(self, parent = ""):
        """
        Compiles tree into list. Example:
        execute if condition
            run command1
            run command2

        gets compiled to:
        [
            execute if condition run command1,
            execute if condition run command2
        ]
        """
        next_str = parent + self.string + " "
        next_list = []


        if len(self.children) > 0:
            for child in self.children:
                next_list += child.compile(next_str)

            return next_list
        else:
            return [next_str]


if __name__ == '__main__':
    main()