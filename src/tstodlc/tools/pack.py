import argparse
import zlib
import tempfile
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from colorama import Fore, Style, init
from tstodlc.tools.index import (
    RemoveDeadPackages,
    UpdatePackageEntry,
    GetIndexTree,
    UpdateServerIndex,
)
from tstodlc.tools.progress import report_progress, colorprint


def progress_str(n, total, message):
    return (
        message
        + Style.BRIGHT
        + Fore.CYAN
        + f"- Progress ({n * 100 / total:.2f}%)"
        + Style.RESET_ALL
    )


def write_str_to_file(file_descriptor, str_name):
    # String length.
    skip = len(str_name) + 1
    file_descriptor.write(skip.to_bytes())

    # String.
    file_descriptor.write(str_name.encode())
    file_descriptor.write(b"\x00")


def main():
    init()
    parser = argparse.ArgumentParser(
        description="""
        This is a simple script for packaging files for usage with "The Simpsons: Tapped Out" game.
        It receives a list of directories containing the files, with the last provided directory being
        the directory where the results will be stored. The files are packed into 1 file
        and the 0 file is created accordingly.
        """,
        # formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--platform",
        help="Specify platform attribute for package entries.",
    )

    parser.add_argument(
        "--version",
        help="Specify version attribute for package entries.",
    )

    parser.add_argument(
        "--tier",
        help="Specify tier attribute for package entries.",
    )

    parser.add_argument(
        "--language",
        help="Specify language for package entries.",
    )

    parser.add_argument(
        "--initial",
        help="Specify whether packages should be installed along with initial packages.",
        action="store_true",
    )

    parser.add_argument(
        "--tutorial",
        help="Specify whether packages should be installed along with tutorial packages.",
        action="store_true",
    )

    parser.add_argument(
        "--priority",
        help="""
        Priority value!
        If two files in game have the same names, the file with the bigger value associated
        with it within 0 file will take precedence on usage by the game.
        Audios, textpools, gamescripts and non graphical elements usually uses 1.
        """,
        type=int,
    )

    parser.add_argument(
        "--index_only",
        help="Update DLCIndex-XXXX.xml and server DLCIndex-XXXX.xml only without patching the files again.",
        action="store_true",
    )

    parser.add_argument(
        "--unzip",
        help="Do not zip the subfolders when installing the dlc. Useful for editing files from the apk.",
        action="store_true",
    )

    parser.add_argument(
        "--clean",
        help="""
        Remove non existing packages from server DLCIndex-XXXX.xml.
        When --clean is requested, normal operations (packing dlcs and such) will not happen.

        Suggestion of usage:

        tstodlc --clean . /path/to/server_dlc_directory
        """,
        action="store_true",
    )

    parser.add_argument(
        "input_dir",
        help="List of directories containing the dlc files.",
        nargs="+",
    )

    parser.add_argument(
        "dlc_dir",
        help="Directory where results will be stored.",
    )

    args = parser.parse_args()

    # Normal operation.
    if args.clean is False:
        colorprint(
            Style.BRIGHT + Fore.MAGENTA,
            "\n\n--- PACKING FILES INTO 0 and 1 FILES ---\n",
        )

        # List of input directories.
        directories = [Path(item) for item in args.input_dir]

        # Help with the progress report.
        n = 0
        total = sum(
            (len(list(Path(directory).glob("*/"))) for directory in args.input_dir)
        )

        if total == 0:
            colorprint(
                Style.BRIGHT + Fore.RED,
                "-> Warning! No subdirectories found under the arguments you have provided.",
            )
            colorprint(
                Style.BRIGHT + Fore.YELLOW,
                """
                \r-  Remember that you should specify your dlc directories.
                \r-  That means that each dlc should be a directory.

                \r-  Within each dlc (each directory) there should be subdirectories
                \r-  corresponding to dlc components.

                \r-  Within these subdirectories there should be the files corresponding to
                \r-  that dlc component.
                """,
            )
            colorprint(
                Style.BRIGHT + Fore.CYAN,
                "-> An example is given bellow with a dlc that is named 'SuperSecretUpdate'.\n",
            )
            colorprint(
                Style.BRIGHT + Fore.WHITE,
                "$  tstodlc SuperSecretUpdate/ /path/to/server/dlc/\n",
            )
            colorprint(
                Style.BRIGHT + Fore.CYAN,
                "** The contents of the ilustrated SuperSecretUpdate directory are shown bellow.\n",
            )
            colorprint(Style.BRIGHT + Fore.WHITE, "\t - SuperSecretUpdate/", "")
            colorprint(Style.BRIGHT + Fore.WHITE, "\t\t - textpools-pt/", "")
            colorprint(Style.BRIGHT + Fore.WHITE, "\t\t - textpools-en/", "")
            colorprint(Style.BRIGHT + Fore.WHITE, "\t\t - buildings/", "")
            colorprint(Style.BRIGHT + Fore.WHITE, "\t\t - decorations/", "")
            colorprint(Style.BRIGHT + Fore.WHITE, "\t\t - buildings-menu/", "")
            colorprint(Style.BRIGHT + Fore.WHITE, "\t\t - decorations-menu/", "\n\n")
            return

        # Set destination of dlc files.
        target_dir = Path(args.dlc_dir)
        target_dir.mkdir(exist_ok=True)

        # Start looking at each subpackage.
        for directory in directories:
            if directory.is_dir() is False:
                report_progress(
                    progress_str(
                        n,
                        total,
                        Style.BRIGHT
                        + Fore.RED
                        + "Warning! "
                        + f"{directory}"
                        + Style.RESET_ALL
                        + Style.BRIGHT
                        + Fore.RED
                        + " is not a directory.\n"
                        + Style.RESET_ALL,
                    ),
                    "",
                )
                continue

            # Subdirectory in dlc.
            subtarget_dir = Path(target_dir, directory.name)
            subtarget_dir.mkdir(exist_ok=True)

            colorprint(
                Style.BRIGHT + Fore.LIGHTBLUE_EX,
                f"- Archive: {subtarget_dir.relative_to(subtarget_dir.parent.parent)}:",
            )

            # Start of DLCIndex file.
            dlc_index_file = Path(directory, f"DLCIndex-{subtarget_dir.name}.xml")

            tree = GetIndexTree(dlc_index_file, "DlcIndex")
            root = tree.getroot()
            root_list = [root]

            # Create InitialPackages tag.
            if root.find("InitialPackages") is not None:
                root_list.append(root.find("InitialPackages"))
            elif args.initial is True:
                root_list.append(ET.SubElement(root, "InitialPackages"))

            # Create TutorialPackages tag.
            if root.find("TutorialPackages") is not None:
                root_list.append(root.find("TutorialPackages"))
            elif args.tutorial is True:
                root_list.append(ET.SubElement(root, "TutorialPackages"))

            if args.index_only is False:
                for subdirectory in (
                    subdirectory
                    for subdirectory in directory.glob("*")
                    if subdirectory.is_dir() is True
                ):
                    # Only install subdirectory if it has changed it in destination subdirectory or --priority has been set.
                    subpath = Path(
                        subtarget_dir,
                        subdirectory.name + ("" if args.unzip is True else ".zip"),
                    )
                    if (
                        subpath.exists() is True
                        and args.priority is None
                        and subdirectory.stat().st_mtime_ns < subpath.stat().st_mtime_ns
                    ):
                        n += 1
                        report_progress(
                            progress_str(
                                n,
                                total,
                                Style.BRIGHT
                                + Fore.WHITE
                                + f"- {subdirectory.name} has not changed since last time!\n"
                                + Style.RESET_ALL,
                            ),
                            "",
                        )

                        continue

                    with tempfile.TemporaryDirectory() as tempdir:
                        # Main files.
                        file_0 = Path(tempdir, "0")
                        file_1 = Path(tempdir, "1")

                        # Get files in current directory.
                        files = [
                            i for i in subdirectory.glob("*") if i.is_dir() is False
                        ]

                        # No files at all. Do nothing!
                        if len(files) == 0:
                            colorprint(
                                Style.BRIGHT + Fore.RED,
                                f"Warning! No files found at {subdirectory}. Skipping to next subdirectory!",
                            )
                            continue

                        # Zip all files into file_1.
                        with ZipFile(file_1, "w", ZIP_DEFLATED) as zip:
                            for file in files:
                                zip.write(file, arcname=file.name)

                        with open(file_0, "wb") as f0:
                            # Write 0 file signature.
                            f0.write(b"\x42\x47\x72\x6d\x03\x02")

                            # Reserve 4 bytes for 0 file size.
                            # Fill it up later.
                            f0.write(b"\x00\x00\x00\x00")

                            # Biggest amount of allocated bytes.
                            longest_filename = sorted(
                                [file.name for file in files], key=len, reverse=True
                            )[0]
                            longest_length = (
                                len(longest_filename) * 2
                                + len(Path(longest_filename).suffix[1:])
                                + 14
                            )
                            f0.write(longest_length.to_bytes(length=2))

                            f0.write(b"\x00")

                            # Full filepath.
                            write_str_to_file(f0, str(subdirectory.name) + "/1")

                            # Number of zipped files and allocated space for filename and crc32.
                            f0.write(b"\x00\x01\x00\x08")

                            # 1 filename.
                            write_str_to_file(f0, file_1.stem)

                            # Unknown but doesn't seem to change between files.
                            f0.write(b"\x01")

                            # File 1 crc32.
                            with open(file_1, "rb") as f1:
                                f0.write(
                                    (zlib.crc32(f1.read()) & 0xFFFFFFFF).to_bytes(
                                        length=4
                                    )
                                )

                            # Number of files.
                            f0.write(len(files).to_bytes(length=2))

                            for file in files:
                                # File skip.
                                skip = 2 * len(file.name) + len(file.suffix[1:]) + 14
                                f0.write(skip.to_bytes(length=2))

                                # Filename, extension, internal filename, file size.
                                write_str_to_file(f0, file.name)
                                write_str_to_file(f0, file.suffix[1:])
                                write_str_to_file(f0, file.name)
                                file_size = file.stat().st_size
                                f0.write(file_size.to_bytes(length=4))

                                # Priority value or build number value.
                                # If two files define the same filenames, the file with the bigger value associated
                                # with it within 0 file will take precedence on usage by the game.
                                # Audios, textpools, gamescripts and non graphical elements usually utilizes 0x0001.
                                f0.write(
                                    b"\x00\x01"
                                    if args.priority is None
                                    else args.priority.to_bytes(length=2)
                                )

                                # Unknown but doesn't seem to change between files.
                                f0.write(b"\x00\x00")

                            # Write 0 file size.
                            f0_size = f0.tell() + 4
                            f0.seek(6)
                            f0.write(f0_size.to_bytes(length=4))

                        # Partial file 0 crc32.
                        with open(file_0, "rb+") as f0:
                            file_0_crc32 = zlib.crc32(f0.read()) & 0xFFFFFFFF
                            f0.write(file_0_crc32.to_bytes(length=4))

                        files = [i for i in Path(tempdir).glob("*") if not i.is_dir()]
                        if args.unzip is True:
                            pkg_dir = Path(subtarget_dir, subdirectory.name)
                            pkg_dir.mkdir(exist_ok=True)

                            for file in files:
                                shutil.copy(file, pkg_dir)

                            # Added file.
                            n += 1

                            report_progress(
                                progress_str(
                                    n,
                                    total,
                                    Style.BRIGHT
                                    + Fore.YELLOW
                                    + f"- Added directory: {subdirectory}\n"
                                    + Style.RESET_ALL,
                                ),
                                "",
                            )
                            pass
                        else:
                            zip_file = Path(subtarget_dir, f"{subdirectory.name}.zip")
                            with ZipFile(zip_file, "w", ZIP_DEFLATED) as zip:
                                for file in files:
                                    zip.write(file, arcname=file.name)

                            # Complete file 0 crc32.
                            with open(file_0, "rb") as f0:
                                file_0_crc32 = zlib.crc32(f0.read()) & 0xFFFFFFFF

                            filename = (
                                str(
                                    Path(subtarget_dir.name, f"{subdirectory.name}")
                                ).replace("/", ":", count=1)
                                + ".zip"
                            )

                            # Add/Update Package in DLCIndex.xml.
                            for root in root_list:
                                UpdatePackageEntry(
                                    root,
                                    args.platform,
                                    args.version,
                                    args.tier,
                                    str(zip_file.stat().st_size // 1000),
                                    str(file_1.stat().st_size // 1000),
                                    str(file_0_crc32),
                                    filename,
                                    args.language,
                                )

                            # Added file.
                            n += 1

                            report_progress(
                                progress_str(
                                    n,
                                    total,
                                    Style.BRIGHT
                                    + Fore.YELLOW
                                    + f"- Added file: {subdirectory}.zip\n"
                                    + Style.RESET_ALL,
                                ),
                                "",
                            )

                colorprint(
                    Style.BRIGHT + Fore.GREEN,
                    f"\n\n-> Sucessfully instaled files listed above in {subtarget_dir.relative_to(subtarget_dir.parent.parent)}!",
                )

            if args.unzip is False:
                # Write local tree.
                ET.indent(tree, "  ")
                with open(
                    Path(dlc_index_file.parent, dlc_index_file.stem + ".xml"), "wb"
                ) as xml_file:
                    tree.write(xml_file)

                # Update server tree if possible.
                update_status, server_index = UpdateServerIndex(
                    dlc_index_file,
                    Path(args.dlc_dir, "dlc"),
                    [
                        subdirectory.name
                        for subdirectory in directory.glob("*")
                        if subdirectory.is_dir() is True
                    ],
                    [root.tag for root in root_list],
                )
                if update_status is True:
                    colorprint(
                        Style.BRIGHT + Fore.GREEN, f"-> Updated: {server_index}!"
                    )

    # Cleaning dead packages.
    else:
        colorprint(
            Style.BRIGHT + Fore.MAGENTA,
            "\n\n--- CLEANING MISSING PACKAGES FROM SERVER DLCIndex ---\n\n",
        )
        RemoveDeadPackages(
            Path(args.dlc_dir), ["DlcIndex", "InitialPackages", "TutorialPackages"]
        )

    colorprint(Style.BRIGHT + Fore.MAGENTA, "\n--- JOB COMPLETED!!! ---\n")
