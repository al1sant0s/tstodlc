# Create and install dlcs in your TSTO server

This tool allows you to create dlcs and implement them into your TSTO server.
It will pack your files into the required 0 and 1 files, zip and copy them over
to your dlc folder and automatically update the required index files so the game will
download them once you log into your server.

## Basic usage

Before you can use the tool you first have to make sure that your dlcs follow a basic structure.
Basically, you should have a directory with the name of your dlc and within
this directory you should have subdirectories that each correspond to a specific component of your dlc.

For example, suppose you are creating a dlc and want to name it SuperSecretUpdate. You decide that this dlcs
will bring textpools for two languages (portuguese and english), some buildings, some decorations and the necessary
menu icons for those last two. Then, in your working directory you will have your dlc structure similar to the following scheme:

* SuperSecretUpdate/
  * buildings/
  * decorations/
  * buildings-menu/
  * decorations-menu/
  * textpools-pt/
  * textpools-en/

Do notice that the names of the root directory (dlc directory) and subdirectories (dlc components)
do not matter and you can name them whatever you wish to. In those subdirectories you will place the files
you need to. For example: the buildings, decorations and menu subdirectories will probably contain rgb,
bsv3 and xml files. It's up to you to decide which files should go on which places.

After you have done the manual job of creating and adding the required the files to compose your dlc,
it's time to pack the files and install them onto your server. This is as simple as running the following
command on the command-line interface:

```shell
tstodlc /path/to/SuperSecretUpdate /path/to/server/dlc/
```

In this situation you would replace /path/to/SuperSecretUpdate/ with the real relative or absolute directory path
to your dlc folder, in this example named to "SuperSecretUpdate". Similarly, /path/to/server/dlc/ would refer to
the actual path to your server dlc repository (the places where all the dlcs are).

If you do this correctly, a new directory under /path/to/server/dlc/ will be created with the same name you've used for your dlc
directory, in this example a new directory named SuperSecretUpdate would be made. The subdirectories would be zipped and placed into
this new directory. Finally, the tool will find and update the necessary DLCIndex_XXXX.zip file (more on that bellow).

## Updating package entries

Before proceeding, let's make some notation clear. We will refer to two kinds of files here, DLCIndex.zip and DLCIndex_XXXX.zip
(the extra X's are just a placeholder for whatever comes after the underscore).

Before getting into more details, we need to explain how the game retrieves dlcs from the server. When the game starts connecting to the server
it will require several things. One of those things is a file called DLCIndex.zip, this file defines a lot of stuff and points to another file
called DLCIndex_XXXX.zip (the X's here are just a placeholder for whatever comes after the underscore). The dlcs your game will actually download
are defined in a list contained in the file DLCIndex_XXXX.zip. So for a new dlc be recognized by the server and be downloaded by your game, it
needs to be within this list as well.

That means that for the game to recognize the dlcs, each dlc component needs to be
written as a package entry onto the required DLCIndex_XXXX.zip file.
As explained before, the tool will do this automatically for you
(as long as you have installed the dlc into the server dlc repository).

However, since the tool does not know which settings to apply for those package
entries, it will write them with some default values. If you wish to easily
update those values you can, by editing the DLCIndex_NameOfYourDlcDirectory.xml file that will be made into your
original dlc directory once you install the dlc.

In the context of the example that we are showing, you will have the following scheme now,
just after running the previous command to install the SuperSecretUpdate dlc:

* SuperSecretUpdate/
  * buildings/
  * decorations/
  * buildings-menu/
  * decorations-menu/
  * textpools-pt/
  * textpools-en/
  * DLCIndex_SuperSecretUpdate.xml

You can edit the attributes and parameters in DLCIndex_SuperSecretUpdate.xml and
then save it. After that, just run the following command to update the values in
the server DLCIndex_XXXX.zip file.

```shell
tstodlc --index_only /path/to/SuperSecretUpdate /path/to/server/dlc/
```

The --index_only argument will tell tstodlc to just update the DLCIndex_XXXX.zip
file and not reinstall the dlc again. If --index_only was not specified, tstodlc
would reinstall the dlcs and update DLCIndex_XXXX.zip file as well but
reinstalling the dlcs would imply in copying all the files again. So you should
only reinstall a dlc if you had updated something in the files. If the only
thing you did was to update some package entries in
DLCIndex_NameOfYourDlcDirectory.xml then you can use use --index_only to just
update DLCIndex_XXXX.zip file without having to copying all the files again.

## Specifying some predefined values for package entries

If you have not installed your dlc yet and you know some of the package entries
will have the same values you can use some arguments to specify them at the
moment of the installation (note that these arguments only apply if the
DLCIndex_NameOfYourDlcDirectory.xml does not exist, because if it does exist the
tool will always prioritize the values contained in that file).
