===============================
tdr-convert: tdr file converter
===============================

Introduction
------------

This utility provides TDR file format conversion to devsim, Gmsh, or Tecplot file format

::

    pip install tdr-convert
    tdr_convert --tdr file.tdr --devsim file.msh --drop_interfaces_at_contact --scale 1e-4

    tdr_convert --help

    usage: tdr_convert [-h] --tdr TDR [--load_datasets] [--tecplot TECPLOT] [--devsim DEVSIM] [--gmsh GMSH] [--gmsh_import GMSH_IMPORT]
                       [--device_name DEVICE_NAME] [--scale SCALE] [--drop_interfaces_at_contact] [--tetgen TETGEN] [--exodus EXODUS]
                       [--vtk VTK] [--old]

    Create mesh from tdr file

    options:
      -h, --help            show this help message and exit
      --tdr TDR             the tdr file to input
      --load_datasets       write data sets
      --tecplot TECPLOT     the tecplot file to output
      --devsim DEVSIM       the devsim file to output
      --gmsh GMSH           the gmsh file to output
      --gmsh_import GMSH_IMPORT
                            the file to write the devsim commands to recreate a new gmsh device
      --device_name DEVICE_NAME
                            the device name
      --scale SCALE         coordinate scaling factor
      --drop_interfaces_at_contact
                            drop interfaces from nodes at contact
      --tetgen TETGEN       the base name for tetgen files to output
      --exodus EXODUS       name of the exodus output file
      --vtk VTK             basename for vtk output file
      --old                 use old method for getting data using devsim


Mesh Requirements
-----------------

Requires triangular device simulation mesh in 2D.  A tetrahedral mesh is required in 3D.  Mixed elements are not supported.

Known Issues
------------

The ``exodus`` exporter loses data at interfaces when a variable has different values in different regions.

Vector data will name its fields with a suffix for the index.  ``E_0``, ``E_1``, ``E_2``

Program does not currently support multiple time steps.
