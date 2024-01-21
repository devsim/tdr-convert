from . import read_tdr
from . import write_gmsh
import devsim as ds
import argparse

def tdr_convert(tdr, device_name, scale, load_datasets, drop_interfaces_at_contact):
    data = read_tdr.read_tdr(tdr, scale, drop_interfaces_at_contact)

    read_tdr.create_mesh(mesh='mesh', data=data)
    device_name = device_name
    ds.create_device(mesh='mesh', device=device_name)
    if load_datasets:
        datasets=read_tdr.load_datasets(device_name, data)
        data['datasets'] = datasets
    return data




def run():
    parser = argparse.ArgumentParser(description='Create mesh from tdr file')
    parser.add_argument('--tdr',           help='the tdr file to input', required=True)
    parser.add_argument('--load_datasets', help='write data sets', default=False, action='store_true')
    parser.add_argument('--tecplot',       help='the tecplot file to output', required=False)
    parser.add_argument('--devsim',        help='the devsim file to output', required=False)
    parser.add_argument('--gmsh',        help='the gmsh file to output', required=False)
    parser.add_argument('--gmsh_import',        help='the file to write the devsim commands to recreate a new gmsh device', required=False)
    parser.add_argument('--device_name',   help='the device name', default="device", required=False)
    parser.add_argument('--scale',   help='coordinate scaling factor', default=1, type=float, required=False)
    parser.add_argument('--drop_interfaces_at_contact', help="drop interfaces from nodes at contact", default=False, action='store_true')

    args = parser.parse_args()

    data=tdr_convert(tdr=args.tdr, device_name=args.device_name, scale=args.scale, load_datasets=args.load_datasets,
                     drop_interfaces_at_contact=args.drop_interfaces_at_contact
                     )

    if args.devsim:
        ds.write_devices(file=args.devsim)
    if args.tecplot:
        ds.write_devices(file=args.tecplot, type='tecplot')
    if args.gmsh:
        all_info = write_gmsh.get_all_info(args.device_name)
        write_gmsh.write_gmsh(filename=args.gmsh, all_info=all_info)
        if args.gmsh_import:
            write_gmsh.write_gmsh_import(args.gmsh, args.gmsh_import, all_info['device_info'])


if __name__ == "__main__":
    run()
