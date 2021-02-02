"""
Utility functions which are used in the CENSO modules. From creating folders to
printout routines.
"""
import os
import sys
import shutil
import math
import hashlib
import time
import subprocess
from copy import deepcopy
from builtins import print as print_orig
from .cfg import ENVIRON, CODING, AU2J, AU2KCAL, BOHR2ANG, KB


def print(*args, **kwargs):
    """
    patch print to always flush
    """
    sep = " "
    end = "\n"
    file = None
    flush = True
    for key, value in kwargs.items():
        if key == "sep":
            sep = value
        elif key == "end":
            end = value
        elif key == "file":
            file = value
        elif key == "flush":
            key = value
    print_orig(*args, sep=sep, end=end, file=file, flush=flush)


def frange(start, end, step=1):
    """
    range with floats
    """
    try:
        start = float(start)
        end = float(end)
        step = float(step)
    except (ValueError, TypeError):
        raise
    if start > end:
        tmp = start
        start = end
        end = tmp
    count = 0
    while True:
        temp = float(start + count * step)
        if temp >= end:
            break
        yield temp
        count += 1


def mkdir_p(path):
    """
    create mkdir -p like behaviour
    """
    try:
        os.makedirs(path)
    except OSError as e:
        if not os.path.isdir(path):
            raise e


def print_block(strlist, width=80):
    """Print all elements of strlist in block mode
    e.g. within 80 characters then newline
    - width [int] width of block
    """
    length = 0
    try:
        maxlen = max([len(str(x)) for x in strlist])
    except (ValueError, TypeError):
        maxlen = 12
    for item in strlist:
        length += maxlen + 2
        if length <= width:
            if not item == strlist[-1]:  # works only if item only once in list!
                print("{:>{digits}}, ".format(str(item), digits=maxlen), end="")
            else:
                print("{:>{digits}}".format(str(item), digits=maxlen), end="")
        else:
            print("{:>{digits}}".format(str(item), digits=maxlen))
            length = 0
    if length != 0:
        print("\n")


def t2x(path, writexyz=False, outfile="original.xyz"):
    """convert TURBOMOLE coord file to xyz data and/or write *.xyz ouput

     - path [abs. path] does not need to include the filename coord
     - writexyz [bool] default=False, directly write to outfile
     - outfile [filename] default = 'original.xyz' filename of xyz file which
                        is written into the same directory as
     returns:
     - coordxyz --> list of strings including atom x y z information
     - number of atoms
    """
    if not os.path.basename(path) == "coord":
        path = os.path.join(path, "coord")
    with open(path, "r", encoding=CODING, newline=None) as f:
        coord = f.readlines()
    x = []
    y = []
    z = []
    atom = []
    for line in coord[1:]:
        if "$" in line:  # stop at $end ...
            break
        x.append(float(line.split()[0]) * BOHR2ANG)
        y.append(float(line.split()[1]) * BOHR2ANG)
        z.append(float(line.split()[2]) * BOHR2ANG)
        atom.append(str(line.split()[3].lower()))
    # natoms = int(len(coord[1:-1])) # unused
    coordxyz = []
    for i in range(len(x)):
        coordxyz.append(
            "{:3} {: .10f}  {: .10f}  {: .10f}".format(
                atom[i][0].upper() + atom[i][1:], x[i], y[i], z[i]
            )
        )
    if writexyz:
        with open(
            os.path.join(os.path.split(path)[0], outfile),
            "w",
            encoding=CODING,
            newline=None,
        ) as out:
            out.write(str(len(coordxyz)) + "\n\n")
            for line in coordxyz:
                out.write(line + "\n")
    return coordxyz, int(len(coordxyz))


def x2t(path, infile="inp.xyz"):
    """convert file inp.xyz to TURBOMOLE coord file"""
    if ".xyz" not in os.path.basename(path):
        path = os.path.join(path, infile)
    with open(path, "r", encoding=CODING, newline=None) as f:
        xyz = f.readlines()
        atom = []
        x = []
        y = []
        z = []
        for line in xyz[2:]:
            atom.append(str(line.split()[0].lower()))
            x.append(float(line.split()[1]) / BOHR2ANG)
            y.append(float(line.split()[2]) / BOHR2ANG)
            z.append(float(line.split()[3]) / BOHR2ANG)
        coordxyz = []
        for i in range(len(x)):
            coordxyz.append(f"{x[i]: .14f} {y[i]: .14f}  {z[i]: .14f}  {atom[i]}")
        with open(
            os.path.join(os.path.split(path)[0], "coord"), "w", newline=None
        ) as coord:
            coord.write("$coord\n")
            for line in coordxyz:
                coord.write(line + "\n")
            coord.write("$end\n")


def write_trj(
    results, cwd, outpath, optfolder, nat, attribute, overwrite=False, *args, **kwargs
):
    """
    Write trajectory (multiple xyz geometries) to file.
    """
    if overwrite and os.path.isfile(outpath):
        os.remove(outpath)
    for key, value in kwargs.items():
        if key == "rrho":
            rrho = value
        elif key == "energy":
            energy = value
    try:
        rrho
    except NameError:
        rrho = None
    try:
        energy
    except NameError:
        energy = None
    try:
        with open(outpath, "a", encoding=CODING, newline=None) as out:
            for conf in results:
                conf_xyz, nat = t2x(os.path.join(cwd, "CONF" + str(conf.id), optfolder))
                ### coordinates in xyz
                out.write("  {}\n".format(nat))
                xtbfree = conf.calc_free_energy(
                    e=energy, solv=None, rrho=rrho, out=True
                )
                if xtbfree is not None:
                    xtbfree = f"{xtbfree:20.8f}"
                out.write(
                    f"G(CENSO)= {getattr(conf, attribute):20.8f}"
                    f"  G(xTB)= {xtbfree}"
                    f"        !CONF{str(conf.id)}\n"
                )
                for line in conf_xyz:
                    out.write(line + "\n")
    except (FileExistsError, ValueError):
        print("Could not write trajectory: {}.".format(last_folders(outpath, 1)))


def check_for_float(line):
    """ Go through line and check for float, return first float"""
    elements = line.strip().split()
    value = None
    for element in elements:
        try:
            value = float(element)
            found = True
        except ValueError:
            found = False
            value = None
        if found:
            break
    return value


def last_folders(path, number=1):
    """
    Return string of last folder or last two folders of path, depending on number
    """
    if number not in (1, 2, 3):
        number = 1
    if number == 1:
        folder = os.path.basename(path)
    if number == 2:
        folder = os.path.join(
            os.path.basename(os.path.dirname(path)), os.path.basename(path)
        )
    if number == 3:
        basename = os.path.basename(path)
        dirname = os.path.basename(os.path.dirname(path))
        predirname = os.path.basename(os.path.split(os.path.split(path)[0])[0])
        folder = os.path.join(predirname, dirname, basename)
    return folder


def get_energy_from_ensemble(path, config, conformers):
    """
    Get energies from the ensemble inputfile and assign xtb_energy and
    rel_xtb_energy
    """
    with open(path, "r", encoding=CODING, newline=None) as inp:
        data = inp.readlines()
    if config.maxconf * (config.nat + 2) > len(data):
        print(
            f"ERROR: Either the number of conformers ({config.nconf}) "
            f"or the number of atoms ({config.nat}) is wrong!"
        )
    # calc energy and rel energy:
    e = {}
    conformers.sort(key=lambda x: int(x.id))
    for conf in conformers:
        e[conf.id] = check_for_float(data[(conf.id - 1) * (config.nat + 2) + 1])
    try:
        lowest = float(min([i for i in e.values() if i is not None]))
    except (ValueError, TypeError):
        print("WARNING: Can't calculate rel_xtb_energy!")
        return
    for conf in conformers:
        try:
            conf.xtb_energy = e[conf.id]
            conf.rel_xtb_energy = (e[conf.id] - lowest) * AU2KCAL
            # print(f"CONF{conf.id} {conf.xtb_energy} {conf.rel_xtb_energy}")
        except (ValueError, TypeError) as e:
            print(e)
    return conformers


def ensemble2coord(config, foldername, conflist, store_confs, save_errors):
    """
    read ensemble file: e.g. 'crest_conformers.xyz' and write coord files into
    designated folders

    - path [abs path] to ensemble file
    - nat  [int] number of atoms in molecule
    - nconf [int] number of considered conformers
    - cwd [path] path to current working directory
    - foldername [str] name of folder into which the coord file is to be written
    - conflist [list with conf object] all conf objects

    returns list with conformer objects
    """
    if not os.path.isfile(config.ensemblepath):
        print(f"ERROR: File {os.path.basename(config.ensemblepath)} does not exist!")
    with open(config.ensemblepath, "r", encoding=CODING, newline=None) as inp:
        data = inp.readlines()
    if config.maxconf * (config.nat + 2) > len(data):
        print(
            f"ERROR: Either the number of conformers ({config.nconf}) "
            f"or the number of atoms ({config.nat}) is wrong!"
        )
    for conf in conflist:
        i = conf.id
        atom = []
        x = []
        y = []
        z = []
        start = (i - 1) * (config.nat + 2) + 2
        end = i * (config.nat + 2)
        for line in data[start:end]:
            atom.append(str(line.split()[0].lower()))
            x.append(float(line.split()[1]) / BOHR2ANG)
            y.append(float(line.split()[2]) / BOHR2ANG)
            z.append(float(line.split()[3]) / BOHR2ANG)
        coordxyz = []
        for j in range(len(x)):
            coordxyz.append(f"{x[j]: .14f} {y[j]: .14f}  {z[j]: .14f}  {atom[j]}")
        outpath = os.path.join(config.cwd, "CONF" + str(conf.id), foldername, "coord")
        if not os.path.isfile(outpath):
            # print(f"Write new coord file in {last_folders(outpath)}")
            with open(outpath, "w", newline=None) as coord:
                coord.write("$coord\n")
                for line in coordxyz:
                    coord.write(line + "\n")
                coord.write("$end")
    return conflist, store_confs, save_errors


def splitting(item):
    """
    Used in move_recursively.

    """
    try:
        return int(item.rsplit(".", 1)[1])
    except ValueError:
        return 0


def move_recursively(path, filename):
    """
    Check if file or file.x exists and move them to file.x+1 ignores e.g.
    file.save
    """
    files = [
        f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))
    ]  # list of all files in directory
    newfiles = []  # list of all files in directory that contain filename and '.'
    for item in files:
        if filename + "." in item:
            newfiles.append(item)
    newfiles.sort(key=splitting, reverse=True)
    for item in newfiles:
        try:
            data = item.rsplit(".", 1)  # splits only at last '.'
            int(data[1])
        except ValueError:
            continue
        tmp_from = os.path.join(path, item)
        newfilename = str(data[0]) + "." + str(int(data[1]) + 1)
        tmp_to = os.path.join(path, newfilename)
        # print("Backing up {} to {}.".format(item, newfilename))
        shutil.move(tmp_from, tmp_to)

    if filename in files:
        print("Backing up {} to {}.".format(filename, filename + ".1"))
        shutil.move(os.path.join(path, filename), os.path.join(path, filename + ".1"))


def calc_boltzmannweights(confs, property, T):
    """
    Calculate Boltzmannweights:
    - confs [list] list with conformer objects
    - property [str] e.g. free_energy of conformer
    - T [float] temperature at which the Boltzmann weight has to be evaluated

    returns confs
    """
    if len(confs) == 1:
        confs[0].bm_weight = 1.0
        return confs
    try:
        T = float(T)
    except ValueError:
        T = 298.15  # K
        print(f"Temperature can not be converted and is therfore set to T = {T} K.")
    if T == 0:
        T += 0.00001  # avoid division by zero
    try:
        minfree = min(
            [
                getattr(conf, property, None)
                for conf in confs
                if getattr(conf, property, None) is not None
            ]
        )
    except ValueError:
        print("ERROR: Boltzmann weight can not be calculated!")
    bsum = 0.0
    for item in confs:
        bsum += getattr(item, "gi", 1.0) * math.exp(
            -((item.free_energy - minfree) * AU2J) / (KB * T)
        )
    for item in confs:
        item.bm_weight = (
            getattr(item, "gi", 1.0)
            * math.exp(-((item.free_energy - minfree) * AU2J) / (KB * T))
            / bsum
        )
    return confs


def new_folders(cwd, conflist, foldername, save_errors, store_confs, silent=False):
    """ 
    create folders for all conformers in conflist
    """

    for conf in conflist:
        tmp_dir = os.path.join(cwd, "CONF" + str(conf.id), foldername)
        try:
            mkdir_p(tmp_dir)
        except Exception as e:
            print(e)
            if not os.path.isdir(tmp_dir):
                print(f"ERROR: Could not create folder for CONF{conf.id}!")
                print(f"CONF{conf.id} is removed, because IO failed!")
                save_errors.append(f"CONF{conf.id} was removed, because IO failed!")
                store_confs.append(conflist.pop(conflist.index(conf)))
    if not silent:
        print("Constructed folders!")
    return save_errors, store_confs, conflist


def check_for_folder(path, conflist, foldername, debug=False):
    """
    Check if folders exist (of conformers calculated in previous run)
    """
    error_logical = False
    for i in conflist:
        tmp_dir = os.path.join(path, "CONF" + str(i), foldername)
        if not os.path.exists(tmp_dir):
            print(
                f"ERROR: directory of {last_folders(tmp_dir, 2)} does not exist, although "
                "it was calculated before!"
            )
            error_logical = True
    if error_logical and not debug:
        print("One or multiple directories are missing.\n")
    return error_logical


def do_md5(path):
    """
    Calculate md5 of file to identifly if restart happend on the same file!
    Input is buffered into smaller sizes to ease on memory consumption.
    """
    BUF_SIZE = 65536
    md5 = hashlib.md5()
    if os.path.isfile(path):
        with open(path, "rb") as f:
            while True:
                data = f.read(BUF_SIZE)
                if not data:
                    break
                md5.update(data)
        return md5.hexdigest()
    else:
        raise FileNotFoundError


def rank_simple(vector):
    """
    needed to rank vectors
    """
    return sorted(range(len(vector)), key=vector.__getitem__)


def rankdata(a):
    """
    rank vectors like in numpy
    """
    n = len(a)
    ivec = rank_simple(a)
    svec = [a[rank] for rank in ivec]
    sumranks = 0
    dupcount = 0
    newarray = [0] * n
    for i in range(n):
        sumranks += i
        dupcount += 1
        if i == n - 1 or svec[i] != svec[i + 1]:
            averank = sumranks / float(dupcount) + 1
            for j in range(i - dupcount + 1, i + 1):
                newarray[ivec[j]] = averank
            sumranks = 0
            dupcount = 0
    return newarray


def pearson(A, B):
    """
    Calculate pearson correlation coefficient
    """
    if len(A) != len(B):
        print("ERROR in PEARSON lists are not of equal length!")
    n = float(len(A))
    muA = sum(A) / n
    muB = sum(B) / n
    diffA = map(lambda x: x - muA, A)
    diffB = map(lambda x: x - muB, B)
    stdA = math.sqrt((1 / (n - 1)) * sum([d * d for d in diffA]))
    stdB = math.sqrt((1 / (n - 1)) * sum([d * d for d in diffB]))
    try:
        return (sum([A[i] * B[i] for i in range(int(n))]) - n * muA * muB) / (
            (n - 1) * stdA * stdB
        )
    except ZeroDivisionError as e:
        print("WARNING: ", e)
        return 0.0


def spearman(A, B):
    """
    Calculate spearman correlation coefficient
    """
    return pearson(rankdata(A), rankdata(B))


def printout(
    outputpath,
    columncall,
    columnheader,
    columndescription,
    columnformat,
    calculate,
    minfree,
    columndescription2=[],
):
    """
    Create printout which is printed to stdout and file.
    """
    calculate.sort(key=lambda x: int(x.id))
    if not any(
        [
            len(i) == len(columncall)
            for i in (columnheader, columndescription, columnformat)
        ]
    ):
        print("Lists of uneqal length!")
    collength = []
    columnheaderprint = []
    columndescriptionprint = []
    columndescriptionprint2 = []
    if not columndescription2:
        columndescription2 = ["" for _ in range(len(columncall))]
    # split on "["   eg. COSMORS[B97-3c/def2-TZVP]

    for i in range(len(columndescription)):
        if "[" in columndescription[i] and columndescription[i] not in (
            "[Eh]",
            "[kcal/mol]",
            "[a.u.]",
        ):
            columndescription2[i] = "[" + str(columndescription[i]).split("[")[1]
            columndescription[i] = str(columndescription[i]).split("[")[0]
    try:
        for j in range(len(columncall)):
            if columnformat[j]:
                collength.append(
                    max(
                        [
                            len(str(f"{i:{columnformat[j][0]}.{columnformat[j][1]}f}"))
                            for i in map(columncall[j], calculate)
                        ]
                    )
                )
            else:
                collength.append(max([len(i) for i in map(columncall[j], calculate)]))
            if (
                max(
                    len(i)
                    for i in [
                        columndescription[j],
                        columnheader[j],
                        columndescription2[j],
                    ]
                )
                > collength[j]
            ):
                collength[j] = max(
                    len(i)
                    for i in [
                        columndescription[j],
                        columnheader[j],
                        columndescription2[j],
                    ]
                )
    except (ValueError, TypeError) as e:
        print(f"\n\nERRROR {e}")
        for j in range(len(columncall)):
            collength.append(12)

    for i in range(len(columncall)):
        columnheaderprint.append(f"{columnheader[i]:>{collength[i]}}")
        columndescriptionprint.append(f"{columndescription[i]:>{collength[i]}}")
        if columndescription2:
            columndescriptionprint2.append(f"{columndescription2[i]:>{collength[i]}}")
    with open(outputpath, "w", newline=None) as out:
        line = " ".join(columnheaderprint)
        print(line)
        out.write(line + "\n")
        line = " ".join(columndescriptionprint)
        print(line)
        out.write(line + "\n")
        if columndescription2:
            line = " ".join(columndescriptionprint2)
            print(line)
            out.write(line + "\n")
        for conf in calculate:
            columncallprint = []
            for i in range(len(columncall)):
                if columnformat[i]:
                    columncallprint.append(
                        f"{columncall[i](conf):{collength[i]}.{columnformat[i][1]}f}"
                    )
                else:
                    columncallprint.append(f"{columncall[i](conf):{collength[i]}}")
            if conf.free_energy != minfree:
                line = " ".join(columncallprint)
                print(line)
                out.write(line + "\n")
            else:
                line = " ".join(columncallprint + [f"    <------"])
                print(line)
                out.write(line + "\n")


def crest_routine(config, conformers, func, store_confs, prev_calculated=[]):
    """
    check if two conformers are rotamers of each other,
    this check is always performed, but removing conformers depends on crestcheck
    returns conformers
    returns store_confs
    returns prev_calculated
    """
    dirn = "conformer_rotamer_check"  ### directory name
    fn = "conformers.xyz"  ### file name

    print("\nChecking for identical structures in ensemble with CREGEN!\n")
    # create folder for comparison
    if not os.path.isdir(os.path.join(config.cwd, dirn)):
        mkdir_p(os.path.join(config.cwd, dirn))
    # delete conformers.xyz file if it already exists
    if os.path.isfile(os.path.join(config.cwd, dirn, fn)):
        os.remove(os.path.join(config.cwd, dirn, fn))
    # delete coord file if exists
    if os.path.isfile(os.path.join(config.cwd, dirn, "coord")):
        os.remove(os.path.join(config.cwd, dirn, "coord"))

    allconfs = deepcopy(conformers)
    allconfs.extend(deepcopy(prev_calculated))

    ### sort conformers according to energy of optimization
    allconfs.sort(key=lambda conf: float(getattr(conf, "optimization_info")["energy"]))
    # write coord:
    try:
        shutil.copy(
            os.path.join(config.cwd, "CONF" + str(allconfs[0].id), func, "coord"),
            os.path.join(config.cwd, dirn, "coord"),
        )
    except Exception as e:
        print(f"ERROR: {e}")

    # write conformers.xyz file
    with open(
        os.path.join(config.cwd, dirn, fn), "w", encoding=CODING, newline=None
    ) as out:
        for conf in allconfs:
            conf_xyz, nat = t2x(os.path.join(config.cwd, "CONF" + str(conf.id), func))
            out.write("  {}\n".format(nat))  ### number of atoms
            out.write(
                "{:20.8f}        !{}\n".format(
                    getattr(conf, "optimization_info")["energy"], "CONF" + str(conf.id)
                )
            )
            for line in conf_xyz:
                out.write(line + "\n")
        for conf in allconfs:
            conf_xyz, nat = t2x(os.path.join(config.cwd, "CONF" + str(conf.id), func))
            out.write("  {}\n".format(nat))  ### number of atoms
            out.write(
                "{:20.8f}        !{}\n".format(
                    getattr(conf, "optimization_info")["energy"], "CONF" + str(conf.id)
                )
            )
            for line in conf_xyz:
                out.write(line + "\n")
    time.sleep(0.01)

    crestcall = [
        config.external_paths["crestpath"],
        "coord",
        "-cregen",
        fn,
        "-ethr",
        "0.15",
        "-rthr",
        "0.175",
        "-bthr",
        "0.03",
        "-enso",
    ]

    with open(
        os.path.join(config.cwd, dirn, "crest.out"), "w", newline=None, encoding=CODING
    ) as outputfile:
        subprocess.call(
            crestcall,
            shell=False,
            stdin=None,
            stderr=subprocess.STDOUT,
            universal_newlines=False,
            cwd=os.path.join(config.cwd, dirn),
            stdout=outputfile,
            env=ENVIRON,
        )
        time.sleep(0.05)
        try:
            with open(
                os.path.join(config.cwd, dirn, "enso.tags"),
                "r",
                encoding=CODING,
                newline=None,
            ) as inp:
                store = inp.readlines()
        except (Exception) as e:
            print(f"ERROR: {e}")
            print("ERROR: output file (enso.tags) of CREST routine does not exist!")
        keep = []
    if config.crestcheck:
        try:
            for line in store:
                keep.append(line.split()[1][1:])
            for conf in list(conformers):
                if "CONF" + str(conf.id) not in keep:
                    conf.optimization_info["info"] = "calculated"
                    conf.optimization_info["cregen_sort"] = "removed"
                    print(
                        f"!!!! Removing CONF{conf.id} because it is sorted "
                        "out by CREGEN."
                    )
                    store_confs.append(conformers.pop(conformers.index(conf)))
            for conf in list(prev_calculated):
                if "CONF" + str(conf.id) not in keep:
                    conf.optimization_info["info"] = "calculated"
                    conf.optimization_info["cregen_sort"] = "removed"
                    print(
                        f"!!!! Removing CONF{conf.id} because it is sorted "
                        "out by CREGEN."
                    )
                    store_confs.append(prev_calculated.pop(prev_calculated.index(conf)))
        except (NameError, Exception) as e:
            print(f"ERROR: {e}")
    return conformers, prev_calculated, store_confs


def format_line(key, value, options, optionlength=70, dist_to_options=30):
    """
    used in print_parameters
    """
    # limit printout of possibilities
    if len(str(options)) > optionlength:
        length = 0
        reduced = []
        for item in options:
            length += len(item) + 2
            if length < optionlength:
                reduced.append(item)
        reduced.append("...")
        options = reduced
        length = 0
    line = "{}: {:{digits}} # {} \n".format(
        key, str(value), options, digits=dist_to_options - len(key)
    )
    return line


def check_tasks(results, check=False, thresh=0.25):
    """
    Check if too many tasks failed and exit if so!
    """
    # Check if preparation failed too often:
    counter = 0
    for item in results:
        if not item.job["success"]:
            counter += 1
    try:
        fail_rate = float(counter) / float(len(results))
    except ZeroDivisionError:
        print(f"ERROR: Too many calculations failed!" "\nGoing to exit!")
        sys.exit(1)
    if fail_rate >= thresh and check:
        print(
            f"ERROR: {fail_rate*100} % of the calculations failed!" "\nGoing to exit!"
        )
        sys.exit(1)
    elif fail_rate >= thresh:
        print(f"WARNING: {fail_rate*100} % of the calculations failed!")


def isclose(value_a, value_b, rel_tol=1e-9, abs_tol=0.0):
    """
    Replace function if not available from math module (exists since python 3.5)
    """
    return abs(value_a - value_b) <= max(
        rel_tol * max(abs(value_a), abs(value_b)), abs_tol
    )


def calc_std_dev(data):
    """
    Calculate standard deviation
    """
    n = len(data)
    mean = sum(data) / n
    variance = sum([(x - mean) ** 2 for x in data]) / (n - 1)
    std_dev = math.sqrt(variance)
    return std_dev


def calc_weighted_std_dev(data, weights=[]):
    """
    Calculate standard deviation
    """
    n = len(data)
    if n == 0:
        return 0.0
    if not weights or len(weights) < n:
        weights = [1.0 for _ in range(n)]
    w_mean = sum([data[i] * weights[i] for i in range(n)]) / sum(weights)
    m = 0
    for i in weights:
        if i != 0.0:
            m += 1
    variance = sum([weights[i] * (data[i] - w_mean) ** 2 for i in range(n)]) / (
        (m - 1) * sum(weights) / m
    )
    std_dev = math.sqrt(variance)
    return std_dev


def write_anmrrc(config):
    """ Write file .anmrrc with information processed by ANMR """
    h_tm_shieldings = {
        "TMS": {
            "pbeh-3c": {
                "tpss": {
                    "gas": 32.0512048,
                    "acetone": 32.03971003333333,
                    "chcl3": 32.041133316666674,
                    "acetonitrile": 32.03617056666667,
                    "ch2cl2": 32.04777176666666,
                    "dmso": 32.039681316666666,
                    "h2o": 32.036860174999994,
                    "methanol": 32.04573335,
                    "thf": 32.04154705833333,
                    "toluene": 32.02829061666666,
                },
                "pbe0": {
                    "gas": 31.820450258333327,
                    "acetone": 31.801199816666667,
                    "chcl3": 31.807363400000003,
                    "acetonitrile": 31.797744033333334,
                    "ch2cl2": 31.815502166666665,
                    "dmso": 31.797286500000002,
                    "h2o": 31.801018416666665,
                    "methanol": 31.809920125,
                    "thf": 31.802681225,
                    "toluene": 31.790892416666665,
                },
                "pbeh-3c": {
                    "gas": 32.32369869999999,
                    "acetone": 32.30552229166667,
                    "chcl3": 32.30850654166667,
                    "acetonitrile": 32.3015773,
                    "ch2cl2": 32.31627083333333,
                    "dmso": 32.303862816666665,
                    "h2o": 32.30345545833333,
                    "methanol": 32.3130819,
                    "thf": 32.306951225,
                    "toluene": 32.29417180833333,
                },
            },
            "b97-3c": {
                "tpss": {
                    "gas": 32.099305599999994,
                    "acetone": 32.07685382499999,
                    "chcl3": 32.078372550000005,
                    "acetonitrile": 32.067920741666676,
                    "ch2cl2": 32.0876576,
                    "dmso": 32.07713496666667,
                    "h2o": 32.07222951666666,
                    "methanol": 32.085467083333334,
                    "thf": 32.07950451666667,
                    "toluene": 32.06162065,
                },
                "pbe0": {
                    "gas": 31.869211950000004,
                    "acetone": 31.83879448333333,
                    "chcl3": 31.845031441666663,
                    "acetonitrile": 31.829924375,
                    "ch2cl2": 31.855811533333338,
                    "dmso": 31.835178675000005,
                    "h2o": 31.83680665833334,
                    "methanol": 31.850090208333338,
                    "thf": 31.841073758333337,
                    "toluene": 31.824697675,
                },
                "pbeh-3c": {
                    "gas": 32.37107341666667,
                    "acetone": 32.341934458333334,
                    "chcl3": 32.34503841666666,
                    "acetonitrile": 32.332714675,
                    "ch2cl2": 32.35537393333334,
                    "dmso": 32.34058045833333,
                    "h2o": 32.338073200000004,
                    "methanol": 32.35207416666667,
                    "thf": 32.34418670833334,
                    "toluene": 32.32693729166667,
                },
            },
            "tpss": {
                "tpss": {
                    "gas": 31.86774000000001,
                    "acetone": 31.848927016666664,
                    "chcl3": 31.851003891666664,
                    "acetonitrile": 31.843538541666664,
                    "ch2cl2": 31.860415141666664,
                    "dmso": 31.849057266666673,
                    "h2o": 31.844762508333332,
                    "methanol": 31.857667625,
                    "thf": 31.851878716666665,
                    "toluene": 31.833541825,
                },
                "pbe0": {
                    "gas": 31.636587116666664,
                    "acetone": 31.60924136666667,
                    "chcl3": 31.616506625,
                    "acetonitrile": 31.604173191666664,
                    "ch2cl2": 31.62743169166667,
                    "dmso": 31.604975658333334,
                    "h2o": 31.607992624999994,
                    "methanol": 31.620864658333335,
                    "thf": 31.611675816666665,
                    "toluene": 31.59546233333333,
                },
                "pbeh-3c": {
                    "gas": 32.14311896666666,
                    "acetone": 32.11710325,
                    "chcl3": 32.12106585833333,
                    "acetonitrile": 32.11156126666667,
                    "ch2cl2": 32.1315459,
                    "dmso": 32.114840533333336,
                    "h2o": 32.11376850833333,
                    "methanol": 32.127508733333336,
                    "thf": 32.11950190833333,
                    "toluene": 32.1023676,
                },
            },
        }
    }
    h_orca_shieldings = {
        "TMS": {
            "pbeh-3c": {
                "tpss": {
                    "gas": 32.17000000000001,
                    "acetone": 32.09433333333334,
                    "chcl3": 32.10649999999999,
                    "acetonitrile": 32.09366666666667,
                    "ch2cl2": 32.099,
                    "dmso": 32.09466666666666,
                    "h2o": 32.10341666666666,
                    "methanol": 32.09250000000001,
                    "thf": 32.10183333333333,
                    "toluene": 32.122833333333325,
                },
                "pbe0": {
                    "gas": 31.819000000000003,
                    "acetone": 31.732666666666663,
                    "chcl3": 31.747000000000003,
                    "acetonitrile": 31.73166666666667,
                    "ch2cl2": 31.738416666666666,
                    "dmso": 31.732666666666663,
                    "h2o": 31.741500000000002,
                    "methanol": 31.73066666666666,
                    "thf": 31.74116666666667,
                    "toluene": 31.765999999999995,
                },
                "dsd-blyp": {
                    "gas": 31.91416666666667,
                    "acetone": 31.83541666666667,
                    "chcl3": 31.84766666666667,
                    "acetonitrile": 31.834666666666667,
                    "ch2cl2": 31.839916666666667,
                    "dmso": 31.835583333333332,
                    "h2o": 31.844166666666666,
                    "methanol": 31.833166666666667,
                    "thf": 31.842583333333334,
                    "toluene": 31.86475,
                },
                "wb97x": {
                    "gas": 31.952,
                    "acetone": 31.867499999999996,
                    "chcl3": 31.880999999999997,
                    "acetonitrile": 31.866666666666664,
                    "ch2cl2": 31.872666666666664,
                    "dmso": 31.86758333333333,
                    "h2o": 31.876083333333337,
                    "methanol": 31.86533333333333,
                    "thf": 31.8755,
                    "toluene": 31.89966666666666,
                },
                "pbeh-3c": {
                    "gas": 32.324999999999996,
                    "acetone": 32.23866666666667,
                    "chcl3": 32.25299999999999,
                    "acetonitrile": 32.23783333333333,
                    "ch2cl2": 32.24466666666667,
                    "dmso": 32.23866666666667,
                    "h2o": 32.24733333333333,
                    "methanol": 32.23666666666667,
                    "thf": 32.24733333333333,
                    "toluene": 32.272,
                },
                "kt2": {
                    "gas": 31.817999999999998,
                    "acetone": 31.73233333333333,
                    "chcl3": 31.746333333333336,
                    "acetonitrile": 31.73133333333333,
                    "ch2cl2": 31.737666666666666,
                    "dmso": 31.73233333333333,
                    "h2o": 31.740666666666666,
                    "methanol": 31.73,
                    "thf": 31.740499999999994,
                    "toluene": 31.765666666666664,
                },
            },
            "b97-3c": {
                "tpss": {
                    "gas": 32.21800000000001,
                    "acetone": 32.140166666666666,
                    "chcl3": 32.152166666666666,
                    "acetonitrile": 32.140499999999996,
                    "ch2cl2": 32.145,
                    "dmso": 32.14183333333333,
                    "h2o": 32.175000000000004,
                    "methanol": 32.13766666666667,
                    "thf": 32.148,
                    "toluene": 32.168833333333325,
                },
                "pbe0": {
                    "gas": 31.868,
                    "acetone": 31.778999999999996,
                    "chcl3": 31.792583333333337,
                    "acetonitrile": 31.778666666666663,
                    "ch2cl2": 31.784333333333336,
                    "dmso": 31.78016666666667,
                    "h2o": 31.815166666666666,
                    "methanol": 31.77633333333333,
                    "thf": 31.787500000000005,
                    "toluene": 31.812,
                },
                "dsd-blyp": {
                    "gas": 31.962999999999997,
                    "acetone": 31.881250000000005,
                    "chcl3": 31.89325,
                    "acetonitrile": 31.881583333333335,
                    "ch2cl2": 31.886000000000006,
                    "dmso": 31.882583333333333,
                    "h2o": 31.916833333333333,
                    "methanol": 31.878500000000003,
                    "thf": 31.889,
                    "toluene": 31.910750000000004,
                },
                "wb97x": {
                    "gas": 32.00091666666666,
                    "acetone": 31.913416666666663,
                    "chcl3": 31.9265,
                    "acetonitrile": 31.9135,
                    "ch2cl2": 31.918499999999995,
                    "dmso": 31.914666666666665,
                    "h2o": 31.94883333333333,
                    "methanol": 31.910666666666668,
                    "thf": 31.921500000000005,
                    "toluene": 31.94516666666667,
                },
                "pbeh-3c": {
                    "gas": 32.373,
                    "acetone": 32.28366666666667,
                    "chcl3": 32.29716666666666,
                    "acetonitrile": 32.28333333333333,
                    "ch2cl2": 32.288666666666664,
                    "dmso": 32.284499999999994,
                    "h2o": 32.317166666666665,
                    "methanol": 32.28066666666667,
                    "thf": 32.29183333333334,
                    "toluene": 32.31616666666667,
                },
                "kt2": {
                    "gas": 31.868,
                    "acetone": 31.778666666666663,
                    "chcl3": 31.792500000000004,
                    "acetonitrile": 31.778666666666663,
                    "ch2cl2": 31.784333333333336,
                    "dmso": 31.78033333333333,
                    "h2o": 31.794583333333332,
                    "methanol": 31.77633333333333,
                    "thf": 31.787500000000005,
                    "toluene": 31.812,
                },
            },
            "tpss": {
                "tpss": {
                    "gas": 31.97300000000001,
                    "acetone": 31.898,
                    "chcl3": 31.909500000000005,
                    "acetonitrile": 31.897833333333338,
                    "ch2cl2": 31.902666666666665,
                    "dmso": 31.898999999999997,
                    "h2o": 31.910666666666668,
                    "methanol": 31.89566666666667,
                    "thf": 31.90516666666667,
                    "toluene": 31.925,
                },
                "pbe0": {
                    "gas": 31.625,
                    "acetone": 31.537166666666668,
                    "chcl3": 31.550499999999996,
                    "acetonitrile": 31.536666666666665,
                    "ch2cl2": 31.542500000000004,
                    "dmso": 31.537666666666667,
                    "h2o": 31.549500000000005,
                    "methanol": 31.53458333333334,
                    "thf": 31.545499999999993,
                    "toluene": 31.569,
                },
                "dsd-blyp": {
                    "gas": 31.718000000000004,
                    "acetone": 31.639666666666667,
                    "chcl3": 31.651416666666663,
                    "acetonitrile": 31.639499999999998,
                    "ch2cl2": 31.644083333333338,
                    "dmso": 31.640416666666667,
                    "h2o": 31.65216666666667,
                    "methanol": 31.636916666666664,
                    "thf": 31.64683333333333,
                    "toluene": 31.667833333333334,
                },
                "wb97x": {
                    "gas": 31.757,
                    "acetone": 31.672250000000002,
                    "chcl3": 31.68516666666667,
                    "acetonitrile": 31.67166666666667,
                    "ch2cl2": 31.6775,
                    "dmso": 31.67266666666666,
                    "h2o": 31.68466666666666,
                    "methanol": 31.66966666666667,
                    "thf": 31.680166666666665,
                    "toluene": 31.703,
                },
                "pbeh-3c": {
                    "gas": 32.13400000000001,
                    "acetone": 32.047333333333334,
                    "chcl3": 32.06066666666667,
                    "acetonitrile": 32.04666666666666,
                    "ch2cl2": 32.05266666666666,
                    "dmso": 32.047666666666665,
                    "h2o": 32.059,
                    "methanol": 32.044666666666664,
                    "thf": 32.05566666666666,
                    "toluene": 32.079,
                },
                "kt2": {
                    "gas": 31.622999999999994,
                    "acetone": 31.536666666666665,
                    "chcl3": 31.55,
                    "acetonitrile": 31.5365,
                    "ch2cl2": 31.54183333333333,
                    "dmso": 31.537666666666667,
                    "h2o": 31.548666666666666,
                    "methanol": 31.533833333333334,
                    "thf": 31.544833333333333,
                    "toluene": 31.56866666666667,
                },
            },
        }
    }
    c_tm_shieldings = {
        "TMS": {
            "pbeh-3c": {
                "tpss": {
                    "gas": 186.6465687,
                    "acetone": 187.27903107499998,
                    "chcl3": 187.238498325,
                    "acetonitrile": 187.372512775,
                    "ch2cl2": 187.0771589,
                    "dmso": 187.243299225,
                    "h2o": 187.37157565,
                    "methanol": 187.10988087500002,
                    "thf": 187.19458635,
                    "toluene": 187.48276635,
                },
                "pbe0": {
                    "gas": 188.859355325,
                    "acetone": 189.6196798,
                    "chcl3": 189.4971041,
                    "acetonitrile": 189.698041075,
                    "ch2cl2": 189.318608125,
                    "dmso": 189.68253637499998,
                    "h2o": 189.65553119999998,
                    "methanol": 189.409198575,
                    "thf": 189.55889105,
                    "toluene": 189.776394325,
                },
                "pbeh-3c": {
                    "gas": 198.41611147499998,
                    "acetone": 199.13367970000002,
                    "chcl3": 199.054179875,
                    "acetonitrile": 199.250248325,
                    "ch2cl2": 198.845265825,
                    "dmso": 199.185056825,
                    "h2o": 199.2289907,
                    "methanol": 198.917945675,
                    "thf": 199.076003325,
                    "toluene": 199.3931504,
                },
            },
            "b97-3c": {
                "tpss": {
                    "gas": 186.97419324999998,
                    "acetone": 187.496073025,
                    "chcl3": 187.45393565,
                    "acetonitrile": 187.554538075,
                    "ch2cl2": 187.31238564999998,
                    "dmso": 187.469466275,
                    "h2o": 187.57139320000002,
                    "methanol": 187.344972675,
                    "thf": 187.42200885,
                    "toluene": 187.671731225,
                },
                "pbe0": {
                    "gas": 189.169130675,
                    "acetone": 189.816064175,
                    "chcl3": 189.69082477499998,
                    "acetonitrile": 189.860330875,
                    "ch2cl2": 189.532330975,
                    "dmso": 189.88587445000002,
                    "h2o": 189.8368566,
                    "methanol": 189.62332455,
                    "thf": 189.76569125,
                    "toluene": 189.94371412499999,
                },
                "pbeh-3c": {
                    "gas": 198.7168509,
                    "acetone": 199.3308802,
                    "chcl3": 199.25125382500002,
                    "acetonitrile": 199.41320919999998,
                    "ch2cl2": 199.06108425,
                    "dmso": 199.390014125,
                    "h2o": 199.41478467500002,
                    "methanol": 199.13192775,
                    "thf": 199.28161922500001,
                    "toluene": 199.562540575,
                },
            },
            "tpss": {
                "tpss": {
                    "gas": 185.410099625,
                    "acetone": 185.99193982499997,
                    "chcl3": 185.949648475,
                    "acetonitrile": 186.0799505,
                    "ch2cl2": 185.80363820000002,
                    "dmso": 185.97415155,
                    "h2o": 186.07484635,
                    "methanol": 185.839592875,
                    "thf": 185.9190184,
                    "toluene": 186.17204557500003,
                },
                "pbe0": {
                    "gas": 187.626469575,
                    "acetone": 188.34549135,
                    "chcl3": 188.212218325,
                    "acetonitrile": 188.413268225,
                    "ch2cl2": 188.04820440000003,
                    "dmso": 188.42875420000001,
                    "h2o": 188.3724699,
                    "methanol": 188.14698049999998,
                    "thf": 188.2963985,
                    "toluene": 188.46803717499998,
                },
                "pbeh-3c": {
                    "gas": 197.27823677499998,
                    "acetone": 197.953274625,
                    "chcl3": 197.871683925,
                    "acetonitrile": 198.0615831,
                    "ch2cl2": 197.6764831,
                    "dmso": 198.014841225,
                    "h2o": 198.048432475,
                    "methanol": 197.75143105,
                    "thf": 197.905333025,
                    "toluene": 198.186480775,
                },
            },
        }
    }
    c_orca_shieldings = {
        "TMS": {
            "pbeh-3c": {
                "tpss": {
                    "gas": 188.604,
                    "acetone": 189.7395,
                    "chcl3": 189.5435,
                    "acetonitrile": 189.77,
                    "ch2cl2": 189.6625,
                    "dmso": 189.8015,
                    "h2o": 189.8495,
                    "methanol": 189.77,
                    "thf": 189.647,
                    "toluene": 189.30400000000003,
                },
                "pbe0": {
                    "gas": 188.867,
                    "acetone": 190.265,
                    "chcl3": 190.02224999999999,
                    "acetonitrile": 190.298,
                    "ch2cl2": 190.16649999999998,
                    "dmso": 190.33175,
                    "h2o": 190.38799999999998,
                    "methanol": 190.29875,
                    "thf": 190.1445,
                    "toluene": 189.73375,
                },
                "dsd-blyp": {
                    "gas": 191.37099999999998,
                    "acetone": 192.606,
                    "chcl3": 192.385,
                    "acetonitrile": 192.63599999999997,
                    "ch2cl2": 192.51575000000003,
                    "dmso": 192.66625000000002,
                    "h2o": 192.7205,
                    "methanol": 192.63524999999998,
                    "thf": 192.4955,
                    "toluene": 192.12275,
                },
                "wb97x": {
                    "gas": 190.36075,
                    "acetone": 191.689,
                    "chcl3": 191.453,
                    "acetonitrile": 191.72175000000001,
                    "ch2cl2": 191.5935,
                    "dmso": 191.753,
                    "h2o": 191.8085,
                    "methanol": 191.72150000000002,
                    "thf": 191.57150000000001,
                    "toluene": 191.17225,
                },
                "pbeh-3c": {
                    "gas": 198.458,
                    "acetone": 199.905,
                    "chcl3": 199.649,
                    "acetonitrile": 199.94,
                    "ch2cl2": 199.8025,
                    "dmso": 199.9715,
                    "h2o": 200.0265,
                    "methanol": 199.93900,
                    "thf": 199.7775,
                    "toluene": 199.3395,
                },
                "kt2": {
                    "gas": 190.719,
                    "acetone": 191.988,
                    "chcl3": 191.7645,
                    "acetonitrile": 192.019,
                    "ch2cl2": 191.8965,
                    "dmso": 192.05150000000003,
                    "h2o": 192.1055,
                    "methanol": 192.02,
                    "thf": 191.8775,
                    "toluene": 191.4905,
                },
            },
            "b97-3c": {
                "tpss": {
                    "gas": 188.908,
                    "acetone": 190.0265,
                    "chcl3": 189.83749999999998,
                    "acetonitrile": 190.062,
                    "ch2cl2": 189.954,
                    "dmso": 190.103,
                    "h2o": 190.07774999999998,
                    "methanol": 190.0595,
                    "thf": 189.9445,
                    "toluene": 189.614,
                },
                "pbe0": {
                    "gas": 189.18025,
                    "acetone": 190.57025000000002,
                    "chcl3": 190.33075,
                    "acetonitrile": 190.60525,
                    "ch2cl2": 190.47,
                    "dmso": 190.65175,
                    "h2o": 190.59925000000004,
                    "methanol": 190.60775,
                    "thf": 190.456,
                    "toluene": 190.058,
                },
                "dsd-blyp": {
                    "gas": 191.66199999999998,
                    "acetone": 192.88025,
                    "chcl3": 192.66174999999998,
                    "acetonitrile": 192.915,
                    "ch2cl2": 192.79025,
                    "dmso": 192.95425,
                    "h2o": 192.91275000000002,
                    "methanol": 192.91250000000002,
                    "thf": 192.77625,
                    "toluene": 192.4135,
                },
                "wb97x": {
                    "gas": 190.65525,
                    "acetone": 191.97199999999998,
                    "chcl3": 191.73825,
                    "acetonitrile": 192.00725,
                    "ch2cl2": 191.875,
                    "dmso": 192.04950000000002,
                    "h2o": 191.99675000000002,
                    "methanol": 192.007,
                    "thf": 191.86025,
                    "toluene": 191.47125,
                },
                "pbeh-3c": {
                    "gas": 198.752,
                    "acetone": 200.196,
                    "chcl3": 199.9445,
                    "acetonitrile": 200.23250000000002,
                    "ch2cl2": 200.0925,
                    "dmso": 200.277,
                    "h2o": 200.15925,
                    "methanol": 200.23350000000002,
                    "thf": 200.075,
                    "toluene": 199.65050000000002,
                },
                "kt2": {
                    "gas": 191.037,
                    "acetone": 192.29649999999998,
                    "chcl3": 192.0765,
                    "acetonitrile": 192.3275,
                    "ch2cl2": 192.20350000000002,
                    "dmso": 192.3755,
                    "h2o": 192.188,
                    "methanol": 192.33275,
                    "thf": 192.1925,
                    "toluene": 191.8175,
                },
            },
            "tpss": {
                "tpss": {
                    "gas": 187.22,
                    "acetone": 188.442,
                    "chcl3": 188.214,
                    "acetonitrile": 188.4745,
                    "ch2cl2": 188.351,
                    "dmso": 188.5115,
                    "h2o": 188.58350000000002,
                    "methanol": 188.473,
                    "thf": 188.33950000000002,
                    "toluene": 187.965,
                },
                "pbe0": {
                    "gas": 187.5725,
                    "acetone": 188.99225,
                    "chcl3": 188.73424999999997,
                    "acetonitrile": 189.0295,
                    "ch2cl2": 188.8875,
                    "dmso": 189.06875,
                    "h2o": 189.14175,
                    "methanol": 189.0275,
                    "thf": 188.8665,
                    "toluene": 188.4305,
                },
                "dsd-blyp": {
                    "gas": 190.06825,
                    "acetone": 191.39,
                    "chcl3": 191.15425,
                    "acetonitrile": 191.42600000000002,
                    "ch2cl2": 191.29475000000002,
                    "dmso": 191.461,
                    "h2o": 191.53225,
                    "methanol": 191.4225,
                    "thf": 191.27499999999998,
                    "toluene": 190.87675000000002,
                },
                "wb97x": {
                    "gas": 189.04575,
                    "acetone": 190.45225000000002,
                    "chcl3": 190.20074999999997,
                    "acetonitrile": 190.4885,
                    "ch2cl2": 190.35025000000002,
                    "dmso": 190.52525,
                    "h2o": 190.5975,
                    "methanol": 190.4855,
                    "thf": 190.32899999999998,
                    "toluene": 189.904,
                },
                "pbeh-3c": {
                    "gas": 197.184,
                    "acetone": 198.7195,
                    "chcl3": 198.449,
                    "acetonitrile": 198.75799999999998,
                    "ch2cl2": 198.611,
                    "dmso": 198.7955,
                    "h2o": 198.8655,
                    "methanol": 198.755,
                    "thf": 198.587,
                    "toluene": 198.1245,
                },
                "kt2": {
                    "gas": 189.386,
                    "acetone": 190.7245,
                    "chcl3": 190.488,
                    "acetonitrile": 190.7585,
                    "ch2cl2": 190.6275,
                    "dmso": 190.7975,
                    "h2o": 190.87900000000002,
                    "methanol": 190.75799999999998,
                    "thf": 190.6095,
                    "toluene": 190.2095,
                },
            },
        }
    }
    f_tm_shieldings = {
        "CFCl3": {
            "pbeh-3c": {
                "tpss": {
                    "gas": 163.5665883,
                    "acetone": 165.9168679,
                    "chcl3": 165.043061,
                    "acetonitrile": 166.377831,
                    "ch2cl2": 164.776383,
                    "dmso": 166.1839641,
                    "h2o": 166.880495,
                    "methanol": 165.4364879,
                    "thf": 165.7384153,
                    "toluene": 165.7812123,
                },
                "pbe0": {
                    "gas": 179.4820255,
                    "acetone": 181.9743764,
                    "chcl3": 181.1338758,
                    "acetonitrile": 182.4438224,
                    "ch2cl2": 180.8751895,
                    "dmso": 182.2224636,
                    "h2o": 182.9958356,
                    "methanol": 181.5031528,
                    "thf": 181.7669891,
                    "toluene": 181.7963177,
                },
                "pbeh-3c": {
                    "gas": 225.045234,
                    "acetone": 226.6335916,
                    "chcl3": 226.0133192,
                    "acetonitrile": 226.9371636,
                    "ch2cl2": 225.8300352,
                    "dmso": 226.8061873,
                    "h2o": 227.4000142,
                    "methanol": 226.3012569,
                    "thf": 226.5247654,
                    "toluene": 226.555523,
                },
            },
            "b97-3c": {
                "tpss": {
                    "gas": 150.4514566,
                    "acetone": 151.5612999,
                    "chcl3": 150.5819485,
                    "acetonitrile": 151.9884593,
                    "ch2cl2": 150.2953968,
                    "dmso": 151.8818575,
                    "h2o": 151.6179136,
                    "methanol": 151.0439011,
                    "thf": 151.4207377,
                    "toluene": 151.4686522,
                },
                "pbe0": {
                    "gas": 167.7783433,
                    "acetone": 169.09491,
                    "chcl3": 168.1354478,
                    "acetonitrile": 169.5416871,
                    "ch2cl2": 167.8558489,
                    "dmso": 169.3950732,
                    "h2o": 169.2178304,
                    "methanol": 168.5860848,
                    "thf": 168.9136991,
                    "toluene": 168.9347931,
                },
                "pbeh-3c": {
                    "gas": 213.6651892,
                    "acetone": 214.1284506,
                    "chcl3": 213.4293417,
                    "acetonitrile": 214.4297108,
                    "ch2cl2": 213.2298905,
                    "dmso": 214.366451,
                    "h2o": 214.1162368,
                    "methanol": 213.76845,
                    "thf": 214.0512078,
                    "toluene": 214.0924969,
                },
            },
            "tpss": {
                "tpss": {
                    "gas": 146.4091676,
                    "acetone": 148.7113398,
                    "chcl3": 147.7715256,
                    "acetonitrile": 149.1854535,
                    "ch2cl2": 147.4708159,
                    "dmso": 148.9781692,
                    "h2o": 148.8407317,
                    "methanol": 148.1815132,
                    "thf": 148.5140784,
                    "toluene": 148.6001306,
                },
                "pbe0": {
                    "gas": 163.4654205,
                    "acetone": 165.9356023,
                    "chcl3": 165.0269644,
                    "acetonitrile": 166.4188044,
                    "ch2cl2": 164.7336009,
                    "dmso": 166.1830401,
                    "h2o": 166.0858984,
                    "methanol": 165.4145633,
                    "thf": 165.7038144,
                    "toluene": 165.7726604,
                },
                "pbeh-3c": {
                    "gas": 209.8752809,
                    "acetone": 211.4025693,
                    "chcl3": 210.7286529,
                    "acetonitrile": 211.7120494,
                    "ch2cl2": 210.5166504,
                    "dmso": 211.5990015,
                    "h2o": 211.4250312,
                    "methanol": 211.0321396,
                    "thf": 211.2798891,
                    "toluene": 211.3499046,
                },
            },
        }
    }
    f_orca_shieldings = {
        "CFCl3": {
            "pbeh-3c": {
                "tpss": {
                    "gas": 166.028,
                    "acetone": 167.858,
                    "chcl3": 167.569,
                    "acetonitrile": 167.92,
                    "ch2cl2": 167.732,
                    "dmso": 167.992,
                    "h2o": 168.239,
                    "methanol": 167.889,
                    "thf": 167.737,
                    "toluene": 167.278,
                },
                "pbe0": {
                    "gas": 178.99,
                    "acetone": 181.086,
                    "chcl3": 180.741,
                    "acetonitrile": 181.154,
                    "ch2cl2": 180.939,
                    "dmso": 181.224,
                    "h2o": 181.464,
                    "methanol": 181.123,
                    "thf": 180.934,
                    "toluene": 180.377,
                },
                "dsd-blyp": {
                    "gas": 225.542,
                    "acetone": 227.877,
                    "chcl3": 227.478,
                    "acetonitrile": 227.949,
                    "ch2cl2": 227.712,
                    "dmso": 228.007,
                    "h2o": 228.213,
                    "methanol": 227.919,
                    "thf": 227.691,
                    "toluene": 227.033,
                },
                "wb97x": {
                    "gas": 193.433,
                    "acetone": 195.381,
                    "chcl3": 195.059,
                    "acetonitrile": 195.445,
                    "ch2cl2": 195.245,
                    "dmso": 195.508,
                    "h2o": 195.733,
                    "methanol": 195.415,
                    "thf": 195.239,
                    "toluene": 194.719,
                },
                "pbeh-3c": {
                    "gas": 224.834,
                    "acetone": 226.308,
                    "chcl3": 226.076,
                    "acetonitrile": 226.36,
                    "ch2cl2": 226.207,
                    "dmso": 226.424,
                    "h2o": 226.639,
                    "methanol": 226.333,
                    "thf": 226.215,
                    "toluene": 225.843,
                },
                "kt2": {
                    "gas": 144.178,
                    "acetone": 146.15,
                    "chcl3": 145.821,
                    "acetonitrile": 146.219,
                    "ch2cl2": 146.007,
                    "dmso": 146.298,
                    "h2o": 146.569,
                    "methanol": 146.185,
                    "thf": 146.012,
                    "toluene": 145.488,
                },
            },
            "b97-3c": {
                "tpss": {
                    "gas": 153.325,
                    "acetone": 153.259,
                    "chcl3": 152.987,
                    "acetonitrile": 153.326,
                    "ch2cl2": 153.137,
                    "dmso": 153.425,
                    "h2o": 153.729,
                    "methanol": 153.292,
                    "thf": 153.16,
                    "toluene": 152.731,
                },
                "pbe0": {
                    "gas": 167.245,
                    "acetone": 167.447,
                    "chcl3": 167.121,
                    "acetonitrile": 167.52,
                    "ch2cl2": 167.31,
                    "dmso": 167.626,
                    "h2o": 167.92,
                    "methanol": 167.486,
                    "thf": 167.322,
                    "toluene": 166.785,
                },
                "dsd-blyp": {
                    "gas": 216.287,
                    "acetone": 217.144,
                    "chcl3": 216.726,
                    "acetonitrile": 217.223,
                    "ch2cl2": 216.969,
                    "dmso": 217.304,
                    "h2o": 217.555,
                    "methanol": 217.19,
                    "thf": 216.957,
                    "toluene": 216.272,
                },
                "wb97x": {
                    "gas": 182.767,
                    "acetone": 182.921,
                    "chcl3": 182.602,
                    "acetonitrile": 182.99,
                    "ch2cl2": 182.783,
                    "dmso": 183.077,
                    "h2o": 183.351,
                    "methanol": 182.957,
                    "thf": 182.792,
                    "toluene": 182.279,
                },
                "pbeh-3c": {
                    "gas": 213.421,
                    "acetone": 213.215,
                    "chcl3": 212.997,
                    "acetonitrile": 213.271,
                    "ch2cl2": 213.116,
                    "dmso": 213.36,
                    "h2o": 213.627,
                    "methanol": 213.241,
                    "thf": 213.14,
                    "toluene": 212.796,
                },
                "kt2": {
                    "gas": 130.539,
                    "acetone": 130.291,
                    "chcl3": 130.081,
                    "acetonitrile": 130.364,
                    "ch2cl2": 130.242,
                    "dmso": 130.472,
                    "h2o": 130.803,
                    "methanol": 130.326,
                    "thf": 130.267,
                    "toluene": 129.808,
                },
            },
            "tpss": {
                "tpss": {
                    "gas": 148.387,
                    "acetone": 149.573,
                    "chcl3": 149.247,
                    "acetonitrile": 149.647,
                    "ch2cl2": 149.43,
                    "dmso": 149.748,
                    "h2o": 150.066,
                    "methanol": 149.609,
                    "thf": 149.446,
                    "toluene": 148.927,
                },
                "pbe0": {
                    "gas": 162.075,
                    "acetone": 163.638,
                    "chcl3": 163.239,
                    "acetonitrile": 163.71,
                    "ch2cl2": 163.472,
                    "dmso": 163.807,
                    "h2o": 164.125,
                    "methanol": 163.671,
                    "thf": 163.476,
                    "toluene": 162.835,
                },
                "dsd-blyp": {
                    "gas": 211.635,
                    "acetone": 213.66,
                    "chcl3": 213.199,
                    "acetonitrile": 213.746,
                    "ch2cl2": 213.469,
                    "dmso": 213.828,
                    "h2o": 214.092,
                    "methanol": 213.71,
                    "thf": 213.451,
                    "toluene": 212.692,
                },
                "wb97x": {
                    "gas": 177.986,
                    "acetone": 179.452,
                    "chcl3": 179.093,
                    "acetonitrile": 179.528,
                    "ch2cl2": 179.299,
                    "dmso": 179.616,
                    "h2o": 179.902,
                    "methanol": 179.491,
                    "thf": 179.302,
                    "toluene": 178.721,
                },
                "pbeh-3c": {
                    "gas": 208.73,
                    "acetone": 209.687,
                    "chcl3": 209.429,
                    "acetonitrile": 209.749,
                    "ch2cl2": 209.573,
                    "dmso": 209.825,
                    "h2o": 210.102,
                    "methanol": 209.716,
                    "thf": 209.592,
                    "toluene": 209.176,
                },
                "kt2": {
                    "gas": 124.897,
                    "acetone": 126.154,
                    "chcl3": 125.806,
                    "acetonitrile": 126.235,
                    "ch2cl2": 126.001,
                    "dmso": 126.345,
                    "h2o": 126.689,
                    "methanol": 126.193,
                    "thf": 126.019,
                    "toluene": 125.465,
                },
            },
        }
    }
    p_tm_shieldings = {
        "PH3": {
            "pbeh-3c": {
                "tpss": {
                    "gas": 560.9783608,
                    "acetone": 559.5567974,
                    "chcl3": 555.7297268,
                    "acetonitrile": 558.7420853,
                    "ch2cl2": 555.9207578,
                    "dmso": 559.0317956,
                    "h2o": 551.9868157,
                    "methanol": 557.7229598,
                    "thf": 559.4070044,
                    "toluene": 558.9538264,
                },
                "pbe0": {
                    "gas": 573.7889709,
                    "acetone": 572.6807308,
                    "chcl3": 568.6200619,
                    "acetonitrile": 572.0156003,
                    "ch2cl2": 568.6775273,
                    "dmso": 572.2984368,
                    "h2o": 564.8512663,
                    "methanol": 570.6948985,
                    "thf": 572.4491708,
                    "toluene": 572.2945282,
                },
                "pbeh-3c": {
                    "gas": 622.6149401,
                    "acetone": 624.221383,
                    "chcl3": 622.2460822,
                    "acetonitrile": 624.0839458,
                    "ch2cl2": 622.3660073,
                    "dmso": 623.8685076,
                    "h2o": 622.54767,
                    "methanol": 623.1569748,
                    "thf": 623.7253948,
                    "toluene": 623.2733775,
                },
            },
            "b97-3c": {
                "tpss": {
                    "gas": 559.5296772,
                    "acetone": 557.5438599,
                    "chcl3": 553.7653249,
                    "acetonitrile": 556.735552,
                    "ch2cl2": 554.1613395,
                    "dmso": 557.010476,
                    "h2o": 550.1185847,
                    "methanol": 555.82703,
                    "thf": 557.2207586,
                    "toluene": 556.8427805,
                },
                "pbe0": {
                    "gas": 572.4232552,
                    "acetone": 570.7398164,
                    "chcl3": 566.7271447,
                    "acetonitrile": 570.0779914,
                    "ch2cl2": 566.9826221,
                    "dmso": 570.3456887,
                    "h2o": 563.05667,
                    "methanol": 568.8622417,
                    "thf": 570.3305746,
                    "toluene": 570.2507738,
                },
                "pbeh-3c": {
                    "gas": 621.2286124,
                    "acetone": 622.356702,
                    "chcl3": 620.3365742,
                    "acetonitrile": 622.2263079,
                    "ch2cl2": 620.6570087,
                    "dmso": 621.9912341,
                    "h2o": 620.7021951,
                    "methanol": 621.3567408,
                    "thf": 621.7091401,
                    "toluene": 621.3088355,
                },
            },
            "tpss": {
                "tpss": {
                    "gas": 558.1589032,
                    "acetone": 556.5475548,
                    "chcl3": 553.3273579,
                    "acetonitrile": 555.6559443,
                    "ch2cl2": 553.600544,
                    "dmso": 556.0983125,
                    "h2o": 548.970911,
                    "methanol": 555.4535832,
                    "thf": 556.3191064,
                    "toluene": 555.9299261,
                },
                "pbe0": {
                    "gas": 571.012794,
                    "acetone": 569.7250563,
                    "chcl3": 566.2936179,
                    "acetonitrile": 568.9923465,
                    "ch2cl2": 566.4237381,
                    "dmso": 569.4236946,
                    "h2o": 561.898531,
                    "methanol": 568.4989088,
                    "thf": 569.4140377,
                    "toluene": 569.3191735,
                },
                "pbeh-3c": {
                    "gas": 620.0674752,
                    "acetone": 621.5116584,
                    "chcl3": 619.9397925,
                    "acetonitrile": 621.2898165,
                    "ch2cl2": 620.15928,
                    "dmso": 621.2154327,
                    "h2o": 619.7280828,
                    "methanol": 621.0126668,
                    "thf": 620.9449236,
                    "toluene": 620.5363442,
                },
            },
        },
        "TMP": {
            "pbeh-3c": {
                "tpss": {
                    "gas": 281.6302978,
                    "acetone": 265.4354914,
                    "chcl3": 257.5409613,
                    "acetonitrile": 263.2430698,
                    "ch2cl2": 257.0543221,
                    "dmso": 262.8752182,
                    "h2o": 242.4838211,
                    "methanol": 245.6431135,
                    "thf": 266.7188352,
                    "toluene": 269.0597797,
                },
                "pbe0": {
                    "gas": 277.8252556,
                    "acetone": 261.5502528,
                    "chcl3": 254.1109855,
                    "acetonitrile": 259.5059377,
                    "ch2cl2": 253.6358478,
                    "dmso": 258.7821425,
                    "h2o": 239.5329333,
                    "methanol": 242.1687948,
                    "thf": 262.8378646,
                    "toluene": 265.4050199,
                },
                "pbeh-3c": {
                    "gas": 390.6073841,
                    "acetone": 378.6668397,
                    "chcl3": 373.2000393,
                    "acetonitrile": 377.1343123,
                    "ch2cl2": 372.9163524,
                    "dmso": 376.6203422,
                    "h2o": 362.7163813,
                    "methanol": 364.8220379,
                    "thf": 379.5051748,
                    "toluene": 381.2789752,
                },
            },
            "b97-3c": {
                "tpss": {
                    "gas": 276.8654211,
                    "acetone": 259.8829696,
                    "chcl3": 251.5648819,
                    "acetonitrile": 257.7225804,
                    "ch2cl2": 251.0880934,
                    "dmso": 256.90761,
                    "h2o": 234.4800595,
                    "methanol": 237.4630709,
                    "thf": 261.291204,
                    "toluene": 263.9827571,
                },
                "pbe0": {
                    "gas": 273.0911933,
                    "acetone": 256.1507446,
                    "chcl3": 248.2072561,
                    "acetonitrile": 254.0571117,
                    "ch2cl2": 247.7513367,
                    "dmso": 253.0100842,
                    "h2o": 231.7425518,
                    "methanol": 234.1695454,
                    "thf": 257.4644157,
                    "toluene": 260.3717755,
                },
                "pbeh-3c": {
                    "gas": 386.2437698,
                    "acetone": 373.8145109,
                    "chcl3": 368.1719462,
                    "acetonitrile": 372.350904,
                    "ch2cl2": 367.8934403,
                    "dmso": 371.4995766,
                    "h2o": 355.9965281,
                    "methanol": 358.0517851,
                    "thf": 374.7716841,
                    "toluene": 376.8283779,
                },
            },
            "tpss": {
                "tpss": {
                    "gas": 278.0447826,
                    "acetone": 261.4382678,
                    "chcl3": 253.5317417,
                    "acetonitrile": 259.5831076,
                    "ch2cl2": 253.0735218,
                    "dmso": 258.8205488,
                    "h2o": 236.9938311,
                    "methanol": 240.0596152,
                    "thf": 262.646474,
                    "toluene": 265.5482099,
                },
                "pbe0": {
                    "gas": 274.1582231,
                    "acetone": 257.5976215,
                    "chcl3": 250.0455696,
                    "acetonitrile": 255.8739799,
                    "ch2cl2": 249.6032437,
                    "dmso": 254.7109046,
                    "h2o": 234.1066151,
                    "methanol": 236.6658834,
                    "thf": 258.6914971,
                    "toluene": 261.8410368,
                },
                "pbeh-3c": {
                    "gas": 387.4697022,
                    "acetone": 375.2569197,
                    "chcl3": 369.9533245,
                    "acetonitrile": 374.0256406,
                    "ch2cl2": 369.6688695,
                    "dmso": 373.1520781,
                    "h2o": 358.1827766,
                    "methanol": 360.3168296,
                    "thf": 376.0015788,
                    "toluene": 378.3153047,
                },
            },
        },
    }
    p_orca_shieldings = {
        "PH3": {
            "pbeh-3c": {
                "tpss": {
                    "gas": 578.49,
                    "acetone": 577.53,
                    "chcl3": 577.773,
                    "acetonitrile": 577.631,
                    "ch2cl2": 577.63,
                    "dmso": 577.688,
                    "h2o": 577.764,
                    "methanol": 577.506,
                    "thf": 577.671,
                    "toluene": 577.946,
                },
                "pbe0": {
                    "gas": 573.639,
                    "acetone": 573.637,
                    "chcl3": 573.71,
                    "acetonitrile": 573.764,
                    "ch2cl2": 573.67,
                    "dmso": 573.829,
                    "h2o": 573.914,
                    "methanol": 573.632,
                    "thf": 573.688,
                    "toluene": 573.665,
                },
                "dsd-blyp": {
                    "gas": 569.431,
                    "acetone": 567.575,
                    "chcl3": 567.994,
                    "acetonitrile": 567.65,
                    "ch2cl2": 567.746,
                    "dmso": 567.695,
                    "h2o": 567.745,
                    "methanol": 567.531,
                    "thf": 567.809,
                    "toluene": 568.372,
                },
                "wb97x": {
                    "gas": 568.27,
                    "acetone": 568.185,
                    "chcl3": 568.261,
                    "acetonitrile": 568.31,
                    "ch2cl2": 568.218,
                    "dmso": 568.375,
                    "h2o": 568.459,
                    "methanol": 568.18,
                    "thf": 568.236,
                    "toluene": 568.231,
                },
                "pbeh-3c": {
                    "gas": 622.505,
                    "acetone": 626.377,
                    "chcl3": 625.536,
                    "acetonitrile": 626.609,
                    "ch2cl2": 626.042,
                    "dmso": 626.709,
                    "h2o": 626.85,
                    "methanol": 626.48,
                    "thf": 625.933,
                    "toluene": 624.513,
                },
                "kt2": {
                    "gas": 587.254,
                    "acetone": 587.821,
                    "chcl3": 587.78,
                    "acetonitrile": 587.962,
                    "ch2cl2": 587.81,
                    "dmso": 588.032,
                    "h2o": 588.129,
                    "methanol": 587.829,
                    "thf": 587.812,
                    "toluene": 587.606,
                },
            },
            "b97-3c": {
                "tpss": {
                    "gas": 574.673,
                    "acetone": 575.587,
                    "chcl3": 575.672,
                    "acetonitrile": 575.6,
                    "ch2cl2": 575.619,
                    "dmso": 575.662,
                    "h2o": 575.948,
                    "methanol": 575.57,
                    "thf": 575.668,
                    "toluene": 575.8,
                },
                "pbe0": {
                    "gas": 569.721,
                    "acetone": 571.667,
                    "chcl3": 571.577,
                    "acetonitrile": 571.703,
                    "ch2cl2": 571.631,
                    "dmso": 571.774,
                    "h2o": 572.075,
                    "methanol": 571.67,
                    "thf": 571.656,
                    "toluene": 571.48,
                },
                "dsd-blyp": {
                    "gas": 565.936,
                    "acetone": 565.88,
                    "chcl3": 566.179,
                    "acetonitrile": 565.866,
                    "ch2cl2": 566.012,
                    "dmso": 565.915,
                    "h2o": 566.166,
                    "methanol": 565.843,
                    "thf": 566.084,
                    "toluene": 566.506,
                },
                "wb97x": {
                    "gas": 564.429,
                    "acetone": 566.244,
                    "chcl3": 566.161,
                    "acetonitrile": 566.279,
                    "ch2cl2": 566.206,
                    "dmso": 566.349,
                    "h2o": 566.646,
                    "methanol": 566.247,
                    "thf": 566.233,
                    "toluene": 566.086,
                },
                "pbeh-3c": {
                    "gas": 618.99,
                    "acetone": 624.483,
                    "chcl3": 623.499,
                    "acetonitrile": 624.639,
                    "ch2cl2": 624.087,
                    "dmso": 624.744,
                    "h2o": 625.072,
                    "methanol": 624.593,
                    "thf": 623.983,
                    "toluene": 622.448,
                },
                "kt2": {
                    "gas": 583.324,
                    "acetone": 585.797,
                    "chcl3": 585.592,
                    "acetonitrile": 585.848,
                    "ch2cl2": 585.715,
                    "dmso": 585.925,
                    "h2o": 586.235,
                    "methanol": 585.813,
                    "thf": 585.725,
                    "toluene": 585.371,
                },
            },
            "tpss": {
                "tpss": {
                    "gas": 574.839,
                    "acetone": 574.09,
                    "chcl3": 574.267,
                    "acetonitrile": 574.11,
                    "ch2cl2": 574.167,
                    "dmso": 574.166,
                    "h2o": 574.435,
                    "methanol": 574.084,
                    "thf": 574.22,
                    "toluene": 574.478,
                },
                "pbe0": {
                    "gas": 569.911,
                    "acetone": 570.088,
                    "chcl3": 570.127,
                    "acetonitrile": 570.133,
                    "ch2cl2": 570.135,
                    "dmso": 570.198,
                    "h2o": 570.482,
                    "methanol": 570.103,
                    "thf": 570.164,
                    "toluene": 570.119,
                },
                "dsd-blyp": {
                    "gas": 566.08,
                    "acetone": 564.411,
                    "chcl3": 564.793,
                    "acetonitrile": 564.406,
                    "ch2cl2": 564.583,
                    "dmso": 564.448,
                    "h2o": 564.684,
                    "methanol": 564.385,
                    "thf": 564.658,
                    "toluene": 565.213,
                },
                "wb97x": {
                    "gas": 564.63,
                    "acetone": 564.706,
                    "chcl3": 564.726,
                    "acetonitrile": 564.75,
                    "ch2cl2": 564.72,
                    "dmso": 564.813,
                    "h2o": 565.093,
                    "methanol": 564.721,
                    "thf": 564.752,
                    "toluene": 564.742,
                },
                "pbeh-3c": {
                    "gas": 619.182,
                    "acetone": 623.189,
                    "chcl3": 622.29,
                    "acetonitrile": 623.352,
                    "ch2cl2": 622.833,
                    "dmso": 623.451,
                    "h2o": 623.764,
                    "methanol": 623.308,
                    "thf": 622.734,
                    "toluene": 621.304,
                },
                "kt2": {
                    "gas": 583.522,
                    "acetone": 584.278,
                    "chcl3": 584.168,
                    "acetonitrile": 584.337,
                    "ch2cl2": 584.241,
                    "dmso": 584.407,
                    "h2o": 584.701,
                    "methanol": 584.305,
                    "thf": 584.256,
                    "toluene": 584.034,
                },
            },
        },
        "TMP": {
            "pbeh-3c": {
                "tpss": {
                    "gas": 291.33,
                    "acetone": 276.264,
                    "chcl3": 277.254,
                    "acetonitrile": 275.207,
                    "ch2cl2": 276.171,
                    "dmso": 276.988,
                    "h2o": 262.671,
                    "methanol": 263.366,
                    "thf": 278.685,
                    "toluene": 283.761,
                },
                "pbe0": {
                    "gas": 277.761,
                    "acetone": 262.673,
                    "chcl3": 263.634,
                    "acetonitrile": 261.631,
                    "ch2cl2": 262.58,
                    "dmso": 263.406,
                    "h2o": 249.27,
                    "methanol": 249.931,
                    "thf": 265.061,
                    "toluene": 270.123,
                },
                "dsd-blyp": {
                    "gas": 299.195,
                    "acetone": 286.35,
                    "chcl3": 287.213,
                    "acetonitrile": 285.469,
                    "ch2cl2": 286.302,
                    "dmso": 286.997,
                    "h2o": 274.843,
                    "methanol": 275.42,
                    "thf": 288.362,
                    "toluene": 292.724,
                },
                "wb97x": {
                    "gas": 277.52,
                    "acetone": 262.317,
                    "chcl3": 263.295,
                    "acetonitrile": 261.26,
                    "ch2cl2": 262.227,
                    "dmso": 263.036,
                    "h2o": 248.805,
                    "methanol": 249.485,
                    "thf": 264.716,
                    "toluene": 269.816,
                },
                "pbeh-3c": {
                    "gas": 390.602,
                    "acetone": 379.7,
                    "chcl3": 380.279,
                    "acetonitrile": 378.978,
                    "ch2cl2": 379.593,
                    "dmso": 380.317,
                    "h2o": 368.831,
                    "methanol": 369.216,
                    "thf": 381.391,
                    "toluene": 384.986,
                },
                "kt2": {
                    "gas": 297.198,
                    "acetone": 281.884,
                    "chcl3": 282.896,
                    "acetonitrile": 280.816,
                    "ch2cl2": 281.794,
                    "dmso": 282.606,
                    "h2o": 268.382,
                    "methanol": 269.076,
                    "thf": 284.334,
                    "toluene": 289.473,
                },
            },
            "b97-3c": {
                "tpss": {
                    "gas": 286.404,
                    "acetone": 270.748,
                    "chcl3": 271.725,
                    "acetonitrile": 269.462,
                    "ch2cl2": 270.524,
                    "dmso": 271.355,
                    "h2o": 256.342,
                    "methanol": 257.122,
                    "thf": 273.469,
                    "toluene": 278.676,
                },
                "pbe0": {
                    "gas": 272.706,
                    "acetone": 257.164,
                    "chcl3": 258.119,
                    "acetonitrile": 255.895,
                    "ch2cl2": 256.94,
                    "dmso": 257.797,
                    "h2o": 242.92,
                    "methanol": 243.667,
                    "thf": 259.855,
                    "toluene": 264.973,
                },
                "dsd-blyp": {
                    "gas": 294.405,
                    "acetone": 281.158,
                    "chcl3": 282.018,
                    "acetonitrile": 280.073,
                    "ch2cl2": 280.993,
                    "dmso": 281.703,
                    "h2o": 269.086,
                    "methanol": 269.737,
                    "thf": 283.464,
                    "toluene": 287.882,
                },
                "wb97x": {
                    "gas": 272.595,
                    "acetone": 256.861,
                    "chcl3": 257.836,
                    "acetonitrile": 255.578,
                    "ch2cl2": 256.643,
                    "dmso": 257.483,
                    "h2o": 242.627,
                    "methanol": 243.389,
                    "thf": 259.577,
                    "toluene": 264.773,
                },
                "pbeh-3c": {
                    "gas": 385.991,
                    "acetone": 374.828,
                    "chcl3": 375.394,
                    "acetonitrile": 373.92,
                    "ch2cl2": 374.61,
                    "dmso": 375.349,
                    "h2o": 363.431,
                    "methanol": 363.874,
                    "thf": 376.762,
                    "toluene": 380.401,
                },
                "kt2": {
                    "gas": 292.227,
                    "acetone": 276.414,
                    "chcl3": 277.413,
                    "acetonitrile": 275.12,
                    "ch2cl2": 276.191,
                    "dmso": 277.05,
                    "h2o": 262.135,
                    "methanol": 262.912,
                    "thf": 279.163,
                    "toluene": 284.4,
                },
            },
            "tpss": {
                "tpss": {
                    "gas": 286.331,
                    "acetone": 271.022,
                    "chcl3": 271.947,
                    "acetonitrile": 269.751,
                    "ch2cl2": 270.768,
                    "dmso": 271.616,
                    "h2o": 256.882,
                    "methanol": 257.6,
                    "thf": 273.659,
                    "toluene": 278.687,
                },
                "pbe0": {
                    "gas": 272.619,
                    "acetone": 257.298,
                    "chcl3": 258.198,
                    "acetonitrile": 256.053,
                    "ch2cl2": 257.051,
                    "dmso": 257.926,
                    "h2o": 243.408,
                    "methanol": 244.095,
                    "thf": 259.935,
                    "toluene": 264.977,
                },
                "dsd-blyp": {
                    "gas": 294.334,
                    "acetone": 281.319,
                    "chcl3": 282.131,
                    "acetonitrile": 280.265,
                    "ch2cl2": 281.144,
                    "dmso": 281.852,
                    "h2o": 269.472,
                    "methanol": 270.068,
                    "thf": 283.556,
                    "toluene": 287.875,
                },
                "wb97x": {
                    "gas": 272.586,
                    "acetone": 257.148,
                    "chcl3": 258.069,
                    "acetonitrile": 255.901,
                    "ch2cl2": 256.919,
                    "dmso": 257.755,
                    "h2o": 243.195,
                    "methanol": 243.894,
                    "thf": 259.785,
                    "toluene": 264.863,
                },
                "pbeh-3c": {
                    "gas": 385.897,
                    "acetone": 374.881,
                    "chcl3": 375.407,
                    "acetonitrile": 373.999,
                    "ch2cl2": 374.652,
                    "dmso": 375.391,
                    "h2o": 363.697,
                    "methanol": 364.097,
                    "thf": 376.757,
                    "toluene": 380.319,
                },
                "kt2": {
                    "gas": 292.105,
                    "acetone": 276.574,
                    "chcl3": 277.519,
                    "acetonitrile": 275.313,
                    "ch2cl2": 276.339,
                    "dmso": 277.197,
                    "h2o": 262.553,
                    "methanol": 263.276,
                    "thf": 279.247,
                    "toluene": 284.37,
                },
            },
        },
    }
    si_tm_shieldings = {
        "TMS": {
            "pbeh-3c": {
                "tpss": {
                    "gas": 334.2579542,
                    "acetone": 334.1639413,
                    "chcl3": 334.1459912,
                    "acetonitrile": 334.1644763,
                    "ch2cl2": 334.143167,
                    "dmso": 334.2355086,
                    "h2o": 334.1700712,
                    "methanol": 334.1638302,
                    "thf": 334.1765686,
                    "toluene": 334.1672644,
                },
                "pbe0": {
                    "gas": 332.1432161,
                    "acetone": 332.0806043,
                    "chcl3": 332.027555,
                    "acetonitrile": 332.070525,
                    "ch2cl2": 332.0181509,
                    "dmso": 332.1389588,
                    "h2o": 332.0768365,
                    "methanol": 332.082777,
                    "thf": 332.0989747,
                    "toluene": 332.0655251,
                },
                "pbeh-3c": {
                    "gas": 425.4500968,
                    "acetone": 425.4194168,
                    "chcl3": 425.3783658,
                    "acetonitrile": 425.4187809,
                    "ch2cl2": 425.3492293,
                    "dmso": 425.4302912,
                    "h2o": 425.4004059,
                    "methanol": 425.3865089,
                    "thf": 425.4157351,
                    "toluene": 425.4555181,
                },
            },
            "b97-3c": {
                "tpss": {
                    "gas": 334.5698984,
                    "acetone": 334.0803779,
                    "chcl3": 334.1093328,
                    "acetonitrile": 334.0665281,
                    "ch2cl2": 334.1280337,
                    "dmso": 334.1272572,
                    "h2o": 334.0495564,
                    "methanol": 334.1137413,
                    "thf": 334.1251606,
                    "toluene": 334.1235476,
                },
                "pbe0": {
                    "gas": 332.3546979,
                    "acetone": 331.9058869,
                    "chcl3": 331.8955148,
                    "acetonitrile": 331.8800833,
                    "ch2cl2": 331.9140658,
                    "dmso": 331.948424,
                    "h2o": 331.8617288,
                    "methanol": 331.9375391,
                    "thf": 331.9562723,
                    "toluene": 331.9253075,
                },
                "pbeh-3c": {
                    "gas": 426.0062656,
                    "acetone": 425.7811084,
                    "chcl3": 425.7602588,
                    "acetonitrile": 425.745999,
                    "ch2cl2": 425.7473718,
                    "dmso": 425.779427,
                    "h2o": 425.7365851,
                    "methanol": 425.7713265,
                    "thf": 425.7964293,
                    "toluene": 425.8200844,
                },
            },
            "tpss": {
                "tpss": {
                    "gas": 333.7779314,
                    "acetone": 333.3511708,
                    "chcl3": 333.3794838,
                    "acetonitrile": 333.3298692,
                    "ch2cl2": 333.3946486,
                    "dmso": 333.3881767,
                    "h2o": 333.3406562,
                    "methanol": 333.3784136,
                    "thf": 333.3860666,
                    "toluene": 333.3885135,
                },
                "pbe0": {
                    "gas": 331.5820841,
                    "acetone": 331.1904714,
                    "chcl3": 331.1839521,
                    "acetonitrile": 331.1565218,
                    "ch2cl2": 331.1982524,
                    "dmso": 331.2347884,
                    "h2o": 331.1670301,
                    "methanol": 331.2231923,
                    "thf": 331.2383692,
                    "toluene": 331.2108329,
                },
                "pbeh-3c": {
                    "gas": 425.0726297,
                    "acetone": 424.9009564,
                    "chcl3": 424.8706079,
                    "acetonitrile": 424.8831877,
                    "ch2cl2": 424.8554965,
                    "dmso": 424.9143792,
                    "h2o": 424.8579037,
                    "methanol": 424.8851226,
                    "thf": 424.9146175,
                    "toluene": 424.9330242,
                },
            },
        }
    }
    si_orca_shieldings = {
        "TMS": {
            "pbeh-3c": {
                "tpss": {
                    "gas": 344.281,
                    "acetone": 344.239,
                    "chcl3": 344.311,
                    "acetonitrile": 344.198,
                    "ch2cl2": 344.231,
                    "dmso": 344.292,
                    "h2o": 344.228,
                    "methanol": 344.291,
                    "thf": 344.283,
                    "toluene": 344.452,
                },
                "pbe0": {
                    "gas": 332.181,
                    "acetone": 332.067,
                    "chcl3": 332.162,
                    "acetonitrile": 332.033,
                    "ch2cl2": 332.082,
                    "dmso": 332.122,
                    "h2o": 332.048,
                    "methanol": 332.122,
                    "thf": 332.134,
                    "toluene": 332.298,
                },
                "dsd-blyp": {
                    "gas": 357.874,
                    "acetone": 357.762,
                    "chcl3": 357.864,
                    "acetonitrile": 357.726,
                    "ch2cl2": 357.783,
                    "dmso": 357.798,
                    "h2o": 357.715,
                    "methanol": 357.809,
                    "thf": 357.826,
                    "toluene": 358.001,
                },
                "wb97x": {
                    "gas": 335.739,
                    "acetone": 335.641,
                    "chcl3": 335.74,
                    "acetonitrile": 335.606,
                    "ch2cl2": 335.659,
                    "dmso": 335.687,
                    "h2o": 335.608,
                    "methanol": 335.692,
                    "thf": 335.707,
                    "toluene": 335.879,
                },
                "pbeh-3c": {
                    "gas": 425.385,
                    "acetone": 425.52,
                    "chcl3": 425.527,
                    "acetonitrile": 425.511,
                    "ch2cl2": 425.508,
                    "dmso": 425.578,
                    "h2o": 425.566,
                    "methanol": 425.557,
                    "thf": 425.54,
                    "toluene": 425.556,
                },
                "kt2": {
                    "gas": 341.186,
                    "acetone": 341.197,
                    "chcl3": 341.284,
                    "acetonitrile": 341.166,
                    "ch2cl2": 341.208,
                    "dmso": 341.263,
                    "h2o": 341.201,
                    "methanol": 341.253,
                    "thf": 341.263,
                    "toluene": 341.446,
                },
            },
            "b97-3c": {
                "tpss": {
                    "gas": 344.503,
                    "acetone": 344.558,
                    "chcl3": 344.676,
                    "acetonitrile": 344.487,
                    "ch2cl2": 344.537,
                    "dmso": 344.67,
                    "h2o": 344.542,
                    "methanol": 344.662,
                    "thf": 344.637,
                    "toluene": 344.919,
                },
                "pbe0": {
                    "gas": 332.338,
                    "acetone": 332.293,
                    "chcl3": 332.442,
                    "acetonitrile": 332.236,
                    "ch2cl2": 332.31,
                    "dmso": 332.4,
                    "h2o": 332.288,
                    "methanol": 332.392,
                    "thf": 332.403,
                    "toluene": 332.676,
                },
                "dsd-blyp": {
                    "gas": 357.729,
                    "acetone": 357.628,
                    "chcl3": 357.774,
                    "acetonitrile": 357.578,
                    "ch2cl2": 357.655,
                    "dmso": 357.692,
                    "h2o": 357.632,
                    "methanol": 357.703,
                    "thf": 357.725,
                    "toluene": 357.985,
                },
                "wb97x": {
                    "gas": 335.744,
                    "acetone": 335.688,
                    "chcl3": 335.837,
                    "acetonitrile": 335.633,
                    "ch2cl2": 335.71,
                    "dmso": 335.774,
                    "h2o": 335.704,
                    "methanol": 335.776,
                    "thf": 335.792,
                    "toluene": 336.064,
                },
                "pbeh-3c": {
                    "gas": 425.911,
                    "acetone": 426.14,
                    "chcl3": 426.185,
                    "acetonitrile": 426.113,
                    "ch2cl2": 426.124,
                    "dmso": 426.254,
                    "h2o": 426.162,
                    "methanol": 426.22,
                    "thf": 426.196,
                    "toluene": 426.294,
                },
                "kt2": {
                    "gas": 341.631,
                    "acetone": 341.666,
                    "chcl3": 341.811,
                    "acetonitrile": 341.61,
                    "ch2cl2": 341.676,
                    "dmso": 341.798,
                    "h2o": 341.602,
                    "methanol": 341.777,
                    "thf": 341.781,
                    "toluene": 342.086,
                },
            },
            "tpss": {
                "tpss": {
                    "gas": 343.24,
                    "acetone": 343.388,
                    "chcl3": 343.506,
                    "acetonitrile": 343.343,
                    "ch2cl2": 343.385,
                    "dmso": 343.48,
                    "h2o": 343.378,
                    "methanol": 343.47,
                    "thf": 343.449,
                    "toluene": 343.647,
                },
                "pbe0": {
                    "gas": 331.055,
                    "acetone": 331.217,
                    "chcl3": 331.313,
                    "acetonitrile": 331.175,
                    "ch2cl2": 331.224,
                    "dmso": 331.303,
                    "h2o": 331.205,
                    "methanol": 331.296,
                    "thf": 331.293,
                    "toluene": 331.461,
                },
                "dsd-blyp": {
                    "gas": 357.099,
                    "acetone": 357.125,
                    "chcl3": 357.231,
                    "acetonitrile": 357.081,
                    "ch2cl2": 357.141,
                    "dmso": 357.179,
                    "h2o": 357.075,
                    "methanol": 357.188,
                    "thf": 357.195,
                    "toluene": 357.379,
                },
                "wb97x": {
                    "gas": 334.802,
                    "acetone": 334.886,
                    "chcl3": 334.987,
                    "acetonitrile": 334.842,
                    "ch2cl2": 334.897,
                    "dmso": 334.957,
                    "h2o": 334.855,
                    "methanol": 334.958,
                    "thf": 334.959,
                    "toluene": 335.134,
                },
                "pbeh-3c": {
                    "gas": 424.346,
                    "acetone": 424.653,
                    "chcl3": 424.66,
                    "acetonitrile": 424.64,
                    "ch2cl2": 424.633,
                    "dmso": 424.74,
                    "h2o": 424.718,
                    "methanol": 424.709,
                    "thf": 424.681,
                    "toluene": 424.701,
                },
                "kt2": {
                    "gas": 340.026,
                    "acetone": 340.228,
                    "chcl3": 340.311,
                    "acetonitrile": 340.189,
                    "ch2cl2": 340.226,
                    "dmso": 340.332,
                    "h2o": 340.207,
                    "methanol": 340.311,
                    "thf": 340.302,
                    "toluene": 340.453,
                },
            },
        }
    }

    if config.solvent != "gas":
        # optimization in solvent:
        if config.prog == "tm" and config.sm2 == "cosmo":
            print(
                "WARNING: The geometry optimization of the reference molecule "
                "was calculated with DCOSMO-RS instead of COSMO as solvent "
                "model (sm2)!"
            )
        elif config.prog == "orca" and config.sm2 == "cpcm":
            print(
                "WARNING: The geometry optimization of the reference molecule "
                "was calculated with SMD instead of CPCM as solvent model (sm2)!"
            )
    if config.prog4_s == "tm":
        h_qm_shieldings = h_tm_shieldings
        c_qm_shieldings = c_tm_shieldings
        f_qm_shieldings = f_tm_shieldings
        p_qm_shieldings = p_tm_shieldings
        si_qm_shieldings = si_tm_shieldings
        lsm = "DCOSMO-RS"
        lsm4 = "DCOSMO-RS"
        lbasisS = "def2-TZVP"
        if config.sm4_s == "cosmo":
            print(
                "WARNING: The reference shielding constant was calculated with DCOSMORS "
                "instead of COSMO as solvent model (sm4_s)!"
            )
    elif config.prog4_s == "orca":
        lsm = "SMD"
        lsm4 = "SMD"
        lbasisS = "def2-TZVP"
        h_qm_shieldings = h_orca_shieldings
        c_qm_shieldings = c_orca_shieldings
        f_qm_shieldings = f_orca_shieldings
        p_qm_shieldings = p_orca_shieldings
        si_qm_shieldings = si_orca_shieldings
        if config.sm4_s == "cpcm":
            print(
                "WARNING: The reference shielding was calculated with SMD "
                "instead of CPCM as solvent model (sm4_2)!"
            )
    if config.func_s == "pbeh-3c":
        lbasisS = "def2-mSVP"

    if config.basis_s != "def2-TZVP" and config.func_s != "pbeh-3c":
        print(
            "WARNING: The reference shielding constant was calculated with the "
            "basis def2-TZVP (basisS)!"
        )
    if config.func == "r2scan-3c":
        print(
            "WARNING: The reference shielding constants is not available for r2scan-3c and b97-3c is used instead!"
        )
        opt_func = "b97-3c"
    else:
        opt_func = config.func

    # get absolute shielding constant of reference
    prnterr = False
    try:
        hshielding = "{:4.3f}".format(
            h_qm_shieldings[config.h_ref][opt_func][config.func_s][config.solvent]
        )
    except KeyError:
        hshielding = 0
        prnterr = True
    try:
        cshielding = "{:4.3f}".format(
            c_qm_shieldings[config.c_ref][opt_func][config.func_s][config.solvent]
        )
    except KeyError:
        cshielding = 0
        prnterr = True
    try:
        fshielding = "{:4.3f}".format(
            f_qm_shieldings[config.f_ref][opt_func][config.func_s][config.solvent]
        )
    except KeyError:
        fshielding = 0
        prnterr = True
    try:
        pshielding = "{:4.3f}".format(
            p_qm_shieldings[config.p_ref][opt_func][config.func_s][config.solvent]
        )
    except KeyError:
        pshielding = 0
        prnterr = True
    try:
        sishielding = "{:4.3f}".format(
            si_qm_shieldings[config.si_ref][opt_func][config.func_s][config.solvent]
        )
    except KeyError:
        sishielding = 0
        prnterr = True
    if prnterr:
        prnterr = (
            "ERROR! The reference absolute shielding constant "
            "could not be found!\n You have to edit the file"
            " .anmrrc by hand!"
        )
        print(prnterr)
    element_ref_shield = {
        "h": float(hshielding),
        "c": float(cshielding),
        "f": float(fshielding),
        "p": float(pshielding),
        "si": float(sishielding),
    }

    # for elementactive
    exch = {True: 1, False: 0}
    exchonoff = {True: "on", False: "off"}
    # write .anmrrc
    with open(os.path.join(config.cwd, ".anmrrc"), "w", newline=None) as arc:
        arc.write("7 8 XH acid atoms\n")
        if config.resonance_frequency is not None:
            arc.write(
                "ENSO qm= {} mf= {} lw= 1.0  J= {} S= {} T= {:6.2f} \n".format(
                    str(config.prog4_s).upper(),
                    str(config.resonance_frequency),
                    exchonoff[config.couplings],
                    exchonoff[config.shieldings],
                    float(config.temperature),
                )
            )
        else:
            arc.write("ENSO qm= {} lw= 1.2\n".format(str(config.prog4_s).upper()))
        try:
            length = max(
                [
                    len(i)
                    for i in [
                        hshielding,
                        cshielding,
                        fshielding,
                        pshielding,
                        sishielding,
                    ]
                ]
            )
        except:
            length = 6
        # lsm4 --> localsm4 ...
        arc.write(
            "{}[{}] {}[{}]/{}//{}[{}]/{}\n".format(
                config.h_ref,
                config.solvent,
                config.func_s,
                lsm4,
                lbasisS,
                opt_func,
                lsm,
                config.basis,
            )
        )
        arc.write(
            "1  {:{digits}}    0.0    {}\n".format(
                hshielding, exch[config.h_active], digits=length
            )
        )  # hydrogen
        arc.write(
            "6  {:{digits}}    0.0    {}\n".format(
                cshielding, exch[config.c_active], digits=length
            )
        )  # carbon
        arc.write(
            "9  {:{digits}}    0.0    {}\n".format(
                fshielding, exch[config.f_active], digits=length
            )
        )  # fluorine
        arc.write(
            "14 {:{digits}}    0.0    {}\n".format(
                sishielding, exch[config.si_active], digits=length
            )
        )  # silicon
        arc.write(
            "15 {:{digits}}    0.0    {}\n".format(
                pshielding, exch[config.p_active], digits=length
            )
        )  # phosphorus
    return element_ref_shield

def print_errors(line, save_errors):
    """print line and append to list save_errors"""
    print(line)
    try:
        save_errors.append(line)
    except:
        pass