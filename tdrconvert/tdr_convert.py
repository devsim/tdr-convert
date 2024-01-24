import tdrconvert.read_tdr as read_tdr
import tdrconvert.all_info as all_info
import tdrconvert.write_gmsh as write_gmsh
import tdrconvert.write_tetgen as write_tetgen
import tdrconvert.write_exodus as write_exodus
import tdrconvert.load_devsim as ds
import argparse

def tdr_convert(tdr, device_name, scale, load_datasets, drop_interfaces_at_contact):
    data = read_tdr.read_tdr(tdr, scale, drop_interfaces_at_contact)
    data['device_name'] = device_name
    if load_datasets:
        datasets=read_tdr.load_datasets(data)
        data['datasets'] = datasets
    return data


def create_devsim_device(device_name, data):
    read_tdr.create_devsim_mesh(mesh='mesh', data=data)
    ds.create_device(mesh='mesh', device=device_name)
    if 'datasets' in data:
        read_tdr.create_devsim_data(device_name, data, data['datasets'])




def run():
    parser = argparse.ArgumentParser(description='Create mesh from tdr file')
    parser.add_argument('--tdr',           help='the tdr file to input', required=True)
    parser.add_argument('--load_datasets', help='write data sets', default=False, action='store_true')
    parser.add_argument('--tecplot',       help='the tecplot file to output', required=False)
    parser.add_argument('--devsim',        help='the devsim file to output', required=False)
    parser.add_argument('--gmsh',          help='the gmsh file to output', required=False)
    parser.add_argument('--gmsh_import',   help='the file to write the devsim commands to recreate a new gmsh device', required=False)
    parser.add_argument('--device_name',   help='the device name', default="device", required=False)
    parser.add_argument('--scale',         help='coordinate scaling factor', default=1, type=float, required=False)
    parser.add_argument('--drop_interfaces_at_contact', help="drop interfaces from nodes at contact", default=False, action='store_true')
    parser.add_argument('--tetgen',        help='the base name for tetgen files to output', required=False)
    parser.add_argument('--exodus',        help='name of the exodus output file', required=False)
    parser.add_argument('--vtk',        help='basename for vtk output file', required=False)
    parser.add_argument('--old', help='use old method for getting data using devsim', default=False, action='store_true')

    args = parser.parse_args()

    data=tdr_convert(tdr=args.tdr, device_name=args.device_name, scale=args.scale, load_datasets=args.load_datasets,
                     drop_interfaces_at_contact=args.drop_interfaces_at_contact
                     )

    use_devsim = any([args.old, args.devsim, args.tecplot, args.vtk])

    if use_devsim:
        create_devsim_device(args.device_name, data)

    if args.devsim:
        ds.write_devices(file=args.devsim)
    if args.tecplot:
        ds.write_devices(file=args.tecplot, type='tecplot')
    if args.vtk:
        ds.write_devices(file=args.tecplot, type='vtk')

    if args.gmsh or args.tetgen or args.exodus:
        if args.old:
            info = all_info.get_all_info(args.device_name)
        else:
            info = all_info.get_info_from_tdr_data(args.device_name, data)

    if args.gmsh:
        write_gmsh.write_gmsh(filename=args.gmsh, all_info=info)
        if args.gmsh_import:
            write_gmsh.write_gmsh_import(args.gmsh, args.gmsh_import, info['device_info'])
    if args.tetgen:
        write_tetgen.write_tetgen(basename=args.tetgen, all_info=info)
    if args.exodus:
        if args.load_datasets:
            if args.old:
                raise RuntimeError('--load_datasets is not currently supported with --old option when writing exodus format')
            #else:
            #    raise RuntimeError('FINISH HERE')
        write_exodus.write_exodus(filename=args.exodus, all_info=info, data=data)


if __name__ == "__main__":
    run()
