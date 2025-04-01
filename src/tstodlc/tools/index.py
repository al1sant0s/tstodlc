import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from colorama import Fore, Style

from tstodlc.tools.progress import colorprint


def GetItemfromDict(dic, key, default):
    if key in dic.keys():
        return dic[key]
    else:
        return default


def GetSubElementAttributes(root, subelement):
    subelement = root.find(subelement)
    if subelement is not None:
        return subelement.attrib
    else:
        return dict()


def SearchPackages(root, filename):
    return [
        package
        for package in root.findall("Package")
        if GetItemfromDict(GetSubElementAttributes(package, "FileName"), "val", None)
        == filename
    ]


def GetXmlFromFile(index_file, root_tag):
    if index_file.exists() is True:
        if index_file.suffix == ".zip":
            with tempfile.TemporaryDirectory() as tempdir:
                with ZipFile(index_file, strict_timestamps=False) as ZObject:
                    ZObject.extractall(path=Path(tempdir, "extracted"))
                    xml_file = Path(
                        tempdir,
                        "extracted",
                        index_file.stem + ".xml",
                    )
                    if xml_file.exists() is True:
                        tree = ET.parse(xml_file)
                        if tree.getroot().tag == root_tag:
                            return tree
                        else:
                            return ET.ElementTree(ET.Element(root_tag))
                    else:
                        return ET.ElementTree(ET.Element(root_tag))
        elif index_file.suffix == ".xml":
            tree = ET.parse(index_file)
            if tree.getroot().tag == root_tag:
                return tree
            else:
                return ET.ElementTree(ET.Element(root_tag))
        else:
            return ET.ElementTree(ET.Element(root_tag))
    else:
        return ET.ElementTree(ET.Element(root_tag))


def GetIndexTree(index_file, root_tag):
    index_tree = GetXmlFromFile(index_file, root_tag)
    return index_tree


def UpdatePackageEntry(
    root,
    platform,
    minVersion,
    tier,
    filesize,
    unc_filesize,
    index_crc,
    filename,
    language,
):
    # Grab existing packages.
    packages = SearchPackages(root, filename)

    # Introduce new package if not a single one was found.
    if len(packages) == 0:
        packages = [ET.Element("Package")]
        root.insert(0, packages[0])

    # Update packages details.
    for pkg in packages:
        (
            pkg.set(
                "platform",
                platform
                if platform is not None
                else GetItemfromDict(pkg.attrib, "platform", "all"),
            ),
        )
        (
            pkg.set(
                "unzip",
                GetItemfromDict(pkg.attrib, "unzip", "false"),
            ),
        )
        (
            pkg.set(
                "minVersion",
                minVersion
                if minVersion is not None
                else GetItemfromDict(pkg.attrib, "minVersion", "4.69.0"),
            ),
        )
        (
            pkg.set(
                "tier",
                tier
                if tier is not None
                else GetItemfromDict(pkg.attrib, "tier", "all"),
            ),
        )
        (
            pkg.set(
                "xml",
                GetItemfromDict(pkg.attrib, "xml", ""),
            ),
        )
        (
            pkg.set(
                "type",
                GetItemfromDict(pkg.attrib, "type", ""),
            ),
        )
        pkg.set(
            "ignore",
            GetItemfromDict(pkg.attrib, "ignore", "false"),
        )

        subelements = {
            "LocalDir": {"name": "dlc"}
            if pkg.find("LocalDir") is None
            else GetSubElementAttributes(pkg, "LocalDir"),
            "FileSize": {"val": filesize},
            "UncompressedFileSize": {"val": unc_filesize},
            "IndexFileCRC": {"val": index_crc},
            "IndexFileSig": {"val": "You should patch the APK/IPA to bypass this!"}
            if pkg.find("IndexFileSig") is None
            else GetSubElementAttributes(pkg, "IndexFileSig"),
            "Version": {"val": "1"}
            if pkg.find("Version") is None
            else GetSubElementAttributes(pkg, "Version"),
            "FileName": {"val": filename},
            "Language": {"val": language}
            if language is not None
            else GetSubElementAttributes(pkg, "Language")
            if pkg.find("Language") is not None
            else {"val": "all"},
        }

        for key, value in subelements.items():
            target = pkg.find(key)
            if target is not None:
                target.attrib = value
            else:
                ET.SubElement(pkg, key, attrib=value)


def GetServerIndexTree(dlc_dlc, root):
    master_index_zip = Path(dlc_dlc, "DLCIndex.zip")
    if master_index_zip.exists():
        with tempfile.TemporaryDirectory() as tempdir:
            with ZipFile(master_index_zip, strict_timestamps=False) as ZObject:
                ZObject.extractall(path=Path(tempdir, "extracted"))
                master_index = Path(tempdir, "extracted", "DLCIndex.xml")
                master_tree = GetXmlFromFile(master_index, "MasterDLCIndex")
                index_file_element = master_tree.getroot().find("IndexFile")
                if index_file_element is not None:
                    server_index = index_file_element.get("index")
                    if server_index is not None:
                        server_index = Path(dlc_dlc, server_index.split(":")[-1])
                        server_tree = GetXmlFromFile(server_index, root)
                        return (server_index, server_tree)
    return (None, None)


def WriteServerTree(server_index, server_tree):
    with tempfile.TemporaryDirectory() as tempdir:
        server_index_xml = Path(tempdir, server_index.stem + ".xml")
        with open(server_index_xml, "wb") as xml_file:
            server_tree.write(xml_file)
            zip_file = server_index
            with ZipFile(zip_file, "w", ZIP_DEFLATED, strict_timestamps=False) as zip:
                zip.write(server_index_xml, arcname=server_index_xml.name)


def UpdateServerIndex(index_file, dlc_dlc, directories_names, branches):
    if index_file.exists() is True:
        tree = ET.parse(index_file)
        # Check if server DLCIndex.zip can be found. If it can, grab dlc_index file from there.
        server_index, server_tree = GetServerIndexTree(dlc_dlc, "DlcIndex")
        if server_index is not None and server_tree is not None:
            local_root = tree.getroot()
            server_root = server_tree.getroot()
            for branch in branches:
                tree_branch = (
                    local_root if branch == local_root.tag else tree.find(branch)
                )
                server_branch = (
                    server_root
                    if branch == server_root.tag
                    else server_tree.find(branch)
                )
                if tree_branch is not None and server_branch is not None:
                    # Grab existing packages.
                    local_packages = [
                        package
                        for package in tree_branch.findall("Package")
                        if Path(
                            GetItemfromDict(
                                GetSubElementAttributes(package, "FileName"),
                                "val",
                                "",
                            ).split(":", maxsplit=1)[-1]
                        ).stem
                        in directories_names
                    ]

                    # Update server packages.
                    for pkg in local_packages:
                        server_packages = SearchPackages(
                            server_branch,
                            GetItemfromDict(
                                GetSubElementAttributes(pkg, "FileName"),
                                "val",
                                "NOT DEFINED!",
                            ),
                        )
                        if len(server_packages) == 0:
                            UpdatePackageEntry(
                                server_branch,
                                pkg.get("platform"),
                                pkg.get("minVersion"),
                                pkg.get("tier"),
                                GetItemfromDict(
                                    GetSubElementAttributes(pkg, "FileSize"),
                                    "val",
                                    "NOT DEFINED!",
                                ),
                                GetItemfromDict(
                                    GetSubElementAttributes(
                                        pkg, "UncompressedFileSize"
                                    ),
                                    "val",
                                    "NOT DEFINED!",
                                ),
                                GetItemfromDict(
                                    GetSubElementAttributes(pkg, "IndexFileCRC"),
                                    "val",
                                    "NOT DEFINED!",
                                ),
                                GetItemfromDict(
                                    GetSubElementAttributes(pkg, "FileName"),
                                    "val",
                                    "NOT DEFINED!",
                                ),
                                None,
                            )
                        else:
                            for server_pkg in server_packages:
                                server_branch.remove(server_pkg)
                            server_branch.insert(0, pkg)

            ET.indent(server_tree, "  ")
            WriteServerTree(server_index, server_tree)
            return (True, server_index.name)

        else:
            return (False, None)
    else:
        return (False, None)


def RemoveDeadPackages(dlc_root, branches):
    server_index, server_tree = GetServerIndexTree(Path(dlc_root, "dlc"), "DlcIndex")
    removed = False
    if server_index is not None and server_tree is not None:
        server_root = server_tree.getroot()
        for branch in branches:
            server_branch = (
                server_root if branch == server_root.tag else server_tree.find(branch)
            )
            if server_branch is not None:
                colorprint(
                    Style.BRIGHT + Fore.CYAN, f"* Checking <{server_branch.tag}>"
                )
                for pkg in server_branch.findall("Package"):
                    filename = GetItemfromDict(
                        GetSubElementAttributes(pkg, "FileName"), "val", None
                    )
                    if filename is not None:
                        filename = filename.replace(":", os.sep)
                        filename = Path(dlc_root, filename)
                        if filename.exists() is False:
                            colorprint(
                                Style.BRIGHT + Fore.YELLOW,
                                f"- {filename.relative_to(dlc_root)} was not found!",
                            )
                            server_branch.remove(pkg)
                            removed = True

        WriteServerTree(server_index, server_tree)
        if removed is True:
            colorprint(
                Style.BRIGHT + Fore.GREEN,
                f"\n-> All packages listed above were removed from {server_index.name}!",
            )
        else:
            colorprint(Style.BRIGHT + Fore.GREEN, "-> Nothing to clean!")
    else:
        colorprint(Style.BRIGHT + Fore.RED, "-> Server DLCIndex was not found!")
